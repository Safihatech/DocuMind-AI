"""Authentication utilities for password hashing and verification."""
import bcrypt


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, stored_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_password.encode("utf-8"))
    except Exception:
        return False
