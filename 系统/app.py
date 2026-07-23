from flask import Flask, render_template, request, jsonify, redirect, url_for, flash  # 导入Flask框架核心组件：应用实例、模板渲染、请求处理、JSON响应、页面重定向、URL生成、闪存消息
from flask_login import LoginManager, login_user, logout_user, login_required, current_user  # 导入用户登录管理：登录管理器、登录/登出函数、登录验证装饰器、当前用户对象
from werkzeug.security import generate_password_hash, check_password_hash  # 导入密码安全工具：生成密码哈希、验证密码哈希
from models import db, User, CrawlRequest, Product  # 从models模块导入数据库实例和三个数据模型
from config import Config  # 从config模块导入配置类
from datetime import datetime, timedelta  # 导入日期时间处理类
import requests  # 导入HTTP请求库，用于发送网络请求爬取网页
from bs4 import BeautifulSoup  # 导入HTML解析库，用于从网页中提取数据
import re  # 导入正则表达式模块，用于文本模式匹配
from sqlalchemy import func  # 导入SQLAlchemy聚合函数，用于数据库统计查询
import pytz  # 导入时区处理库，处理不同时区的时间转换

app = Flask(__name__)  # 创建Flask应用实例，__name__表示当前模块名
app.config.from_object(Config)  # 从Config类加载应用配置（数据库连接、密钥等）
db.init_app(app)  # 初始化数据库，将数据库绑定到当前Flask应用

login_manager = LoginManager()  # 创建登录管理器实例
login_manager.init_app(app)  # 将登录管理器绑定到Flask应用
login_manager.login_view = 'login'  # 设置未登录用户被拦截时跳转的登录页面路由名


@login_manager.user_loader  # 注册用户加载回调函数，Flask-Login用此函数根据ID加载用户
def load_user(user_id):
    return User.query.get(int(user_id))  # 根据用户ID从数据库查询并返回用户对象，ID转为整数防止类型错误


# ==================== 工具函数 ====================

def get_now():
    """获取当前上海时间"""  # 函数文档字符串，说明函数用途
    return datetime.now(pytz.timezone('Asia/Shanghai'))  # 返回带上海时区信息的当前时间，确保时间一致性


def extract_price(price_text):
    """提取价格数值"""  # 从价格文本中提取纯数字价格
    if not price_text:  # 如果输入为空或None
        return None  # 返回空值
    match = re.search(r'(\d+(?:\.\d+)?)', price_text)  # 用正则表达式匹配数字（支持小数点），\d+匹配整数，(?:\.\d+)?匹配可选的小数部分
    return float(match.group(1)) if match else None  # 如果匹配成功，将匹配到的第一个分组转为浮点数返回；否则返回None


def parse_date(date_str):
    """解析日期字符串"""  # 将网页上的日期字符串转为标准datetime对象
    if not date_str:  # 如果日期字符串为空
        return get_now()  # 返回当前时间作为默认值
    match = re.search(r'(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', date_str)  # 正则匹配"月-日 时:分"格式，如"05-06 18:00"
    if match:  # 如果匹配成功
        month, day, hour, minute = map(int, match.groups())  # 将四个匹配分组转为整数
        year = get_now().year  # 获取当前年份
        if month > get_now().month:  # 如果网页日期月份大于当前月份（说明是去年的数据）
            year -= 1  # 年份减1，处理跨年情况
        return datetime(year, month, day, hour, minute, tzinfo=pytz.timezone('Asia/Shanghai'))  # 构建带上海时区的datetime对象并返回
    return get_now()  # 匹配失败时返回当前时间


# ==================== 爬虫模块 ====================

HEADERS = {  # 定义HTTP请求头，模拟浏览器访问防止被网站拦截
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'  # 伪装成Chrome浏览器的User-Agent
}


