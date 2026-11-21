#!/usr/bin/env python3
"""按 Set 字段分组还原机型/黑名单集合：提取 `Set fNNNN = ...m898(new String[]{ m2893(..), m2893(..) })`"""
import re, sys, os, json, collections

def dec(ds, ks):
    d=[int(x)&0xFF for x in re.findall(r'-?\d+',ds)]
    k=[int(x)&0xFF for x in re.findall(r'-?\d+',ks)]
    if not d or not k: return None
    b=bytes((d[i]^k[i%len(k)]) for i in range(d and len(d) or 0))
    s=b.decode('utf8','replace')
    return s if s.strip() and sum(1 for c in s if 32<=ord(c)<127)>=len(s)*0.6 else None

# 一个 m898(new String[]{ ... }) 里所有 m2893 调用
INNER = re.compile(r'm2893\(\s*new\s+byte\[\]\s*\{([^}]*)\}\s*,\s*new\s+byte\[\]\s*\{([^}]*)\}\s*\)')
FIELD = re.compile(
    r'(?:public\s+)?static\s+final\s+(?:Set|HashSet|Collections\.UnmodifiableSet)[^=]*?'
    r'(f\d{4})\s*=\s*[^;]*?m898\(\s*new\s+String\[\]\s*\{(.*?)\}\s*\)\s*;',
    re.S)
VAR = re.compile(r'(?:final\s+)?(?:Set|Collection)<String>\s+(f?\w+)\s*=\s*[^;]*?m898\(\s*new\s+String\[\]\s*\{(.*?)\}\s*\)\s*;', re.S)

def groups(path):
    txt=open(path,encoding='utf-8',errors='replace').read()
    out=[]
    for m in list(FIELD.finditer(txt))+list(VAR.finditer(txt)):
        name, body = m.group(1), m.group(2)   # FIELD/VAR 均为 组1=字段名 组2=集合体
        vals=[v for a,b in INNER.findall(body) if (v:=dec(a,b))]
        if vals: out.append((name, txt[:m.start()].count('\n')+1, vals))
    return out

if __name__=="__main__":
    for p in sys.argv[1:]:
        g=groups(p)
        if not g: continue
        print(f"\n########## {os.path.basename(p)}")
        for name,line,vals in g:
            print(f"  [{name}] L{line}  ({len(vals)} 项)")
            for v in vals: print(f"       {v}")
