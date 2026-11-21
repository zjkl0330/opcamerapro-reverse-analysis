# 任务 6 完成报告 · native 层与运行时数组全量还原

> 2026-11-21 · 无需 Ghidra，全部基于 REA + jadx 反编译 + 作用域感知 XOR 还原
> 产物：`decrypted_runtime_final.json`（新增 96 唯一串）、`native/`（6 个 so 样本）

## 1. submodule_core_3122.zip 全量结构（已验证）

119 个文件，四大块：

| 路径 | 数量 | 体积 | 说明 |
|---|---|---|---|
| `filters_lut/*.cube` | 7 | 8.2MB | 色彩空间转换 LUT（bt2020/p3/bt709 互转），与 v3.1.10 assets **逐字节同名** |
| `meishe_lut/*.bin` | 109 | 6.8MB | 美图（Meishe）滤镜 LUT；比 v3.1.10 **多 5 个**：`ccd_promist_neutral.bin`、`glow_sdr_gen_0_1{,_flash,_normal}.bin`、`polaroid_sdr.mslut` |
| `odm/lib64/libmsnativefilter.so` | 1 | 11.5MB | 美图原生滤镜引擎（v3.1.10 在 assets/odm/ 内，此处外置） |
| `product/lib64/libMsEffectSdk.so` | 1 | 364KB | 美图特效 SDK |

→ **v3.1.22 的"素材外置"实质 = 把美图滤镜全家桶（LUT + 两个 so）从 APK 移到 Magisk 模块挂载**。

## 2. libUhdrUtils-jni.so（两版 MD5 相同：6dff87c3…，即 OPlus 官方库未动）

- 713 个导出，无 `Java_*` 符号 → **JNI_OnLoad + RegisterNatives 动态注册**
- 核心符号（demangle 后）：
  - `android::LocalHdrRus::{parseRusData, matchRusInfo, matchMetaData, convertMetaToStruct, createRusConfiguration, readInt32, readFloat}` — 解析 OPlus "RUS"（本地 HDR 色调映射配置）字节流
  - `android::calFunUhdrGain` / `createLookupTableUhdrGain` / `createLookupTableGroup(GainMapProcParams&)` / `paralGainMapProcYChannel` — gainmap 查找表 + 并行 Y 通道处理
  - `android::edrScaleCalculator(LocalHDRData*)`
- 关键日志串：`oplus_uhdr_mask2map`、`mask2mapImpl`、`libUhdrUtils-jni.so version: %s`
- 元数据字段与 Java 侧 `GainMapMeta` 一一对应：ratioMin/ratioMax/gamma/epsilonSdr/epsilonHdr/displayRatioHdr/scale

→ **这是 AOSP/OPlus 系统图库的 uhdr 转换库原样打包**（`com.oplus.gallery.jni.uhdr` 包名即来源），作者只是复用。

## 3. liboplus_camera_pro_native.so（作者自研，v3.1.10→v3.1.22 的真正变化点）

| | v3.1.10 | v3.1.22 |
|---|---|---|
| 体积 | 6.7KB | 904.8KB（+134×） |
| `Java_*` 导出 | 1 个 | **9 个**（静态名注册，非 RegisterNatives） |

- 旧入口：`AICaptureGuideNativePatcher_patchMorphoAnchorTrackingNative`
  - 行为：`dlopen("libmorpho_anchor_tracking.so")` → 从 /proc/maps 解析 `MorphoAnchorTracking_init` 地址 → **inline patch 其反调试/校验调用**（校验指令字，`unexpected instruction at patch site`）
  - v3.1.22 增强：区分 `apk-embedded` 与 `standalone` 两种 so 定位路径
- 新增 8 个入口 = `PseudoUltraHdrNative` 的 8 个 native 方法，全部 **静态命名注册**（`Java_com_tlsu_..._PseudoUltraHdrNative_*`）
- 内嵌 **libjpeg-turbo 3.1.0 (build 20260524)** 全量源码（版权串可见）→ turbo 系列方法自包含解码/编码，不依赖系统 libjpeg
- 依赖：`libjnigraphics.so`（Bitmap像素锁）

→ **"native 体积翻倍"的真相：不是算法复杂，是把整个 libjpeg-turbo 静态链进来了**，配合 gainmap JPEG 融合编解码（`encodeJpegToGainmapJpegTurbo`：一次调用完成 解码→tone→重编码）。

## 4. Magisk 模块挂载机制（is_mount 全链条，解密串证实）

