"""
Test 3: Encryption engine - encrypt/decrypt, key generation, edge cases
"""
import sys
import os
import tempfile
import shutil
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")


def test_encrypt_decrypt_roundtrip():
    """Encrypt then decrypt should return original text"""
    try:
        from core.encryption import EncryptionEngine
        engine, salt = EncryptionEngine.from_password("test_password_123")

        original = "Hello, this is a secret message!"
        blob = engine.encrypt(original)
        decrypted = engine.decrypt(blob)

        log("encrypt_decrypt_roundtrip", decrypted == original,
            f"match={decrypted == original}")
    except Exception as e:
        log("encrypt_decrypt_roundtrip", False, f"{e}\n{traceback.format_exc()}")


def test_key_generation_and_loading():
    """Key generation and loading from password"""
    tmpdir = tempfile.mkdtemp(prefix="mf_test_enc_")
    try:
        from core.encryption import EncryptionEngine, init_engine

        # Generate key
        engine1, salt = EncryptionEngine.from_password("mypassword")
        blob = engine1.encrypt("secret data")

        # Create new engine with same password and salt
        engine2, _ = EncryptionEngine.from_password("mypassword", salt)
        decrypted = engine2.decrypt(blob)

        log("key_reload_same_password", decrypted == "secret data",
            f"match={decrypted == 'secret data'}")

        # Different password should fail
        engine3, _ = EncryptionEngine.from_password("wrong_password", salt)
        try:
            engine3.decrypt(blob)
            log("key_wrong_password_fails", False, "Should have raised")
        except Exception:
            log("key_wrong_password_fails", True, "Correctly rejected wrong password")

    except Exception as e:
        log("key_generation_loading", False, f"{e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_empty_content():
    """Encrypt/decrypt empty string"""
    try:
        from core.encryption import EncryptionEngine
        engine, salt = EncryptionEngine.from_password("test")

        blob = engine.encrypt("")
        decrypted = engine.decrypt(blob)
        log("encrypt_empty_content", decrypted == "",
            f"got='{decrypted}'")
    except Exception as e:
        log("encrypt_empty_content", False, f"{e}\n{traceback.format_exc()}")


def test_very_long_content():
    """Encrypt/decrypt very long content"""
    try:
        from core.encryption import EncryptionEngine
        engine, salt = EncryptionEngine.from_password("test")

        long_text = "A" * 100000
        blob = engine.encrypt(long_text)
        decrypted = engine.decrypt(blob)
        log("encrypt_long_content", decrypted == long_text,
            f"len={len(decrypted)}")
    except Exception as e:
        log("encrypt_long_content", False, f"{e}\n{traceback.format_exc()}")


def test_unicode_content():
    """Encrypt/decrypt Unicode content (CJK, emoji, etc.)"""
    try:
        from core.encryption import EncryptionEngine
        engine, salt = EncryptionEngine.from_password("test")

        unicode_texts = [
            "Chinese: \u4f60\u597d\u4e16\u754c",
            "Japanese: \u3053\u3093\u306b\u3061\u306f",
            "Korean: \uc548\ub155\ud558\uc138\uc694",
            "Arabic: \u0645\u0631\u062d\u0628\u0627",
            "Emoji: \U0001f600\U0001f60d\U0001f680",
            "Mixed: Hello \u4e16\u754c \U0001f30d test",
        ]

        all_ok = True
        for text in unicode_texts:
            blob = engine.encrypt(text)
            dec = engine.decrypt(blob)
            if dec != text:
                all_ok = False
                log("encrypt_unicode", False, f"mismatch for: {text[:20]}")
                break

        if all_ok:
            log("encrypt_unicode", True, f"all {len(unicode_texts)} unicode texts OK")

    except Exception as e:
        log("encrypt_unicode", False, f"{e}\n{traceback.format_exc()}")


def test_hash_verify():
    """Hash and verify_hash"""
    try:
        from core.encryption import EncryptionEngine
        engine, _ = EncryptionEngine.from_password("test")

        data = "some data to hash"
        h = engine.hash(data)
        log("hash_verify_correct", engine.verify_hash(data, h), "hash matches")
        log("hash_verify_wrong", not engine.verify_hash("wrong data", h), "wrong data rejected")

    except Exception as e:
        log("hash_verify", False, f"{e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 3: Encryption Engine")
    print("=" * 60)

    test_encrypt_decrypt_roundtrip()
    test_key_generation_and_loading()
    test_empty_content()
    test_very_long_content()
    test_unicode_content()
    test_hash_verify()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(RESULTS)} tests")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  FAILED: {name} - {detail}")
    print("=" * 60)