def crawl_manmanbuy(keyword, max_pages=5):
    """从慢慢买爬取商品"""  # 慢慢买网站爬虫函数，默认爬3页
    products = []  # 初始化空列表，存储爬取到的商品
    for page in range(1, max_pages + 1):  # 循环遍历每一页，从第1页到第max_pages页
        try:  # 异常捕获，防止某页爬取失败导致整个函数崩溃
            params = {'c': 'discount', 'keyword': keyword, 'pageId': str(page)}  # 构建请求参数：分类为discount，传入关键词和页码
            resp = requests.get('https://s.manmanbuy.com/pc/search/result', params=params, headers=HEADERS, timeout=10)  # 发送GET请求到慢慢买搜索接口，传入参数、请求头和10秒超时设置
            soup = BeautifulSoup(resp.text, 'html.parser')  # 用BeautifulSoup解析返回的HTML文本

            for item in soup.find_all('div', class_='DiscountItemPC_box__m9G3M'):  # 查找所有商品卡片元素
                try:  # 对每个商品单独捕获异常，防止一个商品解析失败影响其他商品
                    title_elem = item.find('div', class_='DiscountItemPC_itemTitle__hlI5m')  # 查找商品标题元素
                    price_elem = item.find('div', class_='DiscountItemPC_itemSubTitle__rWgWK')  # 查找商品价格元素
                    img_elem = item.find('div', class_='DiscountItemPC_itemCover__2hIIm')  # 查找商品图片元素
                    source_elem = item.find('span', class_='DiscountItemPC_itemMall__R8PlE')  # 查找来源平台元素
                    date_elem = item.find('span', class_='DiscountItemPC_itemTime__F_Ku_')  # 查找发布时间元素

                    title = title_elem.find('a')['title'] if title_elem else ''  # 从标题元素的a标签中提取title属性
                    price_text = price_elem.find('a').get_text() if price_elem else ''  # 从价格元素中提取文本内容

                    if title and price_text:  # 只有标题和价格都存在才保存该商品
                        products.append({  # 将商品信息以字典形式添加到列表
                            'keyword': keyword,  # 记录搜索关键词
                            'title': title,  # 商品标题
                            'price_raw': price_text.strip(),  # 原始价格文本，去除首尾空格
                            'price_value': extract_price(price_text),  # 提取的纯数字价格
                            'platform': source_elem.get_text().strip() if source_elem else '',  # 来源平台名称
                            'publish_date': parse_date(date_elem.get_text().strip()) if date_elem else get_now(),  # 发布时间，解析失败则用当前时间
                            'url': title_elem.find('a')['href'] if title_elem else '',  # 商品链接地址
                            'image_url': img_elem.find('img')['src'] if img_elem else '',  # 商品图片地址
                            'source_site': 'manmanbuy'  # 标记数据来源网站
                        })
                except Exception as e:  # 捕获单个商品解析异常
                    print(f"解析慢慢买商品出错: {e}")  # 打印错误信息到控制台，不影响其他商品
        except Exception as e:  # 捕获整页请求异常
            print(f"爬取慢慢买第{page}页出错: {e}")  # 打印错误，继续爬取下一页
    return products  # 返回所有爬取到的商品列表