模块状态标志文件（`/data/adb/modules/OPCameraPro/` 下）：
`is_mountbind` / `is_overlayfs` / `is_meta` / `is_default` / `is_mini` / `skip_mount` / `skip_mountify` / `version.txt`

三种挂载模式互斥切换（touch/rm/mv 标志文件 + 换 `post-fs-data*.sh`）：
1. **mountbind**：`Common/* → 模块根`，`post-fs-data-mountbind.sh`，touch `is_mountbind`
2. **overlayfs**：`system/* → 模块根`，touch `is_overlayfs`
3. **meta 元模块**：`odm/`+`product/ → system/`，`standalone.sh→mountify.sh`，依赖 `/data/adb/.magic_mount_enable`、`/data/adb/metamodule/module.prop`（Mountify 生态）

运行期检测：
- App 侧探针：`test -f /odm/etc/camera/is_mount`（模块挂载完成的**哨兵文件**，由模块脚本 `touch`）
- 部署链（C3526）：`files/meishe_lut → /odm/etc/camera/meishe_lut`、`files/filters_lut → …/filters_lut`、`basictone/masterlut → …/filters_lut/masterlut`、`ProXDR/* → …/`、`libBasicTonePhoto.so → /odm/lib64/`，全部成功才 `touch is_mount`
- 机型条件裁剪：特定条件删 `800t_{sdr,hdr,blues}.bin`、`ccd_base_{cold,warm}.bin`
- 许可证：`/data/adb/OPCameraPro/license.json`（激活态存 /data/adb，root-only 可读 = 防篡改设计）

## 5. 运行时填充数组：**旧结论"75/114 静态还原不了"作废**

新脚本 `decrypt_runtime_final.py`（作用域感知：声明→填充→调用点区间匹配 + 单字节 `new byte[1]; a[b]=X` jadx 伪影处理）：

**202 个变量型调用点 → 解出 180（89%）**，仅 19 个真不可重建（数组来自跨作用域/方法返回值）。

新解出的关键内容：
- **HEIF/ISO-BMFF box 名 14 个**：`hvcC iinf iloc ipma iprp ipco ispe pitm dimg auxl grpl idat cdsc` → Ultra HDR 写 HEIF 容器（gainmap 作为 aux image + `grpl` 关联组），证实伪超HDR 输出走 **HEIF gainmap 封装**
- **水印样式远程 schema**（C0980）：`styleId styleTitle styleDesc styleDescTwo styleJsonUrl styleJsonMd5 font fontZipUrl buttonName buttonBackgroundImageUrl/Md5 buttonSidePictureUrl/Md5 cornerMarkId version` → 哈苏水印样式从远端 JSON+ZIP 下载，MD5 校验
- **相机 feature 开关**：`enableHasselbladWatermark`、`enableLUMO`、`addFeatureList`、`getGroupConflict/setGroupConflict`
- 其余为 Compose 编译器 trace 串（噪音，可忽略）

## 6. 修正与遗留

- ✅ 修正 PROJECT_STATE「native 体积翻倍=伪超HDR算法」→ 实为 **libjpeg-turbo 3.1.0 整体静态链接**
- ✅ 修正「75/114 数组不可还原」→ **89% 可还原**，剩 19 个跨作用域
- ✅ 确认 `libUhdrUtils-jni.so` 两版未改（作者复用 OPlus 图库官方库）
- ⏳ 遗留（需动态）：19 个跨作用域数组、RUS 配置字节流具体数值、`post-fs-data*.sh` 脚本全文（在 APK assets/SubModule/，可静态提取但未展开）

---
# 追加：第二轮深挖（assets 全量 + 许可证 + 机型矩阵）

## 7. Magisk 模块脚本全文（assets/SubModule/，静态可取，已展开）
- `module.prop`：id=OPCameraPro，version=3.1.22，versionCode=1610211，author=**TimelessU**（与 gitee 账号一致）
- `version.txt` 仍写 `3.0.33`（作者没同步更新，模块版本判定不能信这个文件）
- `post-fs-data.sh`：仅 6 行——若存在 `mountify.sh` 就转交并 exit
- `post-fs-data-mountbind.sh`：`find $MODDIR/Common -type f` 逐文件 `mount` bind + `restorecon`
- `mountify.sh`（185 行）：Mountify standalone 变体，`FAKE_MOUNT_NAME="my_camera"`、`MOUNT_DEVICE_NAME="KSU"`；tmpfs 中转 + `busybox mount -t overlay` 逐层镜像 SELinux context（`chcon --reference`）+ opaque 目录 `setfattr trusted.overlay.opaque`；支持 susfs/ksud kernel umount 钩子（默认关）
- `customize.sh`：检测 `KSU_METAMODULE/APATCH_METAMODULE` 含 "hybrid mount" → 分区目录从 `system/` 提到模块根并留符号链接；否则反向归位
- `module-mini.prop`：空占位模块（"不包含任何底层文件，但请不要卸载"）

