"""Single-owner admin authentication with a signed, http-only cookie."""
import hmac

from fastapi import Cookie, HTTPException, Response
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from .config import get_settings

COOKIE = "mm_admin"
MAX_AGE = 30 * 24 * 3600


def _signer() -> TimestampSigner:
    return TimestampSigner(get_settings().secret_key, salt="megamind-admin")


def check_password(password: str) -> bool:
    return hmac.compare_digest(password.encode(), get_settings().admin_password.encode())


def login(response: Response) -> None:
    token = _signer().sign(b"owner").decode()
    response.set_cookie(COOKIE, token, max_age=MAX_AGE, httponly=True, samesite="lax")


def logout(response: Response) -> None:
    response.delete_cookie(COOKIE)


def is_admin(token: str | None) -> bool:
    if not token:
        return False
    try:
        return _signer().unsign(token, max_age=MAX_AGE) == b"owner"
    except (BadSignature, SignatureExpired):
        return False


def require_admin(mm_admin: str | None = Cookie(default=None)) -> None:
    if not is_admin(mm_admin):
        raise HTTPException(status_code=401, detail="Admin login required")
