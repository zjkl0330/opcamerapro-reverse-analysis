#!/usr/bin/env python3
"""统一字节数组解析：处理 jadx 输出的 Byte.MIN_VALUE / Byte.MAX_VALUE 常量形式。"""
import re

CONST = {'Byte.MIN_VALUE': -128, 'Byte.MAX_VALUE': 127}
TOKEN = re.compile(r'Byte\.MIN_VALUE|Byte\.MAX_VALUE|-?\d+')

def parse_bytes(src: str):
    """把 new byte[]{...} 的内容解析成 int 列表（有符号字节）。"""
    out = []
    for tok in TOKEN.findall(src):
        if tok in ('Byte.MIN_VALUE', 'Byte.MAX_VALUE'):
            out.append(CONST[tok])
        else:
            out.append(int(tok))
    return out

def xor_decode(data_src: str, key_src: str):
    data = [b & 0xFF for b in parse_bytes(data_src)]
    key  = [b & 0xFF for b in parse_bytes(key_src)]
    if not data or not key:
        return None
    raw = bytes((data[i] ^ key[i % len(key)]) for i in range(len(data)))
    try:
        s = raw.decode('utf-8')
    except UnicodeDecodeError:
        return None                      # 严格 UTF-8 失败即判不可信，不再 replace
    if not s or s != s.strip('\x00'):
        return None
    printable = sum(1 for c in s if 32 <= ord(c) < 127)
    if printable < len(s) * 0.85:
        return None
    return s

CALL = re.compile(
    r'm2893\(\s*new\s+byte\[\]\s*\{([^}]*)\}\s*,\s*new\s+byte\[\]\s*\{([^}]*)\}\s*\)')

def balanced(txt: str, open_idx: int, cap: int = 20000):
    depth = 1; i = open_idx; in_str = False; in_chr = False; esc = False
    while i < len(txt) and depth and i - open_idx < cap:
        c = txt[i]
        if in_str:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': in_str = False
        elif in_chr:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == "'": in_chr = False
        elif c == '"': in_str = True
        elif c == "'": in_chr = True
        elif c == '(': depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return txt[open_idx:i]
        i += 1
    return None

if __name__ == "__main__":
    # 自测：ModernHookEntry 里已知答案
    t = "new byte[]{0, 88, 79, 14, 111, -33, -67, -42, 31, 122, 99, 79, 47, -102, -126, -40, 43, 109, 126, 1, 67, -54, -90, -122, Byte.MAX_VALUE, 57}"
    k = "new byte[]{79, 8, 12, 111, 2, -70, -49, -73}"
    ds = t[t.index('{')+1:t.rindex('}')]; ks = k[k.index('{')+1:k.rindex('}')]
    print("自测:", repr(xor_decode(ds, ks)))
