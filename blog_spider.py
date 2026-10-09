import os
import re
import json
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# ==========================================
# 1. 编码探测与修正逻辑
# ==========================================
def get_encoding(response):
    # 1. 优先检查 HTTP 响应头
    content_type = response.headers.get('Content-Type', '')
    header_encoding = None
    if 'charset=' in content_type.lower():
        match = re.search(r'charset=([^;]+)', content_type, re.IGNORECASE)
        if match:
            header_encoding = match.group(1).strip().strip('"\'')

    if header_encoding:
        return header_encoding

    # 2. 检查 HTML meta 标签
    try:
        html_text = response.content.decode('utf-8', errors='ignore')
    except:
        html_text = response.text

    meta_match = re.search(r'<meta\s+charset=["\']?([^"\'\s;>]+)', html_text, re.IGNORECASE)
    if meta_match:
        return meta_match.group(1).strip()

    meta_match = re.search(r'<meta[^>]+http-equiv=["\']content-type["\'][^>]+charset=["\']?([^"\'>\s]+)', html_text, re.IGNORECASE)
    if meta_match:
        return meta_match.group(1).strip()

    # 3. 尝试使用 chardet/apparent_encoding 检测编码
    apparent_encoding = response.apparent_encoding
    if apparent_encoding and apparent_encoding.lower() != 'ascii':
        try:
            html_text = response.content.decode(apparent_encoding, errors='ignore')
            meta_match = re.search(r'charset=["\']?([^"\'\s;>]+)', html_text, re.IGNORECASE)
            if meta_match:
                return meta_match.group(1)
        except Exception:
            pass

    return 'utf-8'

# ==========================================
# 2. 智能域名处理逻辑
# ==========================================
def get_primary_domain(url):
    """
    如果输入的是二级域名，自动替换为一级域名获取信息。
    排除常见的公共二级域名托管平台（如 github.io, vercel.app 等）
    """
    parsed = urlparse(url)
    netloc = parsed.netloc
    
    # 常见公共二级域名后缀，不应被截断
    public_suffixes = ['github.io', 'gitee.io', 'vercel.app', 'netlify.app', 'pages.dev', 'wordpress.com', 'csdn.net', 'juejin.cn']
    for suffix in public_suffixes:
        if netloc.endswith(suffix):
            return url  # 保持不变
    
    parts = netloc.split('.')
    # 如果域名部分大于2段，且第一段是常见的子域前缀，则尝试去掉第一段
    if len(parts) > 2 and parts[0] in ['www', 'm', 'blog', 'docs', 'dev']:
        primary_netloc = '.'.join(parts[1:])
        primary_url = parsed._replace(netloc=primary_netloc).geturl()
        return primary_url
    
    return url

# ==========================================
# 3. 核心抓取逻辑
# ==========================================
def get_blog_info(original_url, method="requests"):
    
    target_url = original_url.strip()

    # 自动替换二级域名为一级域名，逻辑还不是很完善
    # target_url = get_primary_domain(original_url)
    # if target_url != original_url:
        # print(f"[*] 检测到二级域名，已自动尝试替换为一级域名进行抓取: {target_url}\n")

    try:
        my_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }

        s = requests.session()
        s.keep_alive = False
        response = s.get(target_url, headers=my_headers, timeout=10)

        if response.status_code == 429:
            print("[-] Error fetching blog info: 429 Too Many Requests.")
            return None
        
        response.raise_for_status()

        # 判断并修正网页编码
        html_encoding = get_encoding(response)
        if html_encoding:
            response.encoding = html_encoding

        soup = BeautifulSoup(response.text, 'html.parser')

        # 获取博客标题
        blog_title = soup.title.get_text(strip=True) if soup.title else ''
        
        # 获取 Description (按优先级查找)
        blog_description = ''
        tag_description = soup.find('meta', attrs={'name': re.compile(r'^description$', re.IGNORECASE)})
        if tag_description and tag_description.get('content'):
            blog_description = tag_description['content'].strip()

        if not blog_description:
            og_description = soup.find('meta', attrs={'property': 'og:description'})
            if og_description and og_description.get('content'):
                blog_description = og_description['content'].strip()

        if not blog_description:
            tw_description = soup.find('meta', attrs={'name': 'twitter:description'})
            if tw_description and tw_description.get('content'):
                blog_description = tw_description['content'].strip()

        # 探测 RSS
        blog_rss_url = ''
        tag_rss = soup.find('link', type=re.compile(r'application/(rss|atom)\+?xml?'))
        if tag_rss and tag_rss.get('href'):
            blog_rss_url = urljoin(target_url, tag_rss['href'])
        else:
            # 尝试常见路径
            common_paths = ['/feed', '/atom.xml', '/rss.xml', '/feed.xml', '/index.xml', '/?feed=rss2']
            for path in common_paths:
                try:
                    time.sleep(random.uniform(0.5, 1.5)) # 降低延时，提升体验同时避免限流
                    test_url = target_url.rstrip('/') + path
                    test_res = requests.get(test_url, headers=my_headers, timeout=5)

                    if test_res.status_code == 429:
                        print("[-] 探测 RSS 时被限流，停止继续探测。")
                        break

                    if test_res.status_code == 200:
                        content_type = test_res.headers.get('Content-Type', '')
                        text_head = test_res.text[:200].strip()
                        if 'xml' in content_type or text_head.startswith('<?xml') or '<rss' in text_head or '<feed' in text_head:
                            blog_rss_url = test_url
                            break
                except Exception:
                    pass

        blog_data = {
            "name": blog_title,
            "url": target_url,
            "description": blog_description,
            "rss": blog_rss_url,
            "status": "active" if blog_rss_url else "no_rss",
            "added_date": time.strftime('%Y-%m-%d', time.localtime())
        }

        return blog_data

    except Exception as e:
        print(f"[-] Error fetching blog info for {target_url}: {e}")
        return None

