from pydantic import BaseModel, ConfigDict, EmailStr

class UserSchema(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr