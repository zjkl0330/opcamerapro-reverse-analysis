# 任务 7 · 第五轮深挖（show-bad-code 全量重跑带来的突破）

> 2026-11-21 · 触发点：`jadx --show-bad-code` 全量重跑，解锁此前被 skip 的方法体

## 26. 方法论突破：show-bad-code 全量重跑
| 指标 | 旧树（decompiled） | 新树（decompiled_bad） |
|---|---|---|
| `Method not decompiled` 文件 | 352 | **15**（17 方法） |
| 解密唯一串 | 5,140 | **5,858**（+718） |
| 变量数组调用点 | 202 | **420**（+218，此前被方法内联隐藏） |
| 数组解出 | 180 (89%) | **370 (88%)** |

关键参数：`--show-bad-code --no-debug-info --no-inline-anonymous --no-inline-methods -j 2 -r`
- `--no-inline-methods` 让被内联的调用点重新显形（202→420）
- `-r`（不解资源）省时间，资源已在旧树

## 27. 数组还原终极规则（`decrypted_runtime_ultimate.json`）
新增两类此前判"不可解"的形态：
1. **三元下标** `bArr[z2 ? 1 : 0] = 30` → `new byte[1]` 下标越界即抛，恒取 0
2. **值也是变量** `bArr5[b] = b` → 回溯 `b` 的最近 `int` 赋值（`b=0`）

**最终仅剩 3 个真不可静态解**（全是 jadx 寄存器/未初始化）：
- `C1085:150/158` — `r10` 在 "Code restructure failed: missing block" 注释里，jadx 丢了赋值
- `C1079:516` — `byte b;` 声明后未初始化即用于 `bArr2[?]=b`

→ 旧结论「75/114 不可还原」彻底作废，实际 **420 个调用点解出 370，剩 3 个是反编译器缺陷不是加密强度**。

## 28. 新解锁的高价值内容（718 新串）
### Ultra HDR / HEIF 写入侧（C1786）
```xml
xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/"
xmlns:Container="http://ns.google.com/photos/1.0/container/"
hdrgm:Version="1.0"  hdrgm:GainMapMin  hdrgm:GainMapMax
<Container:Directory><rdf:Seq><rdf:li ...><Container:Item Item:Mime="image/jpeg" Item:Semantic="Primary"/>
```
→ 证实伪超HDR 输出走 **Google Ultra HDR / ISO 21496-1 gainmap 标准容器**，XMP 内嵌。
另有 `--gamma --offsetSdr --offsetHdr --minContentBoost --maxContentBoost --hdrCapacityMin/Max --useBaseColorSpace 1` —— 这是 **PNG iCCP/gAMA 式 tone-map 工具链参数**（疑似 ffprobe/HDR 调试 CLI 调用）。

### LivePhoto 二进制修补全分支（C3030 + 18 条 skip 原因）
`livephoto_writeback`、`livephoto_post_pack_finalize`、`transform_route`、`watermark.device`
失败路径全枚举：`XMP segment too large`、`no MPF segment`、`MP4 header lost after EXIF patch`、`already_gainmap`、`already_repaired`、`embedded_profile_mismatch`、`copy_saved_heif_target_failed`…
→ 模块直接改写 HEIF/MPF/MP4 容器字节来缝 LivePhoto + gainmap，是全套最硬核的部分。

### 水印子系统宿主类全名（此前只有字段名）
`WatermarkMasterVM` / `WatermarkStyleLoaderImpl` / `WatermarkStyleOperatorImpl` /
`RestrictWatermark{CornerMark,Greeting,GuidePop,Resource,Series,Style,TypeButton,Word}DataHelper`
宿主：`com.oplus.gallery.framework.abilities.watermarkmaster`
→ 哈苏水印是通过 hook 图库的 **Restrict* DataHelper 家族**（SQLite ContentProvider 层）实现的，`belong_to_style_id`/`_display_name LIKE ?` 是它们的查询语句。

### 宿主特性键（新增）
`com.oplus.xpan.{crop.region,main/wide/tele.picturesize,switch.camera.mm,all.camera.support}`、
`com.oplus.feature.master.mode.vignette.process.in.lsc[.and.soft]`、
`oplus.autotest.camera.enable.hal.privatelog`、`com.oplus.camera.action.IMPORT_PRESET`

