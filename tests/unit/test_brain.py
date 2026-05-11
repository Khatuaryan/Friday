"""Unit tests for FRIDAY brain."""

import pytest
from unittest.mock import patch, MagicMock
from src.core.friday_brain import FridayBrain


class TestFridayBrain:
    def test_init_defaults(self):
        brain = FridayBrain()
        assert brain.max_tokens == 1024
        assert brain.temperature == 0.7
        assert not brain.is_loaded

    def test_think_before_load_raises(self):
        brain = FridayBrain()
        with pytest.raises(RuntimeError, match="not loaded"):
            brain.think("hello")

    def test_format_prompt(self):
        brain = FridayBrain()
        prompt = brain._format_prompt("What time is it?", "You are FRIDAY.")
        assert "<|system|>" in prompt
        assert "You are FRIDAY." in prompt
        assert "<|user|>" in prompt
        assert "What time is it?" in prompt
        assert "<|assistant|>" in prompt

    def test_load_model_missing_dir(self):
        brain = FridayBrain(model_path="/nonexistent/model")
        with pytest.raises((FileNotFoundError, MemoryError)):
            brain.load_model()