def crawl_smzdm(keyword, max_pages=5):
    """从什么值得买爬取商品"""  # 什么值得买网站爬虫函数
    products = []  # 初始化商品列表
    for page in range(1, max_pages + 1):  # 遍历1到max_pages页
        try:  # 捕获页面级异常
            params = {'c': 'home', 's': keyword, 'v': 'b', 'mx_v': 'b', 'p': str(page)}  # 构建什么值得买的搜索参数
            resp = requests.get('https://search.smzdm.com/', params=params, headers=HEADERS, timeout=10)  # 发送搜索请求
            soup = BeautifulSoup(resp.text, 'html.parser')  # 解析HTML
            feed_list = soup.find('ul', id='feed-main-list')  # 查找商品列表容器
            if not feed_list:  # 如果没找到列表容器
                continue  # 跳过当前页，继续下一页

            for item in feed_list.find_all('li', {'data-cid': '1'}):  # 查找所有商品项，data-cid="1"表示商品类型
                try:  # 捕获单个商品异常
                    title_elem = item.find('h5', class_='feed-block-title')  # 查找标题元素
                    if not title_elem:  # 如果标题元素不存在
                        continue  # 跳过该商品
                    links = title_elem.find_all('a')  # 获取标题下的所有链接
                    title = links[0].get_text().strip() if links else ''  # 第一个链接是标题
                    price_text = links[1].get_text().strip() if len(links) > 1 else ''  # 第二个链接是价格

                    link_elem = item.find('div', class_='feed-link-btn-inner')  # 查找购买链接元素
                    img_elem = item.find('div', class_='z-feed-img')  # 查找图片元素
                    extras_elem = item.find('span', class_='feed-block-extras')  # 查找附加信息元素（包含平台和日期）

                    source, p_date = '', get_now()  # 初始化来源和日期
                    if extras_elem:  # 如果附加信息存在
                        source = extras_elem.find('span').get_text().strip() if extras_elem.find('span') else ''  # 提取平台名称
                        date_match = re.search(r'(\d{2}-\d{2}\s+\d{2}:\d{2})', extras_elem.get_text())  # 正则匹配日期
                        if date_match:  # 如果匹配到日期
                            p_date = parse_date(date_match.group(1))  # 解析日期字符串

                    if title and price_text:  # 标题和价格都存在才保存
                        img_url = ''
                        if img_elem and img_elem.find('img'):
                            img_url = 'https:' + img_elem.find('img')['src']
                        products.append({  # 添加商品信息
                            'keyword': keyword,  # 搜索关键词
                            'title': title,  # 商品标题
                            'price_raw': price_text,  # 原始价格文本
                            'price_value': extract_price(price_text),  # 提取的纯数字价格
                            'platform': source,  # 来源平台
                            'publish_date': p_date,  # 发布时间
                            'url': link_elem.find('a')['href'] if link_elem else '',  # 商品链接
                            'image_url': img_url,  # 图片链接
                            'source_site': 'smzdm'  # 标记数据来源
                        })
                except Exception as e:  # 单个商品解析异常
                    print(f"解析什么值得买商品出错: {e}")  # 打印错误
        except Exception as e:  # 页面请求异常
            print(f"爬取什么值得买第{page}页出错: {e}")  # 打印错误
    return products  # 返回商品列表


def save_products(products, keyword):
    """保存商品到数据库"""  # 将爬取的商品批量存入数据库
    Product.query.filter_by(keyword=keyword).delete()  # 先删除该关键词下的旧数据，避免重复
    for p in products:  # 遍历所有商品
        db.session.add(Product(**p))  # 用字典解包创建Product对象并添加到数据库会话
    db.session.commit()  # 提交事务，真正写入数据库
    return len(products)  # 返回保存的商品数量


# ==================== 认证路由 ====================

@app.route('/')  # 注册根路由，访问首页
def index():
    return render_template('index.html')  # 渲染并返回首页模板


@app.route('/login', methods=['GET', 'POST'])  # 注册登录路由，支持GET和POST请求
def login():
    if request.method == 'POST':  # 如果是POST请求（用户提交表单）
        user = User.query.filter_by(username=request.form.get('username')).first()  # 根据用户名查询用户
        if user and check_password_hash(user.password_hash, request.form.get('password')):  # 用户存在且密码正确
            if user.status == 'disabled':  # 检查账户是否被禁用
                flash('账户已被禁用', 'danger')  # 显示错误提示（红色）
                return redirect(url_for('login'))  # 重定向回登录页
            login_user(user)  # 执行登录，设置会话
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'user_dashboard'))  # 根据角色跳转到不同控制台
        flash('用户名或密码错误', 'danger')  # 登录失败提示
    return render_template('login.html')  # GET请求时渲染登录页面


