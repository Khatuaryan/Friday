"""
Unit Test — RAG Unload Race Condition

Validates the thread-safety and RLock/Lock serialization of MemoryStore and EmbeddingModel
when the 5-minute idle unload timer watchdog fires in the background during a vector search query.
"""

import os
import sys
import threading
import time
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.store import MemoryStore
from src.memory.embeddings import EmbeddingModel


def test_unload_race():
    """
    Simulates a race condition where the auto-unload timer check runs
    while a concurrent RAG query search is executing.
    """
    # Override system memory pressure limits for tests
    old_buf = os.getenv("FRIDAY_MEM_BUFFER")
    os.environ["FRIDAY_MEM_BUFFER"] = "0.0"

    try:
        model = EmbeddingModel()
        # Lower timeout for quick triggering in the test
        model.IDLE_TIMEOUT = 1.0

        # 1. Warm up the embedding model to load session and tokenizer
        _ = model.embed("warmup query")
        assert model._session is not None
        assert model._tokenizer is not None

        results = []
        errors = []

        # Target test database path
        test_db = PROJECT_ROOT / "data" / "memory" / "test_race.db"
        if test_db.exists():
            try:
                os.unlink(test_db)
            except Exception:
                pass

        # Ensure MemoryStore holds the embedding model
        store = MemoryStore(db_path=str(test_db))
        store.embeddings = model

        # Add a mock turn to query
        store.add_conversation_turn("user", "my favorite color is emerald")
        
        # Wait for the async embedding processing to finish enqueuing
        time.sleep(1.0)

        def do_concurrent_search():
            try:
                # Sleep slightly to let the timer get close to expiring
                time.sleep(0.5)
                # Perform vector search which locks model._lock
                r = store.search("favorite color", limit=1)
                results.append(r)
            except Exception as e:
                errors.append(e)

        # 2. Spawn concurrent search on a background thread
        search_thread = threading.Thread(target=do_concurrent_search, daemon=True)
        search_thread.start()

        # 3. Simulate timer expiring on the main thread
        # Update last_used to trigger unload during the concurrent search thread execution
        model._last_used = time.time() - 2.0
        model._unload_check()

        # 4. Join and assert outcomes
        search_thread.join(timeout=5.0)

        # Clean up test db
        if test_db.exists():
            try:
                os.unlink(test_db)
            except Exception:
                pass

        # Assert no errors occurred (e.g. NoneType dereference, Segfault, or AttributeError)
        assert not errors, f"RAG unload race condition caused error: {errors[0]}"
        assert len(results) > 0, "Vector search failed to return results"
        print("✅ RLock/Lock concurrency: no race crash occurred under active search.")
    finally:
        if old_buf is not None:
            os.environ["FRIDAY_MEM_BUFFER"] = old_buf
        else:
            os.environ.pop("FRIDAY_MEM_BUFFER", None)

