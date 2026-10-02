import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import Settings
from ..models import Tenant, User
from ..security import DUMMY_HASH, create_token, hash_password, verify_password
from .deps import EMAIL_RE, current_user, get_db, get_settings

router = APIRouter(tags=["auth"])


class TenantCreate(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=100)
    admin_email: str = Field(pattern=EMAIL_RE, max_length=254)
    admin_password: str = Field(min_length=10, max_length=128)


@router.post("/tenants", status_code=201)
def create_tenant(
    body: TenantCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_bootstrap_token: str | None = Header(default=None),
):
    """Create an organization and its first admin. Requires X-Bootstrap-Token when RAG_BOOTSTRAP_TOKEN is set."""
    if settings.bootstrap_token and not hmac.compare_digest(x_bootstrap_token or "", settings.bootstrap_token):
        raise HTTPException(403, "Invalid bootstrap token")
    email = body.admin_email.lower()
    if db.scalar(select(Tenant).where(Tenant.name == body.tenant_name)):
        raise HTTPException(409, "Tenant name already exists")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    tenant = Tenant(name=body.tenant_name)
    db.add(tenant)
    db.flush()
    admin = User(tenant_id=tenant.id, email=email, password_hash=hash_password(body.admin_password), role="admin")
    db.add(admin)
    db.commit()
    audit(db, tenant.id, admin.id, "tenant.create", tenant.id)
    return {"tenant_id": tenant.id, "admin_id": admin.id}


@router.post("/auth/login")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    email = form.username.lower()
    request.app.state.limiter.check(f"login:{email}", settings.login_rate_limit_per_min)
    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(form.password, user.password_hash if user else DUMMY_HASH)  # constant-ish time
    if not (user and ok and user.is_active):
        audit(db, user.tenant_id if user else None, user.id if user else None, "auth.login_failed", detail_email=email)
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    audit(db, user.tenant_id, user.id, "auth.login")
    return {"access_token": create_token(settings, user), "token_type": "bearer"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role, "tenant_id": user.tenant_id}