@app.route('/register', methods=['GET', 'POST'])  # 注册注册路由
def register():
    if request.method == 'POST':  # 处理表单提交
        username = request.form.get('username')  # 获取用户名
        email = request.form.get('email')  # 获取邮箱
        if User.query.filter_by(username=username).first():  # 检查用户名是否已存在
            flash('用户名已存在', 'danger')  # 提示错误
        elif User.query.filter_by(email=email).first():  # 检查邮箱是否已注册
            flash('邮箱已被注册', 'danger')  # 提示错误
        else:  # 用户名和邮箱都可用
            db.session.add(User(  # 创建新用户
                username=username, email=email,  # 设置用户名和邮箱
                password_hash=generate_password_hash(request.form.get('password'))  # 对密码进行哈希加密存储
            ))
            db.session.commit()  # 提交到数据库
            flash('注册成功，请登录', 'success')  # 显示成功提示（绿色）
            return redirect(url_for('login'))  # 跳转到登录页
    return render_template('register.html')  # GET请求时渲染注册页面


@app.route('/logout')  # 注册登出路由
@login_required  # 要求必须登录才能访问
def logout():
    logout_user()  # 清除用户登录状态
    return redirect(url_for('index'))  # 重定向到首页


# ==================== 用户功能 ====================

@app.route('/user/dashboard')  # 用户控制台路由
@login_required  # 需要登录
def user_dashboard():
    if current_user.role == 'admin':  # 如果当前用户是管理员
        return redirect(url_for('admin_dashboard'))  # 重定向到管理员控制台
    return render_template('user/dashboard.html')  # 渲染用户控制台页面


@app.route('/user/request_crawl', methods=['GET', 'POST'])
@login_required
def user_request_crawl():
    if request.method == 'POST':
        keyword = request.form.get('keyword', '').strip()
        reason = request.form.get('reason', '').strip()  # ← 【新增】第1处：接收理由

        if not keyword:
            flash('请输入关键词', 'danger')
            return redirect(url_for('user_request_crawl'))

        db.session.add(CrawlRequest(
            user_id=current_user.id,
            keyword=keyword,
            status='pending',
            remark=reason if reason else None  # ← 【新增】第2处：存入remark
        ))
        db.session.commit()
        flash('爬取请求已提交，等待管理员处理', 'success')
        return redirect(url_for('user_request_crawl'))

    return render_template('user/request_crawl.html')

@app.route('/user/products')  # 用户商品浏览路由
@login_required  # 需要登录
def user_products():
    keywords = [k[0] for k in db.session.query(Product.keyword).distinct().all()]  # 查询所有不重复的关键词列表
    return render_template('user/products.html', keywords=keywords)  # 渲染页面并传入关键词列表


@app.route('/user/api/products')  # 商品数据API接口（返回JSON）
@login_required  # 需要登录
def api_products():
    query = Product.query  # 从Product表开始查询
    if request.args.get('keyword'):  # 如果有关键词参数
        query = query.filter_by(keyword=request.args['keyword'])  # 按关键词筛选
    if request.args.get('platform'):  # 如果有平台参数
        query = query.filter_by(platform=request.args['platform'])  # 按平台筛选

    sort_by = request.args.get('sort_by', 'publish_date')  # 获取排序字段，默认按发布时间
    sort_order = request.args.get('sort_order', 'desc')  # 获取排序方向，默认降序
    if sort_by == 'price':
        order = Product.price_value.desc() if sort_order == 'desc' else Product.price_value.asc()
    else:
        order = Product.publish_date.desc() if sort_order == 'desc' else Product.publish_date.asc()

    pagination = query.order_by(order).paginate(  # 执行分页查询
        page=int(request.args.get('page', 1)),  # 当前页码，默认第1页
        per_page=int(request.args.get('per_page', 20)),  # 每页数量，默认20条
        error_out=False  # 页码超出范围不报错
    )

    return jsonify({  # 返回JSON格式数据
        'products': [{  # 商品列表
            'id': p.id, 'title': p.title, 'price_raw': p.price_raw,  # 商品基本信息
            'price_value': p.price_value, 'platform': p.platform,  # 价格和平台
            'publish_date': p.publish_date.strftime('%Y-%m-%d %H:%M'),  # 格式化发布时间
            'url': p.url, 'image_url': p.image_url  # 链接和图片
        } for p in pagination.items],  # 遍历当前页商品
        'total': pagination.total, 'page': pagination.page, 'pages': pagination.pages  # 分页信息
    })


