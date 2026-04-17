from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from bson import ObjectId
from app.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_token
from app.schemas.auth import UserCreate, UserLogin, Token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    db = get_db()
    
    existing_user = await db.users.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=409, detail="用户名已存在")
    
    existing_email = await db.users.find_one({"email": user.email})
    if existing_email:
        raise HTTPException(status_code=409, detail="邮箱已被注册")
    
    hashed_password = get_password_hash(user.password)
    user_doc = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_password,
        "created_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    token = create_access_token({"user_id": user_id, "username": user.username})
    
    return Token(
        token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": user_id,
            "username": user.username,
            "email": user.email
        }
    )


@router.post("/login", response_model=Token)
async def login(user: UserLogin):
    db = get_db()
    
    db_user = await db.users.find_one({"username": user.username})
    if not db_user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    if not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    user_id = str(db_user["_id"])
    token = create_access_token({"user_id": user_id, "username": db_user["username"]})
    
    return Token(
        token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": user_id,
            "username": db_user["username"],
            "email": db_user["email"]
        }
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")

    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的Token")

    user_id = payload.get("user_id")
    username = payload.get("username")

    if not user_id or not username:
        raise HTTPException(status_code=401, detail="无效的Token")

    new_token = create_access_token({"user_id": user_id, "username": username})

    db = get_db()
    db_user = await db.users.find_one({"_id": ObjectId(user_id)})

    return Token(
        token=new_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": user_id,
            "username": db_user["username"],
            "email": db_user["email"]
        } if db_user else None
    )


@router.post("/logout")
async def logout():
    return {"message": "退出成功"}
