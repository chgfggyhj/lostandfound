"""
核心服务层
包含匹配、协商、通知等业务逻辑
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from typing import List, Optional, Dict, Any
import datetime
import json
import re

from models import (
    Item, ItemType, ItemStatus, ItemImage,
    NegotiationSession, NegotiationStatus, FailedMatch,
    Notification, NotificationType, ReturnSchedule, User
)
from agents import SeekerAgent, FinderAgent, create_llm
from config import MAX_NEGOTIATION_ROUNDS, MIN_MATCH_SCORE

# 尝试导入文本相似度库
try:
    import jieba
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SIMILARITY = True
except ImportError:
    HAS_SIMILARITY = False
    print("[Warning] jieba/sklearn 未安装，使用简单关键词匹配")


class MatchService:
    """匹配服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def _tokenize(self, text: str) -> str:
        """中文分词"""
        if HAS_SIMILARITY:
            return " ".join(jieba.cut(text))
        return text
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        if not HAS_SIMILARITY:
            return self._simple_keyword_match(text1, text2)
        
        try:
            # 分词
            tokens1 = self._tokenize(text1)
            tokens2 = self._tokenize(text2)
            
            # TF-IDF 向量化
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform([tokens1, tokens2])
            
            # 余弦相似度
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except Exception as e:
            print(f"[MatchService] 相似度计算失败: {e}")
            return self._simple_keyword_match(text1, text2)
    
    def _simple_keyword_match(self, text1: str, text2: str) -> float:
        """简单关键词匹配"""
        # 提取关键词
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        
        def extract_keywords(text):
            words = re.split(r'[\s,，。！？、；：""''（）\[\]【】]', text)
            return set(w.strip() for w in words if w.strip() and len(w.strip()) >= 2 and w.strip() not in stop_words)
        
        keywords1 = extract_keywords(text1)
        keywords2 = extract_keywords(text2)
        
        if not keywords1 or not keywords2:
            return 0.0
        
        # 计算 Jaccard 相似度
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_match_score(self, lost_item: Item, found_item: Item) -> float:
        """
        计算两个物品的匹配度
        综合考虑标题、描述、AI描述、地点
        """
        scores = []
        weights = []
        
        # 1. 标题相似度 (权重: 0.3)
        title_score = self._calculate_similarity(lost_item.title, found_item.title)
        scores.append(title_score)
        weights.append(0.3)
        
        # 2. 描述相似度 (权重: 0.3)
        desc1 = lost_item.description or ""
        desc2 = found_item.description or ""
        if desc1 and desc2:
            desc_score = self._calculate_similarity(desc1, desc2)
            scores.append(desc_score)
            weights.append(0.3)
        
        # 3. AI 描述相似度 (权重: 0.3)
        ai_desc1 = lost_item.ai_description or ""
        ai_desc2 = found_item.ai_description or ""
        if ai_desc1 and ai_desc2:
            ai_score = self._calculate_similarity(ai_desc1, ai_desc2)
            scores.append(ai_score)
            weights.append(0.3)
        
        # 4. 地点匹配 (权重: 0.1)
        loc1 = lost_item.location or ""
        loc2 = found_item.location or ""
        if loc1 and loc2:
            loc_score = self._calculate_similarity(loc1, loc2)
            scores.append(loc_score)
            weights.append(0.1)
        
        # 加权平均
        if not scores:
            return 0.0
        
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        
        return round(weighted_score, 4)
    
    def find_matches(self, lost_item: Item, limit: int = 10) -> List[Dict[str, Any]]:
        """
        为丢失物品查找匹配的拾取物品
        返回按匹配度降序排列的列表
        """
        # 获取已失败的配对
        failed_found_ids = self.db.query(FailedMatch.found_item_id).filter(
            FailedMatch.lost_item_id == lost_item.id
        ).all()
        failed_ids = [f[0] for f in failed_found_ids]
        
        # 查询可用的 FOUND 物品（排除同一用户的物品）
        query = self.db.query(Item).filter(
            Item.type == ItemType.FOUND,
            Item.status.in_([ItemStatus.OPEN, ItemStatus.MATCHING]),
            Item.owner_id != lost_item.owner_id  # 排除同一用户的物品
        )
        
        if failed_ids:
            query = query.filter(Item.id.notin_(failed_ids))
        
        found_items = query.all()
        
        # 计算匹配度
        matches = []
        for found_item in found_items:
            score = self.calculate_match_score(lost_item, found_item)
            if score >= MIN_MATCH_SCORE:
                matches.append({
                    "item": found_item,
                    "score": score
                })
        
        # 按匹配度降序排序
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        return matches[:limit]


