from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Annotated

from .security import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES #, JWT_SECRET_KEY, JWT_ALGORITHM (these will be loaded from main config)
from ...models import Token, User, UserInDB, get_user_from_db # Adjusted import path for models
# from ...main import API_CONFIG # If JWT settings are needed directly here, though better from security.py

router = APIRouter()

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user_in_db = get_user_from_db(form_data.username)
    if not user_in_db or not verify_password(form_data.password, user_in_db.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user_in_db.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) # This should use the configured value
    access_token = create_access_token(
        data={"sub": user_in_db.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Example of a protected route that could be in this router or elsewhere
# @router.get("/users/me", response_model=User)
# async def read_users_me(current_user: Annotated[User, Depends(get_current_active_user)]):
#     # get_current_active_user dependency will be defined in dependencies.py 