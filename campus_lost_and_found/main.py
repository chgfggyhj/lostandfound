"""
校园失物招领系统 V2.0 API
FastAPI 应用入口
"""
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os

from models import (
    Base, engine, User, Item, ItemType, ItemStatus, ItemImage,
    NegotiationSession, NegotiationStatus, Notification, ReturnSchedule
)
from auth import (
    AuthService, UserRegister, UserLogin, Token, UserResponse,
    get_current_user, get_current_user_optional, TokenData
)
from services import MatchService, NegotiationService, NotificationService, BackgroundTaskService
from image_service import image_service
from config import UPLOAD_DIR

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="校园失物招领系统 V2.0", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ==================== 健康检查 ====================

@app.get("/health")
def health_check():
    """健康检查端点（用于 Docker 健康检查）"""
    return {"status": "healthy", "version": "2.0.0"}


# ==================== 数据库依赖 ====================

def get_db():
    db = Session(bind=engine)
    try:
        yield db
    finally:
        db.close()


# ==================== Pydantic 模型 ====================

class ItemCreate(BaseModel):
    title: str
    description: str
    type: str  # LOST or FOUND
    location: Optional[str] = None
    ai_description: Optional[str] = None


class ItemResponse(BaseModel):
    id: int
    title: str
    description: str
    ai_description: Optional[str]
    type: str
    status: str
    location: Optional[str]
    owner_id: int
    owner_name: Optional[str]
    images: List[str]
    created_at: str


class ScheduleCreate(BaseModel):
    proposed_time: datetime
    proposed_location: str
    notes: Optional[str] = None


# ==================== 认证接口 ====================

