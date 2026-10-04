import os
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

class CurrentUser(BaseModel):
    id: str
    email: str

AUTH_SERVICE_URL = os.environ["AUTH_SERVICE_URL"]

bearer = HTTPBearer()


async def get_current_user(cred : Annotated[HTTPAuthorizationCredentials , Depends(bearer)] ,) -> CurrentUser:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/auth/verify",
                headers={"Authorization": f"Bearer {cred.credentials}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    data = resp.json()
    return CurrentUser(id=str(data["id"]), email=data["email"])

CurrentUserDep = Annotated[CurrentUser , Depends(get_current_user)]

async def get_current_user_id(userObject : CurrentUserDep):
    return str(userObject.id)

UserDep = Annotated[str, Depends(get_current_user_id)]