class NegotiationService:
    """协商服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm = create_llm()
        self.match_service = MatchService(db)
    
    def create_session(self, lost_item_id: int, found_item_id: int, match_score: float = 0.0) -> NegotiationSession:
        """创建协商会话"""
        # 锁定物品
        lost_item = self.db.query(Item).get(lost_item_id)
        found_item = self.db.query(Item).get(found_item_id)
        
        if lost_item:
            lost_item.status = ItemStatus.NEGOTIATING
        if found_item:
            found_item.status = ItemStatus.NEGOTIATING
        
        session = NegotiationSession(
            lost_item_id=lost_item_id,
            found_item_id=found_item_id,
            match_score=match_score,
            status=NegotiationStatus.ACTIVE,
            chat_log=[]
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def _hydrate_agents(self, session: NegotiationSession):
        """恢复 Agent 实例"""
        seeker = SeekerAgent(
            name="SeekerBot",
            llm=self.llm,
            item_knowledge=session.lost_item
        )
        finder = FinderAgent(
            name="FinderBot",
            llm=self.llm,
            item_knowledge=session.found_item
        )
        
        chat_log = session.chat_log if session.chat_log else []
        seeker.memory = chat_log.copy()
        finder.memory = chat_log.copy()
        
        return seeker, finder
    
    def run_full_negotiation(self, session_id: int) -> Dict[str, Any]:
        """
        执行完整的自动协商流程
        """
        from sqlalchemy.orm.attributes import flag_modified
        
        session = self.db.query(NegotiationSession).get(session_id)
        if not session or session.status != NegotiationStatus.ACTIVE:
            return {"error": "会话无效或已结束"}
        
        seeker, finder = self._hydrate_agents(session)
        
        for round_num in range(MAX_NEGOTIATION_ROUNDS):
            # 轮流对话
            last_sender = None
            if session.chat_log:
                last_sender = session.chat_log[-1].get("sender")
            
            current_agent = seeker if last_sender != "Seeker" else finder
            
            # Agent 决策和执行
            decision = current_agent.decide()
            message = current_agent.execute(decision)
            
            # 更新聊天记录
            current_log = list(session.chat_log) if session.chat_log else []
            current_log.append(message)
            session.chat_log = current_log
            
            # 强制标记 JSON 字段为已修改（SQLAlchemy 对 JSON 修改检测有问题）
            flag_modified(session, "chat_log")
            self.db.commit()
            
            # 同步记忆
            seeker.memory = current_log.copy()
            finder.memory = current_log.copy()
            
            # 检查结果
            action_type = message.get("action_type")
            
            if action_type == "AGREE":
                session.status = NegotiationStatus.PENDING_CONFIRM
                session.completed_at = datetime.datetime.utcnow()
                self.db.commit()
                return {
                    "status": "SUCCESS",
                    "session": session,
                    "rounds": round_num + 1
                }
            
            elif action_type == "REJECT":
                session.status = NegotiationStatus.FAILED
                session.completed_at = datetime.datetime.utcnow()
                self.db.commit()
                return {
                    "status": "FAILED",
                    "session": session,
                    "rounds": round_num + 1
                }
        
        # 超过最大轮数
        session.status = NegotiationStatus.FAILED
        session.completed_at = datetime.datetime.utcnow()
        self.db.commit()
        
        return {
            "status": "MAX_ROUNDS",
            "session": session,
            "rounds": MAX_NEGOTIATION_ROUNDS
        }
    
    def handle_success(self, session: NegotiationSession):
        """处理协商成功"""
        session.lost_item.status = ItemStatus.MATCHED
        session.found_item.status = ItemStatus.MATCHED
        self.db.commit()
    
    def handle_failure(self, session: NegotiationSession, reason: str = None):
        """处理协商失败"""
        # 记录失败
        failed = FailedMatch(
            lost_item_id=session.lost_item_id,
            found_item_id=session.found_item_id,
            session_id=session.id,
            reason=reason
        )
        self.db.add(failed)
        
        # 恢复物品状态
        session.lost_item.status = ItemStatus.OPEN
        session.found_item.status = ItemStatus.OPEN
        
        self.db.commit()


class NotificationService:
    """通知服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def send(self, user_id: int, type: NotificationType, title: str, message: str = None, session_id: int = None):
        """发送通知"""
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            related_session_id=session_id
        )
        self.db.add(notification)
        self.db.commit()
        return notification
    
    def get_user_notifications(self, user_id: int, unread_only: bool = False) -> List[Notification]:
        """获取用户通知"""
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(desc(Notification.created_at)).all()
    
    def mark_as_read(self, notification_id: int):
        """标记为已读"""
        notification = self.db.query(Notification).get(notification_id)
        if notification:
            notification.is_read = True
            self.db.commit()


