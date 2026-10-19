# MotionSites Prompt Gallery

一个用于浏览、筛选和复制本地 328 条 AI 设计提示词快照的网页工具。每条记录提供直达 MotionSites 官网的效果预览入口。

## 内容

- `motionsites_all_prompts.json` - 全部 328 条提示词（含 AI 生成中文描述）
- `motionsites_app_prompts.json` - 17 条 App 提示词
- `motionsites_website_prompts.json` - 311 条 Website 提示词
- `motionsites_free_prompts.json` - 114 条免费提示词
- `motionsites_premium_prompts.json` - 214 条付费提示词
- `motionsites_all_prompts.csv` - CSV 格式表格
- `motionsites_prompts_gallery.html` - 卡片画廊源文件（开发时需 HTTP 服务）
- `build_gallery.py` - 生成免启动服务的离线 HTML 和轻应用上传 ZIP（仅需 Python 3 标准库）
- `THIRD_PARTY_NOTICES.md` - 第三方内容、官网预览与使用边界

## 使用方式

首次或数据更新后执行：

```bash
python3 build_gallery.py
```

双击 `dist/index.html` 即可使用，无需每次启动服务。328 条记录已内嵌；搜索、筛选、详情和复制均在本地运行。预览按钮会在新窗口打开对应官网效果，需要联网。浏览器禁止复制时会显示手动复制提示。

官网预览入口覆盖全部 328 条记录，但不承诺历史内容仍全部存在。官网可能调整名称或访问权限；若未进入对应效果，可在官网按标题搜索。本仓库不镜像或分发官网视频和演示源码，详见[第三方说明](THIRD_PARTY_NOTICES.md)。本次更新没有重新抓取提示词数据。

## 轻应用平台

将 `dist/motionsites-light-app.zip` 上传到支持静态 HTML 的轻应用平台。ZIP 根目录仅含 `index.html`，无需数据库、后端或 API Key。`dist/manifest.json` 包含记录数、文件大小和 SHA-256。

平台需允许 JavaScript 与打开外部 HTTPS 链接；剪贴板受限时可以在详情中手动选取文本。上传成功不代表已发布，仍需完成平台发布流程并检查实际预览链接和复制功能。

## 源文件开发

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

访问 `http://127.0.0.1:8765/motionsites_prompts_gallery.html`。源文件通过相对路径读取 JSON，不能直接以 `file://` 加载；生成的 `dist/index.html` 支持直接打开。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

构建过程验证数据字段与 ID、内嵌 JSON、ZIP 内容和摘要。浏览器检查应覆盖 328 个预览入口、Website/App 路径、搜索筛选、键盘焦点、详情与复制；实际官网内容可用性需与本地功能分别核验。


