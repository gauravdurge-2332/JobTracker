import os
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

AUTH_SERVICE_URL = "http://localhost:8002"

bearer = HTTPBearer()

async def get_current_user_id(cred : Annotated[HTTPAuthorizationCredentials , Depends(bearer)] ,) -> str:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/auth/verify",
                headers={"Authorization": f"Bearer {cred.credentials}"},
            )
    except httpx.RequestError:
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

    return str(resp.json()["id"])

UserDep = Annotated[str, Depends(get_current_user_id)]