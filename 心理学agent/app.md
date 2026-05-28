# 心语 APP 打包发布计划

## 项目信息

| 项目 | 详情 |
|------|------|
| 应用名称 | 心语 |
| 技术栈 | Expo 55 + React Native 0.83.2 |
| 后端地址 | https://xinyu.acai777.cn |
| 目标平台 | Android (APK/AAB) + iOS (IPA) |

---

## 方案选择

### 方案A：EAS Build（推荐）

Expo 官方云构建服务，无需本地配置开发环境。

**优点：**
- 无需安装 Android Studio / Xcode
- 云端构建，不占用本地资源
- 自动处理签名和证书
- 支持 Android + iOS

**缺点：**
- 需要 Expo 账号（免费）
- 需要网络连接
- iOS 构建需要 Apple Developer 账号（¥688/年）

### 方案B：本地构建

在本地配置 Android Studio 进行构建。

**优点：**
- 完全离线
- 无需第三方账号

**缺点：**
- 需要安装 Android Studio（~10GB）
- 配置复杂
- Windows 无法构建 iOS

---

## 推荐流程（EAS Build）

### 第一步：准备工作

1. **注册 Expo 账号**
   - 访问 https://expo.dev 注册
   - 免费账号即可

2. **安装 EAS CLI**
   ```bash
   npm install -g eas-cli
   ```

3. **登录 Expo 账号**
   ```bash
   eas login
   ```

4. **初始化 EAS 配置**
   ```bash
   cd app
   eas build:configure
   ```

### 第二步：配置构建

创建 `eas.json` 文件：

```json
{
  "cli": {
    "version": ">= 5.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      }
    },
    "production": {
      "android": {
        "buildType": "aab"
      }
    }
  },
  "submit": {
    "production": {}
  }
}
```

### 第三步：构建 Android APK

```bash
cd app
eas build --platform android --profile preview
```

这会生成一个可直接安装的 APK 文件。

### 第四步：下载安装包

构建完成后：
1. 访问 https://expo.dev/accounts/[你的用户名]/projects/xinyu/builds
2. 下载 APK 文件
3. 传输到 Android 手机安装

---

## 发布到应用商店（可选）

### Google Play Store

1. **注册 Google Play Developer**（$25 一次性）
2. **构建 AAB 格式**
   ```bash
   eas build --platform android --profile production
   ```
3. **提交到 Play Store**
   ```bash
   eas submit --platform android
   ```

### Apple App Store

1. **需要 Apple Developer 账号**（¥688/年）
2. **在 macOS 上配置证书**（或使用 EAS 自动管理）
3. **构建 iOS**
   ```bash
   eas build --platform ios
   ```

---

## 注意事项

### 1. API 地址配置

当前代码中 API 地址已配置为线上地址：
- `app/services/api.ts`: `https://xinyu.acai777.cn`
- `app/services/websocket.ts`: `wss://xinyu.acai777.cn`

确保后端服务正常运行。

### 2. 应用图标

已有图标资源在 `app/assets/`：
- `icon.png` - 主图标
- `splash-icon.png` - 启动页
- `android-icon-*.png` - Android 自适应图标

### 3. 版本号管理

打包前更新 `app.json` 中的版本号：
```json
{
  "expo": {
    "version": "1.0.0",
    "android": {
      "versionCode": 1
    },
    "ios": {
      "buildNumber": "1"
    }
  }
}
```

### 4. 隐私政策

心理健康类应用需要隐私政策，建议：
- 在应用内添加隐私政策页面
- 在应用商店描述中提供隐私政策链接

---

## 快速开始（最小步骤）

如果只想快速生成一个可安装的 APK：

```bash
# 1. 安装 EAS CLI
npm install -g eas-cli

# 2. 登录（需要先注册 expo.dev 账号）
eas login

# 3. 进入项目目录
cd app

# 4. 配置 EAS
eas build:configure

# 5. 构建 APK
eas build --platform android --profile preview

# 6. 等待构建完成，下载 APK
```

构建时间约 10-20 分钟，完成后会收到邮件通知。

---

## 替代方案：Expo Go 测试

如果只是想在手机上测试，不需要打包：

1. 在手机上安装 **Expo Go** 应用
2. 启动开发服务器：
   ```bash
   cd app
   npx expo start
   ```
3. 用 Expo Go 扫描二维码即可运行

注意：这需要手机和电脑在同一网络，且后端服务可访问。