@app.post("/auth/register", response_model=UserResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """用户注册"""
    auth_service = AuthService(db)
    try:
        user = auth_service.create_user(user_data)
        return UserResponse(
            id=user.id,
            username=user.username,
            name=user.name,
            contact_info=user.contact_info
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户登录（表单方式，OAuth2 兼容）"""
    auth_service = AuthService(db)
    token = auth_service.login(form_data.username, form_data.password)
    if not token:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return token


@app.post("/auth/login/json", response_model=Token)
def login_json(user_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录（JSON 方式）"""
    auth_service = AuthService(db)
    token = auth_service.login(user_data.username, user_data.password)
    if not token:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return token


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户信息"""
    user = db.query(User).get(current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        contact_info=user.contact_info
    )


# ==================== 图片接口 ====================

@app.post("/images/upload")
async def upload_image(file: UploadFile = File(...)):
    """上传图片"""
    content = await file.read()
    try:
        path = image_service.save_image(content, file.filename)
        return {"path": path, "url": f"/static/{path}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/images/analyze")
async def analyze_image(file: UploadFile = File(...), item_type: str = Form("物品")):
    """上传图片并识别"""
    content = await file.read()
    try:
        # 保存图片
        path = image_service.save_image(content, file.filename)
        
        # 识别图片
        description = image_service.analyze_image(path, item_type)
        
        return {
            "path": path,
            "url": f"/static/{path}",
            "ai_description": description
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 物品接口 ====================

@app.post("/items/")
def create_item(
    item: ItemCreate,
    image_paths: Optional[str] = None,  # 改为字符串，从查询参数接收 JSON
    background_tasks: BackgroundTasks = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建物品"""
    import json
    
    # 解析图片路径
    parsed_image_paths = []
    if image_paths:
        try:
            parsed_image_paths = json.loads(image_paths)
        except json.JSONDecodeError:
            parsed_image_paths = [image_paths]  # 单个路径
    
    # 创建物品
    db_item = Item(
        title=item.title,
        description=item.description,
        ai_description=item.ai_description,
        type=ItemType[item.type],
        status=ItemStatus.OPEN,
        location=item.location,
        owner_id=current_user.user_id
    )
    db.add(db_item)
    db.flush()
    
    # 添加图片
    if parsed_image_paths:
        for path in parsed_image_paths:
            img = ItemImage(item_id=db_item.id, image_path=path)
            db.add(img)
    
    db.commit()
    db.refresh(db_item)
    
    # 如果是丢失物品，触发后台匹配
    if db_item.type == ItemType.LOST and background_tasks:
        background_tasks.add_task(
            run_background_matching,
            db_item.id
        )
    
    return {"id": db_item.id, "message": "物品发布成功"}


@app.get("/items/")
def get_items(
    type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取物品列表"""
    query = db.query(Item)
    
    if type:
        query = query.filter(Item.type == ItemType[type])
    if status:
        query = query.filter(Item.status == ItemStatus[status])
    
    items = query.order_by(Item.timestamp.desc()).all()
    
    return [
        {
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "ai_description": item.ai_description,
            "type": item.type.value,
            "status": item.status.value,
            "location": item.location,
            "owner_id": item.owner_id,
            "owner_name": item.owner.name if item.owner else None,
            "images": [f"/static/{img.image_path}" for img in item.images],
            "created_at": item.timestamp.isoformat() if item.timestamp else None
        }
        for item in items
    ]


@app.get("/items/my")
def get_my_items(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的物品"""
    items = db.query(Item).filter(Item.owner_id == current_user.user_id).order_by(Item.timestamp.desc()).all()
    
    return [
        {
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "type": item.type.value,
            "status": item.status.value,
            "location": item.location,
            "images": [f"/static/{img.image_path}" for img in item.images],
            "created_at": item.timestamp.isoformat() if item.timestamp else None
        }
        for item in items
    ]


@app.get("/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    """获取物品详情"""
    item = db.query(Item).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "ai_description": item.ai_description,
        "type": item.type.value,
        "status": item.status.value,
        "location": item.location,
        "owner": {
            "id": item.owner.id,
            "name": item.owner.name,
            "contact": item.owner.contact_info
        } if item.owner else None,
        "images": [f"/static/{img.image_path}" for img in item.images],
        "created_at": item.timestamp.isoformat() if item.timestamp else None
    }


@app.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除物品"""
    item = db.query(Item).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    
    if item.owner_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权删除他人的物品")
    
    # 检查是否有进行中的协商
    from models import NegotiationSession, NegotiationStatus
    active_sessions = db.query(NegotiationSession).filter(
        ((NegotiationSession.lost_item_id == item_id) | (NegotiationSession.found_item_id == item_id)),
        NegotiationSession.status.in_([NegotiationStatus.ACTIVE, NegotiationStatus.PENDING_CONFIRM])
    ).count()
    
    if active_sessions > 0:
        raise HTTPException(status_code=400, detail="该物品有进行中的协商，无法删除")
    
    # 先删除关联记录
    from models import FailedMatch, Notification
    
    # 删除失败匹配记录
    db.query(FailedMatch).filter(
        (FailedMatch.lost_item_id == item_id) | (FailedMatch.found_item_id == item_id)
    ).delete(synchronize_session=False)
    
    # 删除已完成的协商会话
    completed_sessions = db.query(NegotiationSession).filter(
        (NegotiationSession.lost_item_id == item_id) | (NegotiationSession.found_item_id == item_id)
    ).all()
    
    from models import ReturnSchedule
    
    for session in completed_sessions:
        # 删除归还约定
        db.query(ReturnSchedule).filter(ReturnSchedule.session_id == session.id).delete(synchronize_session=False)
        # 删除相关通知
        db.query(Notification).filter(Notification.related_session_id == session.id).delete(synchronize_session=False)
        db.delete(session)
    
    # 删除物品
    db.delete(item)
    db.commit()
    
    return {"message": "物品已删除"}


class ItemUpdate(BaseModel):
    """物品更新请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None


@app.patch("/items/{item_id}")
def update_item(
    item_id: int,
    item_update: ItemUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新物品信息"""
    item = db.query(Item).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    
    if item.owner_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权修改他人的物品")
    
    # 更新字段
    if item_update.title is not None:
        item.title = item_update.title
    if item_update.description is not None:
        item.description = item_update.description
    if item_update.location is not None:
        item.location = item_update.location
    
    db.commit()
    db.refresh(item)
    
    return {"message": "物品已更新", "item_id": item.id}


@app.post("/items/{item_id}/match")
def trigger_matching(
    item_id: int,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """手动触发匹配"""
    item = db.query(Item).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    
    if item.owner_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作")
    
    if item.type != ItemType.LOST:
        raise HTTPException(status_code=400, detail="只有丢失物品可以触发匹配")
    
    # 触发后台匹配
    background_tasks.add_task(run_background_matching, item_id)
    
    return {"message": "匹配任务已启动，请等待通知"}


# ==================== 协商接口 ====================

@app.get("/negotiations/")
def get_my_negotiations(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我相关的协商会话"""
    # 查询我作为失主或拾主的会话
    sessions = db.query(NegotiationSession).join(
        Item, 
        (NegotiationSession.lost_item_id == Item.id) | (NegotiationSession.found_item_id == Item.id)
    ).filter(Item.owner_id == current_user.user_id).all()
    
    return [
        {
            "id": s.id,
            "status": s.status.value,
            "match_score": s.match_score,
            "lost_item": {"id": s.lost_item.id, "title": s.lost_item.title} if s.lost_item else None,
            "found_item": {"id": s.found_item.id, "title": s.found_item.title} if s.found_item else None,
            "created_at": s.created_at.isoformat() if s.created_at else None
        }
        for s in sessions
    ]


@app.get("/negotiations/{session_id}")
def get_negotiation(session_id: int, db: Session = Depends(get_db)):
    """获取协商详情"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 获取约定信息
    schedule = db.query(ReturnSchedule).filter(ReturnSchedule.session_id == session_id).order_by(ReturnSchedule.created_at.desc()).first()
    schedule_info = None
    if schedule:
        schedule_info = {
            "id": schedule.id,
            "proposed_time": schedule.proposed_time.isoformat() if schedule.proposed_time else None,
            "proposed_location": schedule.proposed_location,
            "notes": schedule.notes,
            "status": schedule.status,
            "reject_reason": schedule.reject_reason
        }
    
    return {
        "id": session.id,
        "status": session.status.value,
        "match_score": session.match_score,
        "chat_log": session.chat_log,
        "lost_item": {
            "id": session.lost_item.id,
            "title": session.lost_item.title,
            "description": session.lost_item.description,
            "owner_id": session.lost_item.owner_id
        } if session.lost_item else None,
        "found_item": {
            "id": session.found_item.id,
            "title": session.found_item.title,
            "description": session.found_item.description,
            "owner_id": session.found_item.owner_id
        } if session.found_item else None,
        "seeker_confirmed": session.seeker_confirmed,
        "finder_confirmed": session.finder_confirmed,
        "schedule": schedule_info,
        "created_at": session.created_at.isoformat() if session.created_at else None
    }


@app.post("/negotiations/{session_id}/confirm")
def confirm_item(
    session_id: int,
    is_my_item: bool,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """确认是否是自己的物品"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 确定用户角色
    if session.lost_item and session.lost_item.owner_id == current_user.user_id:
        role = "seeker"
        session.seeker_confirmed = is_my_item
    elif session.found_item and session.found_item.owner_id == current_user.user_id:
        role = "finder"
        session.finder_confirmed = is_my_item
    else:
        raise HTTPException(status_code=403, detail="无权操作")
    
    if not is_my_item:
        # 用户确认不是自己的物品
        session.status = NegotiationStatus.REJECTED
        
        # 恢复物品状态，继续匹配
        neg_service = NegotiationService(db)
        neg_service.handle_failure(session, "用户确认不是自己的物品")
        
        # 触发继续匹配
        if role == "seeker":
            # TODO: 继续匹配下一个
            pass
        
        return {"message": "已记录，将为您继续搜索"}
    
    else:
        # 检查是否双方都确认
        if session.seeker_confirmed and session.finder_confirmed:
            session.status = NegotiationStatus.CONFIRMED
            
            # 更新物品状态
            neg_service = NegotiationService(db)
            neg_service.handle_success(session)
            
            db.commit()
            return {"message": "双方已确认，请约定归还时间地点", "next": "schedule"}
        
        db.commit()
        return {"message": "已确认，等待对方确认"}


@app.post("/negotiations/{session_id}/force-match")
def force_match(
    session_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """强制将失败的协商标记为成功（用户确认是自己的物品）"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 检查用户权限
    if not (session.lost_item and session.lost_item.owner_id == current_user.user_id):
        raise HTTPException(status_code=403, detail="只有失主可以强制匹配")
    
    # 只允许对失败的会话进行强制匹配
    if session.status not in [NegotiationStatus.FAILED, NegotiationStatus.REJECTED]:
        raise HTTPException(status_code=400, detail="只能对失败的协商进行强制匹配")
    
    # 更新状态为待确认
    session.status = NegotiationStatus.PENDING_CONFIRM
    session.seeker_confirmed = True
    
    # 添加强制匹配记录到聊天日志
    chat_log = session.chat_log or []
    chat_log.append({
        "sender": "System",
        "content": "失主确认这是自己的物品，已强制标记为匹配成功。"
    })
    session.chat_log = chat_log
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(session, "chat_log")
    
    db.commit()
    
    return {"message": "已强制匹配成功，等待拾主确认"}


@app.post("/negotiations/{session_id}/schedule")
def create_schedule(
    session_id: int,
    schedule: ScheduleCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建归还约定（仅拾主可发起）"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 仅允许拾主发起约定
    if not (session.found_item and session.found_item.owner_id == current_user.user_id):
        raise HTTPException(status_code=403, detail="只有拾主可以发起约定")
    
    # 检查状态
    if session.status not in [NegotiationStatus.CONFIRMED]:
        raise HTTPException(status_code=400, detail="当前状态不允许发起约定")
    
    # 检查是否已有待处理约定
    existing = db.query(ReturnSchedule).filter(
        ReturnSchedule.session_id == session_id
    ).first()
    
    if existing:
        if existing.status == "PENDING":
            raise HTTPException(status_code=400, detail="已有待处理的约定，请等待失主确认")
        # 更新被回绝的约定
        existing.proposed_time = schedule.proposed_time
        existing.proposed_location = schedule.proposed_location
        existing.notes = schedule.notes
        existing.status = "PENDING"
        existing.reject_reason = None  # 清除回绝理由
    else:
        # 创建新约定
        new_schedule = ReturnSchedule(
            session_id=session_id,
            proposed_time=schedule.proposed_time,
            proposed_location=schedule.proposed_location,
            notes=schedule.notes,
            status="PENDING"
        )
        db.add(new_schedule)
    
    # 更新会话状态
    session.status = NegotiationStatus.SCHEDULE_PENDING
    
    db.commit()
    
    # 发送通知给失主
    notification_service = NotificationService(db)
    seeker_id = session.lost_item.owner_id if session.lost_item else None
    
    from models import NotificationType
    if seeker_id:
        notification_service.send(
            user_id=seeker_id,
            type=NotificationType.SCHEDULE,
            title="拾主发起了归还约定",
            message=f"时间: {schedule.proposed_time}, 地点: {schedule.proposed_location}，请确认是否同意。",
            session_id=session_id
        )
    
    return {"message": "约定已发起，等待失主确认"}


@app.post("/negotiations/{session_id}/schedule/approve")
def approve_schedule(
    session_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """失主同意约定"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 仅允许失主操作
    if not (session.lost_item and session.lost_item.owner_id == current_user.user_id):
        raise HTTPException(status_code=403, detail="只有失主可以审批约定")
    
    if session.status != NegotiationStatus.SCHEDULE_PENDING:
        raise HTTPException(status_code=400, detail="当前状态不允许审批约定")
    
    # 更新约定状态
    schedule = db.query(ReturnSchedule).filter(
        ReturnSchedule.session_id == session_id,
        ReturnSchedule.status == "PENDING"
    ).first()
    if schedule:
        schedule.status = "APPROVED"
    
    # 更新会话状态
    session.status = NegotiationStatus.WAITING_RETURN
    
    db.commit()
    
    # 通知拾主
    notification_service = NotificationService(db)
    finder_id = session.found_item.owner_id if session.found_item else None
    from models import NotificationType
    if finder_id:
        notification_service.send(
            user_id=finder_id,
            type=NotificationType.NEGOTIATION_UPDATE,
            title="失主已同意约定",
            message="可以按约定时间地点进行归还了。",
            session_id=session_id
        )
    
    return {"message": "已同意约定，进入等待归还状态"}


class RejectRequest(BaseModel):
    reason: str


@app.post("/negotiations/{session_id}/schedule/reject")
def reject_schedule(
    session_id: int,
    reject: RejectRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """失主回绝约定"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 仅允许失主操作
    if not (session.lost_item and session.lost_item.owner_id == current_user.user_id):
        raise HTTPException(status_code=403, detail="只有失主可以审批约定")
    
    if session.status != NegotiationStatus.SCHEDULE_PENDING:
        raise HTTPException(status_code=400, detail="当前状态不允许审批约定")
    
    if not reject.reason or not reject.reason.strip():
        raise HTTPException(status_code=400, detail="回绝理由不能为空")
    
    # 更新约定状态
    schedule = db.query(ReturnSchedule).filter(
        ReturnSchedule.session_id == session_id,
        ReturnSchedule.status == "PENDING"
    ).first()
    if schedule:
        schedule.status = "REJECTED"
        schedule.reject_reason = reject.reason.strip()
    
    # 返回 CONFIRMED 状态，允许拾主重新发起
    session.status = NegotiationStatus.CONFIRMED
    
    db.commit()
    
    # 通知拾主
    notification_service = NotificationService(db)
    finder_id = session.found_item.owner_id if session.found_item else None
    from models import NotificationType
    if finder_id:
        notification_service.send(
            user_id=finder_id,
            type=NotificationType.NEGOTIATION_UPDATE,
            title="约定被失主回绝",
            message=f"回绝理由: {reject.reason}，您可以重新发起约定。",
            session_id=session_id
        )
    
    return {"message": "已回绝约定"}


@app.post("/negotiations/{session_id}/start-return")
def start_return(
    session_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """开始等待归还（约定后调用）"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.status != NegotiationStatus.CONFIRMED:
        raise HTTPException(status_code=400, detail="只有已确认的会话才能开始等待归还")
    
    session.status = NegotiationStatus.WAITING_RETURN
    db.commit()
    
    return {"message": "已进入等待归还状态"}


@app.post("/negotiations/{session_id}/confirm-return")
def confirm_return(
    session_id: int,
    is_returned: bool,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """确认归还状态"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.status != NegotiationStatus.WAITING_RETURN:
        raise HTTPException(status_code=400, detail="只有等待归还状态才能确认")
    
    # 记录谁确认了以及确认结果
    is_seeker = session.lost_item and session.lost_item.owner_id == current_user.user_id
    is_finder = session.found_item and session.found_item.owner_id == current_user.user_id
    
    if not (is_seeker or is_finder):
        raise HTTPException(status_code=403, detail="无权操作")
    
    # 获取约定记录
    schedule = db.query(ReturnSchedule).filter(ReturnSchedule.session_id == session_id).first()
    
    if is_seeker:
        if schedule:
            schedule.seeker_confirmed = is_returned
        session.seeker_confirmed = is_returned
    elif is_finder:
        if schedule:
            schedule.finder_confirmed = is_returned
        session.finder_confirmed = is_returned
    
    db.commit()
    db.refresh(session)
    
    # 检查是否有人选了 "否"（任一方选否即恢复物品）
    seeker_said_no = session.seeker_confirmed == False and is_seeker
    finder_said_no = session.finder_confirmed == False and is_finder
    
    # 如果当前用户选了否
    if not is_returned:
        session.status = NegotiationStatus.RETURN_FAILED
        session.completed_at = datetime.utcnow()
        
        # 恢复物品状态为 OPEN
        if session.lost_item:
            session.lost_item.status = ItemStatus.OPEN
        if session.found_item:
            session.found_item.status = ItemStatus.OPEN
        
        # 记录到失败匹配
        from models import FailedMatch
        failed = FailedMatch(
            lost_item_id=session.lost_item.id if session.lost_item else None,
            found_item_id=session.found_item.id if session.found_item else None,
            reason="线下确认不匹配"
        )
        db.add(failed)
        
        db.commit()
        return {"message": "已标记归还失败，物品已恢复可匹配状态"}
    
    # 检查是否双方都确认了"是"
    if session.seeker_confirmed and session.finder_confirmed:
        session.status = NegotiationStatus.RETURNED
        session.completed_at = datetime.utcnow()
        
        # 保存物品ID用于后续删除
        lost_item_id = session.lost_item.id if session.lost_item else None
        found_item_id = session.found_item.id if session.found_item else None
        
        # 先删除关联记录
        from models import FailedMatch, Notification, ItemImage
        
        for item_id in [lost_item_id, found_item_id]:
            if item_id:
                db.query(FailedMatch).filter(
                    (FailedMatch.lost_item_id == item_id) | (FailedMatch.found_item_id == item_id)
                ).delete(synchronize_session=False)
                db.query(ItemImage).filter(ItemImage.item_id == item_id).delete(synchronize_session=False)
        
        # 将会话的物品引用置空（避免外键约束）
        session.lost_item_id = None
        session.found_item_id = None
        db.flush()
        
        # 删除物品
        if lost_item_id:
            db.query(Item).filter(Item.id == lost_item_id).delete(synchronize_session=False)
        if found_item_id:
            db.query(Item).filter(Item.id == found_item_id).delete(synchronize_session=False)
        
        db.commit()
        return {"message": "归还完成，物品已从系统移除"}
    
    return {"message": "已确认，等待对方确认"}


@app.post("/negotiations/{session_id}/return-failed")
def return_failed(
    session_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """归还失败（线下确认不匹配）"""
    session = db.query(NegotiationSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.status != NegotiationStatus.WAITING_RETURN:
        raise HTTPException(status_code=400, detail="只有等待归还状态才能标记归还失败")
    
    # 检查权限
    is_seeker = session.lost_item and session.lost_item.owner_id == current_user.user_id
    is_finder = session.found_item and session.found_item.owner_id == current_user.user_id
    if not (is_seeker or is_finder):
        raise HTTPException(status_code=403, detail="无权操作")
    
    # 更新会话状态
    session.status = NegotiationStatus.RETURN_FAILED
    session.completed_at = datetime.datetime.utcnow()
    
    # 恢复物品状态为 OPEN
    if session.lost_item:
        session.lost_item.status = ItemStatus.OPEN
    if session.found_item:
        session.found_item.status = ItemStatus.OPEN
    
    # 记录到失败匹配
    from models import FailedMatch
    failed = FailedMatch(
        lost_item_id=session.lost_item.id if session.lost_item else None,
        found_item_id=session.found_item.id if session.found_item else None,
        reason="线下确认不匹配"
    )
    db.add(failed)
    
    db.commit()
    
    return {"message": "已标记归还失败，物品已恢复可匹配状态"}


# ==================== 通知接口 ====================

@app.get("/notifications/")
def get_notifications(
    unread_only: bool = False,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的通知"""
    service = NotificationService(db)
    notifications = service.get_user_notifications(current_user.user_id, unread_only)
    
    return [
        {
            "id": n.id,
            "type": n.type.value,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "session_id": n.related_session_id,
            "created_at": n.created_at.isoformat() if n.created_at else None
        }
        for n in notifications
    ]


@app.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """标记通知为已读"""
    service = NotificationService(db)
    service.mark_as_read(notification_id)
    return {"message": "已标记为已读"}


# ==================== 后台任务 ====================

def run_background_matching(item_id: int):
    """后台执行匹配任务"""
    db = Session(bind=engine)
    try:
        service = BackgroundTaskService(db)
        service.run_auto_matching(item_id)
    finally:
        db.close()


# ==================== 健康检查 ====================

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
