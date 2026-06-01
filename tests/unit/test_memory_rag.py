import sys
from pathlib import Path
import os
import time

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.store import MemoryStore
from src.memory.encryption import MemoryEncryption

def test_encryption():
    print("Testing AES-256-GCM encryption...")
    enc = MemoryEncryption()
    plaintext = "Boss likes emerald green."
    ciphertext = enc.encrypt(plaintext)
    assert ciphertext != plaintext
    assert isinstance(ciphertext, bytes)
    decrypted = enc.decrypt(ciphertext)
    assert decrypted == plaintext
    print("✅ Encryption works")

def test_memory_store():
    print("Testing MemoryStore and sqlite-vec...")
    import os
    env_backup = os.environ.get("FRIDAY_MEM_BUFFER")
    os.environ["FRIDAY_MEM_BUFFER"] = "-1.0"
    test_db = PROJECT_ROOT / "data" / "memory" / "test_memory.db"
    try:
        # Use an in-memory or temp DB for testing to not mess up production DB
        if test_db.exists():
            test_db.unlink()
        
        store = MemoryStore(db_path=str(test_db))
        
        # 1. Add some data
        store.add_conversation_turn("user", "My favorite color is emerald.")
        store.add_fact("Boss loves Python programming.", category="preference")
        
        # Wait a moment for background thread to generate embeddings
        time.sleep(2)
        
        # 2. Search
        results = store.search("What is my favorite color?")
        assert len(results) > 0, "No results found"
        
        found_emerald = False
        for r in results:
            if "emerald" in r["content"].lower():
                found_emerald = True
                print(f"✅ Found semantic match: {r['content']} (distance: {r['distance']:.4f})")
                
        assert found_emerald, "Failed to retrieve the emerald fact"
    finally:
        if env_backup is not None:
            os.environ["FRIDAY_MEM_BUFFER"] = env_backup
        else:
            os.environ.pop("FRIDAY_MEM_BUFFER", None)
            
    if test_db.exists():
        test_db.unlink()
    print("✅ MemoryStore test passed")

if __name__ == "__main__":
    test_encryption()
    test_memory_store()
