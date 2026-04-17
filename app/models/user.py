from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr


class User(BaseModel):
    id: Optional[str] = None
    username: str
    email: EmailStr
    hashed_password: str
    created_at: datetime = datetime.utcnow()


class UserInDB(User):
    pass


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True
