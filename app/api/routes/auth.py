import re
from fastapi import APIRouter, HTTPException, Request
from app.core.auth import hash_password, verify_password
from app.models.schemas import LoginRequest, RegisterRequest, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


def validate_email(email: str) -> bool:
    return bool(re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email))


def get_user_from_header(request: Request) -> dict:
    user_id = request.headers.get('x-user-id')
    if user_id is None:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header.")
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid X-User-ID header.")
    user = request.app.state.db.get_user_by_id(user_id_int)
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


@router.post("/register", response_model=UserProfile)
async def register(payload: RegisterRequest, request: Request):
    name = payload.name.strip() if payload.name else ''
    email = payload.email.strip().lower() if payload.email else ''
    password = payload.password or ''

    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required.")
    if len(name) < 3:
        raise HTTPException(status_code=400, detail="Name must be at least 3 characters.")
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="Email must be a valid format.")
    if len(password) < 8 or not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[0-9]', password) or not re.search(r'[^A-Za-z0-9]', password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters and include uppercase, lowercase, number, and special character.",
        )

    existing = request.app.state.db.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    password_hash = hash_password(password)
    user_id = request.app.state.db.create_user(name, email, password_hash)
    user = request.app.state.db.get_user_by_id(user_id)
    return UserProfile(**user)


@router.post("/login", response_model=UserProfile)
async def login(payload: LoginRequest, request: Request):
    email = payload.email.strip().lower()
    user = request.app.state.db.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please register first.")
    if not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")
    return UserProfile(**user)
