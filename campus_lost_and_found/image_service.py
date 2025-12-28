"""
图片识别服务
使用阿里云 Qwen-VL 进行图片识别
"""
import os
import base64
import uuid
from typing import Optional
from datetime import datetime
from PIL import Image

from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE


class ImageService:
    """图片处理与识别服务"""
    
    def __init__(self):
        self.api_key = DASHSCOPE_API_KEY
        self.base_url = DASHSCOPE_BASE_URL
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                import httpx
                # 创建不带代理的 http client
                http_client = httpx.Client(
                    timeout=httpx.Timeout(60.0, connect=10.0)
                )
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    http_client=http_client
                )
                print("[ImageService] Qwen-VL API 已初始化")
            except Exception as e:
                print(f"[ImageService] 初始化失败: {e}")
    
    def _get_file_extension(self, filename: str) -> str:
        """获取文件扩展名"""
        return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    def _is_allowed_file(self, filename: str) -> bool:
        """检查文件类型是否允许"""
        return self._get_file_extension(filename) in ALLOWED_EXTENSIONS
    
    def _generate_filename(self, original_filename: str) -> str:
        """生成唯一文件名"""
        ext = self._get_file_extension(original_filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{timestamp}_{unique_id}.{ext}"
    
    def save_image(self, file_content: bytes, original_filename: str) -> Optional[str]:
        """
        保存上传的图片
        
        Returns:
            保存的文件路径（相对路径），失败返回 None
        """
        if not self._is_allowed_file(original_filename):
            raise ValueError(f"不支持的文件类型，仅支持: {', '.join(ALLOWED_EXTENSIONS)}")
        
        if len(file_content) > MAX_UPLOAD_SIZE:
            raise ValueError(f"文件过大，最大允许 {MAX_UPLOAD_SIZE // 1024 // 1024}MB")
        
        # 生成文件名和路径
        new_filename = self._generate_filename(original_filename)
        file_path = os.path.join(UPLOAD_DIR, new_filename)
        
        # 保存文件
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 返回相对路径（用于前端访问）
        return f"uploads/{new_filename}"
    
    def analyze_image(self, image_path: str, item_type: str = "物品") -> str:
        """
        使用 Qwen-VL 分析图片，返回物品描述
        
        Args:
            image_path: 图片路径（可以是相对路径或绝对路径）
            item_type: 物品类型描述
        
        Returns:
            AI 生成的物品描述
        """
        if not self.client:
            return self._mock_analyze(image_path)
        
        try:
            # 如果是相对路径，转换为绝对路径
            if not os.path.isabs(image_path):
                abs_path = os.path.join(os.path.dirname(UPLOAD_DIR), image_path)
            else:
                abs_path = image_path
            
            # 读取图片并转为 base64
            with open(abs_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
            
            # 获取图片格式
            ext = self._get_file_extension(abs_path)
            mime_type = f"image/{ext}" if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "image/jpeg"
            
            # 调用 Qwen-VL
            response = self.client.chat.completions.create(
                model="qwen-vl-plus",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": f"""请详细描述这个{item_type}的特征，用于失物招领匹配。
请包含以下信息（如果可见）：
1. 颜色
2. 品牌/型号
3. 材质
4. 大小/尺寸
5. 独特标识（如划痕、贴纸、刻字等）
6. 其他显著特征

请用简洁的中文描述，不要分点，用连贯的句子。"""
                        },
                        {
                            "type": "image_url", 
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"}
                        }
                    ]
                }],
                max_tokens=500
            )
            
            description = response.choices[0].message.content
            print(f"[ImageService] AI 识别结果: {description[:100]}...")
            return description
            
        except Exception as e:
            print(f"[ImageService] 识别失败: {e}")
            return self._mock_analyze(image_path)
    
    def _mock_analyze(self, image_path: str) -> str:
        """模拟图片识别（API 不可用时）"""
        return "（图片识别服务暂不可用，请手动填写物品描述）"
    
    def get_image_thumbnail(self, image_path: str, size: tuple = (200, 200)) -> Optional[bytes]:
        """生成缩略图"""
        try:
            if not os.path.isabs(image_path):
                abs_path = os.path.join(os.path.dirname(UPLOAD_DIR), image_path)
            else:
                abs_path = image_path
            
            with Image.open(abs_path) as img:
                img.thumbnail(size)
                from io import BytesIO
                buffer = BytesIO()
                img.save(buffer, format='JPEG')
                return buffer.getvalue()
        except Exception as e:
            print(f"[ImageService] 缩略图生成失败: {e}")
            return None


# 单例
image_service = ImageService()
