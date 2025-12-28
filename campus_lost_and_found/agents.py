from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import os
from models import Item, ItemType

# 尝试加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- LLM Interface ---

class LLMInterface(ABC):
    @abstractmethod
    def generate_response(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        pass


class DeepSeekLLM(LLMInterface):
    """
    DeepSeek 大语言模型接口
    
    使用 OpenAI 兼容格式调用 DeepSeek API
    """
    
    def __init__(self, api_key: str = None, model: str = "deepseek-chat"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model
        self.base_url = "https://api.deepseek.com"
        
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未设置。请设置环境变量 DEEPSEEK_API_KEY 或在构造函数中传入。")
        
        # 使用 openai 库，配置不带代理的 http client
        from openai import OpenAI
        import httpx
        http_client = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=http_client
        )
    
    def generate_response(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        调用 DeepSeek API 生成响应
        
        返回格式: {"action": "ASK|ANSWER|CONFIRM|REJECT|PROPOSE_MEET|AGREE", "content": "消息内容"}
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # 确保返回格式正确
            if "action" not in result:
                result["action"] = "ASK"
            if "content" not in result:
                result["content"] = "请问物品有什么具体特征？"
                
            print(f"[DeepSeek] Response: {result}")
            return result
            
        except Exception as e:
            print(f"[DeepSeek] API Error: {e}")
            # 降级到简单回复
            return {
                "action": "ASK",
                "content": "请问物品有什么具体特征可以描述一下吗？"
            }


class MockLLM(LLMInterface):
    """
    模拟大语言模型 (用于测试或无 API Key 时)
    """
    def __init__(self):
        self.round_count = 0
    
    def generate_response(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        self.round_count += 1
        lines = [line for line in user_prompt.splitlines() if ":" in line and "对话历史" not in line]
        last_message = lines[-1] if lines else ""
        
        # 检查是否有不匹配的关键词（模拟不匹配场景）
        if "不一致" in last_message or "不对" in last_message or "不是" in last_message:
            return {"action": "REJECT", "content": "抱歉，根据您的描述，这个物品似乎不是您丢失的那个。"}
        
        if "时间" in last_message or "地点" in last_message or "见面" in last_message:
            return {"action": "AGREE", "content": "好的，我们在图书馆门口见。"}
        elif "确认" in last_message or "一致" in last_message:
            return {"action": "PROPOSE_MEET", "content": "特征相符，我们可以约定一个地点见面核实吗？"}
        elif any(kw in last_message for kw in ["黑色", "索尼", "Sony", "SONY"]):
            return {"action": "CONFIRM", "content": "描述与我的物品一致，我确认这是我要找的物品。"}
        elif "特征" in last_message or "是什么" in last_message or "品牌" in last_message:
            return {"action": "ANSWER", "content": "这是一个黑色的索尼(Sony)耳机。"}
        else:
            return {"action": "ASK", "content": "请问物品有什么具体的特征吗？比如颜色、品牌等。"}


# --- 智能 Prompt 构建器 ---

def build_seeker_system_prompt(item: Item) -> str:
    """构建失主智能体的 System Prompt"""
    return f"""你是一个校园失物招领系统中的"失主代理人"(SeekerAgent)。

## 你的身份
- 你代表失主进行物品认领协商
- 你需要验证对方捡到的物品是否就是失主丢失的物品

## 你持有的物品信息（这是你知道的全部信息）
- 物品名称: {item.title}
- 物品描述: {item.description}
- 丢失地点: {item.location}

## 你的任务
1. 向对方提问，验证物品特征是否匹配（如品牌、颜色、型号等）
2. 根据对方的回答判断是否匹配
3. 如果确认匹配，提议见面归还
4. 如果明确不匹配，使用 REJECT 动作结束协商

## 回复格式 (必须是 JSON)
你必须返回一个 JSON 对象，包含以下字段:
- "action": 动作类型，必须是以下之一:
  - "ASK": 向对方提问
  - "ANSWER": 回答对方的问题
  - "CONFIRM": 确认物品匹配
  - "REJECT": 确认物品不匹配，结束协商
  - "PROPOSE_MEET": 提议见面归还
  - "AGREE": 同意对方的提议
- "content": 具体的消息内容（中文）

## ⚠️ 重要规则（必须遵守）
1. **绝对禁止编造信息**：你只知道上面"物品信息"中给出的内容，不要编造型号、材质、尺寸等未提供的细节
2. 如果对方问你不知道的细节（如型号），诚实回答"抱歉，我只知道它是XXX，不清楚具体型号"
3. 不要一次性问太多问题，每次只问一个关键问题
4. 如果对方描述的特征与你的物品信息匹配，就确认并提议见面
5. 如果对方描述的特征与你的物品明显不符，使用 REJECT 动作
6. 保持礼貌友好的语气
"""


def build_finder_system_prompt(item: Item) -> str:
    """构建拾主智能体的 System Prompt"""
    return f"""你是一个校园失物招领系统中的"拾主代理人"(FinderAgent)。

## 你的身份
- 你代表捡到物品的人进行协商
- 你需要验证对方是否是真正的失主

## 你持有的物品信息（这是你知道的全部信息）
- 物品名称: {item.title}
- 物品描述: {item.description}
- 拾得地点: {item.location}

## 你的任务
1. 回答对方关于物品特征的问题
2. 也可以反问对方，验证其是否是真正的失主
3. 如果确认对方是失主，同意见面归还
4. 如果发现对方描述与物品不符，使用 REJECT 动作结束协商

## 回复格式 (必须是 JSON)
你必须返回一个 JSON 对象，包含以下字段:
- "action": 动作类型，必须是以下之一:
  - "ASK": 向对方提问
  - "ANSWER": 回答对方的问题
  - "CONFIRM": 确认对方是失主
  - "REJECT": 确认对方不是失主，结束协商
  - "PROPOSE_MEET": 提议见面归还
  - "AGREE": 同意对方的提议
- "content": 具体的消息内容（中文）

## ⚠️ 重要规则（必须遵守）
1. **绝对禁止编造信息**：你只知道上面"物品信息"中给出的内容，不要编造型号、材质、尺寸等未提供的细节
2. 如果对方问你不知道的细节，诚实回答"抱歉，我的描述中没有提到这个，我只知道它是XXX"
3. 根据你持有的物品信息诚实回答问题
4. 如果对方提议见面且之前的验证通过，就同意
5. 如果对方描述的物品与你持有的物品特征不符，使用 REJECT 动作
6. 保持礼貌友好的语气
"""


# --- Agent Definitions ---

class BaseAgent(ABC):
    """
    智能体基类 (Base Agent Class)
    
    定义了所有智能体必须遵循的"感知-决策-执行" (Perception-Decision-Action) 循环接口。
    """
    def __init__(self, name: str, role: str, llm: LLMInterface, item_knowledge: Item):
        self.name = name
        self.role = role
        self.llm = llm
        self.item_knowledge = item_knowledge
        self.memory: List[Dict[str, str]] = []

    def perceive(self, message: Dict[str, str]):
        """
        感知层 (Perception Layer)
        接收来自环境的输入数据，更新智能体的内部状态（记忆）。
        """
        if message:
            self.memory.append(message)
            print(f"[{self.name}] Perceived message from {message.get('sender')}: {message.get('content')}")

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """子类实现：构建系统提示词"""
        pass

    def decide(self) -> Dict[str, str]:
        """
        决策层 (Decision Layer)
        基于记忆和目标，利用 LLM 进行推理，决定下一步动作。
        """
        system_prompt = self._build_system_prompt()
        
        # 构建对话历史
        if self.memory:
            history_str = "\n".join([f"{m['sender']}: {m['content']}" for m in self.memory])
            user_prompt = f"对话历史:\n{history_str}\n\n请根据对话历史决定你的下一步行动，返回 JSON 格式的响应。"
        else:
            user_prompt = "这是协商的开始，请发起第一个问题来验证物品信息，返回 JSON 格式的响应。"

        decision = self.llm.generate_response(system_prompt, user_prompt)
        print(f"[{self.name}] Decided action: {decision.get('action')}")
        return decision

    def execute(self, decision: Dict[str, str]) -> Dict[str, str]:
        """
        执行层 (Execution Layer)
        将决策结果转化为消息，并更新记忆。
        """
        action = decision.get("action")
        content = decision.get("content")
        
        outgoing_message = {
            "sender": self.role,
            "content": content,
            "action_type": action
        }
        
        self.memory.append(outgoing_message)
        return outgoing_message


class SeekerAgent(BaseAgent):
    """失主智能体 - 代表丢失物品的人"""
    
    def __init__(self, name: str, llm: LLMInterface, item_knowledge: Item):
        super().__init__(name, "Seeker", llm, item_knowledge)

    def _build_system_prompt(self) -> str:
        return build_seeker_system_prompt(self.item_knowledge)


class FinderAgent(BaseAgent):
    """拾主智能体 - 代表捡到物品的人"""
    
    def __init__(self, name: str, llm: LLMInterface, item_knowledge: Item):
        super().__init__(name, "Finder", llm, item_knowledge)

    def _build_system_prompt(self) -> str:
        return build_finder_system_prompt(self.item_knowledge)


# --- LLM 工厂函数 ---

def create_llm(use_mock: bool = False) -> LLMInterface:
    """
    创建 LLM 实例
    
    Args:
        use_mock: 是否使用 MockLLM（用于测试或无 API Key 时）
    
    Returns:
        LLMInterface 实例
    """
    if use_mock:
        print("[LLM Factory] Using MockLLM")
        return MockLLM()
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        print("[LLM Factory] Using DeepSeekLLM")
        return DeepSeekLLM(api_key=api_key)
    else:
        print("[LLM Factory] No API Key found, falling back to MockLLM")
        return MockLLM()
