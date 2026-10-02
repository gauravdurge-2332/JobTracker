from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.model import User
from app.scehma import UserSchema, UserOut
from app.security import hash_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED
)
def signup(
    payload: UserSchema,
    session: Session = Depends(get_session)
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
        hashed_password=hash_password(payload.password)
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user