import pytest
from unittest.mock import MagicMock, PropertyMock
from blog_spider import get_encoding


def make_response(headers=None, content=b'', apparent_encoding=None, text=''):
    resp = MagicMock()
    resp.headers = headers or {}
    resp.content = content
    resp.apparent_encoding = apparent_encoding
    type(resp).text = PropertyMock(return_value=text)
    return resp


# 分支1: HTTP 响应头含 charset
def test_header_charset():
    resp = make_response(headers={'Content-Type': 'text/html; charset=gbk'})
    assert get_encoding(resp) == 'gbk'

def test_header_charset_quoted():
    resp = make_response(headers={'Content-Type': 'text/html; charset="utf-8"'})
    assert get_encoding(resp) == 'utf-8'

def test_header_charset_case_insensitive():
    resp = make_response(headers={'Content-Type': 'text/html; CHARSET=Big5'})
    assert get_encoding(resp) == 'Big5'

# 分支2: HTML <meta charset="...">
def test_meta_charset():
    html = b'<html><head><meta charset="gb2312"></head></html>'
    resp = make_response(content=html)
    assert get_encoding(resp) == 'gb2312'

# 分支3: HTML <meta http-equiv="content-type" ... charset=...>
def test_meta_http_equiv_charset():
    html = b'<meta http-equiv="content-type" content="text/html; charset=shift_jis">'
    resp = make_response(content=html)
    assert get_encoding(resp) == 'shift_jis'

# 分支4: chardet 检测到编码，且解码后找到 charset
def test_apparent_encoding_with_charset_in_content():
    html = '你好世界<meta charset="euc-jp">'.encode('euc-jp', errors='ignore')
    resp = make_response(content=html, apparent_encoding='euc-jp')
    assert get_encoding(resp) == 'euc-jp'

# 分支5: chardet 解码失败，返回 None
def test_apparent_encoding_decode_error():
    resp = make_response(content=b'\x80\x81\x82', apparent_encoding='nonexistent-encoding')
    assert get_encoding(resp) is None

# 分支6: 所有方式都失败，返回 utf-8
def test_fallback_utf8():
    resp = make_response(content=b'<html><body>hello</body></html>', apparent_encoding=None)
    assert get_encoding(resp) == 'utf-8'

# content 含非法 UTF-8 字节时，decode 不抛异常但得到空串，最终 fallback 到 utf-8
def test_content_invalid_bytes_fallback():
    resp = make_response(
        content=b'\xff\xfe',
        text='<meta charset="latin-1">',
        apparent_encoding=None
    )
    assert get_encoding(resp) == 'utf-8'