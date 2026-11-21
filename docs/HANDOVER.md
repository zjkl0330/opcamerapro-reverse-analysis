# 交接文档 · REA 逆向 OPCameraPro

> 执行环境：Linux (arm64) 沙箱 · 纯静态分析，未接触任何真机 OPlus 设备
> 任务：安装 REA → 逆向 OPCameraPro 最新发行版 APK → 获取源码学习使用

---

## 1. 任务结论（一句话）

**你给的两个链接是两个不同东西**：仓库是 2025-11 停更的 GPL 开源镜像（Katrina 3.0.1），
真正发布的 APK（v3.1.22）走的是**另一套架构**，公开源码里没有。REA 证明了这一点。

---

## 2. 样本身份

| 项 | 值 |
|----|-----|
| 文件 | `OPCameraPro_v3.1.22.apk` |
| 来源 | Xposed-Modules-Repo/com.tlsu.opluscamerapro（tag `3122-3.1.22`，2026-05-31） |
| 大小 | 9,026,799 bytes |
| SHA-256 | `6bc77cf025296ea8611469ebacfe01786c2951edafb4d6922b5b61658ed86901`（与官方 digest 一致） |
| 包名 | `com.tlsu.opluscamerapro` |
| 版本 | versionName 3.1.22 / versionCode 3122 |
| SDK | minSdk **35** · targetSdk **36** |
| 签名 | 仅 v3 方案 · 证书 CN=`evermore` · 有效期 2025-04-30→2050-04-24 · 指纹 `141fc0d9…9d521038` · 无密钥轮换 · 自洽 |

⚠️ 签名结论是**结构与自洽性**，不是真实性验证：REA 不校验 PKCS#7 签名、证书链与吊销。

---

## 3. 核心发现：APK 与公开源码的三处断裂

### 3.1 Hook 框架换代（最关键）

| | 公开源码 | 发布 APK |
|--|---------|---------|
| 入口类 | `MainHook` | **`ModernHookEntry`** |
| Xposed API | `de.robv.android.xposed:api:82`（legacy） | manifest 声明 `io.github.libxposed.service.XposedProvider`（libxposed 现代 API） |
| 辅助库 | EzXHelper | 不可见 |

源码 `MainHook.kt` 实现 `IXposedHookLoadPackage/ZygoteInit/InitPackageResources`；
APK 里根本没有这个类。作者换框架后未公开这部分。

### 3.2 Native 层是纯黑盒

源码仓库**零** `.c/.cpp/.h`。APK 带 4 个 `.so`（arm64-v8a）：

| 库 | 大小 | 归属 |
|----|------|------|
| `liboplus_camera_pro_native.so` | 904,792 | **模块自有** |
| `libUhdrUtils-jni.so` | 386,352 | OPPO UHDR 工具 |
| `libdexkit.so` | 290,408 | DexKit（反射查找） |
| `libandroidx.graphics.path.so` | 10,096 | AndroidX |

自有库 665 个导出符号，构成：libjpeg-turbo 262 + C++ mangled 340 + **JNI 9**。

**9 个 JNI 入口 = 它对 Java 层的真实 API**（见 `FINDINGS.json`）：
`PseudoUltraHdrNative` 8 个（gainmap 解码/编码/色调映射，走 turbojpeg）
+ `AICaptureGuideNativePatcher.patchMorphoAnchorTrackingNative` 1 个。

→ 「伪超 HDR」这条功能链的实现主体在 native，**读源码永远看不到**。

### 3.3 R8 full-mode 混淆，且保留名有规律

源码 41 个类，DEX 里只有 **5 个**保留原始全名：

```
com/tlsu/opluscamerapro/ModernHookEntry
com/tlsu/opluscamerapro/hook/camera/PseudoUltraHdrNative
com/tlsu/opluscamerapro/hook/camera/AICaptureGuideNativePatcher
com/tlsu/opluscamerapro/ui/MainActivity
com/tlsu/opluscamerapro/utils/App
```

保留原因可解释：`MainActivity` 被 manifest 按名引用；两个 Native 类的** JNI 符号名由类名派生**，改名即断链；
另两个是 keep 规则保护的入口。其余 36 类被重命名为短 ASCII 名（不是「类丢失」）。

> 这是本次逆向最实用的方法论收获：**看哪些类拒绝被混淆，就知道谁在按名字引用它。**

---

## 4. 权限与组件（REA apktool 通道解出）

权限 6 项：`QUERY_ALL_PACKAGES`、`INTERNET`、`MANAGE_EXTERNAL_STORAGE`、
`READ/WRITE_EXTERNAL_STORAGE`、`DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`（自身）

