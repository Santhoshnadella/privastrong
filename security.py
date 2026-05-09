"""
Hardened Security and Access Control Module
Handles JWT authentication and RBAC with production-grade safeguards
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from config import Config

# Enforce SECRET_KEY in production
SECRET_KEY = Config.SECRET_KEY
if Config.is_production() and SECRET_KEY == "dev-secret-key-change-this-in-prod":
    raise ValueError("CRITICAL: SECRET_KEY must be set to a secure value in production!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    roles: List[str] = []
    org_id: Optional[str] = None

class User(BaseModel):
    username: str
    email: str
    org_id: str
    roles: List[str] = ["user"]
    disabled: Optional[bool] = None

# Mock users moved to a conditional block
# In production, this would be replaced by a database lookup
MOCK_USERS_DB = {}
if not Config.is_production():
    MOCK_USERS_DB = {
        "admin": {
            "username": "admin",
            "email": "admin@example.com",
            "org_id": "org_root",
            "roles": ["admin", "user"],
            "hashed_password": pwd_context.hash("admin-password"),
        }
    }

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, roles=payload.get("roles", []), org_id=payload.get("org_id"))
    except JWTError:
        raise credentials_exception
        
    # Security: Log authentication attempt
    # logger.info(f"Auth attempt for user: {username}")
    
    user = MOCK_USERS_DB.get(username) # PRODUCTION: db.get_user(username)
    if user is None:
        raise credentials_exception
    return User(**user)

def check_permissions(required_roles: List[str]):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if any(role in current_user.roles for role in required_roles):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted for your role"
        )
    return role_checker
