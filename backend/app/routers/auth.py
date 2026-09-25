from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import get_current_user, oauth2_scheme, require_roles
from ..models import AuditLog, RevokedToken, User
from ..schemas import LoginRequest, TokenResponse, UserCreate, UserOut, UserUpdate
from ..security import create_access_token, decode_access_token, hash_password, verify_password
from ..services import record_audit

router = APIRouter(prefix="/auth", tags=["authentication"])


def _public_user(user: User) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username.strip().lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_audit(
            db,
            action="LOGIN_FAILURE",
            resource_type="USER",
            resource_id=user.id if user else None,
            details={"username": payload.username.strip().lower()},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    user.last_login_at = datetime.now(UTC)
    token, expires_in, jti, expires_at = create_access_token(user)
    record_audit(db, action="LOGIN_SUCCESS", user_id=user.id, resource_type="USER", resource_id=user.id)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=token, expires_in=expires_in, user=_public_user(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    payload = decode_access_token(token)
    jti = payload.get("jti")
    expires_at = payload.get("exp")
    if isinstance(expires_at, (int, float)):
        expires_at = datetime.fromtimestamp(expires_at, UTC)
    if jti and expires_at and db.get(RevokedToken, jti) is None:
        db.add(RevokedToken(jti=jti, user_id=current_user.id, expires_at=expires_at))
    record_audit(db, action="LOGOUT", user_id=current_user.id, resource_type="USER", resource_id=current_user.id)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _public_user(current_user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [_public_user(user) for user in users]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    _: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> UserOut:
    username = payload.username.strip().lower()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    record_audit(db, action="USER_CREATED", user_id=_.id, resource_type="USER", resource_id=user.id, details={"role": user.role})
    db.commit()
    db.refresh(user)
    return _public_user(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes: dict[str, object] = {}
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
        changes["display_name"] = user.display_name
    if payload.role is not None:
        user.role = payload.role
        changes["role"] = user.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changes["is_active"] = user.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        changes["password"] = "changed"
    record_audit(db, action="USER_UPDATED", user_id=current_user.id, resource_type="USER", resource_id=user.id, details=changes)
    db.commit()
    db.refresh(user)
    return _public_user(user)
