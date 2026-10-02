from collections.abc import Callable, Iterator

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..acl import AccessScope, user_scope
from ..config import Settings
from ..models import User
from ..security import decode_token
from ..services import Services

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def current_user(
    token: str = Depends(oauth2), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> User:
    unauthorized = HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_token(settings, token)
    except jwt.PyJWTError:
        raise unauthorized from None
    user = db.get(User, claims["sub"])
    # Re-checked on every request so deactivation / role changes take effect immediately.
    if user is None or not user.is_active or user.tenant_id != claims["tid"]:
        raise unauthorized
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Insufficient role")
        return user

    return dep


def scope_of(user: User = Depends(current_user), db: Session = Depends(get_db)) -> AccessScope:
    return user_scope(db, user)
