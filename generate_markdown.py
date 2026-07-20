import json
from datetime import datetime

def generate_readme():
    with open('tech-blog-lists-cn.json', 'r', encoding='utf-8') as f:
        blogs = json.load(f)
    
    # 统计
    active_count = len([b for b in blogs if b.get('status') == 'active'])
    total_count = len(blogs)
    
    # 生成表格
    table_rows = []
    for blog in sorted(blogs, key=lambda x: x.get('name', '')):
        print(blog.get('name', '未知'))
        name = blog.get('name', '未知')
        url = blog.get('url', '#')
        added_date = blog.get('added_date')
        status = '✅ 活跃' if blog.get('status') == 'active' else '⚠️ 无RSS'
        
        table_rows.append(f"| {name} | [🔗]({url}) | {added_date} | {status} |")
    
    # print(blogs)
    # print(table_rows)
    readme_content = f"""# popsite.cn - 独立博客发现计划

This repository is used to discover and collect blogs that continuous original and updated by personal. In the era of AI, these blogs are very preciouse. 

这个仓库用来发现并收录那些持续原创、持续更新的个人博客。在AI大模型越来越发达的时代，坚持自主书写、原创输出的博客越为珍贵。

> 今天看到朋友发的一个内容：AI模型越先进，公众号等平台上越是太多的注水内容，没把AI用来生产优质内容，全是自动化生成文章，味同嚼蜡。

**网站地址**：https://popsite.cn

## 统计信息 / Statistics
- 收录博客数量：**{total_count}** 个
- 活跃博客：**{active_count}** 个
- 最后更新：**{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**

## 收录的博客列表 / Blog 

| 博客名称 | 链接 | 收录时间 | 状态 |
|---------|------|------|------|
{chr(10).join(table_rows)}

## 如何提交你的博客

如果你也在坚持写独立博客，欢迎通过以下方式提交：
1. 在 GitHub 提交 Issue
2. 直接修改 tech-blog-lists-cn.json 并提交 PR
3. 访问 popsite.cn 填写表单

## 希望能在您的站点上添加友情链接

为了更好的推广本站，诚挚的希望您能将本站添加至友情链接中，非常感谢。

---

_本项目由 [cocowool](https://github.com/cocowool) 维护_
"""
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("✅ README.md 生成成功")

def generate_latest_posts():
    with open('source/data/latest_posts.json', 'r', encoding='utf-8') as f:
        posts = json.load(f)
    
    # 按日期分组
    posts_by_date = {}
    for post in posts:
        date = post.get('pub_date', '未知')
        if date not in posts_by_date:
            posts_by_date[date] = []
        posts_by_date[date].append(post)
    
    # 生成 Markdown
    md_lines = ["# 独立博客最新文章\n"]
    md_lines.append(f"_最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")
    md_lines.append("---\n")
    
    for date in sorted(posts_by_date.keys(), reverse=True):
        md_lines.append(f"\n## {date}\n")
        for post in posts_by_date[date]:
            title = post.get('title', '无标题')
            link = post.get('link', '#')
            blog_name = post.get('blog_name', '未知')
            blog_url = post.get('blog_url', '#')
            
            md_lines.append(f"- **[{title}]({link})**  ")
            md_lines.append(f"  来自 [{blog_name}]({blog_url})\n")
    
    with open('latest_posts.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    
    print("✅ latest_posts.md 生成成功")

if __name__ == "__main__":
    generate_readme()
    # generate_latest_posts()