"""
MindForge v5.0 加密引擎
AES-256-GCM + PBKDF2 密钥派生
"""

import os
import hashlib
import hmac
import json
import base64
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class SecurityError(Exception):
    """安全相关异常"""
    pass


@dataclass
class EncryptedBlob:
    """加密数据块"""
    ciphertext: bytes
    nonce: bytes
    salt: bytes
    tag: Optional[bytes] = None

    def to_dict(self) -> dict:
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "salt": base64.b64encode(self.salt).decode(),
            "tag": base64.b64encode(self.tag).decode() if self.tag else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EncryptedBlob":
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            nonce=base64.b64decode(data["nonce"]),
            salt=base64.b64decode(data["salt"]),
            tag=base64.b64decode(data["tag"]) if data.get("tag") else None,
        )


class EncryptionEngine:
    """加密引擎"""

    def __init__(self, key: bytes):
        self._key = key
        if _HAS_CRYPTO:
            self._aesgcm = AESGCM(key)

    @classmethod
    def from_password(cls, password: str, salt: Optional[bytes] = None) -> Tuple["EncryptionEngine", bytes]:
        """从密码派生密钥"""
        if salt is None:
            salt = os.urandom(16)

        if _HAS_CRYPTO:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = kdf.derive(password.encode())
        else:
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000, dklen=32)
            key = dk

        return cls(key), salt

    def encrypt(self, plaintext: str) -> EncryptedBlob:
        """加密文本"""
        plaintext_bytes = plaintext.encode("utf-8")
        nonce = os.urandom(12)
        salt = os.urandom(16)

        if _HAS_CRYPTO:
            ciphertext = self._aesgcm.encrypt(nonce, plaintext_bytes, None)
            return EncryptedBlob(ciphertext=ciphertext, nonce=nonce, salt=salt)
        else:
            ciphertext = self._simple_encrypt(plaintext_bytes, nonce)
            return EncryptedBlob(ciphertext=ciphertext, nonce=nonce, salt=salt)

    def decrypt(self, blob: EncryptedBlob) -> str:
        """解密文本"""
        if _HAS_CRYPTO:
            try:
                plaintext = self._aesgcm.decrypt(blob.nonce, blob.ciphertext, None)
                return plaintext.decode("utf-8")
            except Exception as e:
                raise SecurityError(f"解密失败：{e}")
        else:
            plaintext = self._simple_decrypt(blob.ciphertext, blob.nonce)
            return plaintext.decode("utf-8")

    def _simple_encrypt(self, data: bytes, nonce: bytes) -> bytes:
        """简易加密（无 cryptography 库时的降级方案）"""
        derived = hashlib.sha256(self._key + nonce).digest()
        result = bytearray()
        for i, b in enumerate(data):
            result.append(b ^ derived[i % len(derived)])
        tag = hmac.new(self._key, bytes(result), hashlib.sha256).digest()
        return bytes(result) + tag

    def _simple_decrypt(self, data: bytes, nonce: bytes) -> bytes:
        """简易解密"""
        tag = data[-32:]
        ciphertext = data[:-32]
        expected_tag = hmac.new(self._key, ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise SecurityError("完整性校验失败")
        derived = hashlib.sha256(self._key + nonce).digest()
        result = bytearray()
        for i, b in enumerate(ciphertext):
            result.append(b ^ derived[i % len(derived)])
        return bytes(result)

    def hash(self, data: str) -> str:
        """计算数据哈希"""
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_hash(self, data: str, hash_value: str) -> bool:
        """验证哈希"""
        return hmac.compare_digest(self.hash(data), hash_value)


_global_engine: Optional[EncryptionEngine] = None


def init_engine(password: str, key_file: str = "./data/.key") -> EncryptionEngine:
    """初始化全局加密引擎"""
    global _global_engine

    key_path = Path(key_file)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        with open(key_path, "r") as f:
            key_data = json.load(f)
        salt = base64.b64decode(key_data["salt"])
        engine, _ = EncryptionEngine.from_password(password, salt)
    else:
        engine, salt = EncryptionEngine.from_password(password)
        with open(key_path, "w") as f:
            json.dump({
                "salt": base64.b64encode(salt).decode(),
                "version": "5.0",
                "kdf": "PBKDF2-SHA256",
                "iterations": 100000,
            }, f, indent=2)

    _global_engine = engine
    return engine


def get_engine() -> EncryptionEngine:
    """获取全局加密引擎"""
    if _global_engine is None:
        raise SecurityError("加密引擎未初始化，请先调用 init_engine()")
    return _global_engine
