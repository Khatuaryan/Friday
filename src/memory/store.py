import sqlite3
import threading
import json
import time
from src.utils.logger import get_logger
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

logger = get_logger("friday.memory_store")

class MemoryStore:
    """
    RAG Memory Store using SQLite-vec for 100% vector similarity search.
    Features AES-256-GCM encryption at rest, thread-safety, and auto-cleanup.
    """
    
    def __init__(self, db_path: str = "data/memory/friday_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        
        # Connect with check_same_thread=False since we use RLock for thread safety
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.enable_load_extension(True)
        
        # Load extensions
        try:
            import sqlite_vec
            sqlite_vec.load(self._conn)
            logger.info("sqlite-vec loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load sqlite-vec: {e}")
            raise
            
        # Initialize modules
        from src.memory.encryption import MemoryEncryption
        from src.memory.embeddings import EmbeddingModel
        
        self.encryption = MemoryEncryption()
        self.embeddings = EmbeddingModel()
        
        self._init_db()

    def _init_db(self):
        with self._lock:
            cursor = self._conn.cursor()
            
            # Conversations (Episodic)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    encrypted_message BLOB NOT NULL,
                    timestamp REAL NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Facts (Semantic)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    encrypted_fact BLOB NOT NULL,
                    category TEXT,
                    timestamp REAL NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Vector Table (vec0)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS embeddings USING vec0(
                    embedding FLOAT[384]
                )
            """)
            
            # Vector Metadata Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embeddings_metadata (
                    vec_rowid INTEGER PRIMARY KEY,
                    source_table TEXT NOT NULL,
                    source_id INTEGER NOT NULL
                )
            """)
            
            # Create indices for quick lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_source ON embeddings_metadata(source_table, source_id)")
            
            self._conn.commit()

    def add_conversation_turn(self, role: str, message: str, metadata: dict = None) -> int:
        """Adds a message to history and schedules async embedding."""
        timestamp = time.time()
        meta_str = json.dumps(metadata) if metadata else None
        
        encrypted_msg = self.encryption.encrypt(message)
        
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (role, encrypted_message, timestamp, metadata) VALUES (?, ?, ?, ?)",
                (role, encrypted_msg, timestamp, meta_str)
            )
            conv_id = cursor.lastrowid
            self._conn.commit()
            
            self._cleanup_history()
            
        # Spawn async embedding thread
        threading.Thread(
            target=self._embed_and_store_async,
            args=("conversations", conv_id, message),
            daemon=True
        ).start()
        
        return conv_id

    def add_fact(self, fact: str, category: str = "general", metadata: dict = None) -> int:
        """Adds a fact to semantic memory and schedules async embedding."""
        timestamp = time.time()
        meta_str = json.dumps(metadata) if metadata else None
        
        encrypted_fact = self.encryption.encrypt(fact)
        
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "INSERT INTO facts (encrypted_fact, category, timestamp, metadata) VALUES (?, ?, ?, ?)",
                (encrypted_fact, category, timestamp, meta_str)
            )
            fact_id = cursor.lastrowid
            self._conn.commit()
            
        threading.Thread(
            target=self._embed_and_store_async,
            args=("facts", fact_id, fact),
            daemon=True
        ).start()
        
        return fact_id

    def _embed_and_store_async(self, source_table: str, source_id: int, text: str):
        """Generates embedding and stores it atomically with metadata."""
        try:
            embedding = self.embeddings.embed(text)
            embedding_bytes = embedding.astype(np.float32).tobytes()
            
            with self._lock:
                cursor = self._conn.cursor()
                
                # Insert into vec0
                cursor.execute(
                    "INSERT INTO embeddings(embedding) VALUES (?)",
                    (embedding_bytes,)
                )
                vec_rowid = cursor.lastrowid
                
                # Insert into metadata table atomically under the same lock!
                cursor.execute(
                    "INSERT INTO embeddings_metadata(vec_rowid, source_table, source_id) VALUES (?, ?, ?)",
                    (vec_rowid, source_table, source_id)
                )
                
                self._conn.commit()
                
        except Exception as e:
            logger.error(f"Async embedding failed for {source_table} ID {source_id}: {e}")

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Pure vector search via sqlite-vec.
        Retrieves top matches from both conversations and facts.
        """
        try:
            query_emb = self.embeddings.embed(query)
            query_bytes = query_emb.astype(np.float32).tobytes()
        except MemoryError:
            # Memory pressure critical - fallback
            logger.warning("RAG disabled due to memory pressure")
            return []
            
        results = []
        with self._lock:
            cursor = self._conn.cursor()
            
            # Perform vector similarity search and JOIN with metadata
            cursor.execute("""
                SELECT
                    em.source_table,
                    em.source_id,
                    vec_distance_cosine(e.embedding, ?) AS distance
                FROM embeddings e
                JOIN embeddings_metadata em ON e.rowid = em.vec_rowid
                WHERE e.embedding MATCH ? AND k = ?
                ORDER BY distance ASC
            """, (query_bytes, query_bytes, limit))
            
            matches = cursor.fetchall()
            
            for match in matches:
                source_table = match["source_table"]
                source_id = match["source_id"]
                distance = match["distance"]
                
                # Retrieve the actual encrypted content
                if source_table == "conversations":
                    cursor.execute("SELECT role, encrypted_message, timestamp, metadata FROM conversations WHERE id = ?", (source_id,))
                    row = cursor.fetchone()
                    if row:
                        plaintext = self.encryption.decrypt(row["encrypted_message"])
                        results.append({
                            "type": "conversation",
                            "role": row["role"],
                            "content": plaintext,
                            "timestamp": row["timestamp"],
                            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                            "distance": distance
                        })
                elif source_table == "facts":
                    cursor.execute("SELECT category, encrypted_fact, timestamp, metadata FROM facts WHERE id = ?", (source_id,))
                    row = cursor.fetchone()
                    if row:
                        plaintext = self.encryption.decrypt(row["encrypted_fact"])
                        results.append({
                            "type": "fact",
                            "category": row["category"],
                            "content": plaintext,
                            "timestamp": row["timestamp"],
                            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                            "distance": distance
                        })
                        
        return results

    def _cleanup_history(self, keep_latest: int = 500):
        """Deletes conversations older than `keep_latest`."""
        cursor = self._conn.cursor()
        
        # Find IDs to delete
        cursor.execute("""
            SELECT id FROM conversations
            ORDER BY id DESC
            LIMIT -1 OFFSET ?
        """, (keep_latest,))
        
        old_ids = [row["id"] for row in cursor.fetchall()]
        if not old_ids:
            return
            
        placeholders = ",".join(["?"] * len(old_ids))
        
        # Delete from conversations
        cursor.execute(f"DELETE FROM conversations WHERE id IN ({placeholders})", old_ids)
        
        # Delete from vector mapping
        cursor.execute(f"SELECT vec_rowid FROM embeddings_metadata WHERE source_table = 'conversations' AND source_id IN ({placeholders})", old_ids)
        vec_rowids = [row["vec_rowid"] for row in cursor.fetchall()]
        
        if vec_rowids:
            vec_placeholders = ",".join(["?"] * len(vec_rowids))
            cursor.execute(f"DELETE FROM embeddings_metadata WHERE vec_rowid IN ({vec_placeholders})", vec_rowids)
            cursor.execute(f"DELETE FROM embeddings WHERE rowid IN ({vec_placeholders})", vec_rowids)
            
        self._conn.commit()

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Gets recent chronological history for LLM context injection."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT role, encrypted_message 
                FROM conversations 
                ORDER BY timestamp ASC 
                LIMIT ?
            """, (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    "role": row["role"],
                    "content": self.encryption.decrypt(row["encrypted_message"])
                })
            return history
