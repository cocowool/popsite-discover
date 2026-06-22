import os, sys, getopt
import re
from bs4 import BeautifulSoup
import requests
import time
import random
import json
import pypinyin
import chardet
from urllib.parse import urljoin

# 部分网页响应没指定 encoding，或用了与内容编码不一致的编码，需要探测并修正
def get_encoding(response):
    content_type = response.headers.get('Content-Type', '')
    header_encoding = None
    if 'charset=' in content_type.lower():
        # 提取 chaarset= 后面的的值，并去掉可能存在的引号
        match = re.search(r'charset=([^;]+)', content_type, re.IGNORECASE)
        if match:
            header_encoding = match.group(1).strip().strip('"\'')

    if header_encoding:
        return header_encoding
    
    # 尝试使用 chardet 库检测编码
    apparent_encoding = response.apparent_encoding
    if apparent_encoding:
        try:
            html_text = response.content.decode(apparent_encoding, errors='ignore')
            meta_match = re.search(r'charset=["\']?([^"\'\s;>]+)', html_text, re.IGNORECASE)
            if meta_match:
                return meta_match.group(1)
        except Exception as e:
            print(f"Error decoding with {apparent_encoding}: {e}")
            return None

    return apparent_encoding

# 读取中文博客列表清单，生成 Markdown 格式的列表
def get_blog_info(url, method = "requests"):

    try:
        # config = self.read_config()
        my_cookie = ''

        my_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }

        # if config['cookie']:
        #     my_cookie = config['cookie']

        s = requests.session()
        s.keep_alive = False
        response = s.get(url, headers = my_headers, timeout = 10)

        if response.status_code == 429:
            print("Error fetching blog info for {url}: 429 Too Many Requests.")
            return
        
        response.raise_for_status()  # 如果响应状态码不是 200，会抛出 HTTPError 异常

        # 判断网页编码
        html_encoding = get_encoding(response)
        if html_encoding:
            response.encoding = html_encoding

        soup = BeautifulSoup(response.text, 'html.parser')

        # 获取博客标题
        blog_title = soup.title.get_text(strip=True) if soup.title else ''
        
        # 获取 Description
        blog_description = ''

        tag_description = soup.find('meta', attrs={'name': re.compile(r'^description$',re.IGNORECASE)})
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

        # print(tag_description['content'])
        blog_description = tag_description['content'].strip() if tag_description and tag_description.get('content') else ''
        # print("Blog Description:" + blog_description)

        # 探测RSS
        blog_rss_url = ''
        tag_rss = soup.find('link', type=re.compile(r'application/(rss|atom)\+?xml?'))
        if tag_rss and tag_rss.get('href'):
            blog_rss_url = urljoin(url,tag_rss['href'])
        else:
            # 尝试常见路径
            common_paths = ['/feed', '/atom.xml', '/rss.xml', '/feed.xml', '/index.xml', '/?feed=rss2']
            for path in common_paths:
                try:
                    # 增加随机延时，避免被触发限流
                    time.sleep(random.uniform(1.0, 2.5))

                    test_url = url.rstrip('/') + path
                    test_res = requests.get(test_url, headers=my_headers, timeout=5)

                    if test_res.status_code == 429:
                        print("探测RSS时被限流，停止继续探测。")
                        break  # 如果被限流了，就不继续测试了

                    if test_res.status_code == 200:
                        content_type = test_res.headers.get('Content-Type', '')
                        text_head = test_res.text[:200].strip()
                        if 'xml' in content_type or text_head.startswith('<?xml') or '<rss' in text_head or '<feed' in text_head:
                            blog_rss_url = test_url
                            break
                except:
                    pass

        blog_data = {
            "name" : blog_title,
            "url" : url,
            "description" : blog_description,
            "rss" : blog_rss_url,
            "status" : "active" if blog_rss_url else "no_rss",
            "added_date" : time.strftime('%Y-%m-%d', time.localtime())
        }

        print("Get Blog Info Success:")
        print(json.dumps(blog_data, ensure_ascii=False, indent=4))

    except Exception as e:
        print(f"Error fetching blog info for {url}: {e}")
    # return response.text

# 持久化逻辑
# file_name = 'tech-blog-lists-cn.txt'
# fh = open(file_name, 'r', encoding='utf-8')

# markdown_text = ''

# line = fh.readline().strip()
# while line:
#     # print(line)
#     line = fh.readline().strip()
#     if line:
#         html = get_html(line)

#         html_content  = BeautifulSoup(html, 'html.parser')
#         t_title = html_content.find_all('title')[0].get_text().strip()
#         if t_title == '':
#             t_title = line

#         markdown_text += "* [" + t_title + "](" + line + ")\n"

# fh.close()

if __name__ == "__main__":
    target_url = input("Please input the target blog URL: ")
    get_blog_info(target_url)