组件：`MainActivity` / `MainActivityLauncher` / `XposedProvider`(libxposed) /
`FileProvider` / `InitializationProvider` / `ProfileInstallReceiver`

APK 内 assets：`filters`(20) `SubModule`(10) `protobuf`(7) `ProXDR`(6) `watermark`(5) `algo`(2) `main.jar`
附属模块 `module.prop` 显示 version 3.1.22 / versionCode 1610211 / author TimelessU

---

## 5. REA 安装与使用状态

**已装好**
- `rea-agents` **6.10.1** 全局（`/usr/local/bin/rea`、`rea-agents`）
  装前审阅：10490 文件、**无 preinstall/postinstall 脚本**、依赖 30 个包
- MCP 注册写入 `/root/.dsh/cordis.patch.yml`：stdio `node /usr/local/bin/rea mcp`，timeout 450s
- 技能 `reverse-engineer-anything` → `/root/.agents/skills/`
- 依赖：JDK 21（`openjdk-21-jdk-headless`，含 jdk.compiler）、apktool 2.7.0
- jadx MCP JAR 0.7.1 → `/root/.local/share/rea/`，SHA-256 官方校验通过
- `rea doctor --provider jadx` → **healthy**

**当前会话走 CLI**：MCP 工具需**重启 DSH 客户端**才会出现。

**未通的路**
- ❌ jadx 反编译：`Selected JADX input bytes changed during admission at .../ReaJadxBridge.java`
  REA 现场生成的桥接源被自身稳定性校验判为字节漂移；换 TMPDIR、换工作区目录均无效 → **proot 环境限制**
- ❌ Ghidra / IDA / Hopper 未安装（native 伪代码需要 Ghidra 12.x，设 `GHIDRA_INSTALL_DIR`）

---

## 6. 踩坑清单（下次直接照做）

1. `rea setup` 只写注册，**不加载工具**——必须重启客户端
2. jadx 需要**完整 JDK**（含 `jdk.compiler`）；只装 JRE 会报误导性的 admission 错误
3. proot 里 `apt-get install` 前先 `apt-get update`（否则 404）
4. `update-alternatives` 因缺 `/usr/share/man/man1` 失败 → `mkdir -p` 后 `dpkg --configure -a`
5. github.com 直连被掐 → `gh-proxy.com` 镜像 + **官方 digest 校验**（完整性不打折）
6. REA CLI 参数是**位置参数**不是 `--path`；summary 交付要 `--detail summary --evidence_output <file>` 两个一起给
7. 混淆判定**不能**用「非 ASCII 字符」——R8 短名也是 ASCII，会得出错误计数

---

## 7. 复现命令

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-arm64
export REA_JADX_MCP_JAR=/root/.local/share/rea/jadx-headless-mcp-0.7.1-all.jar

rea doctor --provider jadx --json
rea inspect-apk-signature OPCameraPro_v3.1.22.apk --detail summary --evidence_output sig.json
rea decode-android-resources OPCameraPro_v3.1.22.apk --no-strings --json > res.json
rea inspect-native-exports libs/liboplus_camera_pro_native.so --json
# 重启 DSH 后可用 MCP：open_binary → inspect_artifact → search_android_classes
```

---

## 8. 下一步可选（按价值排序）

1. **换正常 Linux/x86 主机跑 jadx** → 拿到 v3.1.22 真实 Java 反编译源码，与镜像 diff 出未公开改动
2. **装 Ghidra 12.x** → `liboplus_camera_pro_native.so` 伪代码，还原 gainmap 色调映射算法
3. **对比 v3.1.10→v3.1.22 两版 APK** → `compare_functions` / `match_native_functions` 看架构迁移过程
4. 拆 `assets/main.jar` 与 `algo/`、`ProXDR/`（本次未展开）

---

## 9. 交付物清单（本 zip 内）

| 文件 | 说明 |
|------|------|
| `HANDOVER.md` | 本文档 |
| `FINDINGS.json` | 全部结构化证据（机器可读，含 Evidence 身份） |
| `OPCameraPro_v3.1.22.apk` | 样本原件（9.03MB，SHA256 见 §2） |
| `libs/*.so` | 4 个原生库（1.6MB） |
| `res.json` | REA apktool 解码原始结果（manifest/权限/元数据） |
| `source-repo/` | GPL 镜像源码（41 Kotlin 文件，1.2MB） |
| `source-repo-LICENSE` | GPL-3.0 原文（再分发须遵守） |