## 8. 激活/许可证体系（C2172/C2190/AbstractC2192，全部解密）
- **license.json 双路径**：`/sdcard/Android/OPCameraPro/license.json`（可写副本，App 用 heredoc `cat <<'EOF' >` 写出）→ `/data/adb/OPCameraPro/license.json`（root-only 权威副本，读取走三级降级：直接读→`cat` shell→libsu `Shell.cmd`）
- **JWT 式三段 token**：`machinePrefix` . `timestampHex` . `signature`（按 `.` 切分，逐字符 XOR 校验 machinePrefix 匹配）
- **签名验证**：`SHA256withRSA` + 内置 X.509 公钥（`-----BEGIN PUBLIC KEY-----`），明文=canonical JSON
- **混淆密钥常量**（XOR 掩码字节数组，非解密串）：`f8708={27,16,59,...}`、`f8709={77,26,28,...}` 12/15 字节
- 解密出的盐/键名：`my_salt_key_123`、`my_token_key_abc`、`internal_sign_key_v2`（键名可读，密钥值仍嵌在字节码）
- 字段：`rawAndroidId`、`token`、`activationCode`、`activationCodeHex`、`legacy_activation_code`
- **RSA 公钥验证无法本地伪造**——这是设计上的硬防线（除非替换 APK 内公钥，需重签名）

## 9. 机型矩阵完整解密（C1202，修正"PHK110 唯一硬屏蔽"）
| 集合 | 机型 | 用途 |
|---|---|---|
| `f4787` | PJZ110, CPH2653, CPH2649, CPH2655 | 主白名单/分支选择（109 处引用） |
| `f4788` | PLK110, CPH2747, CPH2745 | 特殊 LUT 路径分支 |
| **`f4789`** | **PHK110, CPH2487** | **硬屏蔽**（`m2515()`，两版共用） |
| `f4790` | f4787 + RMX5010 | C0234 特性开关 |
| static | PLK110, CPH2747, CPH2745, RMX5200 | 另一分支集 |
- **修正**：硬屏蔽是 **2 个机型**（PHK110 + CPH2487），不是 1 个
- 单例判定：`RMX5010`(m2513)、`RMX5200`(m2514)、`PKX110`(m2517=m2523)
- `m2524()`：ColorOS 版本门 `>= 16.0.1`（正则 `(?:V)?(\d+)\.(\d+)\.(\d+)` 读 `ro.build.version.oplusrom.display`）
- **机型 ID 构造**（m2507）：`ro.build.version.ota` 按 `_` 切分，回退 `ro.product.model`
- **屏蔽执行点**：`ModernHookEntry.onPackageLoaded` + `onPackageReady` 两处，命中即 `log(5,...)` 后 **return 不注入**（模块加载但零 hook）

## 10. Hook 目标包（C1826.f7444，5 个）
`com.oplus.camera`、`com.coloros.gallery3d`、`com.oneplus.gallery`、`com.heytap.mydevices`、`com.oplus.aimemory`
→ 不止相机：还 hook **两个图库 + 设备端 + AI 记忆**（ProXDR/gainmap 显示在图库侧生效）

## 11. 其余 assets（v3.1.22）
- `ProXDR/*.json`（6 个）：gamma 曲线表，按 `luxLow/luxHigh × zoomRatioLow/High × NofaceGammaSet` 分档 → 伪超HDR 的**亮度自适应 gamma LUT**，明文 JSON 无需解密
- `filters/*.cube`（20 个）：人像肤色校正 LUT（`3DLut_Portrait_Correction_Skin_v1-5` 等），**未外置**（与 filters_lut 区别）
- `watermark/gr_style_1-5.json`：哈苏水印样式 schema（`styleId/baseImageSize/size/imageOffset/background/bitmaps[].elements[]`）——即第 5 节解密字段名的实际数据文件
- `protobuf/*.json`（7 个）：`master_video_mode`/`xpan_mode`/`uw` 等，结构 `logName/targetMode/cameraTypeFeatures`；`uw-3rd.json` 为 0 字节占位
- `dexopt/baseline.prof+m`：ART baseline profile（启动优化）
- `algo/oplus_camera_preview_decision_config_{13,GT7P}.json`：预览决策配置（按机型分档）

