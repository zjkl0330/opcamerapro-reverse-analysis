#!/usr/bin/env python3
"""批量还原 OPCameraPro 的循环 XOR 混淆字符串。
解密器：AbstractC1256.m2893(byte[] data, byte[] key) → data[i] ^= key[i % len(key)]
"""
import os, re, sys, json, collections

ROOT = "/root/workspace/rev/decompiled/sources"
# 匹配 m2893(new byte[]{...}, new byte[]{...})，允许任意调用者类名（R8 会重命名）
CALL = re.compile(
    r'\bm2893\(\s*new\s+byte\[\]\s*\{([^}]*)\}\s*,\s*new\s+byte\[\]\s*\{([^}]*)\}\s*\)')
NUM = re.compile(r'-?\d+')

def decode(data_src, key_src):
    try:
        data = [int(x) & 0xFF for x in NUM.findall(data_src)]
        key = [int(x) & 0xFF for x in NUM.findall(key_src)]
    except ValueError:
        return None
    if not data or not key:
        return None
    out = bytes((data[i] ^ key[i % len(key)]) for i in range(len(data)))
    try:
        s = out.decode('utf-8')
    except UnicodeDecodeError:
        s = out.decode('utf-8', 'replace')
    # 过滤明显不是字符串的噪声：可打印比例过低
    printable = sum(1 for c in s if 32 <= ord(c) < 127 or c in '\n\t')
    if not s or printable / max(len(s), 1) < 0.6:
        return None
    return s

def main():
    per_file = {}
    all_hits = collections.Counter()
    files = 0
    for dirpath, _, filenames in os.walk(ROOT):
        for fn in filenames:
            if not fn.endswith('.java'):
                continue
            p = os.path.join(dirpath, fn)
            try:
                txt = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            files += 1
            found = []
            for m in CALL.finditer(txt):
                s = decode(m.group(1), m.group(2))
                if s is None:
                    continue
                line = txt[:m.start()].count('\n') + 1
                found.append((line, s))
                all_hits[s] += 1
            if found:
                rel = os.path.relpath(p, ROOT)
                per_file[rel] = found
    print(f"扫描 Java 文件: {files}")
    print(f"含加密串的类: {len(per_file)}")
    print(f"解密实例: {sum(len(v) for v in per_file.values())}")
    print(f"去重字符串: {len(all_hits)}")
    json.dump({"per_file": per_file}, open("/root/workspace/rev/decrypted.json", "w"),
              ensure_ascii=False, indent=1)
    return per_file, all_hits

if __name__ == "__main__":
    main()
