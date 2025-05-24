from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any

from jose import JWTError, jwt
from passlib.context import CryptContext

# Configuration (ideally loaded from main app config or environment variables)
# These would be set from API_CONFIG.get('jwt', {})
JWT_SECRET_KEY = "your-very-secret-key-please-change-in-production" # Placeholder, load from config
JWT_ALGORITHM = "HS256"  # Placeholder, load from config
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Placeholder, load from config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # Ensure JWT_SECRET_KEY and JWT_ALGORITHM are properly loaded from config in a real app
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        # Ensure JWT_SECRET_KEY and JWT_ALGORITHM are properly loaded from config
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

# This function will be more fleshed out in dependencies.py for actual user loading
# For now, it's a helper for token decoding. 