## 12. 现在真正剩下的（必须动态）
1. 19 个跨作用域数组（值来自方法返回值/运行时拼接）
2. RUS 配置字节流的**实际数值**（`LocalHdrRus::parseRusData` 输入，需从运行中的相机进程 dump）
3. `activationCode` 的**签发流程**（RSA 私钥在作者侧，只能观察验证不能伪造）
4. 运行时 mount 实况：`/proc/mounts` 里 overlay 实际层级（需 root 真机，本沙箱无）
5. PHK110/CPH2487 屏蔽的**具体技术原因**（静态只见结果不见根因，推测为该机型 ISP/gainmap 硬件路径不兼容）

---
# 追加：第三轮 · 激活/许可证体系完整还原

## 13. license.json 记录格式
`C2190` 五字段 → JSON 短键：
```
v  = version(int, 当前 1)
s  = scheme(String: "a1" / "m2" / "l1")
t  = tier(String: "advanced" / 其他)
u  = unused/legacy
ts = timestamp(long)
```
落盘位置双份：`/sdcard/Android/OPCameraPro/license.json`（可写副本）+ `/data/adb/OPCameraPro/license.json`（root-only 权威）

## 14. 加载与缓存链（C0121.m358）
1. `AbstractC2192.m4248()` 计算两份文件的**指纹缓存键**（`路径@长度:最后修改时间`，见 C1202.m2499）→ 命中内存缓存直接返回
2. 先读 sdcard 副本 → 解析成功且 `context!=null` 时 `m4246()` **回写 /data/adb 权威副本**
3. sdcard 无/坏 → 读 `/data/adb` 权威副本 → 成功则 `m4252()` **反向同步到 sdcard**
4. 都失败 → `AbstractC1249.m2790()`（`l1` legacy 迁移）→ 仍失败 → `m2789()`（本地 SharedPreferences `activation_code` 兜底）
5. 校验通过则 `m4247()` 落盘（先比对 `m4250` 读回内容一致才写，避免无谓 IO）

## 15. 三套验证算法（C2172 / C2176）
**设备指纹（真实来源）**：`C1202.m2508()` = `persist.gsm.serial` → `vendor.gsm.serial` → `ro.serialno` 三级回退（**不是** ANDROID_ID）

| scheme | 算法 | 说明 |
|---|---|---|
| `a1` | `SHA256withRSA(machineHash, activationCodeHex)` | 标准非对称签名验证 |
| `m2` | 6 段 `:` 分隔 + 双 HMAC 式 XOR 逐字符比对 | legacy 迁移格式，含 `v2` 前缀 + `legacy_migration_proof_key_2026_04` |
| `l1` | 走 `m4227` + `C2176.m4232` 升级为 m2 | 迁移路径，成功后 `m2780()` 清理 |

**machineHash 计算**（C2172.m4221）：
```
machineHash = SHA-256( serial + m4229("my_salt_key_123", f8708) )
其中 m4229 = 字节数组 XOR 循环密钥
f8708 ^ "my_salt_key_123" = "video_120fps"     ← 真实盐值（已还原）
```
→ 即 **`SHA-256(序列号 + "video_120fps")`**

**m2 内部 seal**（C2176.m4231）：
```
digest = SHA-256( "v2" | machineHash | tier | ts | p3 | p4 | "legacy_migration_proof_key_2026_04" )
取前 32 位 hex，与 license 第 6 段逐字符 XOR 比对
```
**m4228 前缀校验**：`machinePrefix == first16(SHA-256(serial))`；`timestampHex` 长 16、`signature` 长 32

## 16. 内置公钥（RSA-2048 / X.509 SPKI，从混淆字节还原）
```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAo9qQdiTe7kccke0mdrVW
+F6uoEc0eoVps7gsjn+Ku1sgpEBgl3dDxX6uc+9tpdMqPHFHRnuL99/vgzjAKezY
O7ByRXZO3q7vFQgGg1EcTYtk4S6pCOU2l/tr2U/Ff+3252Q3F0X8B/N6M1Vmc0se
FJIVi272csdjJMUwenrmtWiIPzcRVjTgjFUo3LsPqB9eNiwnRlqOhpqN4wPuuLvY
WGyt4TYD223owIo1aFl7ZNqUZFDb/s94mkGQMdzjvLscPMCCeguSYtpZXMsJyG9z
8Ne8LWtEUWQQP9j1xcnIm/VcWM2l/oCETmkrgx9NGf+tZy4vrhHzb73eLWCzEgjH
MQIDAQAB
-----END PUBLIC KEY-----
```
私钥不在 APK 内 → `a1` scheme 无法本地伪造（除非替换公钥并重签名 APK）。

