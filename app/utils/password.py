"""密码工具 — 使用 argon2-cffi 直接实现，不依赖 passlib"""
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

_ph = PasswordHasher()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerificationError, InvalidHashError):
        return False


def get_password_hash(password: str) -> str:
    """对密码进行 argon2 哈希"""
    return _ph.hash(password)


def generate_password(length: int = 12) -> str:
    """生成安全随机密码"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))