@app.route('/user/api/platforms')  # 获取平台列表API
@login_required  # 需要登录
def api_platforms():
    keyword = request.args.get('keyword', '')
    if keyword:
        query = Product.query.filter_by(keyword=keyword)
    else:
        query = Product.query
    return jsonify(sorted([p[0] for p in query.with_entities(Product.platform).distinct().all()]))  # 返回去重排序后的平台列表


@app.route('/user/analysis')  # 用户价格分析页面路由
@login_required  # 需要登录
def user_analysis():
    keywords = [k[0] for k in db.session.query(Product.keyword).distinct().all()]  # 获取所有关键词
    return render_template('user/analysis.html', keywords=keywords)  # 渲染分析页面


@app.route('/user/api/analysis/data')  # 价格分析数据API
@login_required  # 需要登录
def api_analysis_data():
    keyword = request.args.get('keyword', '')  # 获取分析的关键词
    if not keyword:  # 未指定关键词
        return jsonify({'error': '请选择关键词'}), 400  # 返回400错误

    all_products = Product.query.filter_by(keyword=keyword).all()  # 查询该关键词下所有商品
    valid_products = [p for p in all_products if p.price_value and p.price_value > 0]  # 过滤出有有效价格的商品

    if not all_products:  # 没有数据
        return jsonify({'error': '暂无数据'}), 404  # 返回404错误

    prices = [p.price_value for p in valid_products]  # 提取所有有效价格
    min_price, max_price = (min(prices), max(prices)) if prices else (0, 0)  # 计算最低和最高价格
    avg_price = sum(prices) / len(prices) if prices else 0  # 计算平均价格

    # 价格分布
    bins = []  # 初始化价格区间分布列表
    if prices and max_price > min_price:  # 有价格且价格有差异
        step = (max_price - min_price) / 5  # 将价格范围分成5段
        for i in range(5):  # 遍历5个区间
            low = min_price + i * step  # 区间下限
            high = min_price + (i + 1) * step  # 区间上限
            count = sum(1 for p in valid_products if low <= p.price_value <= high)  # 统计该区间内的商品数量
            if count > 0:  # 只记录有商品的区间
                bins.append({'range': '¥%d-%d' % (int(low), int(high)), 'count': count})  # 添加区间信息

    platform_stats = db.session.query(Product.platform, func.count(Product.id)).filter_by(keyword=keyword).group_by(Product.platform).all()
    date_stats = db.session.query(func.date(Product.publish_date), func.avg(Product.price_value), func.min(Product.price_value), func.max(Product.price_value)).filter_by(keyword=keyword).filter(Product.price_value.isnot(None), Product.price_value > 0).group_by(func.date(Product.publish_date)).order_by(func.date(Product.publish_date)).all()

    best_products = Product.query.filter_by(keyword=keyword).filter(Product.price_value.isnot(None), Product.price_value > 0).order_by(Product.price_value.asc()).limit(10).all()

    return jsonify({  # 返回分析数据
        'platform_stats': [{'name': p[0] or '未知', 'value': p[1]} for p in platform_stats],  # 平台分布数据
        'price_range': {'min': min_price, 'max': max_price, 'avg': round(avg_price, 2)},  # 价格范围统计
        'price_trend': [{'date': str(d[0]), 'avg': float(d[1] or 0), 'min': float(d[2] or 0), 'max': float(d[3] or 0)} for d in date_stats],  # 价格趋势数据
        'price_distribution': bins,  # 价格区间分布
        'best_products': [{'title': p.title, 'price_raw': p.price_raw, 'price_value': p.price_value, 'platform': p.platform or '未知', 'url': p.url} for p in best_products],  # 最优惠商品列表
        'statistics': {'total': len(all_products), 'valid': len(valid_products)}  # 数据统计
    })


