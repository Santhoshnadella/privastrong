"""
Security and Access Control Module
Handles JWT authentication and RBAC (Role-Based Access Control)
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-for-development")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day

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

# Mock user database for demonstration
# In production, this would be in PostgreSQL
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
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
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
        
    user = MOCK_USERS_DB.get(username) # In production: db.get_user(username)
    if user is None:
        raise credentials_exception
    return User(**user)

def check_permissions(required_roles: List[str]):
    """Decorator for RBAC check"""
    async def role_checker(current_user: User = Depends(get_current_user)):
        for role in required_roles:
            if role in current_user.roles:
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted for your role"
        )
    return role_checker
