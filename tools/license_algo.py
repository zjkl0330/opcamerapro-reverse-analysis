#!/usr/bin/env python3
"""OPCameraPro 激活算法参考实现（纯静态还原，用于理解与自检，不含私钥无法生成有效码）。"""
import hashlib, base64

def _x(s: str, b: bytes) -> bytes:
    """C2172.m4229: b[i] ^ s[i % len(s)]"""
    k = s.encode()
    return bytes(b[i] ^ k[i % len(k)] for i in range(len(b)))


SALT      = "video_120fps"                                  # f8708 ^ "my_salt_key_123"
MAGIC     = _x("my_token_key_abc", bytes([77,26,28,20,10,17,24,4,90,31,22,26,3,8,9]))  # l1 魔数(15B)
LEGACY_K  = "legacy_migration_proof_key_2026_04"            # C2176.f8739
INNER_K   = "internal_sign_key_v2"                          # C2172.f8712
V2        = "v2"                                            # C2176.f8738
PUBKEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAo9qQdiTe7kccke0mdrVW
+F6uoEc0eoVps7gsjn+Ku1sgpEBgl3dDxX6uc+9tpdMqPHFHRnuL99/vgzjAKezY
O7ByRXZO3q7vFQgGg1EcTYtk4S6pCOU2l/tr2U/Ff+3252Q3F0X8B/N6M1Vmc0se
FJIVi272csdjJMUwenrmtWiIPzcRVjTgjFUo3LsPqB9eNiwnRlqOhpqN4wPuuLvY
WGyt4TYD223owIo1aFl7ZNqUZFDb/s94mkGQMdzjvLscPMCCeguSYtpZXMsJyG9z
8Ne8LWtEUWQQP9j1xcnIm/VcWM2l/oCETmkrgx9NGf+tZy4vrhHzb73eLWCzEgjH
MQIDAQAB
-----END PUBLIC KEY-----"""

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def machine_hash(serial: str) -> str:
    """C2172.m4221 = SHA-256(serial + SALT)"""
    return sha256_hex(serial + SALT)

def machine_prefix(serial: str) -> str:
    """m4228: first16(SHA-256(machineHash)) —— 对应 AbstractC3505.m5797(16, m4221)"""
    return sha256_hex(machine_hash(serial))[:16]

def m2_seal(mh: str, tier: str, ts: int, p3: str, p4: str) -> str:
    """C2176.m4231 = first32(SHA-256(v2|mh|tier|ts|p3|p4|LEGACY_K))"""
    return sha256_hex(f"{V2}|{mh}|{tier}|{ts}|{p3}|{p4}|{LEGACY_K}")[:32]

def l1_seal(serial_hash: str, ts: int, p3: str) -> str:
    """C2172.m4228 内部 = first16(SHA-256(MAGIC + serial_hash + ts + INNER_K))"""
    return sha256_hex(MAGIC.decode('latin1') + serial_hash + str(ts) + INNER_K)[:16]

if __name__ == "__main__":
    demo = "DEMO1234567890"
    print("示例序列号 :", demo)
    print("machineHash:", machine_hash(demo))
    print("prefix(16) :", machine_prefix(demo))
    print("m2 seal(32):", m2_seal(machine_hash(demo), "advanced", 1780000000000, "aaaa", "bbbb"))
    print("\n注：a1 需作者 RSA 私钥签名，本地不可生成；本脚本仅用于验证校验路径与做自检。")
