from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import Token, UserCreate, UserLogin, UserOut
from app.services.audit_service import client_ip, log_action
from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

# tokenUrl just points Swagger's "Authorize" button at the right endpoint;
# our signin route takes JSON, not the OAuth2 form this normally implies.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/signin")


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def signup(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        organisation=payload.organisation,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        # role is intentionally NOT taken from `payload` — signup always
        # creates the most restricted role. See note on User.role.
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_action(
        db,
        action="user.signup",
        user=user,
        resource_type="user",
        resource_id=user.id,
        ip_address=client_ip(request),
    )

    return user


@router.post("/signin", response_model=Token)
@limiter.limit("10/minute")
def signin(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    # Same generic message whether the email doesn't exist, the password is
    # wrong, or the account is deactivated — don't give an attacker a way
    # to tell those apart (account enumeration).
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
    )
    if not user or not verify_password(payload.password, user.hashed_password):
        log_action(
            db,
            action="user.signin_failed",
            user=user if user else None,
            detail=f"attempted email: {payload.email}",
            ip_address=client_ip(request),
        )
        raise invalid_credentials
    if not user.is_active:
        log_action(
            db,
            action="user.signin_failed",
            user=user,
            detail="account inactive",
            ip_address=client_ip(request),
        )
        raise invalid_credentials

    log_action(
        db,
        action="user.signin_success",
        user=user,
        resource_type="user",
        resource_id=user.id,
        ip_address=client_ip(request),
    )

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    Reusable dependency for any route that needs to know who's calling —
    e.g. Depends(get_current_user) in documents.py/query.py once uploads
    and queries should be scoped to a user.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory for role-gated routes. Usage:

        @router.post("/upload", ...)
        def upload_document(
            ...,
            current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
        ):

    Runs get_current_user first (so auth still applies), then checks the
    resolved user's role against the allowed set. 403, not 401 — the
    caller IS authenticated, they're just not permitted to do this
    specific thing, which is a meaningfully different error for the
    frontend to handle (e.g. hide the button vs. redirect to sign-in).
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in {role.value for role in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to perform this action.",
            )
        return current_user

    return dependency


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user