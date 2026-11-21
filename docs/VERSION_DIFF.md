# OPCameraPro v3.1.10 → v3.1.22 版本对比

> 两版 APK 均经官方 digest 校验（v3.1.10 `8d9fab23…170ac7f`，v3.1.22 `6bc77cf0…86901`）

## ⚠️ 先纠正我自己一个错误结论

之前我说「v3.1.22 完成了从 legacy Xposed 到 libxposed 的架构迁移」——**错的**。
实测两版 DEX 里都有：
```
io/github/libxposed/api/XposedModule   ✔ 两版都有
ModernHookEntry                        ✔ 两版都有
io/github/kyuubiran/ezxhelper          ✔ 两版都有（EzXHelper 新包名）
```
**v3.1.10 就已经是 libxposed modern 架构了。** 迁移发生在更早的版本，
或者根本没发生在公开镜像覆盖的区间内。真实差异是别的。

## 真实差异：素材外置（这是本次对比的最大发现）

APK 体积 24.9MB → 8.6MB，但 DEX 反而变大（5.00MB → 5.62MB）。原因：

| 移除（仅 v3.1.10 有） | 体积 |
|---|---|
| `assets/filters_lut/*.cube` | 8.16 MB |
| `assets/meishe_lut/*.bin` | 6.39 MB |
| `assets/odm/` | 8.11 MB |
| `assets/product/` | 8.08 MB |

**共约 30.7MB 素材从 APK 移出。** 已验证它们搬到了 release 附属包：
`submodule_core_3122.zip`（16.7MB，digest `91e4ce68…c933d3` 匹配）内含 119 个 LUT 条目，
目录名 `filters_lut/`、`meishe_lut/` 与 APK 内被移除的路径**逐一对应**。

→ 结合任务 2 解出的 `/data/adb/modules/OPCameraPro/*`、`is_mountbind`、`is_overlayfs`、
`SubModule.zip` 这些字符串，可确认模块改用**Magisk 模块挂载方式**分发滤镜素材，
而不是打包进 APK。这也解释了 `assets/SubModule/` 里那套 `customize.sh` / `module.prop`。

## 新增（仅 v3.1.22 有）

```
assets/protobuf/master_video_mode.json
assets/protobuf/master_video_mode_full.json
assets/protobuf/a6u_master_video_mode_full.json
res/EV.png   res/Vy.xml
```
→ 新增「大师视频模式」配置；`assets/protobuf` 整体从 0.03MB 扩到 0.26MB。

## 代码层变化

| 项 | v3.1.10 | v3.1.22 |
|---|---|---|
| DEX 大小 | 5,240,168 B | 5,889,084 B（+12%） |
| `com/tlsu` 明文类 | 4 个 | **5 个**（新增 `hook/camera/PseudoUltraHdrNative`） |
| `lib/arm64-v8a` | 0.66 MB | **1.52 MB**（+130%） |
| APK 条目 | 295 | 186（素材外置所致） |

`PseudoUltraHdrNative` 是**新出现的类**，且 native 层体积翻倍——
「伪超 HDR / gainmap」这套功能是在 3.1.10→3.1.22 之间加的，
对应 8 个新 JNI 入口和 `local.uhdr.gainmap.info` 等 HEIF 元数据键。

## 一句话结论

v3.1.22 的实质变化是 **① 滤镜素材从 APK 迁到 Magisk 模块挂载分发 ② 新增伪超 HDR 管线（native 体积翻倍）**，
而不是 hook 框架换代。
