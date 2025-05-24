from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from typing import Annotated, Optional

from .security import decode_access_token #, JWT_SECRET_KEY, JWT_ALGORITHM (should be loaded from main config)
from ...models import TokenData, User, UserInDB, get_user_from_db # Adjusted import path
# from ...main import API_CONFIG # To get JWT settings

# This will require clients to send a token with "Bearer " prefix in Authorization header
# tokenUrl should point to your actual token endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") 

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: Optional[str] = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    # In a real app, you might also check token expiry here if not handled by decode_access_token directly
    # or if you need to check against a token revocation list.

    user = get_user_from_db(username=username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[UserInDB, Depends(get_current_user)]) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return User(**current_user.model_dump()) # Return as User model (without hashed_password)

# Example of a dependency for role-based access (if you add roles to User model)
# def require_role(required_role: str):
#     async def role_checker(current_user: Annotated[User, Depends(get_current_active_user)]) -> User:
#         if required_role not in current_user.roles:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN, 
#                 detail=f"User does not have the required '{required_role}' role"
#             )
#         return current_user
#     return role_checker 