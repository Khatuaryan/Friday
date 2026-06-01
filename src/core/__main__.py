"""
F.R.I.D.A.Y. — Production Entry Point

Usage:
    python -m src.core               Start FRIDAY normally
    python -m src.core --debug       Start with DEBUG logging
    python -m src.core --dry-run     Validate config and environment, then exit
    python -m src.core --no-face     Skip face verification (development only)
    python -m src.core --no-brain    Start without loading LLM
    python -m src.core --camera N    Override camera device index
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import setup_logging, get_logger
from src.utils.config import load_config

logger = get_logger("friday.main")

# Global reference for signal handlers
_handler = None
_shutdown_event = threading.Event()


def _handle_sigint(signum, frame):
    """Ctrl+C — graceful shutdown."""
    logger.info("SIGINT received — shutting down gracefully...")
    _shutdown_event.set()
    if _handler:
        _handler.stop()
    sys.exit(0)


def _handle_sigterm(signum, frame):
    """launchctl stop / kill — graceful shutdown."""
    logger.info("SIGTERM received — shutting down gracefully...")
    _shutdown_event.set()
    if _handler:
        _handler.stop()
    sys.exit(0)


def _handle_sigusr1(signum, frame):
    """Custom signal: toggle listening on/off."""
    logger.info("SIGUSR1 received — toggling listening state...")
    if _handler:
        from src.core.activation_handler import ActivationState
        if _handler.state == ActivationState.LISTENING:
            if _handler._wake_word:
                _handler._wake_word.stop()
            logger.info("Wake word detection paused via SIGUSR1")
        else:
            if _handler._wake_word:
                _handler._wake_word.start()
            logger.info("Wake word detection resumed via SIGUSR1")


def parse_args():
    parser = argparse.ArgumentParser(
        description="F.R.I.D.A.Y. — Local Voice AI Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.core               Start FRIDAY normally
  python -m src.core --debug       Start with DEBUG logging
  python -m src.core --dry-run     Validate config and exit
  python -m src.core --no-face     Skip face verification (dev mode)
  python -m src.core --no-brain    Start without loading LLM (tool test mode)
        """,
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable DEBUG logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and environment, then exit",
    )
    parser.add_argument(
        "--no-face",
        action="store_true",
        help="Skip face verification (development only)",
    )
    parser.add_argument(
        "--no-brain",
        action="store_true",
        help="Start without loading LLM",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        help="Override camera device index",
    )
    return parser.parse_args()


def validate_environment() -> bool:
    """
    Pre-flight checks before starting.
    Returns True if all checks pass.
    """
    from src.memory.manager import memory_manager
    from src.utils.config import get_config

    all_ok = True

    # Config validation
    try:
        cfg = get_config()
        logger.info("✅ Config valid. Active model: %s", cfg.active_model)
    except Exception as e:
        logger.error("❌ Config invalid: %s", e)
        all_ok = False
        return all_ok

    # Model validation
    if cfg.active_model == "openrouter":
        api_key = cfg.openrouter.api_key if cfg.openrouter else None
        if not api_key:
            import os
            api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            logger.warning("⚠️  OpenRouter API key is missing. Set OPENROUTER_API_KEY in .env or config.")
        else:
            logger.info("✅ OpenRouter Cloud API configured (Gemma 4 31B:free)")
    else:
        model_path = PROJECT_ROOT / cfg.active_model_config.path
        if not model_path.exists():
            logger.warning(
                "⚠️  Model not found at %s. "
                "Run: python scripts/setup/download_models.py --model active",
                model_path,
            )
        else:
            logger.info("✅ Model found at %s", model_path)

    # Face encodings exist
    face_path = PROJECT_ROOT / "data" / "faces" / "boss_vision.pkl"
    if not face_path.exists():
        logger.warning("⚠️  Face encodings not found. Run: make enroll-face")
    else:
        logger.info("✅ Face encodings found")

    # Memory check
    status = memory_manager.get_status()
    logger.info(
        "Memory: %.1f/%.1fGB used (%.1f%%)",
        status.used_gb,
        status.total_gb,
        status.percent,
    )
    if status.pressure_level.value == "critical":
        logger.warning("⚠️  Memory pressure is CRITICAL before startup")

    return all_ok


def main():
    global _handler

    args = parse_args()

    # Setup logging first
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level, log_to_file=True)

    logger.info("=" * 60)
    logger.info("F.R.I.D.A.Y. v2 — Starting up")
    logger.info("=" * 60)

    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGUSR1, _handle_sigusr1)

    # Load and validate config
    try:
        load_config()
    except Exception as e:
        logger.critical("Cannot start: config error: %s", e)
        sys.exit(1)

    # Pre-flight validation
    ok = validate_environment()

    if args.dry_run:
        logger.info(
            "Dry run complete. Status: %s", "✅ OK" if ok else "❌ Issues found"
        )
        sys.exit(0 if ok else 1)

    # Build boss encodings path
    boss_encodings = str(PROJECT_ROOT / "data" / "faces" / "boss_vision.pkl")

    # Import activation handler
    from src.core.activation_handler import ActivationHandler

    def on_boss_verified():
        logger.info("Boss identity confirmed")

    def on_stranger():
        logger.warning("Stranger detected — access denied")

    def on_no_face():
        logger.info("No face detected — returning to listen")

    # Check if face encodings exist; if not, skip face verification
    skip_face = args.no_face or not Path(boss_encodings).exists()
    if skip_face and not args.no_face:
        logger.warning(
            "Face encodings missing — starting without face verification. "
            "Run 'make enroll-face' to enroll."
        )

    _handler = ActivationHandler(
        boss_encodings_path=boss_encodings,
        on_boss_verified=on_boss_verified,
        on_stranger=on_stranger if not skip_face else None,
        on_no_face=on_no_face if not skip_face else None,
        camera_index=args.camera,
        skip_face_verification=skip_face,
        load_brain=not args.no_brain,
    )

    logger.info("Starting FRIDAY... Say 'Hey Mycroft' to activate.")

    try:
        _handler.start()
        _handler.run_loop()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        if _handler:
            _handler.stop()
        logger.info("F.R.I.D.A.Y. shut down cleanly.")


if __name__ == "__main__":
    main()
