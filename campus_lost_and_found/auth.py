"""
用户认证模块
JWT Token 认证
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from models import User

# OAuth2 Token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


# ==================== Pydantic 模型 ====================

class UserRegister(BaseModel):
    """用户注册请求"""
    username: str
    password: str
    name: str
    contact_info: str


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class Token(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token 数据"""
    username: Optional[str] = None
    user_id: Optional[int] = None


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    name: str
    contact_info: str


# ==================== 密码处理 ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# ==================== Token 处理 ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT Token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """解码 Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if username is None:
            return None
            
        return TokenData(username=username, user_id=user_id)
    except JWTError:
        return None


# ==================== 用户服务 ====================

class AuthService:
    """认证服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """通过 ID 获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def create_user(self, user_data: UserRegister) -> User:
        """创建新用户"""
        # 检查用户名是否已存在
        existing_user = self.get_user_by_username(user_data.username)
        if existing_user:
            raise ValueError("用户名已存在")
        
        # 创建用户
        user = User(
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
            name=user_data.name,
            contact_info=user_data.contact_info
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """验证用户"""
        user = self.get_user_by_username(username)
        
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
            
        return user
    
    def login(self, username: str, password: str) -> Optional[Token]:
        """用户登录，返回 Token"""
        user = self.authenticate_user(username, password)
        
        if not user:
            return None
        
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )
        
        return Token(access_token=access_token, token_type="bearer")


# ==================== 依赖注入 ====================

def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[TokenData]:
    """获取当前用户（可选，不强制登录）"""
    if not token:
        return None
    return decode_token(token)


def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> TokenData:
    """获取当前用户（强制登录）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    token_data = decode_token(token)
    
    if token_data is None:
        raise credentials_exception
        
    return token_data