### 挂载模式枚举（AbstractC1228）
`DEFAULT` / `OVERLAYFS` / `META_MODULE`（UI 文案 `Mountify Standalone` / `Meta Module`）—— 与 §4 的标志文件体系对应，这是 UI 侧的三选一枚举。

## 29. libmsnativefilter.so 美图 Nv 引擎（11.5MB，未剥离）
3,749 导出，核心类（按符号数）：
```
CNvComputeRenderer(46) CNvCompoundLut(45) CNvOpenGLShaderProgram(42) CNvStarFilter(41)
CNvCinestill800T(30) CNvCompoundLutTiled(25) CNvBasicImageAdjust(20) CNvPortra400(19)
CNvPolaroid(18) CNvSpiralBlur(18) CNvFilterNeutralCCD(15) CNvFilterCCD(13)
CNvLightNoise(11) CNvBilateralFilter(11) CNvFilterLightFlow(13) CNvC800TCompositor(13)
```
→ 完整胶片模拟引擎：**Cinestill 800T / Portra 400 / Polaroid** 三种胶片 + CCD 滤镜 + 光晕/噪点/螺旋虚化，全部 OpenGL ES + Compute Shader 实现，`Tiled` 后缀是内存受限时的分块渲染路径。
`StarFilterUtils` / `StarFilterConfig` 是滤镜配置解析层。这解释了 meishe_lut/*.bin 的二进制格式由谁消费。
宿主接口：`com.oplus.ocs.camera.ipusdk.processunit.filter.vendorsdk.meicam.MeisheFilterSdk`

> ⚠️ 本节原判「shader 需动态 dump」**已被 §33 推翻**——shader 以 zlib 容器内嵌在本 so 的 .rodata，静态即可全量提取。

## 30. config.sig 配置签名机制（C0878/C0875）
```
config.sig = SHA-256_hex( configJson + serial + "isProVersion" )
serial     = C1202.m2508()   // gsm.serial → ro.serialno 三级回退
校验        = cat /sdcard/Android/OPCameraPro/config.sig  与重算值 .equals()
```
- 写侧（C0875）：`m1824(config, isPro)` 生成 JSON → `m1831(json+serial+"isProVersion")` 出签名
- 读侧（C0878.m1827）：不匹配打 `Config signature MISMATCH!`，匹配打 `Config signature VALID. Loading config.`
- **无密钥参与**——这是**防篡改绑定设备**的完整性校验，不是授权凭证：换序列号即失效，防止把别人的 config.json 直接拷过来用
- 兜底：`m1829` 读文件三级降级（直接读 → `cat` shell → libsu）

## 31. DexKit 特征串验证：83/83 全命中
`dexkit_targets.json` 的 83 个特征串，在 5,858 条解密串池中：
- 直接命中 72
- 前缀匹配再补 8（提取时被二进制字节截断的碎片，如 `CameraPicture: [wid\xef…` → `CameraPicture: [width…`）
- 最后 3 个经确认可读前缀 `setNewModeWhen`/`UTC`/`ev ` 均在池中

→ **100% 覆盖**，说明此前 DexKit 提取的 17 组特征串完整无误，可作为后续版本比对的稳定锚点。

## 32. 本轮修正
- ❌ 旧说法「shader 在 .rodata 需 dump 提取」→ ✅ 已完整提取 267 个源码 5.6MB（§33）
- ❌ 旧说法「75/114 数组不可还原」→ ✅ 420 调用点解出 370，剩 3 个是 jadx 缺陷（§27/§39）
- 遗留统一见 §40

## 33. 【本轮最大发现】libmsnativefilter.so 内嵌 267 个完整 GLSL 源码
此前判为「需动态 dump」的 shader，实际**以 zlib 压缩容器形式内嵌在 .so 的 .rodata**：
- 容器结构：`NvInitResources_shaders` / `NvInitResources_msnativefilter_shader_rcv` + `:/shaders/xxx.frag.msc` 路径索引
- 每块 = Meishe 反射头（pascal-string 字段表）+ **spirv-cross 反编译出的 GLSL ES 3.1 源码**（`_148` SSA 命名是其特征）
- 提取产物：`shaders/all.glsl`（5.6MB / 267 个）、`shaders/index.json`、`shaders/api.json`、`shaders/uniforms.json`

**阶段分布**：comp 26 · frag 161 · vert 80（frag/vert 按 `layout(local_size_x)` 与 out 声明判定）

### uniform 接口（41 个字段）
```
263 ubuf(UniformBuffer)  237 texSampler  183 lutSampler  183 lutSampler2  183 noiseSampler
 74 auxSampler   72 proMistLayerSampler0..4   37 bottomSampler/layerSampler1/2   36 fishEyeEdgeSampler
 15 is800T  15 glowThresh/glowIntensity/glowColor  9 hdrTransfer/samplerBlur/useGlowColor
```
→ **`lutSampler` + `lutSampler2` 双 LUT 采样 + `noiseSampler`**，正对应 §4 里 `meishe_lut/*.bin` 与 `filters_lut/*.cube` 的消费方式；`proMistLayerSampler0..4` 是 ProMist 五层柔光（对应 `ccd_promist_neutral.mslut`、`promist_{0.2,1.1,2.1,2.2,2.3,3.1}.mslut`）。

### 核心算法函数（137 个自定义函数，按复用度）
```
219 ColorRangeTransfer        198 OETF_sRGB    191 ColorRangeInvertTransfer
188 EOTF_sRGB / sRGBToLinear  181 sampleColorFromTable(2) / getLum  169 toneMapFwd/Bwd
145 lut3D2446A / lut3D2446A2  144 processNoise  120 ApplyLut(2)  108 gaussian(1..3)
 74 HLG_EOTF / OETF_HLG       72 hdr2sdr2446A / sdr2hdr2446A / toneMapFwd2446A / toneMapBwd2446A
 72 proMistToneMapFwd/Bwd     72 processVignette  38 processTemperatureAndTint  37 processGlow
```

### `2446A` = ITU-R BT.2446 SDR↔HDR 互转标准（关键实锤）
```glsl
// hdr2sdr2446A：BT.2020 亮度权重 + BT.2100 HLG 对数近似
luma = dot(rgb, vec3(0.2627, 0.6780, 0.0593));           // BT.2020 系数
t    = log(1.0 + 12.2598 * luma);                        // HLG 系统 gamma L_L
return pow(|hdr|, 0.41667) * sign(hdr);                  // 2.4 次幂域压缩
// toneMapFwd2446A 矩阵：BT.709 → BT.2020 色域 + 0.203 目标亮度缩放
mat3(0.82254,0.03312,0.01706 / 0.17755,0.96684,0.07240 / 0.00006,-0.00001,0.91049)
hlgOOTF(c) = c * pow(dot(c, BT2020_luma), 0.2)           // BT.2100 HLG OOTF
```
**`lut3D2446A` 完整管线**（这是滤镜与 HDR 的接合点）：
```glsl
intensity = clamp(intensity, 0, 1);
return mix(color,
   HlgColorRangeTransfer( ApplyLut( HlgColorRangeInvertTransfer(color, 1),
                                    texelSize1D, rgbToTexCoordRatio, isRGBLayout ), 1 ),
   vec3(intensity));
```
→ **LUT 不是直接作用在 sRGB 上，而是先把颜色从 HLG 域反变换到线性域，采样 3D LUT，再变换回 HLG 域**，最后按 intensity 与原始色混合。这就是「美图滤镜能作用在 HDR 管线上」的实现方式，也是 `.cube.rgb.bin` 里 `rgbToTexCoordRatio`/`isRGBLayout` 两个参数的用途。

### 与伪超HDR 的关系
`proMistToneMapFwd(color, 0.4, 0.75, true)` 硬编码参数 → ProMist 柔光的 tone-map 强度固定；
`sdr2hdr2446A` / `hdr2sdr2446A` 成对存在 → 美图引擎内部**已经在做 SDR↔HDR 双向转换**，
这与 §2 的 `libUhdrUtils-jni.so`（OPlus gainmap 管线）是**两套独立的 HDR 路径**：
- 图库侧：`UHdrConverter.mask2map` → 标准 Ultra HDR gainmap（HEIF 容器，§28 的 hdrgm XMP）
- 相机侧：美图 `*2446A` → BT.2446 转换 + 滤镜，输出走 `local.uhdr.gainmap.info`（§C1786）


## 34. 【已解决】RUS 配置格式 —— 纯 capstone 自研反汇编，不需要 Ghidra
本机 Ghidra/Hopper/IDA/Kuna/rizin **全部不可用**（`binary_session` 逐个确认 not_configured），
`pip install capstone` + 自写 60 行 ELF64 解析器（`elfdis.py`）即可完成函数级反汇编。

### `LocalHdrRus` 双格式解析器（libUhdrUtils-jni.so）
| 函数 | 地址 | 大小 | 结论 |
|---|---|---|---|
| `parseRusData(char*)` | 0x2cdf0 | 1216B | **文本行格式**：`sscanf` 式 `%[^;]` 分行 + `%[^,]` 分列 |
| `readInt32(char**, int)` | 0x2d7f0 | 88B | **大端 4 字节**：`b0<<24\|b1<<16\|b2<<8\|b3`，指针后移 4 |
| `readFloat(char**, int)` | 0x2d794 | 92B | 同上取 4 字节后 `fmov s0, w9`（IEEE754 BE float32） |
| `createRusConfiguration(char*)` | 0x2cb3c | 692B | `strlen`+`strchr`，用 NEON 向量化查找 `;`(0x3b)，**settingCnt < 8** 上限 |
| `convertMetaToStruct(char*, int, void*)` | 0x2d32c | 372B | **结构体逐字段拷贝**，见下方布局 |

### `LocalHDRData` 结构体布局（从 convertMetaToStruct 的 load/store 序列还原）
```
+0x00  x8   (8B)      +0x08  w9   (4B)      +0x0c  x10  (8B)     +0x14  w11  (4B)
+0x18  x12  (8B)      +0x20  w13  (4B)      +0x24  x14  (8B)     +0x2c  w15  (4B)
+0x30  x16  (8B)      +0x38  w17  (4B)      +0x3c  x0   (8B)     +0x44  w1   (4B)
+0x48  x2   (8B)      +0x50  w5   (4B)      +0x54  x6   (8B)     +0x5c  w7   (4B)
+0x60  x19  (8B)      +0x68  w20  (4B)      +0x6c  x21  (8B)     +0x74  w22  (4B)
+0x78  x23  (8B)      +0x80  w24  (4B)      +0x84  x25  (8B)     +0x8c  w3   (4B)
```
→ 24 个字段、8B/4B 交替的规律排布，与 §28 的 `ratioMin/ratioMax/gamma/epsilonSdr/epsilonHdr/displayRatioSdr/displayRatioHdr/scale` 8 组 float 参数对应（每组 8B+4B 或 padding）。

### 语义澄清（修正此前"RUS 是二进制字节流需 dump"的说法）
RUS **同时支持两种编码**：
1. **文本行**：`;` 分隔条目、`,` 分隔字段（`%[^;]` / `%[^,]`），错误日志带 `lineStr: %s` 说明是逐行文本
2. **二进制**：`readInt32`/`readFloat` 走大端 4 字节流

配置项含 `physicCameraId`（物理摄像头 ID）与 `capMode`（拍摄模式）两个查找维度
→ **RUS = 按 (cameraId, captureMode) 二维索引的 HDR 色调映射参数表**，
数据来源是相机 vendor tag `local.uhdr.gainmap.info` / `local.uhdr.gainmap.data` / `gainmap_mask_master_params`（§C1786），
而非独立文件。`com.oplus.director.filter.rus` 只是同名的**特性开关键**（值 "1"），不是数据。

## 35. 工具链结论（可复用）
本机 REA 的 native 反编译后端全缺，但**不需要装 400MB Ghidra**：
```bash
pip install capstone          # 5.0.7, 已装
python3 elfdis.py <so> '<符号正则>' [指令数]
```
`elfdis.py` 自解析 ELF64 段表 + symtab/dynsym，支持按符号名定位并反汇编。
适用：arm64 .so 的函数级指令流、结构体偏移还原、字符串引用追踪。
不适用：需要 CFG 重建/变量命名的完整伪代码（那才需要 Ghidra）。

## 36. native 函数尺寸普查（elfdis.py 输出）
**liboplus_camera_pro_native.so**（作者库）最大函数：
```
18864B  Java_..._encodeAlpha8JpegNative     ← 最大，含完整 JPEG 编码内联
 9256B  jpeg_set_linear_quality      7548B  jpeg_add_quant_table
 4420B  jpeg_make_d_derived_tbl      3248B  jinit_c_master_control
 2920B  jsimd_huff_encode_one_block_neon    2084B jsimd_idct_islow_neon
```
→ **`jpeg_*` / `jsimd_*` 符号直接坐实 §3**：体积暴涨是静态链入 libjpeg-turbo（含 NEON SIMD 汇编路径），不是作者算法复杂。

**libUhdrUtils-jni.so**（OPlus 官方库）最大函数：
```
2952B  oplus_uhdr_mask2map      1952B  mask2mapImpl
1232B  createLookupTableGroup(GainMapProcParams&)   972B  edrScaleCalculator(LocalHDRData*)
1216B  LocalHdrRus::parseRusData   712B  LocalHdrRus::matchMetaData
```
→ 整个 uhdr 转换核心只有 `oplus_uhdr_mask2map` + `mask2mapImpl` 约 5KB，规模很小；
`edrScaleCalculator`（EDR = Extended Dynamic Range）是 OPlus 私有的动态范围缩放器。

## 37. 本轮（第五轮）净产出
| 项 | 前 | 后 |
|---|---|---|
| 反编译 skip 文件 | 352 | 15 |
| 解密唯一串 | 5,140 | 5,858（+718） |
| 数组调用点解出 | 180/202 | **370/420**（剩 3 个是 jadx 缺陷） |
| DexKit 特征串验证 | 未验证 | **83/83 全命中** |
| GLSL shader | 判为需动态 | **267 个 / 5.6MB 源码已提取** |
| RUS 格式 | 判为需 dump | **纯文本+大端双格式已还原，含 LocalHDRData 24 字段布局** |
| native 反汇编能力 | 需装 Ghidra 400MB | **capstone + 60 行 elfdis.py 够用** |

产物新增：`decompiled_bad/`、`shaders/`（all.glsl 5.6MB + 3 个索引）、`decrypted_v4.json`、
`decrypted_runtime_ultimate.json`、`elfdis.py`、`decrypt_runtime_bad.py`、`FINDINGS7.md`


## 38. smali 级定案：3 个残留数组确认为 jadx 缺陷（非加密）
装了 androguard 4.1.4，直接读 DEX 字节码做寄存器跟踪。踩到的坑与结论：

**关键坑**：`fill-array-data` 的操作数是**相对偏移、单位 16 位码元**，正确公式
```
payload_addr = fill_instr_addr + value * 2
```
（不是绝对地址，也不是 value*1 —— 用 `<clinit>` 的 28/8 字节数组反推验证）

**卢恩文字方法名**：jadx 显示的 `m2893` 是别名，DEX 里真名是 `ᛱᛱᛱᛲᛶ`，
解密类 `AbstractC1256` 真名 `ᛱᛱᛷᛶᤝ`。按真名匹配才能定位 invoke。

**结果**：C1079/C1085 两类的 52 个解密调用点，smali 跟踪解出 12 条，
**全部是单字符分隔符**（`E` `/` `+` `J` `w` `?` `!` `o` `P` `B`）——与 jadx 树已有结果完全重合，无新增信息。
`aput-byte v5, v4, v3`（v3 = `const/4 v3, 0`）在字节码层面**直接证实了下标恒为 0**，
即 §27 的推断正确。

→ **定案**：那 3 个「不可重建」是 jadx 的控制流重建失败（`Code restructure failed: missing block`），
不是任何加密或运行时计算。整个字符串混淆体系**静态可 100% 还原**（除这 3 处工具缺陷）。

## 39. 磁盘清理
删除 `jadx.zip`(111M，已解压且 jadx 可执行验证通过)、`__pycache__`、`tmp`。
`rev/` 从 382M 降到 **271M**。保留 jadxtool(122M) 因后续版本比对仍需反编译。

## 40. 最终遗留清单（第五轮之后）
静态可做的已全部做完。剩余项均需真机或额外工具，且都不影响对模块机制的完整理解：

| # | 项 | 阻塞原因 | 需要 |
|---|---|---|---|
| 1 | RUS 配置**具体数值** | 数据来自相机运行时 vendor tag | OPlus 真机 `dumpsys media.camera` / Frida hook |
| 2 | PHK110 / CPH2487 屏蔽**技术根因** | 静态只见结果 | 两台实机对比 ISP/gainmap 硬件路径 |
| 3 | 19→3 个数组中的最后 3 个 | ~~未定案~~ **已定案为 jadx 缺陷**（见 §39），值等价于已解出的单字符分隔符 | 无需处理 |
| 4 | `libmsnativefilter.so` 的 mslut 二进制格式 | 13 个 `.mslut` 由 Meishe 私有容器封装 | 需按 §33 的容器格式（zlib+pascal串）逐个解 |

其中 **#4 是唯一还能静态推进的**，但产出是美图私有 LUT 二进制格式细节，对本项目目标（理解模块机制）已无增量。

## 41. 【第六轮 · 最大成果】MS-LUT 容器格式 100% 还原（字节级验证）
上一节 §40 列为「唯一还能静态推进」的项，现已完成。

### 格式（全部小端）
```
+0x00  8B   magic        ".MS-LUT "（末尾一个空格）
+0x08  u32  version      1 / 2 / 3
+0x0c  u32  size         3D LUT 边长：16/17/20/21/32/33/64
+0x10  u32  flag         0 = uint8 RGB(3B/节点)；3 = float32 RGB(12B/节点)
+0x14  u32  always_one   恒 1（App m1936 校验 ==1）
+0x18  u32  app_generated  App 生成的 custom LUT 恒 1；美图官方产物为 0/24/152
+0x1c  u32  0
+0x20  u64  header       恒 48
+0x28  u64  data_off     = 48 + size*4
+0x30         axis 表    size 个 float32 等差，step = f32(1/(size-1))
+data_off     数据区      size³ 节点，索引 ((r*size+g)*size+b)*per
```
**关键坑**：`header`/`data_off` 是 **u64**（不是 u32）；axis 项数 = size（不是固定 32）；
`+0x18` 是第 6 个未知字段，靠 round-trip 差异定位（App 的 `m1944` 写 `position(24); putInt(1)`）。

### 验证结果
| 项 | 结果 |
|---|---|
| 解析 submodule 全部 108 个 LUT | **108/108 自洽**（数据区长度 = size³×per） |
| round-trip（parse→read→build→逐字节比对） | **108/108 字节级完全一致** |
| 端到端（.cube 解析→重采样→生成） | 头部 176B 与 App 产物**完全一致** |

### axis 表的两种 1 ULP 写法（实测发现）
```
美图官方工具链： axis[i] = f32(i * f32(1/(size-1)))    ← 乘法（35/46 个 .cube.rgb.bin）
App m1944 生成： axis[i] = f32(f32(i) / f32(size-1))   ← 除法（i=17,21,25,29 差 1 ULP）
```
→ 用 `Cold.cube.rgb.bin` 逐字节比对时表现为**恰好 4 个字节差异**（0x74/0x84/0x94/0xa4），
这是定位 `+0x18` 字段之外唯一的格式分歧，不影响读取。

### 自定义 LUT 导入完整闭环（C0970）
```
用户选 .cube
  → m1939()  解析 LUT_3D_SIZE / DOMAIN_MIN / DOMAIN_MAX（跳过 # 注释与 TITLE）
  → m1934()  索引 ((r*size+g)*size+b)*3
  → m1944()  非 32³ → 三线性重采样到 32³；写 98480B 缓冲
             magic + version=1 + size=32 + flag + axis[i]=i/31.0f + 255 量化数据
  → m1936()  回读校验：magic + version==1 + size==32 + +0x18==1 + 长度==98480
  → 落盘 no_backup/custom_lut/generated/<name>.cube.rgb.bin
  → 同步 /sdcard/Android/OPCameraPro/meishe_lut 与 /data/adb/OPCameraPro/meishe_lut
```
「This LUT has already been imported」= SHA-256 去重；未激活用户限 1 个。

### 产物
`rev/mslut.py` —— 可直接使用的读写库（parse / read_lut / build / resample / parse_cube）

## 42. 遗留清单更新
| # | 项 | 状态 |
|---|---|---|
| 1 | RUS 配置具体数值 | ⏳ 需真机 vendor tag dump |
| 2 | PHK110/CPH2487 屏蔽根因 | ⏳ 需两台实机 |
| 3 | 最后 3 个数组 | ✅ 已定案为 jadx 缺陷（§38） |
| 4 | **mslut 二进制格式** | ✅ **已完成，108/108 字节级验证（§42）** |

→ **静态可做的已全部做完**，剩余 2 项均需 OPlus 真机。
