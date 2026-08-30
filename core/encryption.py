"""
MindForge v5.0 加密引擎
AES-256-GCM + PBKDF2 密钥派生
"""

import os
import hashlib
import hmac
import json
import base64
import threading  # v5.4.7 修复 H-4：全局引擎初始化线程安全
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

# 懒加载 cryptography：避免 CLI 启动时导入耗时（低配电脑 300ms+）
_CRYPTO_MODULE = None

def _get_crypto():
    global _CRYPTO_MODULE
    if _CRYPTO_MODULE is None:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            _CRYPTO_MODULE = (AESGCM, PBKDF2HMAC, hashes)
        except ImportError:
            _CRYPTO_MODULE = False
    return _CRYPTO_MODULE

# PBKDF2 迭代次数：60000（OWASP 2023 推荐最低值，兼顾安全与低配电脑性能）
_PBKDF2_ITERATIONS = 60000


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
    algorithm: str = "AES-256-GCM"  # 加密算法标识

    def to_dict(self) -> dict:
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "salt": base64.b64encode(self.salt).decode(),
            "tag": base64.b64encode(self.tag).decode() if self.tag else None,
            "algorithm": self.algorithm,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EncryptedBlob":
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            nonce=base64.b64decode(data["nonce"]),
            salt=base64.b64decode(data["salt"]),
            tag=base64.b64decode(data["tag"]) if data.get("tag") else None,
            algorithm=data.get("algorithm", "AES-256-GCM"),
        )


class EncryptionEngine:
    """加密引擎"""

    def __init__(self, key: bytes):
        self._key = key
        crypto = _get_crypto()
        if not crypto:
            # P1-008: 移除 HMAC-XOR fallback，cryptography 缺失时直接拒绝初始化
            raise SecurityError(
                "cryptography library is required for encryption. "
                "Install with: pip install cryptography"
            )
        AESGCM = crypto[0]
        self._aesgcm = AESGCM(key)

    @classmethod
    def from_password(cls, password: str, salt: Optional[bytes] = None) -> Tuple["EncryptionEngine", bytes]:
        """从密码派生密钥"""
        if salt is None:
            salt = os.urandom(16)

        crypto = _get_crypto()
        if not crypto:
            # P1-008: 移除 fallback，cryptography 缺失时直接拒绝
            raise SecurityError(
                "cryptography library is required for encryption. "
                "Install with: pip install cryptography"
            )
        _, PBKDF2HMAC, hashes = crypto
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_PBKDF2_ITERATIONS,
        )
        key = kdf.derive(password.encode())

        return cls(key), salt

    def encrypt(self, plaintext: str) -> EncryptedBlob:
        """加密文本"""
        plaintext_bytes = plaintext.encode("utf-8")
        nonce = os.urandom(12)
        salt = os.urandom(16)

        ciphertext = self._aesgcm.encrypt(nonce, plaintext_bytes, None)
        return EncryptedBlob(ciphertext=ciphertext, nonce=nonce, salt=salt, algorithm="AES-256-GCM")

    def decrypt(self, blob: EncryptedBlob) -> str:
        """解密文本"""
        try:
            plaintext = self._aesgcm.decrypt(blob.nonce, blob.ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception as e:
            raise SecurityError(f"解密失败：{e}")

    def hash(self, data: str) -> str:
        """计算数据哈希"""
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_hash(self, data: str, hash_value: str) -> bool:
        """验证哈希"""
        return hmac.compare_digest(self.hash(data), hash_value)


_global_engine: Optional[EncryptionEngine] = None
_init_lock = threading.Lock()  # v5.4.7 修复 H-4：全局引擎初始化线程安全


def init_engine(password: str, key_file: str = "./data/.key") -> EncryptionEngine:
    """初始化全局加密引擎

    v5.2.2 修复：显式指定文件 encoding='utf-8'，避免在中文/Windows 系统上
    出现 UnicodeDecodeError 或编码不一致问题。
    v5.4.7 修复 H-4：添加线程锁保护全局引擎初始化。
    v5.4.7 修复 H-2：密钥文件创建时即设置受限权限，避免权限窗口期。
    """
    global _global_engine

    with _init_lock:
        key_path = Path(key_file)
        key_path.parent.mkdir(parents=True, exist_ok=True)

        if key_path.exists():
            with open(key_path, "r", encoding="utf-8") as f:
                key_data = json.load(f)
            salt = base64.b64decode(key_data["salt"])
            engine, _ = EncryptionEngine.from_password(password, salt)
        else:
            engine, salt = EncryptionEngine.from_password(password)
            # v5.4.7 修复 H-2：创建文件时即设置受限权限
            key_content = json.dumps({
                "salt": base64.b64encode(salt).decode(),
                "version": "5.0",
                "kdf": "PBKDF2-SHA256",
                "iterations": _PBKDF2_ITERATIONS,
            }, indent=2)

            import sys
            if sys.platform != "win32":
                # Unix/Linux/macOS: 使用 os.open 以 0o600 权限创建文件
                import stat
                fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
                try:
                    os.write(fd, key_content.encode("utf-8"))
                finally:
                    os.close(fd)
            else:
                # Windows: 先写文件再尝试设置 ACL
                with open(key_path, "w", encoding="utf-8") as f:
                    f.write(key_content)
                try:
                    import subprocess
                    import os as _os
                    username = _os.getlogin()
                    subprocess.run(
                        ["icacls", str(key_path), "/inheritance:r", "/grant:r", f"{username}:F"],
                        capture_output=True, timeout=5, check=False
                    )
                except Exception:
                    pass  # icacls 失败不阻断流程

        _global_engine = engine
        return engine


def get_engine() -> EncryptionEngine:
    """获取全局加密引擎"""
    if _global_engine is None:
        raise SecurityError("加密引擎未初始化，请先调用 init_engine()")
    return _global_engine
