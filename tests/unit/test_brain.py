import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.core.brain import FridayBrain

class TestFridayBrain:
    def test_init_defaults(self):
        brain = FridayBrain()
        assert brain.active_model == "openrouter"  # Now openrouter is central default
        assert brain.model_memory_gb == 0.0
        assert brain.context_window == 8192

    def test_init_custom_path(self):
        brain = FridayBrain(model_path="models/custom-model")
        assert brain.model_path == "models/custom-model"
        assert brain.model_memory_gb == 2.2
        assert brain.context_window == 4096

    def test_init_from_centralized_config(self, tmp_path):
        # Create a temp YAML config file
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
            
            assert response == "We have 4.5 GB of RAM currently free and clear, Sir."
            assert brain.get_history_length() == 1
            assert brain._conversation_history[0] == ("How much memory is free?", "We have 4.5 GB of RAM currently free and clear, Sir.")

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
            
            assert response == "The sky is blue."
            mock_gen.assert_called_once()
            mock_load.assert_not_called()  # Verified fast-path direct conversational synthesis
            mock_gen_local.assert_not_called()
            mock_unload.assert_not_called()

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
            
            assert response == "You have 100.0 GB available of a total 250.0 GB, Sir."
            assert mock_gen.call_count == 2
            mock_execute.assert_called_once_with({"name": "get_system_info", "arguments": {"info_type": "storage"}})
            mock_load.assert_not_called()
            mock_gen_local.assert_not_called()
            mock_unload.assert_not_called()
