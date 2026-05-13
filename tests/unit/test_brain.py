"""Unit tests for FRIDAY brain."""

import pytest
from unittest.mock import patch, MagicMock
from src.core.brain import FridayBrain


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

    def test_history_starts_empty(self):
        brain = FridayBrain()
        assert brain.get_history_length() == 0

    def test_add_to_history(self):
        brain = FridayBrain()
        brain._add_to_history("hello", "Hi Boss!")
        assert brain.get_history_length() == 1

    def test_history_trimming_at_max(self):
        brain = FridayBrain()
        # Add 12 turns (max is 10)
        for i in range(12):
            brain._add_to_history(f"msg {i}", f"resp {i}")
        assert brain.get_history_length() == 10
        # Oldest turns should be trimmed (0, 1 gone)
        assert brain._conversation_history[0] == ("msg 2", "resp 2")

    def test_clear_history(self):
        brain = FridayBrain()
        brain._add_to_history("hello", "Hi!")
        brain._add_to_history("how are you", "Good!")
        assert brain.get_history_length() == 2
        brain.clear_history()
        assert brain.get_history_length() == 0

    def test_format_prompt_with_history(self):
        brain = FridayBrain()
        brain._add_to_history("My name is Aryan", "Nice to meet you, Aryan!")
        prompt = brain._format_prompt("What is my name?", "You are FRIDAY.")
        # History turn should be in prompt
        assert "My name is Aryan" in prompt
        assert "Nice to meet you, Aryan!" in prompt
        # Current message should be last
        assert prompt.endswith("<|assistant|>\n")
        assert "What is my name?" in prompt
