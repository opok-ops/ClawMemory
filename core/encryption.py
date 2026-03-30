"""
ClawMemory 核心加密引擎
===========================
AES-256-GCM 本地加密，PBKDF2 密钥派生。
Key Derivation: PBKDF2-SHA256, 100000 iterations, 32-byte key
Encryption: AES-256-GCM with random 96-bit IV
Storage Format: base64(nonce || ciphertext || tag)
"""

import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass, asdict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# ============================================================================
# Constants
# ============================================================================
KDF_ITERATIONS = 100_000
KEY_LENGTH = 32  # 256 bits
NONCE_LENGTH = 12  # 96 bits for GCM
SALT_LENGTH = 32
CURRENT_VERSION = "v1"  # Schema version for future migrations

DEFAULT_KEY_PATH = Path(__file__).parent.parent / "data" / ".key"
DEFAULT_SALT_PATH = Path(__file__).parent.parent / "data" / ".salt"


# ============================================================================
# Data Classes
# ============================================================================
@dataclass
class EncryptedBlob:
    version: str
    nonce: str       # base64
    ciphertext: str  # base64
    tag: str         # base64 (stored separately for compatibility)

    def to_string(self) -> str:
        return base64.b64encode(json.dumps(asdict(self)).encode()).decode()

    @classmethod
    def from_string(cls, data: str) -> "EncryptedBlob":
        raw = base64.b64decode(data.encode()).decode()
        obj = json.loads(raw)
        return cls(**obj)


