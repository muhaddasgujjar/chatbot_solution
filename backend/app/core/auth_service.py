import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import User

_ISSUER = "ou-chatbot"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "iss": _ISSUER,
        "sub": user_id,
        "email": email,
        "role": role,
        "is_admin": is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if data.get("iss") != _ISSUER:
            return {}
        return data
    except Exception:
        return {}


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, email: str, password: str, display_name: str, role: str) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        display_name=(display_name or "").strip() or email.split("@")[0],
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
