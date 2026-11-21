#!/usr/bin/env python3
"""提取 DexKit 查询里的特征字符串（usingStrings / searchClasses 的加密参数）"""
import os, re, sys, collections, json

ROOT="/root/workspace/rev/decompiled/sources"
def dec(ds,ks):
    d=[int(x)&0xFF for x in re.findall(r'-?\d+',ds)]
    k=[int(x)&0xFF for x in re.findall(r'-?\d+',ks)]
    if not d or not k: return None
    b=bytes((d[i]^k[i%len(k)]) for i in range(len(d)))
    try: s=b.decode('utf-8')
    except UnicodeDecodeError: s=b.decode('utf-8','replace')
    ok=sum(1 for c in s if 32<=ord(c)<127)
    return s if s.strip() and ok>=len(s)*0.7 else None

M2893=re.compile(r'm2893\(\s*new\s+byte\[\]\s*\{([^}]*)\}\s*,\s*new\s+byte\[\]\s*\{([^}]*)\}\s*\)')
CALL=re.compile(r'\.(usingStrings|usingEqStrings|searchClasses|searchFields|usingStringsCount)\s*\(')

def balanced(txt, open_idx, cap=6000):
    """从 '(' 之后按括号深度取到匹配的 ')'，跳过字符串/字符字面量"""
    depth=1; i=open_idx; in_str=False; in_chr=False
    while i < len(txt) and depth and i-open_idx < cap:
        c=txt[i]
        if in_str:
            if c=='\\': i+=2; continue
            if c=='"': in_str=False
        elif in_chr:
            if c=='\\': i+=2; continue
            if c=="'": in_chr=False
        elif c=='"': in_str=True
        elif c=="'": in_chr=True
        elif c=='(': depth+=1
        elif c==')':
            depth-=1
            if depth==0: return txt[open_idx:i]
        i+=1
    return None

out=collections.defaultdict(list)
for dp,_,fs in os.walk(ROOT):
    for fn in fs:
        if not fn.endswith('.java'): continue
        if 'luckypray' in dp: continue          # DexKit 库自身跳过
        p=os.path.join(dp,fn)
        txt=open(p,encoding='utf-8',errors='replace').read()
        if 'usingStrings' not in txt and 'searchClasses' not in txt: continue
        rel=os.path.relpath(p,ROOT)
        for m in CALL.finditer(txt):
            kind=m.group(1)
            body=balanced(txt, m.end())
            if not body: continue
            vals=[v for a,b in M2893.findall(body) if (v:=dec(a,b))]
            # 也收明文常量
            vals+= [x.strip('"') for x in re.findall(r'"([^"\n]{3,60})"',body) if x.strip('"')]
            for v in dict.fromkeys(vals):
                if v and v not in out[(rel,kind)]:
                    out[(rel,kind)].append(v)

json.dump({f"{k[0]}|{k[1]}":v for k,v in out.items()},
          open("/root/workspace/rev/dexkit_targets.json","w"),ensure_ascii=False,indent=1)
print(f"命中类: {len(set(k[0] for k in out))}  调用组: {len(out)}")
tot=sum(len(v) for v in out.values())
print(f"特征串总数: {tot}")
for (rel,kind),vals in sorted(out.items())[:14]:
    print(f"\n--- {rel}  [{kind}]")
    for v in vals[:6]: print(f"     {v!r}")
