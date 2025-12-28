-- ==========================================
-- 校园失物招领系统 V2.0 - 数据库初始化脚本
-- ==========================================

-- 设置字符集
ALTER DATABASE lost_and_found CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 表结构会由 SQLAlchemy 自动创建，这里只做一些初始化设置

-- 如果需要修改已存在的表结构，可以在这里添加 ALTER 语句
-- 例如扩展 status 列长度
-- ALTER TABLE negotiation_sessions MODIFY COLUMN status VARCHAR(30);
-- ALTER TABLE return_schedules ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'PENDING';
-- ALTER TABLE return_schedules ADD COLUMN IF NOT EXISTS reject_reason TEXT;
