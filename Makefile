.PHONY: install verify-env benchmark-memory monitor test test-wake-word clean help

# Default target
help:
	@echo "F.R.I.D.A.Y. v2 — Available Commands"
	@echo "────────────────────────────────────────"
	@echo "  make install         Setup environment & install deps"
	@echo "  make verify-env      Verify all components are working"
	@echo "  make download-model  Download Phi-3.5-mini"
	@echo "  make benchmark-memory  Run RAM benchmark"
	@echo "  make monitor         Live memory pressure monitor"
	@echo "  make test            Run all tests"
	@echo "  make test-wake-word  Manual wake word unit test"
	@echo "  make test-face       Manual face recognition unit test"
	@echo "  make test-pipeline   Integration test (Wake Word + Face)"
	@echo "  make enroll-face     Enroll Boss face (Setup)"
	@echo "  make clean           Remove caches"

install:
	bash scripts/setup/install.sh

verify-env:
	@echo "Verifying 8GB environment..."
	@echo ""
	@/opt/homebrew/bin/python3.11 --version && echo "✅ Python 3.11" || echo "❌ Python 3.11 not found"
	@.venv/bin/python -c "import mlx.core as mx; print(f'✅ MLX {mx.__version__}')" 2>/dev/null || echo "❌ MLX missing"
	@.venv/bin/python -c "import psutil; print(f'✅ psutil {psutil.__version__}')" 2>/dev/null || echo "❌ psutil missing"
	@.venv/bin/python -c "import yaml; print('✅ PyYAML')" 2>/dev/null || echo "❌ PyYAML missing"
	@.venv/bin/python -c "from src.memory.manager import memory_manager; s=memory_manager.get_status(); print(f'✅ MemoryManager: {s}')" 2>/dev/null || echo "❌ MemoryManager broken"
	@test -d models/phi-3.5-mini-4bit && ls models/phi-3.5-mini-4bit/*.safetensors >/dev/null 2>&1 && echo "✅ Phi-3.5-mini downloaded" || echo "⏭️  Phi-3.5-mini not yet downloaded"
	@sysctl hw.memsize | awk '{printf "ℹ️  RAM: %.1f GB\n", $$2/1024/1024/1024}'
	@echo ""

download-model:
	.venv/bin/python scripts/setup/download_models.py

benchmark-memory:
	.venv/bin/python scripts/benchmark_memory.py

monitor:
	.venv/bin/python scripts/monitor_pressure.py

test:
	.venv/bin/pytest tests/ -v

test-wake-word:
	.venv/bin/python tests/unit/manual_test_wake_word.py

test-face:
	.venv/bin/python tests/unit/manual_test_face_recognition.py

enroll-face:
	.venv/bin/python scripts/setup/enroll_face.py

test-pipeline:
	.venv/bin/python tests/integration/pipeline_v1_activation.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true
	@echo "✅ Cleaned"
