#!/bin/bash
# =============================================
# F.R.I.D.A.Y. v2 — One-Shot Environment Setup
# =============================================
# Usage: bash scripts/install.sh
# Target: MacBook Air M2 2023, 8GB RAM

set -euo pipefail

echo "============================================="
echo " F.R.I.D.A.Y. v2 — Environment Setup (8GB)"
echo "============================================="

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# ── Check prerequisites ──
echo -e "\n[1/6] Checking prerequisites..."

if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Install: https://brew.sh"
    exit 1
fi
echo "  ✅ Homebrew: $(brew --version | head -1)"

if ! sysctl -n machdep.cpu.brand_string | grep -q "Apple"; then
    echo "❌ Apple Silicon required (MLX needs M-series chip)"
    exit 1
fi
echo "  ✅ Apple Silicon: $(sysctl -n machdep.cpu.brand_string)"

RAM_GB=$(sysctl hw.memsize | awk '{print int($2/1024/1024/1024)}')
echo "  ✅ RAM: ${RAM_GB}GB"

DISK_FREE=$(df -h / | tail -1 | awk '{print $4}')
echo "  ✅ Disk free: ${DISK_FREE}"

# ── Install system dependencies ──
echo -e "\n[2/6] Installing system packages..."

brew install python@3.11 2>/dev/null || echo "  python@3.11 already installed"
brew install portaudio 2>/dev/null || echo "  portaudio already installed"
brew install ffmpeg 2>/dev/null || echo "  ffmpeg already installed"

# ── Create virtual environment ──
echo -e "\n[3/6] Creating Python 3.11 virtual environment..."

if [ ! -d ".venv" ]; then
    /opt/homebrew/bin/python3.11 -m venv .venv
    echo "  ✅ Virtual environment created"
else
    echo "  ✅ Virtual environment already exists"
fi

source .venv/bin/activate
pip install --upgrade pip --quiet

# ── Install Python packages ──
echo -e "\n[4/6] Installing Python packages..."
pip install -r requirements-8gb.txt --quiet

# ── Create directories ──
echo -e "\n[5/6] Creating project directories..."

mkdir -p models/phi-3.5-mini-4bit
mkdir -p models/distil-whisper-small
mkdir -p models/piper-tts
mkdir -p data/faces
mkdir -p data/memory
mkdir -p logs
mkdir -p docs/research-paper/benchmarks

echo "  ✅ All directories created"

# ── Verify ──
echo -e "\n[6/6] Verifying installation..."

python -c "import mlx.core as mx; print(f'  ✅ MLX: {mx.__version__}')" 2>/dev/null || echo "  ❌ MLX import failed"
python -c "import psutil; print(f'  ✅ psutil: {psutil.__version__}')" 2>/dev/null || echo "  ❌ psutil import failed"
python -c "import yaml; print('  ✅ PyYAML')" 2>/dev/null || echo "  ❌ PyYAML import failed"

echo ""
echo "============================================="
echo " ✅ Environment setup complete!"
echo "============================================="
echo ""
echo "Next steps:"
echo "  1. Download model: python scripts/download_models.py"
echo "  2. Benchmark RAM:  python scripts/benchmark_memory.py"
echo "  3. Run tests:      make verify-env"
