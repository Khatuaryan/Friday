"""
File Write Tool — Support write, append, directory creation, moving, and deletion of files.
"""

from __future__ import annotations

from src.utils.logger import get_logger
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from .base import Tool

logger = get_logger("friday.tools.file_write")


class FileWriteTool(Tool):
    """Write, append, move, create directories, and delete files on the filesystem."""

    MAX_WRITE_SIZE = 50_000  # 50KB ceiling

    @property
    def name(self) -> str:
        return "write_filesystem"

    @property
    def description(self) -> str:
        return "Write, append, create directories, move, or delete files on the local filesystem"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["write_file", "append_file", "create_directory", "move_file", "delete_file"],
                    "description": "The file system action to execute",
                },
                "path": {
                    "type": "string",
                    "description": "Target absolute or relative file/directory path",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write or append (required for write_file and append_file)",
                },
                "destination": {
                    "type": "string",
                    "description": "Target path for move_file action (required for move_file)",
                },
                "_confirmed": {
                    "type": "boolean",
                    "description": "Internal confirmation flag for destructive operations",
                    "default": False,
                },
            },
            "required": ["action", "path"],
        }

    def execute(self, action: str, path: str, **kwargs) -> Dict[str, Any]:
        # Path resolution and auto-correct common LLM hallucinations for the home directory
        path_obj = self._resolve_path(path)

        if action == "write_file":
            content = kwargs.get("content")
            if content is None:
                return {"error": "content is required for write_file"}
            if len(content.encode("utf-8")) > self.MAX_WRITE_SIZE:
                return {"error": f"Content exceeds maximum write size of {self.MAX_WRITE_SIZE} bytes"}
            return self._write_file(path_obj, content)

        elif action == "append_file":
            content = kwargs.get("content")
            if content is None:
                return {"error": "content is required for append_file"}
            
            existing_size = path_obj.stat().st_size if path_obj.exists() else 0
            if existing_size + len(content.encode("utf-8")) > self.MAX_WRITE_SIZE:
                return {"error": f"Resulting file size would exceed maximum limit of {self.MAX_WRITE_SIZE} bytes"}
            return self._append_file(path_obj, content)

        elif action == "create_directory":
            return self._create_directory(path_obj)

        elif action == "move_file":
            destination = kwargs.get("destination")
            if not destination:
                return {"error": "destination path is required for move_file"}
            dest_obj = self._resolve_path(destination)
            return self._move_file(path_obj, dest_obj)

        elif action == "delete_file":
            if not kwargs.get("_confirmed", False):
                # Destructive operation requires confirmation
                return {
                    "requires_confirmation": True,
                    "action_description": f"permanently delete the file or folder at '{path}'",
                    "pending_action": {
                        "name": "write_filesystem",
                        "arguments": {"action": "delete_file", "path": path, "_confirmed": True},
                    },
                }
            return self._delete_file(path_obj)

        else:
            return {"error": f"Unknown file system action: {action}"}

    def _resolve_path(self, path_str: str) -> Path:
        if path_str.startswith("/Users/YourUsername") or path_str.startswith("/Users/Username"):
            parts = path_str.split("/")
            if len(parts) > 3:
                path_str = os.path.join(str(Path.home()), *parts[3:])
        return Path(path_str).expanduser().resolve()

    def _write_file(self, path: Path, content: str) -> Dict[str, Any]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {
                "status": "success",
                "action": "write_file",
                "path": str(path),
                "bytes_written": len(content.encode("utf-8")),
            }
        except Exception as e:
            logger.error("Failed to write to file %s: %s", path, e)
            return {"error": str(e)}

    def _append_file(self, path: Path, content: str) -> Dict[str, Any]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return {
                "status": "success",
                "action": "append_file",
                "path": str(path),
                "bytes_appended": len(content.encode("utf-8")),
            }
        except Exception as e:
            logger.error("Failed to append to file %s: %s", path, e)
            return {"error": str(e)}

    def _create_directory(self, path: Path) -> Dict[str, Any]:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return {
                "status": "success",
                "action": "create_directory",
                "path": str(path),
            }
        except Exception as e:
            logger.error("Failed to create directory %s: %s", path, e)
            return {"error": str(e)}

    def _move_file(self, src: Path, dest: Path) -> Dict[str, Any]:
        try:
            if not src.exists():
                return {"error": f"Source path does not exist: {src}"}
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            return {
                "status": "success",
                "action": "move_file",
                "source": str(src),
                "destination": str(dest),
            }
        except Exception as e:
            logger.error("Failed to move %s to %s: %s", src, dest, e)
            return {"error": str(e)}

    def _delete_file(self, path: Path) -> Dict[str, Any]:
        try:
            if not path.exists():
                return {"error": f"Path to delete does not exist: {path}"}
            
            name = path.name
            if path.is_dir():
                shutil.rmtree(path)
                type_str = "Directory"
            else:
                path.unlink()
                type_str = "File"
            
            return {
                "status": "success",
                "action": "delete_file",
                "path": str(path),
                "confirmation_message": f"Successfully deleted the {type_str.lower()} at '{path}'.",
            }
        except Exception as e:
            logger.error("Failed to delete %s: %s", path, e)
            return {"error": str(e)}
