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
    content_type = response.headers.get('Content-Type', '')
    header_encoding = None
    if 'charset=' in content_type.lower():
        match = re.search(r'charset=([^;]+)', content_type, re.IGNORECASE)
        if match:
            header_encoding = match.group(1).strip().strip('"\'')
    if header_encoding:
        return header_encoding

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
# 2. 根域名提取逻辑 (用于去重与比对)
# ==========================================
def get_root_domain(url):
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    for prefix in ['www.', 'm.', 'blog.', 'docs.', 'dev.', 'app.']:
        if netloc.startswith(prefix):
            netloc = netloc[len(prefix):]
    common_double_suffixes = ['.com.cn', '.org.cn', '.net.cn', '.github.io', '.gitee.io', '.vercel.app', '.netlify.app']
    for suffix in common_double_suffixes:
        if netloc.endswith(suffix):
            return netloc
    parts = netloc.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return netloc

# ==========================================
# 3. 核心抓取逻辑
# ==========================================
def get_blog_info(target_url, method="requests"):
    try:
        my_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        s = requests.session()
        s.keep_alive = False
        response = s.get(target_url, headers=my_headers, timeout=10)

        if response.status_code == 429:
            print("[-] 抓取被限流 (429 Too Many Requests)，请稍后再试。")
            return None
        response.raise_for_status()

        html_encoding = get_encoding(response)
        if html_encoding:
            response.encoding = html_encoding

        soup = BeautifulSoup(response.text, 'html.parser')
        blog_title = soup.title.get_text(strip=True) if soup.title else ''
        
        blog_description = ''
        tag_description = soup.find('meta', attrs={'name': re.compile(r'^description$', re.IGNORECASE)})
        if tag_description and tag_description.get('content'):
            blog_description = tag_description['content'].strip()
        if not blog_description:
            og_description = soup.find('meta', attrs={'property': 'og:description'})
            if og_description and og_description.get('content'):
                blog_description = og_description['content'].strip()

        blog_rss_url = ''
        tag_rss = soup.find('link', type=re.compile(r'application/(rss|atom)\+?xml?'))
        if tag_rss and tag_rss.get('href'):
            blog_rss_url = urljoin(target_url, tag_rss['href'])
        else:
            common_paths = ['/feed', '/atom.xml', '/rss.xml', '/feed.xml', '/index.xml', '/?feed=rss2']
            for path in common_paths:
                try:
                    time.sleep(random.uniform(0.3, 0.8))
                    test_url = target_url.rstrip('/') + path
                    test_res = requests.get(test_url, headers=my_headers, timeout=5)
                    if test_res.status_code == 200:
                        content_type = test_res.headers.get('Content-Type', '')
                        text_head = test_res.text[:200].strip()
                        if 'xml' in content_type or text_head.startswith('<?xml') or '<rss' in text_head or '<feed' in text_head:
                            blog_rss_url = test_url
                            break
                except Exception:
                    pass

        return {
            "name": blog_title,
            "url": target_url,
            "description": blog_description,
            "rss": blog_rss_url,
            "status": "active" if blog_rss_url else "no_rss",
            "added_date": time.strftime('%Y-%m-%d', time.localtime())
        }
    except Exception as e:
        print(f"[-] 抓取失败: {e}")
        return None

# ==========================================
# 4. 数据管理与持久化逻辑 (支持预检与更新)
# ==========================================
def load_json_data(filename="tech-blog-lists-cn.json"):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            print(f"[-] 警告: {filename} 格式错误，将初始化为空列表。")
    return []

def save_json_data(data_list, filename="tech-blog-lists-cn.json"):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"[-] 保存文件失败: {e}")
        return False

