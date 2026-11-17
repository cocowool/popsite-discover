import json
import feedparser
import requests
from bs4 import BeautifulSoup
import time
import os

# ==========================================
# 1. 动态路径配置 (适配 scripts/ 目录下的运行)
# ==========================================
# 获取当前脚本所在的绝对目录
script_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (scripts 的上一级)
project_root = os.path.dirname(script_dir)

# 统一数据源路径 (支持未来多语言合并)
BLOGS_JSON_PATH = os.path.join(project_root, 'data', 'blogs.json')
LATEST_POSTS_PATH = os.path.join(project_root, 'data', 'latest_posts.json')

def get_webpage_title(url):
    """如果 name 为空，尝试从网页获取 title"""
    try:
        # 增加 allow_redirects=True 确保能处理 301/302 重定向
        res = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, allow_redirects=True)
        res.raise_for_status() # 确保是 200 OK
        soup = BeautifulSoup(res.text, 'html.parser')
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except Exception:
        pass
    return ""

def process_blogs():
    # 1. 读取数据
    if not os.path.exists(BLOGS_JSON_PATH):
        print(f"❌ 找不到文件: {BLOGS_JSON_PATH}")
        print("💡 提示: 请确保 data/blogs.json 存在。")
        return

    with open(BLOGS_JSON_PATH, 'r', encoding='utf-8') as f:
        blogs = json.load(f)

    latest_posts = []
    
    print(f"🚀 开始处理 {len(blogs)} 个博客...\n")

    for i, blog in enumerate(blogs):
        name = blog.get('name', '').strip()
        url = blog.get('url', '').strip()
        rss = blog.get('rss', '').strip()
        
        # 预留多语言字段，如果缺失则默认为中文
        blog.setdefault('lang', 'zh')
        
        print(f"[{i+1}/{len(blogs)}] 处理: {name or url}")

        # 补全空 Name
        if not name and url:
            name = get_webpage_title(url)
            if name:
                blog['name'] = name
                print(f"   🔍 自动补全名称: {name}")

        # 清理无效的占位符 RSS (防御性编程)
        if 'johndoe.com' in rss or 'example.com' in rss:
            rss = ""
            blog['rss'] = ""

        # 2. 检查 URL 是否存活
        is_url_alive = False
        try:
            res = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, allow_redirects=True)
            if res.status_code == 200:
                is_url_alive = True
        except Exception:
            pass

        if not is_url_alive:
            blog['status'] = 'archived'
            print(f"   ❌ 网站无法访问，标记为 archived")
            continue

        # 3. 检查 RSS 并抓取最新文章
        if rss:
            try:
                feed = feedparser.parse(rss)
                # 判断 feed 是否有效 (至少有 1 个 entry 且没有致命解析错误)
                if feed.entries and not feed.bozo:
                    blog['status'] = 'active'
                    
                    # 提取最新文章
                    latest_entry = feed.entries[0]
                    title = latest_entry.get('title', '无标题')
                    link = latest_entry.get('link', url)
                    
                    # 处理发布时间
                    pub_date = "未知时间"
                    if 'published_parsed' in latest_entry and latest_entry.published_parsed:
                        pub_date = time.strftime('%Y-%m-%d', latest_entry.published_parsed)
                    elif 'updated_parsed' in latest_entry and latest_entry.updated_parsed:
                        pub_date = time.strftime('%Y-%m-%d', latest_entry.updated_parsed)
                        
                    latest_posts.append({
                        "blog_name": name,
                        "blog_url": url,
                        "title": title,
                        "link": link,
                        "pub_date": pub_date,
                        "lang": blog.get('lang', 'zh') # 同步语言标签
                    })
                    print(f"   ✅ 状态: active | 最新文章: {title[:30]}... ({pub_date})")
                else:
                    blog['status'] = 'no_rss'
                    print(f"   ⚠️ RSS 无内容或格式错误，降级为 no_rss")
            except Exception as e:
                blog['status'] = 'no_rss'
                print(f"   ⚠️ RSS 解析异常，降级为 no_rss")
        else:
            blog['status'] = 'no_rss'
            print(f"   ⚠️ 无 RSS 地址，标记为 no_rss")

        # 礼貌爬取，防止被封 IP (符合长期主义，保护你的爬虫资产)
        time.sleep(1.5) 

    # 4. 保存更新后的 blogs.json
    with open(BLOGS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(blogs, f, ensure_ascii=False, indent=4)
    print(f"\n💾 已更新: {BLOGS_JSON_PATH}")

    # 5. 保存最新文章列表 latest_posts.json
    # 优化排序逻辑：将 "未知时间" 视为极早的时间，确保有效日期的文章排在前面
    def sort_key(x):
        return x['pub_date'] if x['pub_date'] != '未知时间' else '0000-00-00'
        
    latest_posts.sort(key=sort_key, reverse=True)
    
    with open(LATEST_POSTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(latest_posts, f, ensure_ascii=False, indent=4)
    print(f"💾 已生成: {LATEST_POSTS_PATH}，共 {len(latest_posts)} 篇最新文章。")
    print("🎉 全部完成！你可以基于 latest_posts.json 生成博客首页的『最近更新』模块。")

if __name__ == "__main__":
    process_blogs()