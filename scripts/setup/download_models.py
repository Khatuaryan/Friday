#!/usr/bin/env python3
"""
Download models for F.R.I.D.A.Y. (8GB system).

Loads snapshot coordinates (repo_id, path) directly from the YAML config registry.

Usage:
    python scripts/setup/download_models.py
    python scripts/setup/download_models.py --model active
    python scripts/setup/download_models.py --model gemma-3-12b
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_config() -> dict:
    """Load configuration from friday_config_8gb.yaml."""
    config_path = PROJECT_ROOT / "config" / "friday_config_8gb.yaml"
    if config_path.exists():
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config at {config_path}: {e}")
    return {}


config = load_config()
active_model_name = config.get("active_model", "phi-3.5-mini")
models_registry = config.get("models_registry", {})


def download_model(model_key: str, repo_id: str, local_path: str) -> Path:
    """Download a specified model from huggingface snapshot."""
    from huggingface_hub import snapshot_download

    print("\n" + "=" * 60)
    print(f"Downloading model: {model_key}")
    print(f"Repository: {repo_id}")
    print(f"Destination: {local_path}")
    print("Size may range from 500MB to 7GB — may take 5–30 minutes depending on speed.")
    print("=" * 60 + "\n")

    model_dir = PROJECT_ROOT / local_path
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = snapshot_download(
        repo_id=repo_id,
        local_dir=str(model_dir),
        local_dir_use_symlinks=False,
    )

    # Calculate size
    size_gb = sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, _, filenames in os.walk(model_path)
        for filename in filenames
    ) / (1024 ** 3)

    print(f"\n✅ {model_key} downloaded to: {model_path}")
    print(f"   Total size: {size_gb:.2f} GB")
    return Path(model_path)


def download_whisper_model() -> Path:
    """Download Whisper Small for MLX."""
    # Fallback default values
    repo_id = "mlx-community/whisper-small.en-mlx"
    local_path = "models/whisper-small.en-mlx"

    # Try to read from config
    stt_config = config.get("models", {}).get("stt", {})
    if stt_config:
        repo_id = stt_config.get("repo_id", repo_id)
        local_path = stt_config.get("path", local_path)

    return download_model("whisper-small", repo_id, local_path)


def verify_model(model_path: Path, model_name: str) -> bool:
    """Verify model loads and responds correctly."""
    import time

    print(f"\n--- Verifying {model_name} loads correctly ---")

    try:
        from mlx_lm import load, generate
    except ImportError:
        print("❌ mlx-lm library not found. Skipping verification.")
        return False

    print("Loading model...")
    start = time.time()
    try:
        model, tokenizer = load(str(model_path))
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return False
    load_time = time.time() - start
    print(f"✅ Loaded in {load_time:.1f} seconds")

    print("Testing inference...")
    start = time.time()
    try:
        response = generate(
            model,
            tokenizer,
            prompt="Say hello in exactly 5 words.",
            max_tokens=20,
            verbose=False,
        )
    except Exception as e:
        print(f"❌ Failed to run inference: {e}")
        return False
    inference_time = time.time() - start

    print(f"Response: {response}")
    print(f"Inference time: {inference_time:.1f} seconds")

    if inference_time < 5.0:
        print("✅ Performance acceptable")
        return True
    else:
        print("⚠️  Slower than expected (>5s), but may improve during use")
        return True


def main():
    # Choices: active, whisper, all, phi (backward compatible alias), and all registry keys
    registry_keys = list(models_registry.keys())
    choices = ["active", "whisper", "all", "phi"] + registry_keys

    parser = argparse.ArgumentParser(description="Download FRIDAY models")
    parser.add_argument(
        "--model",
        choices=choices,
        default="all",
        help="Which model to download (default: all)",
    )
    parser.add_argument(
        "--verify", action="store_true", default=True,
        help="Verify model after download (default: True)",
    )
    args = parser.parse_args()

    # Resolve target model keys
    to_download = []
    
    if args.model == "all":
        # Download active LLM and Whisper
        to_download.append(("llm", active_model_name))
        to_download.append(("stt", "whisper"))
    elif args.model == "active":
        to_download.append(("llm", active_model_name))
    elif args.model == "phi":
        to_download.append(("llm", "phi-3.5-mini"))
    elif args.model == "whisper":
        to_download.append(("stt", "whisper"))
    else:
        # Must be a registry key
        to_download.append(("llm", args.model))

    # Process downloads
    for mtype, mkey in to_download:
        if mtype == "llm":
            model_cfg = models_registry.get(mkey)
            if not model_cfg:
                print(f"❌ Model key '{mkey}' not found in registry. Skipping.")
                continue
            repo_id = model_cfg["repo_id"]
            path = model_cfg["path"]
            
            model_path = download_model(mkey, repo_id, path)
            if args.verify:
                verify_model(model_path, mkey)
        elif mtype == "stt":
            download_whisper_model()

    print("\n🎯 Model download sequence complete!")


if __name__ == "__main__":
    main()
