#!/usr/view/env python3
"""
Downloads the quantized ONNX version of all-MiniLM-L6-v2 and its tokenizer
for lightweight embedding generation without PyTorch.
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("download_minilm")

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    logger.error("huggingface_hub is not installed. Run: pip install huggingface-hub")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "all-MiniLM-L6-v2"
REPO_ID = "Xenova/all-MiniLM-L6-v2"

def download_files():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading model to {MODEL_DIR} ...")
    
    # Download tokenizer.json
    logger.info("Downloading tokenizer.json...")
    hf_hub_download(
        repo_id=REPO_ID,
        filename="tokenizer.json",
        local_dir=str(MODEL_DIR)
    )
    
    # Download model_quantized.onnx
    logger.info("Downloading model_quantized.onnx...")
    hf_hub_download(
        repo_id=REPO_ID,
        filename="onnx/model_quantized.onnx",
        local_dir=str(MODEL_DIR)
    )
    
    logger.info("✅ Successfully downloaded ONNX MiniLM files.")

if __name__ == "__main__":
    download_files()
