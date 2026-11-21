#!/usr/bin/env python3
"""作用域感知 XOR 数组还原：处理 jadx 的 new byte[N]/new byte[]{}/new byte[1]+变量下标三种形态。
202 个变量调用点解出 180（89%）。"""
import os, re, collections, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dexor import xor_decode
ROOT = "/root/workspace/rev/decompiled/sources"
DECL1   = re.compile(r'byte\[\]\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+byte\[\s*1\s*\]')
DECLLIT = re.compile(r'byte\[\]\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+byte\[\]\s*\{([^}]*)\}')
DECLNV  = re.compile(r'byte\[\]\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+byte\[\s*(\d+|[a-zA-Z_$][\w$]*)\s*\]')
FILL    = re.compile(r'^\s*([A-Za-z_$][\w$]*)\[(\d+|[a-zA-Z_$][\w$]*)\]\s*=\s*(-?\d+|Byte\.MIN_VALUE|Byte\.MAX_VALUE)\s*;', re.M)
CALLD   = re.compile(r'm2893\(\s*([A-Za-z_$][\w$]*)\s*,\s*new\s+byte\[\]\s*\{([^}]*)\}\s*\)')
CALLV   = re.compile(r'm2893\(\s*new\s+byte\[\]\s*\{([^}]*)\}\s*,\s*([A-Za-z_$][\w$]*)\s*\)')
CONST = {'Byte.MIN_VALUE': -128, 'Byte.MAX_VALUE': 127}
def pv(t): return CONST[t] if t in CONST else int(t)

def main():
    cat = collections.Counter(); solved = collections.defaultdict(list)
    for dp, _, fs in os.walk(ROOT):
        for fn in fs:
            if not fn.endswith('.java'): continue
            p = os.path.join(dp, fn)
            txt = open(p, encoding='utf-8', errors='replace').read()
            if 'm2893(' not in txt: continue
            rel = os.path.relpath(p, ROOT)
            decls = collections.defaultdict(list)
            for m in DECL1.finditer(txt):   decls[m.group(1)].append((m.start(), 'one', None))
            for m in DECLLIT.finditer(txt): decls[m.group(1)].append((m.start(), 'lit', m.group(2)))
            for m in DECLNV.finditer(txt):
                if not any(d0 == m.start() for d0, _, _ in decls[m.group(1)]):
                    decls[m.group(1)].append((m.start(), 'n', m.group(2)))
            evs = [(m.start(), m.group(1), m.group(2), pv(m.group(3))) for m in FILL.finditer(txt)]
            def build(var, callpos):
                ds = [d for d in decls.get(var, []) if d[0] < callpos]
                if not ds: return None
                dpos, kind, payload = max(ds, key=lambda x: x[0])
                if kind == 'lit':
                    try: return [pv(t) for t in re.findall(r'Byte\.MIN_VALUE|Byte\.MAX_VALUE|-?\d+', payload)]
                    except Exception: return None
                seg = [e for e in evs if dpos < e[0] < callpos and e[1] == var]
                if not seg: return None
                if kind == 'one': return [seg[0][3]]          # 单字节：下标恒 0（jadx 伪影）
                d = {int(e[2]): e[3] for e in seg if e[2].isdigit()}
                if payload.isdigit():
                    n = int(payload)
                    return [d[i] for i in range(n)] if set(d) == set(range(n)) else None
                if set(d) == set(range(len(d))): return [d[i] for i in range(len(d))]
                return None
            for m in CALLD.finditer(txt):
                a = build(m.group(1), m.start())
                if a is None: cat['datavar_unbuildable'] += 1; continue
                s = xor_decode(",".join(map(str, a)), m.group(2))
                if s: cat['datavar_SOLVED'] += 1; solved[rel].append(s)
                else: cat['datavar_decode_fail'] += 1
            for m in CALLV.finditer(txt):
                a = build(m.group(2), m.start())
                if a is None: cat['keyvar_unbuildable'] += 1; continue
                s = xor_decode(m.group(1), ",".join(map(str, a)))
                if s: cat['keyvar_SOLVED'] += 1; solved[rel].append(s)
                else: cat['keyvar_decode_fail'] += 1
    tot = cat['datavar_SOLVED'] + cat['keyvar_SOLVED']
    allc = tot + cat['datavar_decode_fail'] + cat['keyvar_decode_fail'] + cat['datavar_unbuildable'] + cat['keyvar_unbuildable']
    uniq = sorted({s for v in solved.values() for s in v})
    print("=== 变量调用点还原 ===")
    for k, v in cat.most_common(): print(f"  {k}: {v}")
    print(f"\n总 {allc} | 解出 {tot} ({100*tot//max(allc,1)}%) | 唯一串 {len(uniq)}")
    out = "/root/workspace/rev/decrypted_runtime_final.json"
    json.dump({"per_file": {k: sorted(set(v)) for k, v in solved.items()},
               "summary": {"solved_call_sites": tot, "total_variable_call_sites": allc, "unique_strings": len(uniq)}},
              open(out, "w"), ensure_ascii=False, indent=1)
    print("写", out)

if __name__ == "__main__":
    main()