class BackgroundTaskService:
    """后台任务服务 - 使用 FastAPI BackgroundTasks"""
    
    def __init__(self, db: Session):
        self.db = db
        self.match_service = MatchService(db)
        self.negotiation_service = NegotiationService(db)
        self.notification_service = NotificationService(db)
    
    def run_auto_matching(self, lost_item_id: int):
        """
        自动匹配流程（后台执行）
        """
        lost_item = self.db.query(Item).get(lost_item_id)
        if not lost_item:
            return
        
        # 更新状态为匹配中
        lost_item.status = ItemStatus.MATCHING
        self.db.commit()
        
        # 获取匹配列表
        matches = self.match_service.find_matches(lost_item)
        
        if not matches:
            # 无匹配
            lost_item.status = ItemStatus.OPEN
            self.db.commit()
            
            self.notification_service.send(
                user_id=lost_item.owner_id,
                type=NotificationType.NO_MATCH,
                title="暂无匹配物品",
                message="系统暂时没有找到与您丢失物品匹配的拾取记录，我们会持续为您搜索。"
            )
            return
        
        # 依次尝试匹配
        for match in matches:
            found_item = match["item"]
            score = match["score"]
            
            # 创建协商会话
            session = self.negotiation_service.create_session(
                lost_item.id, found_item.id, score
            )
            
            # 执行协商
            result = self.negotiation_service.run_full_negotiation(session.id)
            
            if result.get("status") == "SUCCESS":
                # 协商成功，通知双方确认
                self.notification_service.send(
                    user_id=lost_item.owner_id,
                    type=NotificationType.MATCH_FOUND,
                    title="找到疑似匹配物品！",
                    message=f"系统为您找到了一个匹配度 {score*100:.0f}% 的物品，请确认是否是您丢失的物品。",
                    session_id=session.id
                )
                
                self.notification_service.send(
                    user_id=found_item.owner_id,
                    type=NotificationType.MATCH_FOUND,
                    title="您拾取的物品可能找到失主啦！",
                    message="有用户的丢失物品与您拾取的物品匹配，请等待对方确认。",
                    session_id=session.id
                )
                return
            
            else:
                # 协商失败，继续下一个
                self.negotiation_service.handle_failure(session, result.get("status"))
                continue
        
        # 所有匹配都失败
        lost_item.status = ItemStatus.OPEN
        self.db.commit()
        
        self.notification_service.send(
            user_id=lost_item.owner_id,
            type=NotificationType.NO_MATCH,
            title="暂无匹配物品",
            message=f"系统尝试了 {len(matches)} 个可能匹配的物品，但都未能确认。我们会持续为您搜索。"
        )