## 17. 能力门（tier）
`C2191.m4243(EnumC2929)` 前置三条件全过才查表：
1. `f8801`（license 有效）
2. `seal` 逐字符 XOR 比对通过
3. **`tier == "advanced"`**

10 个能力位：`Enable25MP / EnablePreviewHdr / EnableXPAN / EnableMasterVideo / EnableAICaptureGuide / EnablePseudoUltraHdr / EnableHeifUltraHdr / UnlockVideoFilter / EnableUWMode / FilterOrder`

## 18. 其他解密常量
- `feature_gate_key_2026_04`（C0121，feature gate 盐）
- `legacy_migration_proof_key_2026_04`（C2176.f8739）
- `internal_sign_key_v2`（C2172.f8712，m2 seal 尾盐）
- `my_token_key_abc` 掩码 `f8709` 还原结果非可读 ASCII（一次性混淆掩码，无独立语义）
- DexKit 目标：`com.oplus.aimemory.utils.h0` / `AiMemoryPreset` / 特性串 `aimemory.master_preset_import.method.support`（未命中打 "DexKit missed …"）

## 19. 兜底激活路径（AbstractC1249.m2789，jadx 未反编译，从字节码手工还原）
```
1. serial = C1202.m2508()                       // gsm.serial / ro.serialno
2. prefs  = context.getSharedPreferences("app_prefs", 0)
3. code   = prefs.getString("motion_param_v3", null)      // ← 键名伪装成"运动参数"
4. code   = C2172.m4224(code)                   // 规整（去空白/前缀）
5. raw    = AbstractC2192.m4250("/sdcard/Android/OPCameraPro/token")  // 文件兜底
6. code   = C2172.m4224(raw)                    // 二次规整
```
→ 除 license.json 外还有两条隐藏激活入口：SharedPreferences 键 **`motion_param_v3`** 与明文文件 **`/sdcard/Android/OPCameraPro/token`**。

---
# 追加：第四轮 · 发布通道 + 相机特性注入全表

## 20. 发布/更新通道（已核实）
`update.json`（gitee raw，HTTP 200 实取）：
```json
{"versionCode":3122,"versionName":"3.1.22","date":"2026-05-31",
 "downloadUrl":"https://gitee.com/bugme7/OPCameraPro/releases/download/3122/OPCameraPro_v3.1.22.apk",
 "changelog":"…ProXDR、自定义水印、滤镜LUT优化、人像前置彩光屏幕补光灯、EV EXIF、大师模式参数修复、自动夜景开关、相册创作板块、元模块、闪退…"}
```
- **主发布仓库**：`github.com/Xposed-Modules-Repo/com.tlsu.opluscamerapro`（LSPositor 官方模块仓库，tag `3122-3.1.22`）
- **APK 二进制托管**：gitee `bugme7` releases（源码在 gitee，二进制也在 gitee）
- 更新检查另读 `qa.json`（FAQ 频道）

## 21. 相机特性注入全表（C0859，33 组 / 约 150 个 vendor 键）
模块的核心机制：**向 `com.oplus.camera` 注入 `ro.oplus.camera.*` 式特性键**，骗过相机 App 自身的机型能力表。按功能域归类：