# ==================== 爬取次数系统 ====================

@app.route('/user/api/quota')  # 查询用户剩余爬取次数API
@login_required  # 需要登录
def api_user_quota():
    can_watch = True  # 默认可观看广告
    cooldown = 0  # 默认冷却时间0秒
    if current_user.last_ad_watch:  # 如果用户看过广告
        last_watch = current_user.last_ad_watch.replace(tzinfo=pytz.timezone('Asia/Shanghai'))  # 为数据库时间添加上海时区
        elapsed = (get_now() - last_watch).total_seconds()  # 计算距离上次看广告经过的秒数
        if elapsed < 30:  # 如果不到30秒冷却期
            can_watch = False  # 不能观看广告
            cooldown = int(30 - elapsed)  # 计算剩余冷却时间
    return jsonify({  # 返回次数信息
        'quota': current_user.crawl_quota,  # 剩余爬取次数
        'can_watch_ad': can_watch,  # 是否可观看广告
        'cooldown_seconds': cooldown  # 冷却倒计时秒数
    })


@app.route('/user/api/watch_ad', methods=['POST'])  # 观看广告获取次数API
@login_required  # 需要登录
def api_watch_ad():
    if current_user.last_ad_watch:  # 如果之前看过广告
        last_watch = current_user.last_ad_watch.replace(tzinfo=pytz.timezone('Asia/Shanghai'))  # 添加时区
        elapsed = (get_now() - last_watch).total_seconds()  # 计算间隔
        if elapsed < 30:  # 冷却期内
            return jsonify({'error': '冷却中', 'cooldown_seconds': int(30 - elapsed)}), 429  # 返回429 Too Many Requests

    current_user.crawl_quota += 1  # 增加一次爬取次数
    current_user.last_ad_watch = get_now()  # 记录当前观看时间
    db.session.commit()  # 保存到数据库
    return jsonify({'success': True, 'quota': current_user.crawl_quota})  # 返回成功和最新次数


@app.route('/user/api/crawl_with_quota', methods=['POST'])  # 使用次数直接爬取API
@login_required  # 需要登录
def user_crawl_with_quota():
    data = request.get_json()  # 获取POST的JSON数据
    keyword = data.get('keyword', '').strip()  # 提取关键词
    if not keyword:  # 关键词为空
        return jsonify({'error': '请输入关键词'}), 400  # 返回错误
    if current_user.crawl_quota <= 0:  # 次数不足
        return jsonify({'error': '次数不足', 'need_ad': True}), 403  # 返回403，标记需要看广告

    current_user.crawl_quota -= 1  # 扣除一次爬取次数
    products = crawl_manmanbuy(keyword) + crawl_smzdm(keyword)  # 从两个网站爬取商品

    if not products:  # 未爬取到任何商品
        db.session.commit()  # 先提交次数扣除（避免回滚）
        return jsonify({'error': '未找到商品', 'quota': current_user.crawl_quota}), 400  # 返回错误但告知剩余次数

    count = save_products(products, keyword)  # 保存商品到数据库
    db.session.add(CrawlRequest(  # 记录爬取请求
        user_id=current_user.id, keyword=keyword, status='completed',  # 标记为已完成
        processed_at=get_now(), processed_by=current_user.id,  # 记录处理信息
        result_count=count, remark='用户自助爬取'  # 记录结果数和备注
    ))
    db.session.commit()  # 提交所有更改
    return jsonify({'message': '爬取完成，共%d条' % count, 'count': count, 'quota': current_user.crawl_quota})  # 返回成功信息


