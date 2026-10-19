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

双击 `dist/index.html` 即可使用，无需每次启动服务。328 条记录已内嵌；搜索、筛选、详情和复制均在本地运行。已导入的视频可在详情里本地播放；官网预览入口需要联网。浏览器禁止复制时会显示手动复制提示。

## 本地视频播放

页面顶部点击“导入视频目录”或“选择视频文件”，选择自己已取得的视频。文件不会上传。按效果 ID、标题或父目录名称精确匹配，例如：

```text
interactive-discovery.mp4
Projects Catalog.webm
supplement-shop/video.mp4
```

导入后，卡片会显示“本地预览已就绪”，点击“本地预览”即可在详情中播放；关闭详情会暂停视频。“仅显示有本地预览的条目”可筛选已有文件的效果。未匹配、同一效果对应多个视频及缓存空间不足时会明确提示，不会猜测或静默覆盖。

页面会尝试保存到当前浏览器的 IndexedDB，刷新后可重新读取。浏览器不支持或写入失败时，仅本次打开可用；浏览器也可能清理缓存，因此请保留原始视频。不同浏览器、不同网址、不同端口和部分 `file://` 环境不共享缓存；页面会明确报告保存失败。

若需要不依赖浏览器缓存的本地目录，将视频或图片放入 `local_previews/`，每个效果只保留一个同名预览文件，然后执行：

```bash
python3 build_gallery.py --local-previews local_previews
```

打开 `local_gallery/index.html`，预览会从同目录的 `media/` 读取。鼠标移入预览图时，视频静音循环播放；移出即停止并恢复缩略图。键盘聚焦卡片操作也能预览，触屏可点击“本地预览”进入详情。同一时间只加载一个悬停播放器，切换筛选、打开详情、滚出视口或切到后台时停止；自动播放失败会显示原因和详情播放入口。

视频和图片分别计数，图片会在详情中明确标注，不会被当作视频。`local_previews/` 和 `local_gallery/` 已加入 Git 忽略列表。此模式不生成轻应用上传 ZIP，避免把本机媒体混入公开上传包。匹配、媒体类型数量和缺失清单写入 `local_gallery/manifest.json`；请保留整个目录。

可选的 `local_previews/posters/<效果ID>.jpg` 会作为视频卡片缩略图随私有构建复制；图片预览直接使用自身作为缩略图。缩略图目录不会被误算为重复的预览文件。

公开仓库不附带 MotionSites 的预览媒体。用户本机的私有构建可以包含已下载的文件，实际覆盖率以该构建的 `manifest.json` 为准。文件扩展名不保证实际类型：部分官网 `.gif` 链接返回静态 PNG，动态 WebP 则可包含完整动画；应按实际解码结果分类。

官网预览入口覆盖全部 328 条记录，但不承诺历史内容仍全部存在。官网可能调整名称或访问权限；若未进入对应效果，可在官网按标题搜索。本仓库不镜像或分发官网视频和演示源码，详见[第三方说明](THIRD_PARTY_NOTICES.md)。本次更新没有重新抓取提示词数据。

## 轻应用平台

将 `dist/motionsites-light-app.zip` 上传到支持静态 HTML 的轻应用平台。ZIP 根目录仅含 `index.html`，无需数据库、后端或 API Key。`dist/manifest.json` 包含记录数、文件大小和 SHA-256。

默认上传 ZIP 不含本地视频及浏览器缓存。平台需允许 JavaScript 与打开外部 HTTPS 链接；剪贴板受限时可以在详情中手动选取文本。上传成功不代表已发布，仍需完成平台发布流程并检查实际预览链接和复制功能。

## 源文件开发

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

访问 `http://127.0.0.1:8765/motionsites_prompts_gallery.html`。源文件通过相对路径读取 JSON，不能直接以 `file://` 加载；生成的 `dist/index.html` 支持直接打开。

## 验证

```bash
python3 -m unittest discover -s tests -v
node tests/test_local_previews.cjs
node tests/test_card_preview.cjs
```

构建过程验证数据字段与 ID、内嵌 JSON、ZIP 内容和摘要。新增测试覆盖本地文件匹配、重名冲突、路径边界、私有与公开构建隔离；JavaScript 测试模拟缓存保存、重新读取和空间不足。模拟存储测试不代表浏览器持久化或播放器已实测。浏览器检查应覆盖导入、刷新恢复、媒体解码、关闭暂停、筛选与复制；本次新增播放器的页面实测因浏览器工具访问限制未完成。


