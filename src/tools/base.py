"""
Base classes for MCP tools.

Provides structure and safety for tool execution.
All tools inherit from Tool and implement name, description, and execute().
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

logger = logging.getLogger("friday.tools")


class Tool(ABC):
    """Base class for all FRIDAY tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (used in tool calls)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for the LLM."""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Tool parameters schema (JSON schema format)."""
        return {}

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool.

        Returns:
            Dictionary with result or error.
        """

    def safe_execute(self, **kwargs) -> Dict[str, Any]:
        """Wrapper with error handling."""
        try:
            return self.execute(**kwargs)
        except Exception as e:
            logger.error("Tool %s failed: %s", self.name, e)
            return {"error": str(e)}
