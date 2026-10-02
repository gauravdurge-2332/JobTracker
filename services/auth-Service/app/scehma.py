from pydantic import BaseModel , EmailStr

class UserSchema(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr