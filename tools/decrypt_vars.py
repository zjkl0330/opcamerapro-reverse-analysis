#!/usr/bin/env python3
"""补漏：处理 m2893(<var>, new byte[]{...}) 形式，回溯同方法内 var 的数组赋值。
价值：这类调用承载 Kotlin 协程调试串（CC(remember):XxxScreen.kt#hash），可还原原始源文件名。"""
import os, re, json, collections, sys
sys.path.insert(0, "/root/workspace/rev")
from dexor import parse_bytes, xor_decode

ROOT = "/root/workspace/rev/decompiled/sources"

# 直接内联两数组
INLINE = re.compile(r'm2893\(\s*new\s+byte\[\]\s*\{([^}]*)\}\s*,\s*new\s+byte\[\]\s*\{([^}]*)\}\s*\)')
# 变量数据 + 内联 key
VARDATA = re.compile(r'm2893\(\s*([A-Za-z_$][\w$]*)\s*,\s*new\s+byte\[\]\s*\{([^}]*)\}\s*\)')
# 变量赋值：byte[] bArr = {..} / bArr = new byte[]{..} / bArr2 = {...}
ASSIGN = re.compile(
    r'(?:byte\[\]\s*)?([A-Za-z_$][\w$]*)\s*=\s*(?:new\s+byte\[\]\s*)?\{([^}]*)\}')

def collect(txt):
    """返回 (内联结果, 变量回溯结果, 统计)"""
    inline = []
    for m in INLINE.finditer(txt):
        s = xor_decode(m.group(1), m.group(2))
        if s: inline.append((txt[:m.start()].count('\n') + 1, s))

    # 建 var -> [(行号, 字节串)] 映射；同名变量在多方法复用，按行距就近取候选，避免张冠李戴
    env = collections.defaultdict(list)
    for m in ASSIGN.finditer(txt):
        env[m.group(1)].append((txt[:m.start()].count('\n') + 1, m.group(2)))

    resolved = []
    ambiguous = 0
    unresolved = 0
    for m in VARDATA.finditer(txt):
        var, key = m.group(1), m.group(2)
        line = txt[:m.start()].count('\n') + 1
        cands = env.get(var, [])
        if not cands:
            unresolved += 1
            continue
        # 就近优先：行距最小的赋值最可能属于同一方法
        cands = sorted(cands, key=lambda t: abs(t[0] - line))
        got = None
        for _, body in cands[:3]:
            s = xor_decode(body, key)
            if s:
                got = s
                break
        if got:
            resolved.append((line, got))
            if len(cands) > 1:
                ambiguous += 1
        else:
            unresolved += 1
    return inline, resolved, unresolved, ambiguous

def main():
    per_file = {}
    stats = collections.Counter()
    for dp, _, fs in os.walk(ROOT):
        for fn in fs:
            if not fn.endswith('.java'):
                continue
            p = os.path.join(dp, fn)
            txt = open(p, encoding='utf-8', errors='replace').read()
            if 'm2893' not in txt:
                continue
            rel = os.path.relpath(p, ROOT)
            inline, resolved, unresolved, ambiguous = collect(txt)
            stats['inline'] += len(inline)
            stats['var_resolved'] += len(resolved)
            stats['var_unresolved'] += unresolved
            stats['var_ambiguous'] += ambiguous
            allhits = sorted(inline + resolved)
            if allhits:
                per_file[rel] = allhits
    json.dump({"per_file": per_file},
              open("/root/workspace/rev/decrypted_v3.json", "w"),
              ensure_ascii=False, indent=1)
    uniq = {s for v in per_file.values() for _, s in v}
    print(f"内联解密 {stats['inline']} | 变量回溯成功 {stats['var_resolved']} "
          f"(其中多候选 {stats['var_ambiguous']}) | 仍无法解析 {stats['var_unresolved']}")
    print(f"含串类 {len(per_file)} | 去重字符串 {len(uniq)}")
    # Kotlin 协程调试串有强格式特征，可作为「回溯正确」的自证
    kt = sorted(s for s in uniq if re.search(r'^CC\(remember\):[\w$]+\.kt#\w+$', s))
    loose = sorted(s for s in uniq if '.kt' in s and s not in kt)
    print(f"\n严格匹配 Kotlin 调试串（自证正确）: {len(kt)}")
    for s in kt[:15]:
        print("  ", s[:80])
    print(f"\n含 .kt 但格式不严格（可能受多候选影响）: {len(loose)}")
    for s in loose[:10]:
        print("  ", s[:80])

if __name__ == "__main__":
    main()
