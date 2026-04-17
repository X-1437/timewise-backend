from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from app.database import get_db
from app.core.security import get_password_hash, decode_token
from app.models.user import UserResponse

router = APIRouter(prefix="/users", tags=["用户"])


def get_current_user_id(token: str = Depends(lambda: None)) -> str:
    return "current_user_id"


async def get_current_user(token: str):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    return user_id


@router.get("/me", response_model=UserResponse)
async def get_me(authorization: str = Depends(lambda x: x)):
    token = authorization.replace("Bearer ", "")
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user["email"],
        created_at=user["created_at"]
    )


@router.patch("/me", response_model=UserResponse)
async def update_me(updates: dict, authorization: str = Depends(lambda x: x)):
    token = authorization.replace("Bearer ", "")
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if "email" in updates:
        user["email"] = updates["email"]
    if "password" in updates:
        user["hashed_password"] = get_password_hash(updates["password"])
    
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": user}
    )
    
    return UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user["email"],
        created_at=user["created_at"]
    )