@app.route('/user/api/my_requests')  # 获取用户爬取历史API
@login_required  # 需要登录
def api_my_requests():
    requests = CrawlRequest.query.filter_by(user_id=current_user.id).order_by(CrawlRequest.created_at.desc()).all()  # 查询当前用户的所有请求，按时间倒序
    return jsonify([{  # 返回JSON列表
        'id': r.id, 'keyword': r.keyword, 'status': r.status,  # 基本信息
        'result_count': r.result_count, 'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),  # 结果数和时间
        'remark': r.remark  # 备注
    } for r in requests])


@app.route('/user/profile', methods=['GET', 'POST'])  # 用户个人中心路由
@login_required  # 需要登录
def user_profile():
    if request.method == 'POST':  # 提交修改
        if request.form.get('email'):  # 如果填写了邮箱
            current_user.email = request.form['email']  # 更新邮箱
        if request.form.get('password'):  # 如果填写了密码
            current_user.password_hash = generate_password_hash(request.form['password'])  # 更新密码（加密存储）
        db.session.commit()  # 保存更改
        flash('更新成功', 'success')  # 提示成功
        return redirect(url_for('user_profile'))  # 刷新页面
    return render_template('user/profile.html')  # GET请求时渲染个人中心


# ==================== 管理员功能 ====================

def admin_required(f):
    """管理员权限装饰器"""  # 自定义装饰器，限制只有管理员能访问
    from functools import wraps  # 导入wraps保持函数元信息
    @wraps(f)  # 保留被装饰函数的原始信息
    def decorated(*args, **kwargs):  # 包装函数
        if current_user.role != 'admin':  # 如果不是管理员
            return redirect(url_for('user_dashboard'))  # 重定向到用户控制台
        return f(*args, **kwargs)  # 是管理员则执行原函数

    return decorated  # 返回包装后的函数


@app.route('/admin/dashboard')  # 管理员控制台路由
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def admin_dashboard():
    return render_template('admin/dashboard.html', user_count=User.query.count(), product_count=Product.query.count(), pending_requests=CrawlRequest.query.filter_by(status='pending').count(), keyword_count=db.session.query(Product.keyword).distinct().count())


@app.route('/admin/users')  # 用户管理页面路由
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def admin_users():
    return render_template('admin/users.html')  # 渲染用户管理页面


@app.route('/admin/api/users')  # 用户列表API
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def api_users():
    pagination = User.query.order_by(User.created_at.desc()).paginate(page=int(request.args.get('page', 1)), per_page=int(request.args.get('per_page', 20)), error_out=False)
    return jsonify({
        'users': [{'id': u.id, 'username': u.username, 'email': u.email, 'role': u.role, 'status': u.status, 'created_at': u.created_at.strftime('%Y-%m-%d %H:%M')} for u in pagination.items],
        'total': pagination.total, 'page': pagination.page, 'pages': pagination.pages
    })


@app.route('/admin/user/<int:user_id>', methods=['PUT', 'DELETE'])  # 用户操作API（修改/删除）
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def admin_user_action(user_id):
    user = User.query.get_or_404(user_id)  # 根据ID查询用户，不存在返回404
    if request.method == 'PUT':  # 修改用户
        data = request.get_json()  # 获取JSON数据
        if 'role' in data:  # 如果提供了角色
            user.role = data['role']  # 更新角色
        if 'status' in data:  # 如果提供了状态
            user.status = data['status']  # 更新状态（启用/禁用）
        db.session.commit()  # 保存
        return jsonify({'message': '更新成功'})  # 返回成功

    elif request.method == 'DELETE':  # 删除用户
        if user.id == current_user.id:  # 不能删除自己
            return jsonify({'error': '不能删除自己'}), 400  # 返回错误
        db.session.delete(user)  # 删除用户
        db.session.commit()  # 提交
        return jsonify({'message': '删除成功'})  # 返回成功


