# 电商比价工具

基于 Python 爬虫与 Flask Web 的多平台商品比价系统，支持多电商平台数据采集、价格趋势分析和后台管理。

---

## 项目简介

本系统是一个全栈 Web 应用，用户可以通过关键词提交爬取请求，系统自动采集淘宝、京东等多个电商平台的商品数据，进行价格对比和趋势分析。系统采用积分激励体系（观看广告获取爬取次数），支持用户注册登录、爬取请求管理、价格数据可视化等功能。

## 技术栈

- **后端框架**: Python Flask + SQLAlchemy
- **前端**: Bootstrap 5 + jQuery + ECharts
- **数据库**: MySQL（phpstudy_pro 环境）
- **爬虫**: Requests + BeautifulSoup
- **开发工具**: Navicat Premium 17、phpstudy_pro、PyCharm
- **其他**: Flask-Login（用户认证）、Flask-WTF（表单验证）

## 功能特性

### 用户端
- 用户注册 / 登录 / 个人信息管理
- 提交商品爬取请求（输入关键词）
- 查看爬取结果与多平台价格对比
- 价格趋势可视化图表
- 观看广告获取爬取次数（积分激励体系）
- 管理自己的爬取请求记录

### 管理端
- 用户管理（查看、禁用 / 启用账户）
- 爬取请求审核与分配
- 查看用户提交的爬取详情
- 数据统计与分析看板

## 项目结构

```
电商比价工具/
  price_comparison.sql      MySQL 数据库结构 + 数据导出
  settings.local.json       本地运行配置
  .gitignore                Git 忽略文件
  README.md                 项目说明文档
  系统/
    app.py                  Flask 主应用（路由、视图函数）
    config.py               配置（数据库连接、密钥等）
    models.py               数据模型（User、CrawlRequest 等）
    static/                 静态资源
      css/                  样式文件
      js/                   JavaScript 文件
      ads/                  广告视频素材
    templates/              HTML 模板
      admin/                管理后台页面
      user/                 用户端页面
```

## 快速开始

### 环境要求

- Python 3.8+
- MySQL（推荐使用 phpstudy_pro 集成环境）
- Navicat Premium 17（可选，用于数据库管理）

### 安装步骤

**1. 导入数据库**

打开 phpstudy_pro 启动 MySQL 服务，使用 Navicat Premium 17 连接到本地 MySQL：

连接信息（配置文件中默认值）:
- 主机: localhost
- 端口: 3306
- 用户名: root
- 密码: root

新建数据库 `price_comparison`，导入项目中的 `price_comparison.sql`:
```
mysql -u root -p price_comparison < price_comparison.sql
```

**2. 配置虚拟环境**

```
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate    # Linux/Mac
```

**3. 安装依赖**

```
pip install flask flask-sqlalchemy flask-login flask-wtf
pip install requests beautifulsoup4
pip install pymysql python-dotenv
pip install pytz
```

**4. 修改数据库配置**

编辑 `系统/config.py`，根据实际环境修改数据库连接信息。

**5. 启动应用**

```
cd 系统
python app.py
```

访问 `http://localhost:5000` 即可使用。

## 使用指南

### 用户流程

1. 注册账号 -> 登录系统
2. 在个人中心观看广告获取爬取次数（每次观看获得一次爬取额度）
3. 提交爬取请求（输入商品关键词）
4. 等待管理员审核通过后，系统自动爬取多平台数据
5. 在商品列表中查看价格对比和趋势图

### 管理员流程

1. 使用管理员账号登录（需在数据库中手动设置 role='admin'）
2. 在管理后台查看爬取请求列表，审核并处理用户提交的请求
3. 管理用户账号（启用 / 禁用）
4. 查看数据统计看板

## 数据库说明

### 主要数据表

- **users** - 用户信息（用户名、密码哈希、邮箱、角色、爬取配额）
- **crawl_requests** - 爬取请求记录（关键词、提交人、状态、时间）
- **products** - 爬取的商品数据（名称、价格、平台、链接等）
- **prices** - 价格历史记录（用于价格趋势分析）

## 激励体系说明

系统设计了"观看广告获取爬取次数"的激励模型：

- 用户观看 1 次广告 = 获得 1 次爬取配额
- 每次爬取消耗 1 次配额
- 广告观看有 30 秒冷却时间，防止刷取

## 注意事项

- 爬虫功能依赖目标电商平台的公开接口或页面结构，如遇反爬机制需相应调整
- 首次运行请确保 phpstudy_pro 中的 MySQL 服务已启动
- 建议使用 python-dotenv 管理敏感配置（数据库密码、SECRET_KEY 等）

## License

MIT