| 域 | 代表键 |
|---|---|
| 高帧视频 | `video.4k.120fps.support`、`video.1080p.120fps.zoom.range`、`4k120fps.max.zoom.list=1,2.9,10` |
| HDR/预览 | `preview.hdr.support`、`capture.hdr.support`、`preview.hdr.brightness.ratio=5`、`preview.hdr.cap.mode.value=common,night,highPixel,sticker,idPhoto,professional` |
| 800T 胶片滤镜 | `feature.800t.filter.{portrait,}.support` + 6 组 `thresh.*`（前/后摄 × 普通/专业/人像，如 `-1,-1,0.998,-1,-1,1.35`） |
| 屏幕补光 | `feature.screen.bright.{support,value=55,threshold=400,recover.threshold=350}`、`front.torch.color=#FFF6E3`、`colorful.screen.torch.button.color`（7 色板） |
| 哈苏高像素 | `hasselblad.super.definition.support`、`main.full.qbc.output.sizes`（7 组尺寸，最大 5888x4416）、`4K Live` 50MP=8192x6144 / 12MP=4096x3072 |
| LivePhoto | 12 个键：`bitrate`/`max.duration`/`min.duration`/`audio.sample.rate=16000`/`gyro.threshould.vector=2.6,2.6`/`enable.eis=0`/`enable.frc=0`/`kill.app.list=com.oplus.games` |
| 大师视频 | `master.video.feature.list=1,1,0,0,0`、`master.video.{hdr,24fps,60fps}.support`、`lock.wb.support` |
| TurboRAW | `turboraw.re.{support,open.bydefault}`、`master.mode.version=2.0` |
| 水下模式 | `under.water.mode.support`（14 段参数串）、`ultrasonic.finger.top.margin=2146`、`tele.point.value=3` |
| 人像虚化 | `portrait.zoom.value.default`（6 组焦段 1–4x）、`portrait.lens.bag.support`、`portrait.preview.rear.sizes`（8 组） |
| 美颜/IPU 柔光 | `facebeauty.version=7`、`ipu.soft.light.{photo,night,professional}.mode.support`、`director.filter.rus` |

**机型门控点**（C0859 内）：
- `!m2523() && 开关` → `grand.tour.filter`（**非 PKX110 才注入**）
- `m2523() && f15430` → `cross.window.blur`（PKX110 专属）
- `m2523() && m6377()` → `gt-3dcity / gt-glazed-tile / gt-desert` 三支 GT 滤镜
- `f4787.contains()` → 整组高帧/多帧 burst 分支

→ **PHB110 走的是 `!m2523()` 分支**：拿到 `grand.tour.filter`，拿不到 GT 三滤镜与 cross.window.blur，其余 150 键与机型无关全部注入。

## 22. 未反编译残留（jadx 限制）
- `AbstractC1255.m2839(String)`：license JSON → C2190 解析器，560 指令，jadx 直接抛 `Method dump skipped`（需 `--show-bad-code` 或 smali 级读取）
- `AbstractC1249.m2789`：已从字节码手工还原（见 §19）

## 23. license.json 解析器完整还原（AbstractC1255.m2839，绕过 jadx 失败项）
用 `jadx --show-bad-code --single-class` 成功反编译出被跳过的 560 指令方法。

**双键名兼容**（`m2857(json, 短键, 长键, 默认)`）：
| 字段 | 短键 | 长键 | 默认 | 处理 |
|---|---|---|---|---|
| scheme | `s` | `scheme` | `""` | 过 `m2832` 别名映射 |
| code | `c` | `activationCode` | `""` | 按 scheme 分别规整 |
| tier | `t` | `tier` | **`advanced`** | — |
| version | `v` | `version` | `1` | — |
| 时间 | `a` | `activatedAt` | `System.currentTimeMillis()` | — |

**scheme 别名映射**（`m2832`）：
```
"legacy_activation_code" → "a1"
"legacy_migrated_v2"     → "m2"
"legacy_token"           → "l1"
其他 → 原样
```

**code 规整**：
- `a1` → `m4223`：逐字符过滤掉 `AbstractC2021.m3964(c)` 判定为"空白/分隔"的字符（即去空白拼回连续 hex）
- `l1` → `m4224`：`replace('\r','\n')` 后压缩换行（PEM 风格规整）
- `m2` → 原样

**有效性硬门槛**：`m2832 != "" && str2 != "" && obj2 != ""` 三者非空才构造 C2190，否则返回 null。

**注意**：`tier` 缺省即 `"advanced"` —— 但 `m4243` 的 seal/签名校验仍在前面，缺 tier 不等于绕过授权，只是省了一个字段。

## 24. l1 → m2 迁移链（AbstractC1249.m2790）
```
l1 记录 → C2172.m4227(serial, code)  [即 m4220 JWT 式三段解析 != null]
       → C2176.m4232(serial, code, ts)  生成新 m2 记录
       → AbstractC2192.m4252() 写 sdcard + m2780() 清理旧 l1
```
## 25. l1 token 格式（C2172.m4220，4 段冒号）
```
token = "<magic>" ":" <machinePrefix16> ":" <timestampHex16> ":" <signature32>
magic = m4229("my_token_key_abc", f8709) = 15 字节不可打印串（硬编码魔数，非 ASCII）
校验 = machinePrefix == first16(SHA-256(machineHash))
       && m4228(...) 内 seal 逐字符 XOR 比对
```
`m4227(serial, code)` 即「能解析出 4 段且 magic 匹配」的布尔封装。