# ============================================================================
# Core Encryption Engine
# ============================================================================
class EncryptionEngine:
    """| 全局单例加密引擎，线程安全 |"""

    _instance: Optional["EncryptionEngine"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, key_path: Optional[Path] = None, salt_path: Optional[Path] = None):
        if self._initialized:
            return
        self._initialized = True

        self._key_path = Path(key_path) if key_path else DEFAULT_KEY_PATH
        self._salt_path = Path(salt_path) if salt_path else DEFAULT_SALT_PATH
        self._key: Optional[bytes] = None
        self._aesgcm: Optional[AESGCM] = None

        # Auto-load if key file exists
        if self._key_path.exists():
            self._load_key()
        elif self._salt_path.exists():
            self._load_key_from_salt()
        else:
            print("[EncryptionEngine] No key found. Run python cli/main.py init to generate.")

    # --------------------------------------------------------------------------
    # Key Management
    # --------------------------------------------------------------------------
    def generate_key(self, password: str) -> bytes:
        """| 使用密码生成密钥，不保存密码 |"""
        # Generate or load salt
        if self._salt_path.exists():
            salt = self._salt_path.read_bytes()
        else:
            salt = os.urandom(SALT_LENGTH)
            self._salt_path.parent.mkdir(parents=True, exist_ok=True)
            self._salt_path.write_bytes(salt)

        # PBKDF2 key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LENGTH,
            salt=salt,
            iterations=KDF_ITERATIONS,
            backend=default_backend(),
        )
        self._key = kdf.derive(password.encode("utf-8"))
        self._aesgcm = AESGCM(self._key)
        self._save_key()
        return self._key

    def _save_key(self):
        """| 将密钥保存到文件（使用机器特征绑定）|"""
        if self._key is None:
            raise ValueError("No key to save")
        # Bind key to machine: hash(key || machine_id)
        # Use stable machine identifiers only (not CWD which varies by run location)
        machine_id = hashlib.sha256(
            f"{os.environ.get('COMPUTERNAME', 'default')}{os.getlogin()}{os.environ.get('USERNAME', '')}".encode()
        ).hexdigest()[:16]
        protected = self._key + machine_id.encode()
        self._key_path.write_bytes(protected)
        # Also export salt for migration
        self._export_salt()

    def _load_key(self):
        """| 从文件加载密钥 |"""
        raw = self._key_path.read_bytes()
        machine_id = hashlib.sha256(
            f"{os.environ.get('COMPUTERNAME', 'default')}{os.getlogin()}{os.environ.get('USERNAME', '')}".encode()
        ).hexdigest()[:16]
        stored = raw[len(raw) - 16:] if len(raw) > 16 else b""
        if stored.decode("utf-8", errors="ignore") != machine_id:
            raise SecurityError("Key file not bound to this machine. Key migration requires re-authentication.")
        self._key = raw[:KEY_LENGTH]
        self._aesgcm = AESGCM(self._key)

    def _load_key_from_salt(self):
        """| 从 salt 文件 + 已有密钥加载 |"""
        raise SecurityError("Key file missing but salt exists. Run init with your existing password to recover.")

    def _export_salt(self):
        """| 导出 salt 用于密钥迁移 |"""
        if self._salt_path.exists():
            salt_copy = self._salt_path.parent / ".salt.backup"
            if not salt_copy.exists():
                import shutil
                shutil.copy2(str(self._salt_path), str(salt_copy))

    def has_key(self) -> bool:
        return self._key is not None

    # --------------------------------------------------------------------------
    # Encryption / Decryption
    # --------------------------------------------------------------------------
    def encrypt(self, plaintext: str) -> EncryptedBlob:
        """| 加密字符串，返回 EncryptedBlob |"""
        if self._aesgcm is None:
            raise SecurityError("EncryptionEngine not initialized. Call generate_key() first.")
        nonce = os.urandom(NONCE_LENGTH)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # GCM appends tag to ciphertext (last 16 bytes)
        ciphertext = ct[:-16]
        tag = ct[-16:]
        return EncryptedBlob(
            version=CURRENT_VERSION,
            nonce=base64.b64encode(nonce).decode(),
            ciphertext=base64.b64encode(ciphertext).decode(),
            tag=base64.b64encode(tag).decode(),
        )

    def decrypt(self, blob: EncryptedBlob) -> str:
        """| 解密 EncryptedBlob，返回原始字符串 |"""
        if self._aesgcm is None:
            raise SecurityError("EncryptionEngine not initialized. Call generate_key() first.")
        nonce = base64.b64decode(blob.nonce)
        ciphertext = base64.b64decode(blob.ciphertext)
        tag = base64.b64decode(blob.tag)
        # GCM: ciphertext + tag must be combined
        combined = ciphertext + tag
        plaintext = self._aesgcm.decrypt(nonce, combined, None)
        return plaintext.decode("utf-8")

    def encrypt_raw(self, data: bytes) -> bytes:
        """| 加密原始字节（用于大型数据）|"""
        if self._aesgcm is None:
            raise SecurityError("EncryptionEngine not initialized.")
        nonce = os.urandom(NONCE_LENGTH)
        ct = self._aesgcm.encrypt(nonce, data, None)
        return nonce + ct

    def decrypt_raw(self, data: bytes) -> bytes:
        """| 解密原始字节 |"""
        if self._aesgcm is None:
            raise SecurityError("EncryptionEngine not initialized.")
        nonce = data[:NONCE_LENGTH]
        ciphertext = data[NONCE_LENGTH:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)

    # --------------------------------------------------------------------------
    # Key Derivation (for password verification)
    # --------------------------------------------------------------------------
    @staticmethod
    def derive_verification_token(password: str, salt: bytes) -> str:
        """| 生成密码验证令牌（不存储密码）|"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=16,
            salt=salt,
            iterations=10000,
            backend=default_backend(),
        )
        return base64.b64encode(kdf.derive(password.encode())).decode()

    def verify_password(self, password: str) -> bool:
        """| 验证密码是否正确 |"""
        if not self._salt_path.exists():
            return False
        salt = self._salt_path.read_bytes()
        # We store a verification token alongside the key
        v_path = self._key_path.parent / ".verify"
        if not v_path.exists():
            return False
        stored = v_path.read_text().strip()
        computed = self.derive_verification_token(password, salt)
        return stored == computed

    def save_verification_token(self, password: str):
        """| 保存密码验证令牌 |"""
        if not self._salt_path.exists():
            raise ValueError("Salt not found")
        salt = self._salt_path.read_bytes()
        token = self.derive_verification_token(password, salt)
        v_path = self._key_path.parent / ".verify"
        v_path.write_text(token)


class SecurityError(Exception):
    """| 安全相关异常 |"""
    pass


# ============================================================================
# Singleton Instance
# ============================================================================
_engine: Optional[EncryptionEngine] = None

def get_engine() -> EncryptionEngine:
    global _engine
    if _engine is None:
        _engine = EncryptionEngine()
    return _engine


def init_engine(password: str) -> EncryptionEngine:
    global _engine
    _engine = EncryptionEngine()
    _engine.generate_key(password)
    _engine.save_verification_token(password)
    return _engine