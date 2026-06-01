"""
Centralized constants for Project F.R.I.D.A.Y.

Every magic number previously scattered across the codebase lives here.
This file has ZERO imports — just plain Python literals.
All other modules import from here instead of using inline values.
"""

# ── Audio ────────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE_STR = "int16"
VAD_FRAME_SAMPLES = 480            # 30ms at 16kHz
VAD_FRAME_BYTES = 960              # 480 samples * 2 bytes (int16)
WAKE_WORD_CHUNK_SIZE = 1280        # 80ms at 16kHz
DEFAULT_LISTEN_TIMEOUT = 10.0
DEFAULT_SILENCE_DURATION = 1.5
CONFIRMATION_TIMEOUT = 8.0

# ── Memory ───────────────────────────────────────────────────
FRIDAY_BUDGET_GB = 3.5
DEFAULT_SAFETY_BUFFER_GB = 1.0
MIN_SAFETY_BUFFER_GB = 0.5
WARNING_THRESHOLD_PERCENT = 75.0
CRITICAL_THRESHOLD_PERCENT = 85.0
MAX_CONVERSATION_TURNS = 10
MAX_RAG_RESULTS = 3
EMBEDDING_DIM = 384
EMBEDDING_IDLE_TIMEOUT_S = 300.0   # 5 minutes

# ── Brain ────────────────────────────────────────────────────
MAX_INPUT_CHARS = 500
MAX_RESPONSE_CHARS = 300
MAX_TOOL_CALLS = 2
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.7
REPETITION_PENALTY = 1.1
REPETITION_CONTEXT_SIZE = 50

# ── Storage ──────────────────────────────────────────────────
MAX_FILE_READ_BYTES = 100_000      # 100KB
MAX_FILE_WRITE_BYTES = 51_200      # 50KB
MAX_CLIPBOARD_CHARS = 1_000
MAX_SHELL_OUTPUT_CHARS = 500
MAX_CONVERSATION_HISTORY = 500
SHELL_TIMEOUT_S = 30

# ── Tools ────────────────────────────────────────────────────
RATE_LIMIT_CALLS = 5
RATE_LIMIT_WINDOW_S = 60.0

# ── IPC ──────────────────────────────────────────────────────
STATUS_FILE = "~/.cache/friday/status.json"
COMMAND_DIR = "~/.cache/friday/commands/"
STATUS_UPDATE_INTERVAL_S = 1.0

# ── Paths (relative to project root) ────────────────────────
ASSETS_DIR = "assets"
ICON_SVG = "assets/friday-icon.svg"
CONFIG_FILE = "config/friday_config.yaml"
MODELS_DIR = "models"
DATA_DIR = "data"
LOGS_DIR = "logs"
FACES_DIR = "data/faces"
MEMORY_DB = "data/memory/friday_memory.db"
BENCHMARKS_DIR = "docs/research-paper/benchmarks"

# ── Face Recognition ────────────────────────────────────────
FACE_THRESHOLD = 0.75
FACE_TIMEOUT_S = 3
MIN_ENROLLMENT_PHOTOS = 20
