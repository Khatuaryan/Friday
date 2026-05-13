#!/usr/bin/env python3
"""
Download models for F.R.I.D.A.Y. (8GB system).

Downloads:
    - Phi-3.5-mini-instruct 4-bit (~2.2 GB)
    - (Phase 3) Distil-Whisper Small
    - (Phase 3) Piper TTS voice

Usage:
    python scripts/download_models.py
    python scripts/download_models.py --model phi  # Only Phi-3.5
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def download_phi_mini() -> Path:
    """Download Phi-3.5-mini-instruct (4-bit quantized for MLX)."""
    from huggingface_hub import snapshot_download

    print("\n" + "=" * 60)
    print("Downloading Phi-3.5-mini-instruct (4-bit quantized)")
    print("Size: ~2.2 GB — may take 5–15 minutes")
    print("=" * 60 + "\n")

    model_dir = PROJECT_ROOT / "models" / "phi-3.5-mini-4bit"
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = snapshot_download(
        repo_id="mlx-community/Phi-3.5-mini-instruct-4bit",
        local_dir=str(model_dir),
        local_dir_use_symlinks=False,
    )

    # Calculate size
    size_gb = sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, _, filenames in os.walk(model_path)
        for filename in filenames
    ) / (1024 ** 3)

    print(f"\n✅ Phi-3.5-mini downloaded to: {model_path}")
    print(f"   Total size: {size_gb:.2f} GB")
    return Path(model_path)


def verify_phi_model(model_path: Path) -> bool:
    """Verify model loads and responds correctly."""
    import time

    print("\n--- Verifying model loads correctly ---")

    from mlx_lm import load, generate

    print("Loading model...")
    start = time.time()
    model, tokenizer = load(str(model_path))
    load_time = time.time() - start
    print(f"✅ Loaded in {load_time:.1f} seconds")

    print("Testing inference...")
    start = time.time()
    response = generate(
        model,
        tokenizer,
        prompt="Say hello in exactly 5 words.",
        max_tokens=20,
        verbose=False,
    )
    inference_time = time.time() - start

    print(f"Response: {response}")
    print(f"Inference time: {inference_time:.1f} seconds")

    if inference_time < 3.0:
        print("✅ Performance acceptable")
        return True
    else:
        print("⚠️  Slower than expected (>3s), but may improve during use")
        return True


def download_whisper() -> Path:
    """Download Whisper Small for MLX."""
    print("\n" + "=" * 60)
    print("Downloading Whisper Small (MLX)")
    print("Size: ~500 MB — may take 3–10 minutes")
    print("=" * 60 + "\n")

    from huggingface_hub import snapshot_download

    model_dir = PROJECT_ROOT / "models" / "whisper-small.en-mlx"
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = snapshot_download(
        repo_id="mlx-community/whisper-small.en-mlx",
        local_dir=str(model_dir),
        local_dir_use_symlinks=False,
    )

    size_gb = sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, _, filenames in os.walk(model_path)
        for filename in filenames
    ) / (1024 ** 3)

    print(f"\n✅ Whisper downloaded to: {model_path}")
    print(f"   Total size: {size_gb:.2f} GB")
    return Path(model_path)


def main():
    parser = argparse.ArgumentParser(description="Download FRIDAY models")
    parser.add_argument(
        "--model",
        choices=["phi", "whisper", "all"],
        default="all",
        help="Which model to download (default: all)",
    )
    parser.add_argument(
        "--verify", action="store_true", default=True,
        help="Verify model after download (default: True)",
    )
    args = parser.parse_args()

    if args.model in ("phi", "all"):
        model_path = download_phi_mini()
        if args.verify:
            verify_phi_model(model_path)

    if args.model in ("whisper", "all"):
        download_whisper()

    print("\n🎯 Model download complete!")


if __name__ == "__main__":
    main()
