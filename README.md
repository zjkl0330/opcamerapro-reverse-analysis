# OPCameraPro 静态逆向分析

> 对 Android Xposed/LSPosed 相机增强模块 `com.tlsu.opluscamerapro`（OPCameraPro）v3.1.10 / v3.1.22 的**纯静态**逆向分析成果。
> 全过程在本地沙箱完成，未接触任何真实设备、未运行目标代码、未联网交互。

## 法律与安全声明

- 本项目**不包含**任何目标 APK、`.so` 二进制、Magisk 模块包或许可证文件。
- 仓库内所有二进制相关结论均来自对公开分发样本的静态读取（jadx / capstone / 自研 ELF 解析）。
- 文档中出现的 RSA **公钥**来自被分析产物自身，属于分析结论的一部分；对应的私钥不在本文档范围内，也无法由本文档推导。
- 分析目的限于格式互操作研究与安全评估。使用者需自行遵守目标软件许可协议与当地法律。

## 目录结构

```
docs/       分析报告（按轮次累积，§编号全局连续）
  HANDOVER.md          第一轮交接文档：身份识别、断裂点、踩坑记录
  DEVICE_MATRIX.md     机型适配矩阵（14 个机型代号 + 判定链 + 实机影响分析）
  DEXKIT_TARGETS.md    83 个 DexKit 特征串，分 17 组
  VERSION_DIFF.md      v3.1.10 → v3.1.22 真实差异
  FINDINGS6.md         任务 6 全量报告 §1-25（native 层 / 挂载机制 / 激活体系）
  FINDINGS7.md         第五、六轮 §26-42（GLSL 提取 / RUS 格式 / MS-LUT 破解）
tools/      可复用脚本（Python 3，无第三方依赖，capstone 除外）
  dexor.py             循环 XOR 字符串解密核心
  decrypt_strings.py   全量字符串批量解密
  decrypt_runtime_final.py  作用域感知数组还原（处理 jadx 三类伪影）
  mslut.py             Meishe MS-LUT 容器读写库（格式已 100% 还原）
  elfdis.py            极简 ELF64/ARM64 反汇编器（capstone + 自解析符号表）
  license_algo.py      激活校验算法参考实现（仅用于自检，无法生成有效码）
  extract_dexkit.py    DexKit 特征串提取
data/       解密产物（JSON）
  decrypted_v4.json    5,858 个唯一解密串
  decrypted_runtime_ultimate.json  运行时数组还原结果
  dexkit_targets.json  特征串 → 宿主类映射
shaders/    从 native 库提取的 267 个 GLSL ES 3.1 着色器
  all.glsl             完整源码（5.5 MB，spirv-cross 反编译产物）
  index.json           偏移 / 阶段 / 字段索引
  api.json             uniform 与函数签名聚合
```

## 核心结论速览

### 1. 项目身份
真实上游仓库为 Gitee `bugme7/OPCameraPro`（作者署名 **TimelessU**），GitHub 上的 `Xposed-Modules-Repo/com.tlsu.opluscamerapro` 是 LSPosed 官方模块发布仓库。代码经 R8 混淆，类名/方法名使用**卢恩文字**（ᛱᛲᛳ…）而非传统短名。

### 2. v3.1.22 的实质变化（不是框架换代）
- **滤镜素材外置**：30.7 MB LUT + 两个美图 `.so` 从 APK `assets/` 迁到 Magisk 模块挂载分发（APK 24.9 MB → 8.6 MB）
- **新增伪超 HDR**：`PseudoUltraHdrNative` 类 + 8 个 JNI 入口
- **native 体积 6.7 KB → 904.8 KB 的真相**：静态链入 **libjpeg-turbo 3.1.0**（含 NEON SIMD），不是算法变复杂
- 早期「架构迁移到 libxposed」的判断是错的 —— v3.1.10 就已经是 libxposed modern 架构

### 3. 两套独立的 HDR 路径
| 路径 | 位置 | 机制 |
|---|---|---|
| 图库侧 | `libUhdrUtils-jni.so` | OPlus 官方 `oplus_uhdr_mask2map`，输出标准 Ultra HDR gainmap（HEIF + `hdrgm:` XMP） |
| 相机侧 | `libmsnativefilter.so` | 美图 Nv 引擎，`*2446A` 系列 = **ITU-R BT.2446** SDR↔HDR 互转 |

关键实锤：`lut3D2446A` 把颜色先从 HLG 域反变换到线性域、采样 3D LUT、再变换回 HLG 域 —— 这是「美图滤镜能作用在 HDR 管线上」的实现方式。

### 4. MS-LUT 容器格式（已字节级验证）
```
+0x00  8B   magic  ".MS-LUT "（末尾一个空格）
+0x08  u32  version / size / flag / always_one / app_generated
+0x20  u64  header(=48) / data_off(=48+size*4)
+0x30       axis 表：size 个 float32 等差，step = f32(1/(size-1))
+data_off   size³ 节点 × (3×uint8 | 3×float32)
```
`tools/mslut.py` 对仓库内全部 108 个 LUT 做 parse→read→build 往返，**108/108 字节级完全一致**。

### 5. 机型与授权
- 硬屏蔽机型是 **PHK110 + CPH2487 两个**（命中则跳过全部 hook 注入）
- 设备指纹**不是 ANDROID_ID**，而是序列号三级回退：`persist.gsm.serial` → `vendor.gsm.serial` → `ro.serialno`
- `machineHash = SHA-256(序列号 + 盐)`，盐从双层混淆中还原
- 授权走 `SHA256withRSA` 验签，公钥内置于 APK，私钥不在产物内
- 能力门取决于许可证的 `tier == "advanced"`，**与机型无关**

### 6. 方法论：不需要 Ghidra
本次全部结论在**未安装 Ghidra / Hopper / IDA** 的前提下得出：

| 需求 | 方案 |
|---|---|
| Java 层 | `jadx --show-bad-code --no-inline-methods` 全量重跑，未反编译文件 352 → 15 |
| 运行时填充数组 | 作用域感知还原脚本，420 个调用点解出 370（88%），剩 3 个是 jadx 控制流缺陷 |
| native 函数 | `pip install capstone` + `tools/elfdis.py`（60 行 ELF64 自解析） |
| 着色器 | 直接扫 `.rodata` 的 zlib 流，提取 267 个 GLSL 源码 5.5 MB |
| 二进制格式 | 自写 round-trip 字节级比对定位未知字段 |

## 复现

```bash
# 解密全部字符串（需先自行准备样本 APK 并用 jadx 反编译）
python3 tools/decrypt_strings.py

# 作用域感知数组还原
python3 tools/decrypt_runtime_final.py

# 读写 MS-LUT
python3 -c "import sys; sys.path.insert(0,'tools'); import mslut; print(mslut.parse(open('x.bin','rb').read()))"

# 反汇编 ELF64/ARM64 函数
pip install capstone
python3 tools/elfdis.py <lib.so> '<符号正则>' [指令数]
```

## 统计

| 指标 | 数值 |
|---|---|
| 反编译 Java 类 | 3,841 |
| 解密唯一字符串 | 5,858 |
| 运行时数组调用点还原率 | 370 / 420（88%） |
| DexKit 特征串验证 | 83 / 83 |
| 提取 GLSL 着色器 | 267 个（5.5 MB） |
| MS-LUT 往返验证 | 108 / 108 字节一致 |
| 报告篇幅 | 42 节 |
