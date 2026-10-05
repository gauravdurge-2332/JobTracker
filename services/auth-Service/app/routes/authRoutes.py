from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.model import User
from app.scehma import UserOut, UserSchema
from app.security import (
    create_access_token,
    decode_token,
    hash_Password,
    verifyPassword,
)

SessionDep = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False) #tells fastapi to look at the Authoriztion in header and extract bearer token


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED
)
def signup(
    payload: UserSchema,
    session: SessionDep
):
    existing_user = session.scalar(
        select(User).where(User.email == payload.email)
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    user = User(
        email=payload.email,
        hashed_password=hash_Password(payload.password)
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user

@router.post("/login")
def login_function(payload: UserSchema, session:SessionDep):
    existing_user = session.scalar(
            select(User).where(User.email == payload.email)
        )

    if existing_user is None :
        raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                     headers={"WWW-Authenticate": "Bearer"},
                )

    
    if verifyPassword(payload.password , existing_user.hashed_password) :
        return {
            "access_token": create_access_token(existing_user.id),
            "token_type": "bearer"
            }

    raise HTTPException(
                     status_code=status.HTTP_401_UNAUTHORIZED,
                                        detail="Incorrect email or password",
                                         headers={"WWW-Authenticate": "Bearer"},
                )
        
        
@router.get("/verify", response_model=UserOut) # This is to verify by JWT
def verify_jwt_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user