# ==========================================
# 4. 交互式修改与持久化逻辑
# ==========================================
def edit_blog_data(data):
    print("\n" + "="*40)
    print("✅ 抓取成功！当前获取到的博客信息如下：")
    print("="*40)
    for k, v in data.items():
        print(f"  {k:12}: {v}")
    print("="*40)
    
    edit_choice = input("\n是否需要手工修改这些信息？(y/n, 默认 n): ").strip().lower()
    if edit_choice == 'y':
        print("\n--- 进入编辑模式 (直接回车则保持原值) ---")
        new_data = {}
        for k, v in data.items():
            if k == 'added_date':
                new_data[k] = v  # 日期通常不需要手动修改
                continue
            
            new_val = input(f"  {k:12} (当前: {v})\n  请输入新值 > ").strip()
            new_data[k] = new_val if new_val else v
        return new_data
    return data

def save_to_json(blog_data, filename="tech-blog-lists-cn.json"):
    # 1. 读取现有文件
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data_list = json.load(f)
                if not isinstance(data_list, list):
                    data_list = []
        except json.JSONDecodeError:
            print(f"[-] 警告: {filename} 格式错误，将创建新的列表。")
            data_list = []
    else:
        data_list = []
    
    # 2. 检查 URL 是否已存在，避免重复添加
    for item in data_list:
        if item.get('url') == blog_data['url']:
            print(f"\n⚠️  该 URL ({blog_data['url']}) 已存在于文件中，跳过保存。")
            return
    
    # 3. 追加新数据并保存
    data_list.append(blog_data)
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)
        print(f"\n🎉 成功将信息追加到 {filename}")
    except Exception as e:
        print(f"\n[-] 保存文件失败: {e}")

# ==========================================
# 5. 主程序入口
# ==========================================
if __name__ == "__main__":
    print("🚀 个人自媒体博客信息收集工具 v2.0")
    print("💡 提示: 支持自动识别并尝试一级域名，支持交互式修改与 JSON 持久化。\n")
    
    while True:
        target_url = input("请输入目标博客 URL (输入 'q' 退出): ").strip()
        if target_url.lower() in ['q', 'quit', 'exit']:
            print("👋 退出程序。坚持长期主义，祝你的自媒体事业蒸蒸日上！")
            break
            
        if not target_url.startswith('http'):
            target_url = 'https://' + target_url

        print(f"\n正在抓取: {target_url} ...")
        blog_data = get_blog_info(target_url)
        
        if blog_data:
            # 交互式修改
            final_data = edit_blog_data(blog_data)
            # 持久化保存
            save_to_json(final_data)
        else:
            print("[-] 抓取失败，请检查 URL 是否正确或网络连接。")
        
        print("\n" + "-"*50 + "\n")