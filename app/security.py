from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())  # urlsafe-base64 string from Session 0


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:  # never leak ciphertext in the message
        raise ValueError("token could not be decrypted (key rotated or corrupt)") from e


def link_robinhood(db: Session, user: User, access_token: str, refresh_token: str | None) -> None:
    user.rh_access_token_enc = encrypt_token(access_token)
    user.rh_refresh_token_enc = encrypt_token(refresh_token) if refresh_token else None
    user.robinhood_linked = True
    db.commit()


def get_robinhood_access_token(user: User) -> str | None:
    return decrypt_token(user.rh_access_token_enc) if user.rh_access_token_enc else None