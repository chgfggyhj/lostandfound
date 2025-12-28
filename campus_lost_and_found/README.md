# 🎓 校园失物招领系统 V2.0

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)
![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

**基于多智能体协商的智能失物招领平台**

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [系统架构](#-系统架构) • [API 文档](#-api-文档) • [部署指南](#-部署指南)

</div>

---

## ✨ 功能特性

### 🤖 智能匹配与协商
- **AI 智能体自动协商**：SeekerBot（失主代理）和 FinderBot（拾主代理）自动进行物品验证对话
- **多轮对话验证**：通过特征交叉验证确保物品归属
- **智能匹配算法**：基于文本相似度自动匹配丢失物品和拾取物品

### 📦 物品管理
- **发布物品**：支持发布丢失物品或拾取物品
- **图片上传**：支持物品图片上传，辅助识别
- **物品编辑**：支持修改物品信息
- **物品删除**：支持删除已发布的物品

### 🤝 归还流程
- **约定管理**：拾主发起约定，失主审批
- **回绝机制**：失主可回绝约定并说明理由
- **归还确认**：双方线下确认归还状态
- **状态追踪**：完整的协商和归还状态追踪

### 🔔 消息通知
- **实时通知**：匹配成功、协商进度、约定状态等实时推送
- **未读标记**：未读消息高亮显示

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- MySQL 8.0（或使用 SQLite 本地开发）
- Node.js（可选，用于前端开发）

### 方式一：本地开发

```bash
# 1. 克隆项目
git clone <repository-url>
cd campus_lost_and_found

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
copy .env.example .env
# 编辑 .env 文件，填入必要配置

# 5. 启动服务
uvicorn main:app --reload
```

### 方式二：Docker 部署（本地）

```bash
# 1. 配置环境变量
cp .env.docker .env
# 编辑 .env 文件，填入密码和 API 密钥

# 2. 启动服务
docker compose up -d --build

# 3. 查看日志
docker compose logs -f
```

### 方式三：Docker 部署到服务器

```bash
# 1. SSH 登录服务器
ssh user@your-server-ip

# 2. 创建目录
mkdir -p /opt/lost-and-found && cd /opt/lost-and-found

# 3. 下载配置文件
curl -O https://raw.githubusercontent.com/chgfggyhj/lostandfound/main/campus_lost_and_found/docker-compose.yml

# 4. 创建并编辑 .env 文件
cat > .env << 'EOF'
MYSQL_ROOT_PASSWORD=your_root_password
MYSQL_USER=lost_found_user
MYSQL_PASSWORD=your_app_password
MYSQL_DATABASE=lost_and_found
SECRET_KEY=your-secret-key
DEEPSEEK_API_KEY=your_api_key
DASHSCOPE_API_KEY=your_api_key
EOF

# 5. 启动服务
docker compose up -d

# 6. 查看状态
docker compose ps
docker compose logs -f web
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 🌐 Web 应用 | http://localhost:8000/static/index.html |
| 📖 API 文档 | http://localhost:8000/docs |
| ❤️ 健康检查 | http://localhost:8000/health |

---

## 📐 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (HTML/JS)                        │
├─────────────────────────────────────────────────────────────┤
│                     FastAPI 后端服务                         │
├───────────────┬───────────────┬───────────────┬─────────────┤
│   用户认证    │   物品管理    │   协商管理    │   通知服务   │
├───────────────┴───────────────┴───────────────┴─────────────┤
│                    多智能体协商引擎                          │
│              ┌─────────────┬─────────────┐                  │
│              │ SeekerBot   │ FinderBot   │                  │
│              │ (失主代理)  │ (拾主代理)  │                  │
│              └─────────────┴─────────────┘                  │
├─────────────────────────────────────────────────────────────┤
│                      LLM 接口层                              │
│         (DeepSeek / DashScope / MockLLM)                    │
├─────────────────────────────────────────────────────────────┤
│                   MySQL / SQLite                             │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | HTML5, CSS3, JavaScript (原生) |
| 后端 | FastAPI, Uvicorn |
| 数据库 | MySQL 8.0 / SQLite |
| ORM | SQLAlchemy 2.0 |
| AI 模型 | DeepSeek API / DashScope (通义千问) |
| 认证 | JWT (python-jose) |
| 部署 | Docker, Docker Compose |

---

## 🤖 智能体协商流程

```
发布物品                     系统匹配                    智能协商
┌──────┐                   ┌────────┐                 ┌─────────────┐
│失主  │──发布丢失物品──▶│        │                 │ SeekerBot   │
│      │                   │ 匹配   │──创建会话──▶  │     🗣️      │
│拾主  │──发布拾取物品──▶│ 引擎   │                 │ FinderBot   │
└──────┘                   └────────┘                 └─────────────┘
                                                            │
                              ◀────── 多轮对话验证 ────────┘
                                                            │
                                                      ┌─────▼─────┐
                                                      │ 验证成功? │
                                                      └─────┬─────┘
                                            ┌───────────────┼───────────────┐
                                            ▼               ▼               ▼
                                     [匹配成功]      [需人工确认]      [匹配失败]
                                            │
                                            ▼
                                  ┌─────────────────┐
                                  │   约定归还流程   │
                                  │ 拾主发起 → 失主确认│
                                  │ → 线下交接 → 确认归还│
                                  └─────────────────┘
```

---

## 📖 API 文档

### 主要接口

#### 用户认证
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/register` | 用户注册 |
| POST | `/login` | 用户登录 |
| GET | `/users/me` | 获取当前用户信息 |

#### 物品管理
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/items/` | 发布物品 |
| GET | `/items/` | 获取物品列表 |
| GET | `/items/{id}` | 获取物品详情 |
| PATCH | `/items/{id}` | 编辑物品 |
| DELETE | `/items/{id}` | 删除物品 |

#### 协商管理
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/find-matches` | 触发匹配 |
| GET | `/negotiations/` | 获取协商列表 |
| GET | `/negotiations/{id}` | 获取协商详情 |
| POST | `/negotiations/{id}/confirm` | 确认物品 |
| POST | `/negotiations/{id}/schedule` | 发起约定 |
| POST | `/negotiations/{id}/schedule/approve` | 同意约定 |
| POST | `/negotiations/{id}/schedule/reject` | 回绝约定 |
| POST | `/negotiations/{id}/confirm-return` | 确认归还 |

#### 通知
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/notifications/` | 获取通知列表 |
| POST | `/notifications/{id}/read` | 标记已读 |

> 💡 完整 API 文档请访问：http://localhost:8000/docs

---

## 🐳 部署指南

### Docker Compose 部署

```bash
# 1. 配置环境变量
cp .env.docker .env
vim .env  # 修改密码和 API 密钥

# 2. 启动所有服务
docker-compose up -d --build

# 3. 查看服务状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f web
```

### 启动 phpMyAdmin（可选）

```bash
docker-compose --profile admin up -d phpmyadmin
# 访问: http://localhost:8080
```

### 数据备份

```bash
# 导出
docker exec lost_and_found_mysql mysqldump -u root -p lost_and_found > backup.sql

# 恢复
docker exec -i lost_and_found_mysql mysql -u root -p lost_and_found < backup.sql
```

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `USE_SQLITE` | 是否使用 SQLite | `true` |
| `DATABASE_URL` | MySQL 连接地址 | - |
| `SECRET_KEY` | JWT 密钥 | 随机生成 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | - |
| `DASHSCOPE_API_KEY` | 阿里云 API 密钥 | - |

### LLM 配置优先级

1. **DeepSeek** - 如果配置了 `DEEPSEEK_API_KEY`
2. **DashScope** - 如果配置了 `DASHSCOPE_API_KEY`
3. **MockLLM** - 兜底方案，规则模拟

---

## 📁 项目结构

```
campus_lost_and_found/
├── main.py              # FastAPI 应用入口
├── models.py            # 数据库模型
├── auth.py              # 用户认证
├── agents.py            # AI 智能体
├── services.py          # 业务服务
├── config.py            # 配置管理
├── image_service.py     # 图片处理服务
│
├── static/              # 前端静态文件
│   ├── index.html       # 主页面
│   ├── app.js           # 前端逻辑
│   └── styles.css       # 样式
│
├── uploads/             # 上传文件目录
│
├── Dockerfile           # Docker 镜像配置
├── docker-compose.yml   # Docker 编排配置
├── requirements.txt     # Python 依赖
├── .env.example         # 环境变量模板
└── README.md            # 项目文档
```

---

## 🔧 开发指南

### 本地调试

```bash
# 启动开发服务器（自动重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 数据库迁移

```bash
# 自动创建表结构
python -c "from models import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 添加新字段

```sql
-- 示例：给表添加新列
ALTER TABLE return_schedules ADD COLUMN new_field VARCHAR(100);
```

---

## 📝 更新日志

### V2.0 (2024-12)
- ✅ 多智能体协商系统
- ✅ 完整的归还约定流程
- ✅ 消息通知系统
- ✅ Docker 部署支持
- ✅ 物品编辑和删除功能

### V1.0 (初始版本)
- 基础的物品发布和展示
- 简单的匹配功能

---

## 📄 许可证

MIT License

---

<div align="center">

**校园失物招领系统 V2.0** | Powered by AI Agents

</div>
