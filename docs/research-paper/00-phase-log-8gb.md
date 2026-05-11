## Hardware Baseline (Before FRIDAY)

**Date**: 2026-05-11
**Hardware**: MacBook Air M2 2023, 8GB RAM, 256GB SSD

### Current State
- Total RAM: 8.0 GB
- Chip: Apple M2
- Disk free: 56 GB
- Python: 3.11.15 (via Homebrew)

### Baseline Memory
- Active: ~1,524 MB
- Wired: ~1,407 MB
- Compressed: ~3,089 MB
- Available: ~62 MB (system actively compressing)

### Running Applications
- Antigravity IDE: ~7.5% RAM
- WebKit: ~4.1% RAM

### Verification
- ✅ Apple Silicon M2
- ✅ 8GB RAM
- ✅ 56GB disk free (>30GB required)
- ✅ Python 3.11.15 installed
- ✅ Homebrew available

---

## Phase 0: Environment Setup - Results

**Completion Date**: 2026-05-11
**Duration**: ~30 minutes

### Installed Versions
- Python: 3.11.15
- MLX: 0.31.2
- psutil: 7.2.2
- PyYAML: 6.0.3
- Pydantic: 2.13.4

### Memory Manager
- Status: Operational ✅
- Pressure at idle: WARNING (expected with IDE running)

### Test Results
- Unit tests: 14/14 passed ✅
- Memory manager: Working ✅
- Brain interface: Working (model not yet downloaded) ✅

### Phi-3.5-mini Download
- Status: ✅ COMPLETE
- Model: `mlx-community/Phi-3.5-mini-instruct-4bit`
- Size on disk: 2.00 GB
- Load time: 1.8s (cold), 2.8s (benchmark)
- Inference: 2.0s for short prompt ✅

### Memory Benchmark Results
| Component | RSS (MB) | Notes |
|-----------|----------|-------|
| Baseline (Python) | 16.6 | Minimal |
| + Memory Manager | 20.4 | +3.8 MB |
| + Phi-3.5-mini | 471.3 | +450.8 MB (model in unified memory) |
| **Total** | **471.3** | **Budget: 3,500 MB ✅** |

- System before: 72.5% used, 2.2 GB available
- System after: 82.1% used, 1.4 GB available
- Pressure: WARNING (expected with IDE running)
- Model weights reside in macOS unified memory (~2.2 GB), not Python RSS

### SwiftBar
- Status: ✅ Installed (v2.0.1)
- Plugin: `~/.swiftbar/friday.5s.sh`
- Shows: 🤖 icon + memory/status info
