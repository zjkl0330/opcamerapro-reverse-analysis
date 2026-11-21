#!/usr/bin/env python3
"""极简 ELF64 arm64 反汇编器（capstone + 自解析符号表），无需 Ghidra/rizin。"""
import struct, sys, re
from capstone import *
from capstone.arm64 import *

SHT_SYMTAB, SHT_DYNSYM, SHT_STRTAB = 2, 11, 3
class ELF:
    def __init__(self, path):
        self.d = open(path,'rb').read()
        assert self.d[:4]==b'\x7fELF' and self.d[4]==2, "need ELF64"
        e_shoff, = struct.unpack_from('<Q', self.d, 0x28)
        e_shentsize, e_shnum = struct.unpack_from('<HH', self.d, 0x3a)
        self.sections=[]
        for i in range(e_shnum):
            o=e_shoff+i*e_shentsize
            name,typ,flags,addr,off,size,link,info,align,entsize = struct.unpack_from('<IIQQQQIIQQ', self.d, o)
            self.sections.append(dict(name=name,typ=typ,addr=addr,off=off,size=size,link=link,entsize=entsize))
        # symtab（优先 .symtab，退回 .dynsym）
        self.symbols={}
        for st in [s for s in self.sections if s['typ'] in (SHT_SYMTAB,SHT_DYNSYM)]:
            strtab=self.sections[st['link']]
            n=st['size']//max(st['entsize'],1) or (st['size']//24)
            for i in range(n):
                o=st['off']+i*st['entsize']
                nm,info,other,shndx = struct.unpack_from('<IBBH', self.d, o)
                value,size = struct.unpack_from('<QQ', self.d, o+8)
                if not value: continue
                end=self.d.index(b'\x00', strtab['off']+nm)
                sname=self.d[strtab['off']+nm:end].decode('utf8','replace')
                if sname: self.symbols.setdefault(value, (sname,size))
        self.base=self.sections[0]['addr'] if self.sections else 0
    def sec_by_addr(self, addr):
        for s in self.sections:
            if s["typ"]==1 and s['addr']<=addr<s['addr']+s['size']: return s  # SHT_PROGBITS
        return None
    def read(self, addr, n):
        s=self.sec_by_addr(addr)
        if not s: return b''
        off=s['off']+(addr-s['addr'])
        return self.d[off:off+n]
    def disasm(self, addr, nbytes=2048, maxi=400):
        md=Cs(CS_ARCH_ARM64, CS_MODE_ARM); md.detail=True
        out=[]
        buf=self.read(addr,nbytes)
        for ins in md.disasm(buf, addr):
            nm=self.symbols.get(ins.address)
            out.append(f"  0x{ins.address:x}: {ins.mnemonic:<9} {ins.op_str}" + (f"   ; {nm[0]}" if nm else ""))
            if len(out)>=maxi: break
        return out
    def find(self, name_pat):
        rx=re.compile(name_pat)
        return [(v,s[0],s[1]) for v,s in self.symbols.items() if rx.search(s[0])]

if __name__=='__main__':
    e=ELF(sys.argv[1])
    print(f"符号数 {len(e.symbols)}")
    if len(sys.argv)>2:
        for v,n,sz in e.find(sys.argv[2])[:20]:
            print(f"\n### {n}  @0x{v:x} size={sz}")
            if len(sys.argv)>3:
                for l in e.disasm(v, min(sz or 512, 900), int(sys.argv[3])): print(l)