def show_diff(old_data, new_data):
    print("\n" + "="*50)
    print("🔍 检查信息是否有差异，请根据检查结果确认是否更新：")
    print("="*50)
    keys_to_compare = ['name', 'url', 'description', 'rss', 'status']
    has_diff = False
    for key in keys_to_compare:
        old_val = str(old_data.get(key, '')).strip()
        new_val = str(new_data.get(key, '')).strip()
        if old_val != new_val:
            has_diff = True
            print(f"  [{key:12}]")
            print(f"    旧值: {old_val if old_val else '(空)'}")
            print(f"    新值: {new_val if new_val else '(空)'}")
            print("-" * 40)
    
    if not has_diff:
        print("  ✅ 抓取到的信息与现有记录完全一致，无需更新。")
    print("="*50)
    return has_diff

def edit_blog_data(data):
    print("\n--- 进入编辑模式 (直接回车则保持原值) ---")
    new_data = data.copy()
    for k, v in data.items():
        if k == 'added_date':
            continue
        new_val = input(f"  {k:12} (当前: {v})\n  请输入新值 > ").strip()
        if new_val:
            new_data[k] = new_val
    return new_data

# ==========================================
# 5. 主程序入口
# ==========================================
if __name__ == "__main__":
    print("🚀 个人自媒体博客信息收集工具 v3.0 (支持预检与智能更新)")
    print("💡 提示: 自动基于一级域名去重，支持比对差异并更新现有记录。\n")
    
    filename = "tech-blog-lists-cn.json"
    data_list = load_json_data(filename)
    
    while True:
        target_url = input("请输入目标博客 URL (输入 'q' 退出): ").strip()
        if target_url.lower() in ['q', 'quit', 'exit']:
            print("👋 退出程序。坚持长期主义，祝你的自媒体事业蒸蒸日上！")
            break
            
        if not target_url.startswith('http'):
            target_url = 'https://' + target_url

        # 1. 预检查：基于根域名判断是否已存在
        root_domain = get_root_domain(target_url)
        existing_item = None
        existing_index = -1
        
        for idx, item in enumerate(data_list):
            if get_root_domain(item.get('url', '')) == root_domain:
                existing_item = item
                existing_index = idx
                break

        # 2. 根据预检查结果决定流程
        if existing_item:
            print(f"\n⚠️  预检提示: 该博客的一级域名 ({root_domain}) 已存在于库中。")
            print(f"   现有记录: {existing_item.get('name')} ({existing_item.get('url')})")
            choice = input("   是否继续抓取以检查是否有信息更新？(y/n, 默认 n): ").strip().lower()
            if choice != 'y':
                print("[-] 已取消抓取。\n" + "-"*50 + "\n")
                continue
        
        # 3. 执行抓取
        print(f"\n正在抓取: {target_url} ...")
        new_data = get_blog_info(target_url)
        
        if not new_data:
            print("[-] 抓取失败，请检查 URL 是否正确或网络连接。\n" + "-"*50 + "\n")
            continue

        # 4. 抓取后处理：比对与确认
        if existing_item:
            has_diff = show_diff(existing_item, new_data)
            if not has_diff:
                print("[-] 信息无变化，跳过保存。\n" + "-"*50 + "\n")
                continue
                
            update_choice = input("\n是否使用新抓取的信息更新现有记录？(y/n, 默认 y): ").strip().lower()
            if update_choice != 'n':
                # 允许用户在更新前做最后的手动微调
                final_data = edit_blog_data(new_data)
                final_data['added_date'] = existing_item.get('added_date', time.strftime('%Y-%m-%d', time.localtime())) # 保留原始添加日期
                
                data_list[existing_index] = final_data
                if save_json_data(data_list, filename):
                    print(f"\n🎉 成功更新记录: {final_data.get('name')}")
            else:
                print("[-] 已取消更新。\n")
        else:
            # 全新博客：交互式修改后追加
            print("\n✅ 抓取成功！这是一个全新的博客记录。")
            final_data = edit_blog_data(new_data)
            data_list.append(final_data)
            if save_json_data(data_list, filename):
                print(f"\n🎉 成功追加新记录: {final_data.get('name')}")
        
        print("\n" + "-"*50 + "\n")