#!/usr/bin/env python3
"""回溯 `byte[] bArr = new byte[n]; bArr[0]=-97; bArr[1]=-4; ...` 形式的数组，重建后解密。
这类是运行时逐元素填充，静态可还原当且仅当所有下标为常量且连续。"""
import os, re, sys, json, collections
sys.path.insert(0, "/root/workspace/rev")
from dexor import xor_decode

ROOT = "/root/workspace/rev/decompiled/sources"
DECL = re.compile(r'byte\[\]\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+byte\[\]\s*\{([^}]*)\}'
                  r'|byte\[\]\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+byte\[\]\s*\((\w+)\)')
FILL = re.compile(r'([A-Za-z_$][\w$]*)\[(\d+)\]\s*=\s*(-?\d+|Byte\.MIN_VALUE|Byte\.MAX_VALUE)')
CALL = re.compile(r'm2893\(\s*([A-Za-z_$][\w$]*)\s*,\s*new\s+byte\[\]\s*\{([^}]*)\}\s*\)')
CONST = {'Byte.MIN_VALUE': -128, 'Byte.MAX_VALUE': 127}

def rebuild(txt):
    """返回 var -> {index: value}，只保留从 0 连续填充的完整数组"""
    fills = collections.defaultdict(dict)
    for m in FILL.finditer(txt):
        var, idx, val = m.group(1), int(m.group(2)), m.group(3)
        v = CONST[val] if val in CONST else int(val)
        fills[var].setdefault(idx, v)
    out = {}
    for var, d in fills.items():
        n = len(d)
        if set(d.keys()) == set(range(n)):      # 必须 0..n-1 连续
            out[var] = ",".join(str(d[i]) for i in range(n))
    return out

def main():
    per_file = {}
    stats = collections.Counter()
    for dp, _, fs in os.walk(ROOT):
        for fn in fs:
            if not fn.endswith('.java'):
                continue
            p = os.path.join(dp, fn)
            txt = open(p, encoding='utf-8', errors='replace').read()
            if 'm2893(' not in txt:
                continue
            rel = os.path.relpath(p, ROOT)
            arrays = rebuild(txt)
            hits = []
            for m in CALL.finditer(txt):
                var, key = m.group(1), m.group(2)
                stats['call'] += 1
                body = arrays.get(var)
                if not body:
                    stats['no_rebuild'] += 1
                    continue
                s = xor_decode(body, key)
                if s:
                    hits.append((txt[:m.start()].count('\n') + 1, s))
                    stats['ok'] += 1
                else:
                    stats['decode_fail'] += 1
            if hits:
                per_file[rel] = hits
    json.dump({"per_file": per_file}, open("/root/workspace/rev/decrypted_runtime.json", "w"),
              ensure_ascii=False, indent=1)
    uniq = sorted({s for v in per_file.values() for _, s in v})
    print(f"变量调用点 {stats['call']} | 可重建并解密 {stats['ok']} | "
          f"无法重建 {stats['no_rebuild']} | 重建但解码失败 {stats['decode_fail']}")
    print(f"新解出类 {len(per_file)} | 去重字符串 {len(uniq)}")
    kt = [s for s in uniq if '.kt' in s]
    print(f"\n其中含源文件名线索: {len(kt)}")
    for s in kt[:25]:
        print("  ", s[:90])
    other = [s for s in uniq if '.kt' not in s]
    print(f"\n其他新串: {len(other)}")
    for s in other[:20]:
        print("  ", s[:90])

if __name__ == "__main__":
    main()
