from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    token: str
    expires_in: int
    user: Optional[dict] = None


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
