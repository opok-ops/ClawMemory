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
    algorithm: str = "AES-256-GCM"  # v5.4.2：标记加密算法，降级时为 EXPERIMENTAL_HMAC_XOR

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
        self._aesgcm = None
        crypto = _get_crypto()
        if crypto:
            AESGCM = crypto[0]
            self._aesgcm = AESGCM(key)

    @classmethod
    def from_password(cls, password: str, salt: Optional[bytes] = None) -> Tuple["EncryptionEngine", bytes]:
        """从密码派生密钥"""
        if salt is None:
            salt = os.urandom(16)

        crypto = _get_crypto()
        if crypto:
            _, PBKDF2HMAC, hashes = crypto
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=_PBKDF2_ITERATIONS,
            )
            key = kdf.derive(password.encode())
        else:
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS, dklen=32)
            key = dk

        return cls(key), salt

    def encrypt(self, plaintext: str) -> EncryptedBlob:
        """加密文本"""
        plaintext_bytes = plaintext.encode("utf-8")
        nonce = os.urandom(12)
        salt = os.urandom(16)

        if self._aesgcm is not None:
            ciphertext = self._aesgcm.encrypt(nonce, plaintext_bytes, None)
            return EncryptedBlob(ciphertext=ciphertext, nonce=nonce, salt=salt, algorithm="AES-256-GCM")
        else:
            ciphertext = self._simple_encrypt(plaintext_bytes, nonce)
            return EncryptedBlob(ciphertext=ciphertext, nonce=nonce, salt=salt, algorithm="EXPERIMENTAL_HMAC_XOR")

    def decrypt(self, blob: EncryptedBlob) -> str:
        """解密文本"""
        if self._aesgcm is not None:
            try:
                plaintext = self._aesgcm.decrypt(blob.nonce, blob.ciphertext, None)
                return plaintext.decode("utf-8")
            except (ValueError, TypeError) as e:
                raise SecurityError(f"解密失败：{e}")
        else:
            plaintext = self._simple_decrypt(blob.ciphertext, blob.nonce)
            return plaintext.decode("utf-8")

    def _simple_encrypt(self, data: bytes, nonce: bytes) -> bytes:
        """简易加密（无 cryptography 库时的降级方案）

        v5.3.3 安全加固：改用 HMAC-SHA256 计数器模式生成密钥流，
        替代此前固定 32 字节重复 XOR 的弱方案。每 32 字节使用不同密钥流块，
        消除密钥流重复导致的明文泄露风险。
        """
        result = bytearray()
        block_idx = 0
        for i, b in enumerate(data):
            if i % 32 == 0:
                # v5.3.3：计数器模式，每块使用不同密钥流
                counter = block_idx.to_bytes(8, "big")
                derived = hmac.new(
                    self._key, nonce + counter, hashlib.sha256
                ).digest()
                block_idx += 1
            result.append(b ^ derived[i % 32])
        tag = hmac.new(self._key, bytes(result), hashlib.sha256).digest()
        return bytes(result) + tag

    def _simple_decrypt(self, data: bytes, nonce: bytes) -> bytes:
        """简易解密

        v5.3.3 安全加固：与 _simple_encrypt 对称的计数器模式解密。
        """
        tag = data[-32:]
        ciphertext = data[:-32]
        expected_tag = hmac.new(self._key, ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise SecurityError("完整性校验失败")
        result = bytearray()
        block_idx = 0
        for i, b in enumerate(ciphertext):
            if i % 32 == 0:
                counter = block_idx.to_bytes(8, "big")
                derived = hmac.new(
                    self._key, nonce + counter, hashlib.sha256
                ).digest()
                block_idx += 1
            result.append(b ^ derived[i % 32])
        return bytes(result)

    def hash(self, data: str) -> str:
        """计算数据哈希"""
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_hash(self, data: str, hash_value: str) -> bool:
        """验证哈希"""
        return hmac.compare_digest(self.hash(data), hash_value)


_global_engine: Optional[EncryptionEngine] = None


def init_engine(password: str, key_file: str = "./data/.key") -> EncryptionEngine:
    """初始化全局加密引擎

    v5.2.2 修复：显式指定文件 encoding='utf-8'，避免在中文/Windows 系统上
    出现 UnicodeDecodeError 或编码不一致问题。
    """
    global _global_engine

    key_path = Path(key_file)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        with open(key_path, "r", encoding="utf-8") as f:
            key_data = json.load(f)
        salt = base64.b64decode(key_data["salt"])
        engine, _ = EncryptionEngine.from_password(password, salt)
    else:
        engine, salt = EncryptionEngine.from_password(password)
        with open(key_path, "w", encoding="utf-8") as f:
            json.dump({
                "salt": base64.b64encode(salt).decode(),
                "version": "5.0",
                "kdf": "PBKDF2-SHA256",
                "iterations": _PBKDF2_ITERATIONS,
            }, f, indent=2)
        # v5.4.2 安全修复：设置严格的文件权限（仅所有者可读写）- 防止密钥泄露
        import sys
        if sys.platform == "win32":
            # Windows: 使用 icacls 设置 ACL，仅允许当前用户访问
            try:
                import subprocess
                import os as _os
                username = _os.getlogin()
                subprocess.run(
                    ["icacls", str(key_path), "/inheritance:r", "/grant:r", f"{username}:F"],
                    capture_output=True, timeout=5, check=False
                )
            except Exception:
                pass  # icacls 失败不阻断流程，但已尝试设置权限
        else:
            # Unix/Linux/macOS: chmod 600
            try:
                import stat
                key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except (OSError, AttributeError):
                pass

    _global_engine = engine
    return engine


def get_engine() -> EncryptionEngine:
    """获取全局加密引擎"""
    if _global_engine is None:
        raise SecurityError("加密引擎未初始化，请先调用 init_engine()")
    return _global_engine
