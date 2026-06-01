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

    def test_dynamic_registry_loading_phi(self, tmp_path):
        config_data = {
            "active_model": "phi-3.5-mini",
            "models_registry": {
                "phi-3.5-mini": {
                    "repo_id": "mlx-community/Phi-3.5-mini-instruct-4bit",
                    "path": "models/phi-3.5-mini-4bit",
                    "memory_gb": 2.2,
                    "context_window": 4096
                },
                "gemma-3-12b": {
                    "repo_id": "mlx-community/gemma-3-12b-it-4bit",
                    "path": "models/gemma-3-12b-4bit",
                    "memory_gb": 7.0,
                    "context_window": 8192
                }
            }
        }
        import yaml
        cfg_file = tmp_path / "friday_config.yaml"
        with open(cfg_file, "w") as f:
            yaml.dump(config_data, f)
            
        brain = FridayBrain(config_path=cfg_file)
        assert brain.model_path == "models/phi-3.5-mini-4bit"
        assert brain.model_memory_gb == 2.2
        assert brain.context_window == 4096

    def test_dynamic_registry_loading_gemma(self, tmp_path):
        config_data = {
            "active_model": "gemma-3-12b",
            "models_registry": {
                "phi-3.5-mini": {
                    "repo_id": "mlx-community/Phi-3.5-mini-instruct-4bit",
                    "path": "models/phi-3.5-mini-4bit",
                    "memory_gb": 2.2,
                    "context_window": 4096
                },
                "gemma-3-12b": {
                    "repo_id": "mlx-community/gemma-3-12b-it-4bit",
                    "path": "models/gemma-3-12b-4bit",
                    "memory_gb": 7.0,
                    "context_window": 8192
                }
            }
        }
        import yaml
        cfg_file = tmp_path / "friday_config.yaml"
        with open(cfg_file, "w") as f:
            yaml.dump(config_data, f)
            
        brain = FridayBrain(config_path=cfg_file)
        assert brain.model_path == "models/gemma-3-12b-4bit"
        assert brain.model_memory_gb == 7.0
        assert brain.context_window == 8192

    def test_format_prompt_with_tokenizer_chat_template(self):
        brain = FridayBrain()
        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.return_value = "Formatted Chat Template Result"
        brain._tokenizer = mock_tokenizer
        
        prompt = brain._format_prompt("Hello!", "System instruction")
        assert prompt == "Formatted Chat Template Result"
        mock_tokenizer.apply_chat_template.assert_called_once_with(
            [
                {"role": "system", "content": "System instruction"},
                {"role": "user", "content": "Hello!"}
            ],
            tokenize=False,
            add_generation_prompt=True
        )

    def test_think_full_offline(self):
        brain = FridayBrain()
        brain._loaded = True
        
        # Mock _generate to simulate a tool call followed by a final response
        with patch.object(brain, "_generate") as mock_gen, \
             patch("src.tools.server.MCPToolServer.execute_tool") as mock_execute:
             
            # Call 1: returns a tool call XML
            mock_gen.side_effect = [
                '<tool_call>{"name": "get_system_info", "arguments": {"info_type": "memory"}}</tool_call>'
            ]
            mock_execute.return_value = {"memory": {"available_gb": 4.5}}
            
            response = brain.think_full("How much memory is free?")
            
            assert response == "Your Mac has 4.5 GB of RAM available."
            assert brain.get_history_length() == 1
            assert brain._conversation_history[0] == ("How much memory is free?", "Your Mac has 4.5 GB of RAM available.")

    def test_think_full_openrouter_conversational(self):
        brain = FridayBrain()
        brain.active_model = "openrouter"
        brain._loaded = True
        brain._model = MagicMock()
        
        with patch.object(brain, "_generate") as mock_gen, \
             patch.object(brain, "_generate_local") as mock_gen_local, \
             patch.object(brain, "_lazy_load_local_fallback") as mock_load, \
             patch.object(brain, "unload_model") as mock_unload:
             
            mock_gen.return_value = '{"intent": "conversational", "tool_name": null, "arguments": null, "conversational_response": "The sky is blue."}'
            mock_gen_local.return_value = "Boss, the sky is blue."
            
            response = brain.think_full("Why is the sky blue?")
            
            assert response == "Boss, the sky is blue."
            mock_gen.assert_called_once()
            mock_load.assert_called_once_with(reason="running local tool-result synthesis pass")
            mock_gen_local.assert_called_once()
            mock_unload.assert_called_once()

    def test_think_full_openrouter_tool_call(self):
        brain = FridayBrain()
        brain.active_model = "openrouter"
        brain._loaded = True
        brain._model = MagicMock()
        
        with patch.object(brain, "_generate") as mock_gen, \
             patch("src.tools.server.MCPToolServer.execute_tool") as mock_execute, \
             patch.object(brain, "_generate_local") as mock_gen_local, \
             patch.object(brain, "_lazy_load_local_fallback") as mock_load, \
             patch.object(brain, "unload_model") as mock_unload:
             
            mock_gen.side_effect = [
                '{"intent": "tool_call", "tool_name": "get_system_info", "arguments": {"info_type": "storage"}, "conversational_response": null}',
                '{"intent": "conversational", "tool_name": null, "arguments": null, "conversational_response": "I have retrieved your storage details."}'
            ]
            mock_execute.return_value = {"storage": {"free_gb": 100.0, "total_gb": 250.0}}
            mock_gen_local.return_value = "Boss, you have 100 GB of storage left."
            
            response = brain.think_full("How much storage is free?")
            
            assert response == "Boss, you have 100 GB of storage left."
            assert mock_gen.call_count == 2
            mock_execute.assert_called_once_with({"name": "get_system_info", "arguments": {"info_type": "storage"}})
            mock_load.assert_called_once_with(reason="running local tool-result synthesis pass")
            mock_gen_local.assert_called_once()
            mock_unload.assert_called_once()