@app.route('/admin/requests')  # 爬取请求管理页面
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def admin_requests():
    return render_template('admin/requests.html')  # 渲染请求管理页面


@app.route('/admin/api/requests')  # 爬取请求列表API
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def api_requests():
    query = CrawlRequest.query  # 从请求表开始查询
    if request.args.get('status'):  # 如果指定了状态筛选
        query = query.filter_by(status=request.args['status'])  # 按状态筛选
    pagination = query.order_by(CrawlRequest.created_at.desc()).paginate(page=int(request.args.get('page', 1)), per_page=int(request.args.get('per_page', 20)), error_out=False)
    return jsonify({
        'requests': [{'id': r.id, 'username': r.user.username, 'keyword': r.keyword, 'status': r.status, 'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'), 'processed_at': r.processed_at.strftime('%Y-%m-%d %H:%M') if r.processed_at else None, 'result_count': r.result_count, 'remark': r.remark} for r in pagination.items],
        'total': pagination.total, 'page': pagination.page, 'pages': pagination.pages
    })


@app.route('/admin/request/<int:request_id>/process', methods=['POST'])  # 处理爬取请求API
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def admin_process_request(request_id):
    crawl_request = CrawlRequest.query.get_or_404(request_id)  # 查询请求，不存在返回404
    action = request.get_json().get('action')  # 获取操作类型（approve/reject）

    if action == 'approve':  # 批准请求
        products = crawl_manmanbuy(crawl_request.keyword) + crawl_smzdm(crawl_request.keyword)  # 执行爬取
        count = save_products(products, crawl_request.keyword)  # 保存商品
        crawl_request.status = 'completed'  # 状态改为已完成
        crawl_request.processed_at = get_now()  # 记录处理时间
        crawl_request.processed_by = current_user.id  # 记录处理人
        crawl_request.result_count = count  # 记录结果数
        crawl_request.remark = '成功爬取%d条' % count  # 添加备注

    elif action == 'reject':  # 拒绝请求
        crawl_request.status = 'rejected'  # 状态改为已拒绝
        crawl_request.processed_at = get_now()  # 记录处理时间
        crawl_request.processed_by = current_user.id  # 记录处理人
        crawl_request.remark = request.get_json().get('remark', '已拒绝')  # 记录拒绝原因

    else:  # 未知操作
        return jsonify({'error': '无效操作'}), 400  # 返回错误

    db.session.commit()  # 保存更改
    return jsonify({'message': '处理成功'})  # 返回成功


@app.route('/admin/crawl')  # 管理员直接爬取页面
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def admin_crawl():
    return render_template('admin/crawl.html')  # 渲染直接爬取页面


@app.route('/admin/api/crawl', methods=['POST'])  # 管理员直接爬取API
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def api_crawl():
    keyword = request.get_json().get('keyword', '').strip()  # 获取关键词
    if not keyword:  # 关键词为空
        return jsonify({'error': '请输入关键词'}), 400  # 返回错误

    products = crawl_manmanbuy(keyword) + crawl_smzdm(keyword)  # 爬取商品
    if products:  # 爬取成功
        count = save_products(products, keyword)  # 保存商品
        return jsonify({'message': '爬取完成，共%d条' % count, 'count': count})  # 返回成功
    return jsonify({'error': '未爬取到任何商品'}), 400  # 未爬取到数据


@app.route('/admin/analysis')  # 管理员数据分析页面
@login_required  # 需要登录
@admin_required  # 需要管理员权限
def admin_analysis():
    keywords = [k[0] for k in db.session.query(Product.keyword).distinct().all()]  # 获取所有关键词
    return render_template('admin/analysis.html', keywords=keywords)  # 渲染分析页面


if __name__ == '__main__':  # 当直接运行此文件时（非导入）
    app.run(debug=False, host='0.0.0.0', port=5000)  # 启动Flask服务器，关闭调试模式，监听所有IP，端口5000