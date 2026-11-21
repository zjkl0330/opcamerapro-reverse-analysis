#!/usr/bin/env python3
"""Meishe MS-LUT (.bin / .mslut) 容器读写 —— 从 OPCameraPro v3.1.22 静态逆向还原。

格式（全部小端）：
  +0x00  8B   magic  ".MS-LUT "（末尾一个空格）
  +0x08  u32  version      1 / 2 / 3
  +0x0c  u32  size         3D LUT 边长（16/17/20/21/32/33/64）
  +0x10  u32  flag         0 = uint8 RGB(3B/节点)；3 = float32 RGB(12B/节点)
  +0x14  u32  always_one   恒 1（App m1936 会校验 == 1）
  +0x18  u32  app_generated  App 生成的 custom LUT 恒为 1（m1936 校验 ==1）；
                          美图官方工具链产物为 0/24/152（含义未定，不影响读取）
  +0x1c  u32  ?            观测恒 0
  +0x20  u64  header       恒 48
  +0x28  u64  data_off     = 48 + size*4
  +0x30 起      axis 表    size 个 float32，等差，step = f32(1/(size-1))
  data_off 起    数据      size^3 个节点，索引 ((r*size + g)*size + b)*bytes_per_node
                          flag=0: 3×uint8（0..255）
                          flag=3: 3×float32（0.0..1.0，可略超 1）

轴生成存在两种 1 ULP 差异的写法：
  美图官方工具链： axis[i] = f32(i * f32(1/(size-1)))     ← 乘法
  App m1944 生成： axis[i] = f32(i / (size-1)f)           ← 除法（32³ 时 i=17,21,25,29 差 1ULP）
"""
import struct, math, os

MAGIC = b'.MS-LUT '
FLAG_U8, FLAG_F32 = 0, 3


def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def parse(buf):
    """返回 dict 或 None"""
    if len(buf) < 48 or buf[:8] != MAGIC:
        return None
    version, size = struct.unpack_from('<II', buf, 8)
    flag = struct.unpack_from('<I', buf, 16)[0]
    one14, f18 = struct.unpack_from('<II', buf, 20)
    # +0x20 header(u64)=48, +0x28 data_off(u64)=48+size*4, axis 从 +0x30 起
    header, data_off = struct.unpack_from('<QQ', buf, 32)
    axis_n = size
    axis = [struct.unpack_from('<f', buf, header + i * 4)[0] for i in range(axis_n)]
    per = 12 if flag == FLAG_F32 else 3
    n = size ** 3
    body = len(buf) - data_off
    return dict(version=version, size=size, flag=flag, one14=one14, f18=f18, header=header,
                data_off=data_off, axis=axis, per_node=per,
                nodes=n, body_bytes=body, expect=n * per,
                consistent=(body == n * per))


def read_lut(buf):
    """解出 float 网格，索引 ((r,g,b)) -> [R,G,B] in 0..1"""
    m = parse(buf)
    if not m or not m['consistent']:
        return None
    off = m['data_off']; size = m['size']
    out = []
    if m['flag'] == FLAG_F32:
        vals = struct.unpack_from(f'<{size**3*3}f', buf, off)
    else:
        vals = [b / 255.0 for b in buf[off:off + size**3 * 3]]
    for i in range(size**3):
        out.append(vals[i*3:i*3+3])
    return m, out


def build(size, rgb_flat, version=1, flag=FLAG_U8, axis_mul=True, f18=1):
    """rgb_flat: 长度 size^3*3 的 0..1 float 序列，索引 ((r*size+g)*size+b)*3"""
    assert len(rgb_flat) == size ** 3 * 3, len(rgb_flat)
    header = 48
    data_off = header + size * 4
    per = 12 if flag == FLAG_F32 else 3
    total = data_off + (size ** 3) * per
    buf = bytearray(total)
    buf[0:8] = MAGIC
    struct.pack_into('<II', buf, 8, version, size)
    struct.pack_into('<I', buf, 16, flag)
    struct.pack_into('<I', buf, 20, 1)
    struct.pack_into('<I', buf, 24, f18)
    struct.pack_into('<QQ', buf, 32, header, data_off)
    step = f32(1.0 / (size - 1))
    for i in range(size):
        v = f32(i * step) if axis_mul else f32(f32(i) / f32(size - 1.0))
        struct.pack_into('<f', buf, 48 + i * 4, v)
    if flag == FLAG_F32:
        for i, v in enumerate(rgb_flat):
            struct.pack_into('<f', buf, data_off + i * 4, v)
    else:
        for i, v in enumerate(rgb_flat):
            q = int(round(min(max(v, 0.0), 1.0) * 255))
            buf[data_off + i] = max(0, min(255, q))
    return bytes(buf)


def resample(src_size, src, dst_size=32):
    """三线性重采样到 dst_size（复刻 App m1944 行为：非 32³ 一律重采样）"""
    if src_size == dst_size:
        return src, 1
    n1 = src_size - 1
    out = [0.0] * (dst_size ** 3 * 3)
    def at(i, j, k):
        o = ((i * src_size + j) * src_size + k) * 3
        return src[o], src[o+1], src[o+2]
    step = f32(1.0 / (dst_size - 1))
    for bi in range(dst_size):
        x = f32(bi * step) * n1
        f0 = int(math.floor(x)); f1 = min(f0 + 1, n1); fx = x - f0
        for gi in range(dst_size):
            y = f32(gi * step) * n1
            g0 = int(math.floor(y)); g1 = min(g0 + 1, n1); fy = y - g0
            for ri in range(dst_size):
                z = f32(ri * step) * n1
                h0 = int(math.floor(z)); h1 = min(h0 + 1, n1); fz = z - h0
                c = [at(p, q, r) for p in (f0, f1) for q in (g0, g1) for r in (h0, h1)]
                o = (bi * dst_size * dst_size + gi * dst_size + ri) * 3
                for ch in range(3):
                    a = c[0][ch] + (c[4][ch] - c[0][ch]) * fx
                    b = c[1][ch] + (c[5][ch] - c[1][ch]) * fx
                    d = c[2][ch] + (c[6][ch] - c[2][ch]) * fx
                    e = c[3][ch] + (c[7][ch] - c[3][ch]) * fx
                    lo = a + (b - a) * fy
                    hi = d + (e - d) * fy
                    out[o + ch] = lo + (hi - lo) * fz
    return out, 1


def parse_cube(text):
    """解析标准 .cube，返回 (size, float 列表, domain_min, domain_max)"""
    size = None; dmin = (0.0, 0.0, 0.0); dmax = (1.0, 1.0, 1.0); vals = []
    for raw in text.splitlines():
        ln = raw.split('#')[0].strip()
        if not ln or ln.upper().startswith('TITLE'):
            continue
        u = ln.upper()
        if u.startswith('LUT_3D_SIZE'):
            size = int(ln.split(None, 1)[1].strip())
        elif u.startswith('DOMAIN_MIN'):
            dmin = tuple(float(x) for x in ln.split()[1:4])
        elif u.startswith('DOMAIN_MAX'):
            dmax = tuple(float(x) for x in ln.split()[1:4])
        else:
            parts = ln.split()
            if len(parts) == 3:
                vals.extend(float(p) for p in parts)
    return size, vals, dmin, dmax


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        b = open(sys.argv[1], 'rb').read()
        m = parse(b)
        print(m if m else '非 MS-LUT')
    else:
        print(__doc__)
