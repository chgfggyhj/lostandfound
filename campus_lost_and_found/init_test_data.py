"""
测试数据初始化脚本
运行方式: python init_test_data.py
"""

from models import Base, engine, User, Item, ItemType, ItemStatus
from sqlalchemy.orm import Session

# 创建表
Base.metadata.create_all(bind=engine)

# 测试数据
test_users = [
    {"name": "张三", "contact_info": "13800001111"},
    {"name": "李四", "contact_info": "13900002222"},
    {"name": "王五", "contact_info": "15000003333"},
    {"name": "赵六", "contact_info": "18600004444"},
    {"name": "钱七", "contact_info": "13700005555"},
]

test_items = [
    # 张三丢失的物品
    {"title": "黑色索尼耳机", "description": "在食堂丢的，黑色索尼(Sony)无线耳机，型号WH-1000XM4", "type": ItemType.LOST, "location": "食堂一楼", "owner_idx": 0},
    
    # 李四捡到的物品
    {"title": "黑色无线耳机", "description": "在食堂二楼捡到的黑色无线耳机，看起来像索尼的", "type": ItemType.FOUND, "location": "食堂二楼", "owner_idx": 1},
    
    # 王五丢失的物品
    {"title": "蓝色小米手环", "description": "小米手环7，蓝色表带，在图书馆丢的", "type": ItemType.LOST, "location": "图书馆", "owner_idx": 2},
    
    # 赵六捡到的物品
    {"title": "运动手环", "description": "在图书馆三楼自习室捡到一个蓝色的运动手环", "type": ItemType.FOUND, "location": "图书馆三楼", "owner_idx": 3},
    
    # 钱七丢失的物品
    {"title": "黑色皮革钱包", "description": "黑色牛皮钱包，里面有身份证和几张银行卡，在教学楼丢的", "type": ItemType.LOST, "location": "教学楼A栋", "owner_idx": 4},
    
    # 李四又捡到一个物品
    {"title": "棕色钱包", "description": "在教学楼走廊捡到的棕色钱包，里面有一些卡", "type": ItemType.FOUND, "location": "教学楼B栋", "owner_idx": 1},
    
    # 张三丢失的另一个物品
    {"title": "苹果充电器", "description": "白色苹果20W充电头，在实验室丢的", "type": ItemType.LOST, "location": "实验楼", "owner_idx": 0},
    
    # 王五捡到的物品
    {"title": "白色充电器", "description": "在实验楼一楼捡到一个白色的苹果充电器", "type": ItemType.FOUND, "location": "实验楼一楼", "owner_idx": 2},
]

def init_data():
    db = Session(bind=engine)
    
    try:
        # 检查是否已有数据
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"数据库中已有 {existing_users} 个用户，跳过初始化")
            return
        
        # 创建用户
        users = []
        for user_data in test_users:
            user = User(**user_data)
            db.add(user)
            users.append(user)
        
        db.flush()  # 获取用户ID
        
        # 创建物品
        for item_data in test_items:
            owner_idx = item_data.pop("owner_idx")
            item = Item(**item_data, owner_id=users[owner_idx].id)
            db.add(item)
        
        db.commit()
        
        print("✅ 测试数据初始化成功！")
        print(f"   - 创建了 {len(users)} 个用户")
        print(f"   - 创建了 {len(test_items)} 个物品")
        print()
        print("📋 物品列表:")
        for i, item in enumerate(test_items, 1):
            type_emoji = "😢" if item["type"] == ItemType.LOST else "🎉"
            print(f"   {i}. {type_emoji} {item['title']} - {item['location']}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 初始化失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_data()
