# ARCHITECTURE.md - ZeroTraceBrowser 低 Token 架构说明

本文给 AI 快速理解项目架构使用。更详细的产品说明看 `README_zh.md`；具体开发入口看 `AGENTS.md` 和 `TASKS.md`。

---

## 1. 架构总览

```text
Browser UI (static HTML/CSS/JS)
        |
        | fetch /api/*
        v
FastAPI routes
        |
        v
Route Context (core/context.py)
        |
        +--> services/        业务逻辑
        +--> repositories/    持久化读写封装
        +--> domain/          root workspace / 数据对象
        +--> infrastructure/  文件系统、hash、图片处理、任务队列
        |
        v
Local filesystem + data/roots/<root_id>/
```

项目不是云服务，也不是多用户系统。默认是本机浏览器访问本机 FastAPI 服务。

---

## 2. 后端层次

### 2.1 `core/routes/`

负责 HTTP API 输入输出、参数校验、调用 context。
路由里可以做轻量 orchestration，但不要堆复杂业务逻辑。

### 2.2 `core/context.py`

当前项目的“适配/聚合层”。它把 settings、root workspace、service 函数、平台操作、Pillow 能力等聚合成 route context。

AI 修改时注意：

- 不要随意把所有逻辑继续塞进 context。
- 新业务优先放到 `services/` 或 `use_cases/`。
- 需要兼容现有 tests monkeypatch 的常量引用。

### 2.3 `core/services/`

业务逻辑层。

- `image_scan_service.py`：图片/视频扫描、列表缓存、时间线入口
- `image_index_service.py`：索引缓存、summary、timeline index
- `thumbnail_service.py`：图片缩略图与视频占位缩略图
- `file_operations.py`：路径解析、复制/移动
- `recycle_paths.py`：应用内回收区路径解析
- `recycle_service.py`：删除日志、回收区记录
- `settings_service.py`：配置读写、语言/任务参数规范化
- `task_service.py`：任务注册表

### 2.4 `core/domain/`

领域数据结构与 root workspace 规则。
最关键文件：`root_context.py`。

### 2.5 `core/infrastructure/`

偏技术实现的底层适配，例如文件系统、图片元数据、hash、缩略图生成。

---

## 3. 前端层次

```text
static/
├── *.html                  页面骨架
├── css/style.css           全局样式
└── js/
    ├── core/               DOM / dialog / format / common elements
    ├── locales/            zh/en/ja + i18n helper
    └── pages/              每个页面的状态与事件逻辑
```

### 3.1 i18n 规则

- `static/js/locales/i18n.js` 负责语言规范化与 `t/trMsg/trUi/trDialog`。
- 当前支持 `zh`, `en`, `ja`。
- `zh-CN` 归一为 `zh`，`en-US` 归一为 `en`，`ja-JP` 归一为 `ja`。
- 新 UI 文案必须同时加到三个 locale 文件。

### 3.2 页面状态

页面 JS 通常包含：

- `getXElements()`：收集 DOM 节点
- `createXState()`：页面状态
- `fetchJson/postJson()`：API 请求
- render / bind / init 函数

保持这种模式，不要引入全局复杂状态管理。

---

## 4. 数据与运行目录

### 4.1 settings

`settings.json` 保存：

- active root
- image roots
- copy target
- language
- task defaults

### 4.2 root workspace

每个图片根目录对应一个 deterministic `root_id`，运行数据在：

```text
data/roots/<root_id>/
```

典型内容：

```text
root.json              当前 root 元数据
indexes/               图片索引、时间线索引
thumbnails/            缩略图缓存
deleted/               应用内回收区
logs/                  删除/操作日志
tasks/                 任务日志与输出
hash_db.sqlite3         hash 数据库
duplicates.json        当前 root 的重复检测结果
```

### 4.3 legacy 路径

`thumbnails/`, `deleted/`, `logs/` 等旧目录只保留用于兼容/迁移。
新功能不要继续依赖旧路径。

---

## 5. 关键流程

### 5.1 图片列表

```text
GET /api/images
 -> routes/images_route.py
 -> ctx.get_active_image_root()
 -> list_images_page 或 list_images_cached_page
 -> indexes cache / timeline cache
 -> 返回 relative_path、缩略图、timeline_time 等
```

### 5.2 缩略图

```text
GET /api/thumbnail?relative_path=...
 -> resolve_under_root(active_root, relative_path)
 -> thumbnail_path_for(root, relative_path)
 -> image_file_response(...)
 -> 图片生成缩略图 / 视频生成占位缩略图
```

### 5.3 安全删除

```text
POST /api/delete
 -> resolve_under_root(active_root, relative_path)
 -> build_deleted_path(root, relative_path)
 -> move_file_preserve_times
 -> append delete log
 -> clear image list cache
```

### 5.4 恢复

```text
POST /api/recycle-bin/restore
 -> resolve_deleted_file(deleted_to)
 -> move back to original relative_path
 -> update/delete log rows
```

### 5.5 重复检测任务

```text
POST /api/tasks/run-organizer
 -> validate src/dst/mode/duplicate_detection
 -> build task_id/log_path/outputs
 -> call media_engine/main.py in background thread
 -> task status available from /api/tasks/{task_id}
```

---

## 6. 测试地图

- `tests/test_api_boundaries.py`：路径安全、删除安全、root scoped runtime dirs、open path 限制
- `tests/test_api_user_flow.py`：图片列表、EXIF 时间优先级、时间线、复制/删除/恢复流程
- `tests/test_api_duplicates.py`：duplicates.json 选择、分页、active root 匹配
- `tests/test_api_tasks.py`：任务生命周期、并发限制、hash DB / duplicates root 隔离
- `tests/test_root_context.py`：root_id、root workspace 布局、settings repository 默认路径

---

## 7. 设计边界

ZeroTraceBrowser 的设计边界：

- 是本地工具，不是云相册。
- 是人工可控工具，不是自动整理机器人。
- 是轻量前端，不是 SPA 框架应用。
- 文件操作要可解释、可恢复、可审计。
