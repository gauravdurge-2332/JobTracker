import os
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def hash_Password(password: str) -> str:
    return password_hash.hash(password)


def verifyPassword(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)

JWT_SECRET = os.getenv("JWT_SECRET" , "HappybirthdayGaurav")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM" , "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES" , "30")
)


def create_access_token(user_id : int) -> str :
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub" : str(user_id) , 
        "exp" : expire
    }
    return jwt.encode(payload , JWT_SECRET , algorithm = JWT_ALGORITHM)

def decode_token(token : str) -> dict:
    return jwt.decode(token , JWT_SECRET , algorithms=[JWT_ALGORITHM])