from flask_sqlalchemy import SQLAlchemy  # 导入Flask-SQLAlchemy扩展，用于ORM数据库操作
from flask_login import UserMixin  # 导入UserMixin类，为User模型提供登录管理所需的方法（如is_authenticated、get_id等）
from datetime import datetime  # 导入datetime类，用于处理日期和时间
import pytz  # 导入pytz时区库，用于处理不同时区的时间转换

db = SQLAlchemy()  # 创建SQLAlchemy数据库实例，后续在app.py中通过db.init_app(app)绑定到Flask应用


def get_now():
    """获取当前上海时间"""  # 函数文档字符串
    return datetime.now(pytz.timezone('Asia/Shanghai'))  # 返回带上海时区信息的当前时间，确保所有时间记录统一使用中国标准时间


class User(UserMixin, db.Model):  # 定义用户模型，继承UserMixin（提供登录相关方法）和db.Model（SQLAlchemy基类）
    __tablename__ = 'users'  # 指定数据库表名为users

    id = db.Column(db.Integer, primary_key=True)  # 用户ID，整数类型，主键，自动递增
    username = db.Column(db.String(80), unique=True, nullable=False)  # 用户名，最大80字符，唯一不可重复，不能为空
    password_hash = db.Column(db.String(200), nullable=False)  # 密码哈希值，最大200字符，不能为空（存储加密后的密码，不存明文）
    email = db.Column(db.String(120), unique=True, nullable=False)  # 邮箱，最大120字符，唯一不可重复，不能为空
    role = db.Column(db.String(20), default='user')  # 用户角色，默认值为'user'（普通用户），可选'admin'（管理员）
    status = db.Column(db.String(20), default='active')  # 账户状态，默认'active'（正常），可选'disabled'（禁用）
    created_at = db.Column(db.DateTime, default=get_now)  # 注册时间，默认值为创建记录时的上海时间

    # 爬取次数系统
    crawl_quota = db.Column(db.Integer, default=0)  # 剩余爬取次数，默认0次（通过观看广告可增加）
    last_ad_watch = db.Column(db.DateTime)  # 上次观看广告的时间，用于计算30秒冷却期

    crawl_requests = db.relationship('CrawlRequest', foreign_keys='CrawlRequest.user_id',
                                     backref='user', lazy=True)  # 建立与CrawlRequest的关系：一个用户可提交多个爬取请求，通过user_id外键关联，backref='user'表示在CrawlRequest中可通过request.user访问提交者，lazy=True表示延迟加载


class CrawlRequest(db.Model):  # 定义爬取请求模型，记录用户提交的爬取申请
    __tablename__ = 'crawl_requests'  # 指定数据库表名为crawl_requests

    id = db.Column(db.Integer, primary_key=True)  # 请求ID，整数类型，主键，自动递增
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 申请人ID，外键关联users表的id字段，不能为空
    keyword = db.Column(db.String(100), nullable=False)  # 爬取关键词，最大100字符，不能为空
    status = db.Column(db.String(20), default='pending')  # 请求状态，默认'pending'（待审核），可选'completed'（已完成）、'rejected'（已拒绝）
    created_at = db.Column(db.DateTime, default=get_now)  # 提交时间，默认当前上海时间
    processed_at = db.Column(db.DateTime)  # 处理时间，管理员审核时记录
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # 处理人ID，外键关联users表的id字段（记录哪个管理员处理的）
    result_count = db.Column(db.Integer, default=0)  # 爬取结果数量，默认0
    remark = db.Column(db.Text)  # 备注信息，文本类型（可存储较长内容）

    processor = db.relationship('User', foreign_keys=[processed_by], backref='processed_requests')  # 建立与User的关系：通过processed_by外键关联，backref='processed_requests'表示在用户对象中可通过user.processed_requests查看该管理员处理的所有请求


class Product(db.Model):  # 定义商品模型，存储爬取到的商品信息
    __tablename__ = 'products'  # 指定数据库表名为products

    id = db.Column(db.Integer, primary_key=True)  # 商品ID，整数类型，主键，自动递增
    keyword = db.Column(db.String(100), nullable=False, index=True)  # 搜索关键词，最大100字符，不能为空，建立索引加速查询
    title = db.Column(db.String(500), nullable=False)  # 商品标题，最大500字符，不能为空
    price_raw = db.Column(db.String(100), nullable=False)  # 原始价格文本（如"¥1999.00"），最大100字符，不能为空
    price_value = db.Column(db.Float)  # 提取的纯数字价格（如1999.0），浮点数类型，可为空（解析失败时）
    platform = db.Column(db.String(100), nullable=False)  # 来源平台名称（如"京东"、"天猫"），最大100字符，不能为空
    publish_date = db.Column(db.DateTime, index=True)  # 商品发布时间，建立索引加速按时间排序查询
    url = db.Column(db.String(500), nullable=False)  # 商品链接地址，最大500字符，不能为空
    image_url = db.Column(db.String(500))  # 商品图片地址，最大500字符，可为空
    source_site = db.Column(db.String(50))  # 数据来源网站标识（如"manmanbuy"、"smzdm"），最大50字符
    created_at = db.Column(db.DateTime, default=get_now)  # 记录入库时间，默认当前上海时间

    __table_args__ = (  # 定义复合索引，优化常见查询性能
        db.Index('idx_keyword_platform', 'keyword', 'platform'),  # 联合索引：关键词+平台，加速按关键词和平台筛选的查询
        db.Index('idx_price_value', 'price_value'),  # 单列索引：价格，加速按价格排序和范围查询
    )