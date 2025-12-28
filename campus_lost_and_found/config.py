"""
配置文件
从环境变量或 .env 文件加载配置
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== 数据库配置 ====================
# MySQL 连接字符串格式: mysql+pymysql://用户名:密码@主机:端口/数据库名
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "lost_and_found")

DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# SQLite 备用（如果 MySQL 未配置）
USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() == "true"
SQLITE_URL = "sqlite:///./lost_and_found.db"

# ==================== JWT 配置 ====================
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# ==================== AI API 配置 ====================
# DeepSeek (对话)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 阿里云 DashScope (图片识别 Qwen-VL)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ==================== 文件上传配置 ====================
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

# 确保上传目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==================== 协商配置 ====================
MAX_NEGOTIATION_ROUNDS = 20  # 最大协商轮数
MIN_MATCH_SCORE = 0.3  # 最低匹配度阈值
