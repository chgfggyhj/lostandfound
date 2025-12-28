"""
数据库模型定义
支持 MySQL 和 SQLite（备用）
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON, Boolean, Float
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy import create_engine
import datetime
import enum

from config import DATABASE_URL, USE_SQLITE, SQLITE_URL

Base = declarative_base()


# ==================== 枚举类型 ====================

class ItemType(enum.Enum):
    LOST = "LOST"      # 丢失
    FOUND = "FOUND"    # 拾取


class ItemStatus(enum.Enum):
    OPEN = "OPEN"              # 开放，可匹配
    MATCHING = "MATCHING"      # 正在匹配中
    NEGOTIATING = "NEGOTIATING"  # 协商中
    MATCHED = "MATCHED"        # 已匹配成功
    CLOSED = "CLOSED"          # 已关闭


class NegotiationStatus(enum.Enum):
    ACTIVE = "ACTIVE"              # 协商进行中
    SUCCESS = "SUCCESS"            # 协商成功
    FAILED = "FAILED"              # 协商失败
    PENDING_CONFIRM = "PENDING_CONFIRM"  # 等待用户确认
    CONFIRMED = "CONFIRMED"        # 用户已确认是自己的物品
    REJECTED = "REJECTED"          # 用户确认不是自己的物品
    SCHEDULE_PENDING = "SCHEDULE_PENDING"  # 约定待失主确认
    WAITING_RETURN = "WAITING_RETURN"  # 等待归还
    RETURNED = "RETURNED"          # 已归还成功
    RETURN_FAILED = "RETURN_FAILED"    # 归还失败


class NotificationType(enum.Enum):
    MATCH_FOUND = "MATCH_FOUND"        # 找到匹配物品
    CONFIRM_REQUEST = "CONFIRM_REQUEST"  # 请求确认
    SCHEDULE = "SCHEDULE"              # 约定归还
    NO_MATCH = "NO_MATCH"              # 暂无匹配
    NEGOTIATION_UPDATE = "NEGOTIATION_UPDATE"  # 协商进度更新


# ==================== 用户模型 ====================

class User(Base):
    """用户表"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    contact_info = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 关系
    items = relationship("Item", back_populates="owner")
    notifications = relationship("Notification", back_populates="user")


# ==================== 物品模型 ====================

class Item(Base):
    """物品表"""
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)  # 用户填写的描述
    ai_description = Column(Text, nullable=True)  # AI 识别的描述
    type = Column(Enum(ItemType), nullable=False)
    status = Column(Enum(ItemStatus), default=ItemStatus.OPEN)
    location = Column(String(200))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner_id = Column(Integer, ForeignKey('users.id'))
    owner = relationship("User", back_populates="items")
    
    # 图片关联
    images = relationship("ItemImage", back_populates="item", cascade="all, delete-orphan")


class ItemImage(Base):
    """物品图片表"""
    __tablename__ = 'item_images'

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    image_path = Column(String(500), nullable=False)  # 存储路径
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    item = relationship("Item", back_populates="images")


# ==================== 协商模型 ====================

class NegotiationSession(Base):
    """协商会话表"""
    __tablename__ = 'negotiation_sessions'

    id = Column(Integer, primary_key=True, index=True)
    
    lost_item_id = Column(Integer, ForeignKey('items.id'))
    found_item_id = Column(Integer, ForeignKey('items.id'))
    
    status = Column(Enum(NegotiationStatus), default=NegotiationStatus.ACTIVE)
    match_score = Column(Float, default=0.0)  # 匹配度分数
    chat_log = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # 用户确认状态
    seeker_confirmed = Column(Boolean, nullable=True)  # None=未确认, True=是我的, False=不是我的
    finder_confirmed = Column(Boolean, nullable=True)

    lost_item = relationship("Item", foreign_keys=[lost_item_id])
    found_item = relationship("Item", foreign_keys=[found_item_id])
    
    # 归还约定
    return_schedule = relationship("ReturnSchedule", back_populates="session", uselist=False)


class FailedMatch(Base):
    """失败匹配记录表"""
    __tablename__ = 'failed_matches'
    
    id = Column(Integer, primary_key=True, index=True)
    lost_item_id = Column(Integer, ForeignKey('items.id'))
    found_item_id = Column(Integer, ForeignKey('items.id'))
    session_id = Column(Integer, ForeignKey('negotiation_sessions.id'), nullable=True)
    reason = Column(String(200), nullable=True)  # 失败原因
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# ==================== 通知模型 ====================

class Notification(Base):
    """通知表"""
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    related_session_id = Column(Integer, ForeignKey('negotiation_sessions.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="notifications")


# ==================== 归还约定模型 ====================

class ReturnSchedule(Base):
    """归还约定表"""
    __tablename__ = 'return_schedules'

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('negotiation_sessions.id'), nullable=False, unique=True)
    
    proposed_time = Column(DateTime, nullable=True)
    proposed_location = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)  # 备注
    
    # 约定状态：PENDING/APPROVED/REJECTED
    status = Column(String(20), default="PENDING")
    reject_reason = Column(Text, nullable=True)  # 回绝理由
    
    seeker_confirmed = Column(Boolean, default=False)
    finder_confirmed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    session = relationship("NegotiationSession", back_populates="return_schedule")


# ==================== 数据库引擎 ====================

def get_database_url():
    """获取数据库 URL"""
    if USE_SQLITE:
        return SQLITE_URL
    return DATABASE_URL


# 创建引擎
db_url = get_database_url()
if db_url.startswith("sqlite"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(db_url, pool_pre_ping=True)

print(f"[Database] Using: {'SQLite' if USE_SQLITE else 'MySQL'}")
