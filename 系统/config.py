import os  # 导入操作系统模块，用于读取环境变量和文件路径
from dotenv import load_dotenv  # 从python-dotenv库导入load_dotenv函数，用于加载.env配置文件

load_dotenv()  # 加载当前目录下的.env文件（如果存在），将文件中的环境变量导入到程序中

class Config:  # 定义Config配置类，Flask应用将引用此类的属性作为配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'  # 设置应用密钥：优先从环境变量读取SECRET_KEY，如果不存在则使用默认的开发密钥（用于会话加密、表单验证等安全功能）
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:root@localhost/price_comparison?charset=utf8mb4'  # 设置数据库连接地址：优先从环境变量读取DATABASE_URL，如果不存在则使用默认的本地MySQL连接（用户名root，密码root，数据库名price_comparison，使用utf8mb4字符集支持中文和表情符号）
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # 关闭SQLAlchemy的事件追踪功能，减少内存开销，避免不必要的警告信息
    ITEMS_PER_PAGE = 20  # 设置分页参数，每页默认显示20条记录（用于商品列表、用户列表等分页展示）