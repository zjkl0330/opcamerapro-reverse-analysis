# OPCameraPro v3.1.22 · DexKit 反射搜索目标

> 模块用 DexKit（`libdexkit.so` + `org.luckypray.dexkit`）在**运行时**从系统相机 APK 里
> 按特征字符串定位混淆类/方法。下面 83 个特征串就是它的"指纹库"。
> 提取方式：jadx 反编译 → 平衡括号解析 `.usingStrings(...)` → XOR 解密。

## 按功能分组

### 1. 相机 UI 结构（注入入口）
| 特征串 | 指向 |
|--------|------|
| `CameraMenuOptionTop` / `CameraMenuContainerTopRight` | 相机菜单容器 View 类 |
| `_BaseMode` / `pref_camera_photo_ratio_key` | 拍摄模式基类、画幅设置键 |
| `MasterEffectMenuV2` / `hideMasterEffectHint, hint text view is null` | 大师效果菜单 |
| `PhotoDetails` / `ev ` / `ISO ` | 相册 EXIF 详情面板（EV/ISO 显示） |

### 2. 滤镜体系（最大一块）
| 特征串 | 指向 |
|--------|------|
| `getAllFilters, start.` / `getAllFilters, processImage end.` | 滤镜枚举方法 |
| `initFilterGroupFromIpu, filterGroup modeType: ` + `, deviceName=` + `, location=` | **IPU 滤镜组初始化**，按机型+地区匹配 |
| `drawing_item_filter_type` / `_name` / `_category` | 滤镜列表 UI 数据项 |
| `generateDrawingItemsVertical` | 滤镜列表生成方法 |
| `pref_jiangwen_filter_enable` | 「江文」滤镜开关（内部代号） |

### 3. HDR / 超高清管线（对应 native 层）
| 特征串 | 指向 |
|--------|------|
| `local.hdr.linear.mask` / `local.hdr.meta.data` / `local.uhdr.gainmap.info` | **HEIF gainmap 元数据键** —— 与 `PseudoUltraHdrNative` 的 8 个 native 方法直接对应 |
| `HeicProcessUtil` | HEIC 处理工具类 |
| `DATASPACE_DISPLAY_P3_HLG` | 预览 HDR 色彩空间 |
| `OplusCameraCharacteristics` | OPPO 相机特性键容器 |

### 4. 水印体系
| 特征串 | 指向 |
|--------|------|
| `watermark_master` | 水印主控 |
| `BaseWatermark*`（解密残缺） | 水印基类 |
| `feature_is_support_hassel_watermark` | 哈苏水印支持位 |
| `, subWatermarkType=` / `, isLumoDevice=` | LUMO 水印分支 |
| `CameraApsExtendData` + `mWatermarkCoveredImageInfo:` | 水印覆盖图数据结构 |
| `invalidateLivePhotoTagFlags, save attributes failed.` | LivePhoto 标签位刷新 |

### 5. 配置能力读取（三处重复）
`ConfigAbilityWrapper` + `getInt/getBoolean/getString configAbility is null, configId:`
出现在 **C1417 / C1656 / C1661 / C1685 / C2299** 五个类 —— 模块反复从系统相机
`ConfigAbility` 里按 configId 读开关，这是它「按机型自动匹配可用功能」的实现底座。

### 6. 调试后门（值得注意）
```
'CameraDebugActivity'  'APSVisualizationDialog'  'password is invalid'
'NetworkAuthenticationUtils'  'checkAuthenticationTimeout, stopTime:'
```
→ OPPO 相机自带调试面板，模块把它 hook 出来做 APS 可视化调试，且**带密码校验**。

### 7. 相册写入
`newImageForGallery, ` / `writeDataByUri, uri: ` / `savePicToUri, exception` / `StorageDepositorFactory`
`yyyy:MM:dd HH:mm:ss` + `UTC`（EXIF 时间格式）

### 8. 连拍/多图合成
`assemble, drawOriginBitmap` / `assemble, draw downBitmapList` / `assemble, draw upperBitmapList`
`captureX savePicture size:` / `continueSavePicture, picture:` / `pictureArrive, closeHardwareBuffer ...`
`continue_update_defer_image_fail` / `s4ContinueUpdateDeferIm…`
→ 多帧合成的上/下层位图绘制与延迟帧更新链路。

## 阅读提示
- 带 `\x..` 乱尾的串是**我解密时 key 长度取错位的残留**（部分调用 key 与 data 长度非整除），
  不是原始字符串有误；需要精确值可回源码逐条核对。
- 类名 `C####` 是 jadx 对 R8 卢恩文字混淆类的临时命名，非真实类名。
- 这些是**静态声明**，不证明运行时真的匹配成功；实际命中依赖目标 ROM 版本。
