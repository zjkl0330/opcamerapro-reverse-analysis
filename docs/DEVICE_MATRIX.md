# OPCameraPro v3.1.22 · 机型适配表（解密还原）

> 来源：jadx 反编译 + 循环 XOR 字符串解密（`AbstractC1256.m2893`）
> 判定入口：`defpackage.C1202`（R8 混淆类，原名不可考）
> 机型解析：`C1202.m2507()` → 优先 `ro.build.version.ota` 按 `_` 切段，
> 空或无 `_` 时回退 `ro.product.model`

## 四个机型集合

| 字段 | 成员 | 判定函数 | 实际作用 |
|------|------|---------|---------|
| `f4787` | PJZ110 · CPH2653 · CPH2649 · CPH2655 | `.contains(m2507())` | 选预览决策配置 **`oplus_camera_preview_decision_config_GT7P.json`**；并被 `App.java` / `ModernHookEntry` / `C1119` 引用（主开关组） |
| `f4788` | PLK110 · CPH2747 · ⚠️第三项解密为噪声 | `.contains(m2507())` | 选 **`..._config_GT8P.json`**；`C0859:292` 另有分支 |
| `f4789` | **PHK110** | `m2515()` | **不支持名单**：命中则打印 "Unsupported device detected, skip PackageLoaded hooks for {pkg}"，整个 hook 阶段直接跳过 |
| `f4790` | PJZ110 · CPH2653 · CPH2649 · CPH2655 · **RMX5010** | `C0234:201` | 某功能开关（比 f4787 多一个 RMX5010） |

## 两个单机型判定

```java
m2513() → m2507().equals("RMX5010")   // realme 机型
m2514() → m2507().equals("RMX5200")
```
二者在 `C3526:567` 的三元链里分别对应 `f4787`/`f4788` 之后的分支，
最终落到不同的 preview decision 配置文件。

## 机型对照（公开资料核对，非本次逆向所得）

| 代号 | 市场名 |
|------|--------|
| CPH2649 / 2653 / 2655 | OnePlus 13 系列（海外） |
| CPH2745 / 2747 | OnePlus 海外新机种 |
| PJZ110 / PLK110 / PHK110 / PHY110 / PHY120 / PKX110 | OPPO/OnePlus 国行代号 |
| RMX5010 / RMX5200 | realme |

⚠️ 上表是代号→商品的常见映射，**APK 内未包含该映射**，仅作阅读辅助，不作为结论。

## 关键结论

1. **PHK110 与 CPH2487 是硬屏蔽机型**（`f4789` 集合两个成员，`m2515()` 命中即跳过全部 PackageLoaded/Ready hook）—— 早期本文档记成「PHK110 唯一」是错的，见文末追加节
2. **RMX5010 享受双重待遇** —— 既在 f4790 功能组里，又有 `m2513()` 单独判定
3. **配置按机型分 GT7P / GT8P 两套** —— 说明 ColorOS 15(GT7) 与 16(GT8) 的相机预览决策管线不同，模块要分别适配
4. `C1143.java` 另有 `{PHY110, PHY120}` 独立集合（第三处机型分支，未展开）

## 附：解密出的模块路径体系

```
/sdcard/Android/OPCameraPro/{config,logs,custom_lut,meishe_lut,gr_watermark_restrict_runtime,
                             decode_runtime/{draft,staged,running.lock,last_result.json}}
/data/adb/modules/OPCameraPro/{is_mini,is_meta,is_default,is_mountbind,is_overlayfs,skip_mount,system,Common}
/data/adb/OPCameraPro/license.json          ← 授权文件
/sdcard/Android/OPCameraPro/config.sig      ← 配置签名校验（6 处引用）
```

**更新源（公开源码里没有）**
```
https://gitee.com/bugme7/OPCameraPro/raw/master/update.json
https://gitee.com/bugme7/OPCameraPro/raw/master/qa.json
```
→ 作者真实仓库是 **gitee.com/bugme7**，GitHub 的 Weverses 镜像只是公开副本。

---
# 追加（2026-11-21）：PHB110 实机影响分析 + 分支链修正

## ⚠️ 修正本文件早期错误
四元分支与配置文件的配对（此前表格配错行）：
```
f4787(PJZ110,CPH2653/2649/2655) → config_13.json
f4788(PLK110,CPH2747/2745)      → config_15.json
m2513(RMX5010)                  → config_GT7P.json
m2514(RMX5200)                  → config_GT8P.json
```
且 APK `assets/algo/` **只打包了 `_13` 和 `_GT7P` 两个文件**（`_15`/`_GT8P` 被代码引用但不在包里，f4788/RMX5200 命中会 cp 失败）。

## PHB110 判定结果（静态全量核对）
- APK 内出现的机型代号共 14 个：PHK110 CPH2487（屏蔽）· PJZ110 CPH2649/2653/2655 · PLK110 CPH2745/2747 · RMX5010/5200 · PKX110 · PHY110/PHY120
- **PHB110 不在任何集合** → 逐项影响：

| 检查点 | PHB110 结果 | 影响 |
|---|---|---|
| `m2515()` 硬屏蔽 | ✅ 不命中 | hook 正常注入，**可用** |
| preview decision 配置 | ❌ 四分支全不命中 → 跳过部署 | 相机用系统默认预览决策（只影响预览管线微调，不影响拍摄/LUT/HDR 主链路；部署其余步骤照常，is_mount 照常 touch） |
| `m2523()` PKX110 专属 | false | 无 `gt-3dcity/gt-glazed-tile/gt-desert` 滤镜、无 `cross.window.blur`；**但 `grand.tour.filter` 反而是非 PKX110 才注入**（`!m2523() && 开关`） |
| `f4790` 功能组 | ❌ 不命中 | C0234 相应开关为 false |
| 伪超HDR/ProXDR | **与机型无关** | 取决于激活 tier（见下） |

## ProXDR 真实门槛（C2191.m4243 解密）
`canUsePseudoUltraHdr` 等 10 个能力位（EnumC2929：25MP/PreviewHdr/XPAN/MasterVideo/AICaptureGuide/PseudoUltraHdr/HeifUltraHdr/VideoFilter/UWMode/FilterOrder）判定链：
1. license 有效（RSA `SHA256withRSA` 验签 activationCode）
2. `seal == SHA-256(machineHash|record字段…|salt)` 逐字符 XOR 比对通过（防手改 json）
3. **tier 字段 == `"advanced"`**
→ 判定仅作用于目标 OPlus 机型；分析所用主机与目标机无关。

## 机型伪装路径（如需 f4787 的 _13 配置）
`m2507()` = `ro.build.version.ota` 取首个 `_` 前段，空则回退 `ro.product.model`。
→ Magisk `resetprop ro.build.version.ota "PJZ110_..."` 即可命中 f4787 拿到 config_13；改 `ro.product.model` 同理。副作用：同时获得 f4787 组的全部行为（含滤镜排序等白名单功能）。
