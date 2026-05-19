import os
import subprocess
import logging
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("friday.memory_encryption")

class MemoryEncryption:
    """
    AES-256-GCM encryption for memory storage.
    Key is derived from macOS Platform UUID or a fallback file.
    """

    def __init__(self, key_path: str = "data/memory/.key") -> None:
        self.key_path = Path(key_path)
        self._key = self._get_or_create_key()
        self._aesgcm = AESGCM(self._key)

    def _get_or_create_key(self) -> bytes:
        # Try to get the macOS Platform UUID
        try:
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.split("\n"):
                if "IOPlatformUUID" in line:
                    uuid_str = line.split('"')[3]
                    # We need exactly 32 bytes for AES-256
                    key = uuid_str.encode("utf-8")
                    if len(key) < 32:
                        key = key.ljust(32, b"0")
                    return key[:32]
        except Exception as e:
            logger.warning(f"Could not read macOS Platform UUID: {e}. Using fallback file key.")

        # Fallback: Load or generate a persistent key
        if self.key_path.exists():
            return self.key_path.read_bytes()
        else:
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            key = AESGCM.generate_key(bit_length=256)
            self.key_path.write_bytes(key)
            return key

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypts a string and returns a binary blob (nonce + ciphertext + tag)."""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return nonce + ciphertext

    def decrypt(self, ciphertext_blob: bytes) -> str:
        """Decrypts a binary blob and returns the plaintext string."""
        nonce = ciphertext_blob[:12]
        ciphertext = ciphertext_blob[12:]
        plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
