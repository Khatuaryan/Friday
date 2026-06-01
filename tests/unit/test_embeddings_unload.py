import sys
from pathlib import Path
import time
import logging
import os

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.embeddings import EmbeddingModel

logging.basicConfig(level=logging.INFO)

def test_auto_unload():
    print("Testing EmbeddingModel lazy load and auto-unload...")
    env_backup = os.environ.get("FRIDAY_MEM_BUFFER")
    os.environ["FRIDAY_MEM_BUFFER"] = "-1.0"
    
    try:
        model = EmbeddingModel()
        
        # Overwrite timeout for fast testing
        model.IDLE_TIMEOUT = 2.0
        
        # 1. Initially unloaded
        assert model._session is None
        
        # 2. Lazy load
        emb = model.embed("Hello world")
        assert model._session is not None
        assert emb.shape == (384,)
        
        # 3. Wait for timeout
        print("Waiting 3 seconds for unload...")
        time.sleep(3)
        
        # 4. Should be unloaded
        assert model._session is None
        print("✅ Auto-unload works")
    finally:
        if env_backup is not None:
            os.environ["FRIDAY_MEM_BUFFER"] = env_backup
        else:
            os.environ.pop("FRIDAY_MEM_BUFFER", None)

if __name__ == "__main__":
    test_auto_unload()
