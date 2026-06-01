"""
Pydantic-based configuration validation for Project F.R.I.D.A.Y.

Replaces raw yaml.safe_load() with type-checked settings that fail
fast at boot if the config YAML is invalid or inconsistent.

Usage:
    from src.utils.config import load_config, get_config

    cfg = load_config()                   # first call — loads and validates
    cfg = get_config()                    # subsequent calls — returns cached
    print(cfg.active_model_config.path)   # type-safe access
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

from src.utils.constants import CONFIG_FILE


class ModelEntry(BaseModel):
    """A single model in the registry."""
    repo_id: str
    path: str
    memory_gb: float = Field(gt=0, lt=16)
    context_window: int = Field(gt=0)


class HardwareConfig(BaseModel):
    """Hardware constraints."""
    total_ram_gb: float = 8.0
    friday_budget_gb: float = 3.5
    warning_threshold: float = 0.75
    critical_threshold: float = 0.85


class STTConfig(BaseModel):
    """Speech-to-text model config."""
    name: str = "whisper-small-multilingual"
    repo_id: str = "mlx-community/whisper-small-mlx"
    path: str = "models/whisper-small-mlx"
    memory_gb: float = 0.6
    supported_languages: List[str] = ["en", "hi"]


class MemoryConfig(BaseModel):
    """Memory subsystem settings."""
    enable_monitoring: bool = True
    check_interval_seconds: int = 30
    auto_cleanup: bool = True
    max_conversation_turns: int = 10
    max_rag_results: int = 5
    safety_buffer_gb: float = 1.0



class OpenRouterConfig(BaseModel):
    """OpenRouter API configuration."""
    api_key: Optional[str] = None
    model: str = "google/gemma-4-31b-it:free"


class FridayConfig(BaseModel):
    """Top-level validated configuration."""
    hardware: HardwareConfig = HardwareConfig()
    active_model: str
    models_registry: Dict[str, ModelEntry]
    memory: MemoryConfig = MemoryConfig()
    openrouter: Optional[OpenRouterConfig] = None

    @model_validator(mode="after")
    def _check_active_model(self) -> "FridayConfig":
        if self.active_model == "openrouter":
            return self
        if self.active_model not in self.models_registry:
            raise ValueError(
                f"active_model '{self.active_model}' not found in models_registry. "
                f"Available: {list(self.models_registry.keys())}"
            )
        return self

    @property
    def active_model_config(self) -> ModelEntry:
        if self.active_model == "openrouter":
            return ModelEntry(
                repo_id="openrouter",
                path="",
                memory_gb=0.0,
                context_window=8192
            )
        return self.models_registry[self.active_model]


# ── Singleton ────────────────────────────────────────────────

_config: Optional[FridayConfig] = None


def load_config(path: str | Path | None = None) -> FridayConfig:
    """
    Load and validate the FRIDAY configuration YAML.

    Caches the result — subsequent calls return the same instance.
    """
    global _config
    import dotenv
    dotenv.load_dotenv()
    if _config is not None:
        return _config

    config_path = Path(path or CONFIG_FILE)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found: {config_path}. "
            f"Copy config/.env.template and create {config_path}"
        )

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    _config = FridayConfig(**raw)
    return _config


def get_config() -> FridayConfig:
    """Return the cached config, loading it if necessary."""
    if _config is None:
        return load_config()
    return _config
