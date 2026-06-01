.PHONY: install verify-env benchmark-memory monitor test test-wake-word test-face test-stt test-tts test-voice-pipeline test-brain test-pipeline enroll-face download-model download-whisper run run-debug run-no-face dry-run install-agent uninstall-agent agent-status agent-logs clean help

# Default target
help:
	@echo "F.R.I.D.A.Y. v2 — Available Commands"
	@echo "════════════════════════════════════════"
	@echo ""
	@echo " ── Run ──"
	@echo "  make run               Start FRIDAY"
	@echo "  make run-debug         Start with DEBUG logging"
	@echo "  make run-no-face       Start without face verification"
	@echo "  make dry-run           Validate config and environment"
	@echo ""
	@echo " ── LaunchAgent ──"
	@echo "  make install-agent     Install auto-start LaunchAgent"
	@echo "  make uninstall-agent   Remove LaunchAgent"
	@echo "  make agent-status      Check LaunchAgent status"
	@echo "  make agent-logs        Tail LaunchAgent stdout/stderr"
	@echo ""
	@echo " ── Setup ──"
	@echo "  make install           Setup environment & install deps"
	@echo "  make verify-env        Verify all components are working"
	@echo "  make download-model    Download Phi-3.5-mini"
	@echo "  make enroll-face       Enroll Boss face"
	@echo "  make download-whisper  Download Distil-Whisper model"
	@echo ""
	@echo " ── Test ──"
	@echo "  make test              Run all unit tests"
	@echo "  make test-wake-word    Manual wake word test"
	@echo "  make test-face         Manual face recognition test"
	@echo "  make test-stt          Manual STT test"
	@echo "  make test-tts          Manual TTS test"
	@echo "  make test-voice-pipeline  Voice pipeline integration"
	@echo "  make test-brain        Brain integration (requires model)"
	@echo "  make test-pipeline     Integration (Wake Word + Face)"
	@echo ""
	@echo " ── Diagnostics ──"
	@echo "  make benchmark-memory  Run RAM benchmark"
	@echo "  make monitor           Live memory pressure monitor"
	@echo "  make clean             Remove caches"

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

test-stt:
	.venv/bin/python tests/unit/manual_test_stt.py

test-tts:
	.venv/bin/python tests/unit/manual_test_tts.py

test-voice-pipeline:
	.venv/bin/python tests/integration/pipeline_v2_voice.py

test-brain:
	.venv/bin/python tests/integration/pipeline_v3_brain.py

download-whisper:
	.venv/bin/python scripts/setup/download_models.py --model whisper

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true
	@echo "✅ Cleaned"

# ── Run Targets ────────────────────────────────────────────
run:
	.venv/bin/python -m src.core

run-debug:
	.venv/bin/python -m src.core --debug

run-no-face:
	.venv/bin/python -m src.core --no-face

dry-run:
	.venv/bin/python -m src.core --dry-run

# ── LaunchAgent Targets ───────────────────────────────────
install-agent:
	bash scripts/setup/install_launchagent.sh

uninstall-agent:
	bash scripts/setup/uninstall_launchagent.sh

agent-status:
	@launchctl list 2>/dev/null | grep friday || echo "LaunchAgent not loaded"

agent-logs:
	@echo "=== stdout ==="
	@tail -30 logs/friday.stdout.log 2>/dev/null || echo "No stdout log"
	@echo ""
	@echo "=== stderr ==="
	@tail -30 logs/friday.stderr.log 2>/dev/null || echo "No stderr log"
