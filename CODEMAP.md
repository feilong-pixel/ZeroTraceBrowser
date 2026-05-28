# CODEMAP.md - ZeroTraceBrowser 文件地图

用于 AI 快速定位文件，避免全仓库扫描。

---

## 根目录

| 文件 | 作用 |
|---|---|
| `app.py` | FastAPI app 导出入口 |
| `core/app/factory.py` | 创建 app、注册 middleware/routes、挂载 static |
| `core/config/app_config.py` | 全局路径、语言、扩展名、legacy 路径常量 |
| `core/context.py` | route context 聚合层 |
| `core/app/security.py` | 路径安全、CORS、TrustedHost、安全打开路径 |
| `core/schemas.py` | API 请求模型 |
| `requirements.txt` | 运行依赖 |
| `requirements-dev.txt` | 开发/测试依赖 |
| `pytest.ini` / `pyproject.toml` | 测试与项目元数据 |
| `start.ps1` | Windows 启动脚本 |
| `test.ps1` | Windows 测试脚本 |

---

## 后端 routes

| 文件 | API 范围 |
|---|---|
| `core/routes/settings_route.py` | `/api/config`, settings, roots, open path |
| `core/routes/images_route.py` | `/api/images`, image, thumbnail, exif, copy, delete |
| `core/routes/recycle_route.py` | `/api/recycle-bin*` |
| `core/routes/duplicates_route.py` | `/api/duplicates*` |
| `core/routes/tasks_route.py` | `/api/tasks*` |

---

## 后端 services/domain

| 文件 | 作用 |
|---|---|
| `core/services/image_scan_service.py` | 图片/视频扫描、列表缓存、时间线入口 |
| `core/services/image_index_service.py` | 索引缓存、summary、timeline index |
| `core/services/thumbnail_service.py` | 图片缩略图与视频占位缩略图 |
| `core/services/file_operations.py` | 路径解析、copy/move 文件操作 |
| `core/services/recycle_service.py` | 删除日志、回收区记录 |
| `core/services/settings_service.py` | settings.json 与参数规范化 |
| `core/services/task_service.py` | 内存任务注册 |
| `core/domain/root_context.py` | root_id 与 `data/roots/<root_id>/` 布局 |
| `core/domain/*.py` | 图片、重复组、时间线等数据对象 |

---

## infrastructure/repositories/use_cases

| 目录 | 作用 |
|---|---|
| `core/infrastructure/filesystem/` | 本地文件系统适配 |
| `core/infrastructure/hashing/` | hash 计算 |
| `core/infrastructure/imaging/` | EXIF/元数据/缩略图 |
| `core/repositories/` | cache/file/index/log/settings/thumbnail repository |
| `core/use_cases/` | build index/timeline, copy/delete/restore image, create task 等用例 |

---

## 前端

| 文件 | 作用 |
|---|---|
| `static/index.html` | 主图廊页面 |
| `static/js/pages/index-page.js` | 主图廊逻辑：虚拟列表、筛选、选择、复制、删除、时间线 |
| `static/viewer.html` | 图片查看页面 |
| `static/js/pages/viewer-page.js` | 查看器逻辑 |
| `static/duplicates.html` | 重复图片页面 |
| `static/js/pages/duplicates-page.js` | 重复图片逻辑 |
| `static/recycle.html` | 回收区页面 |
| `static/js/pages/recycle-page.js` | 回收区逻辑 |
| `static/tasks.html` | 任务页面 |
| `static/js/pages/tasks-page.js` | 任务逻辑 |
| `static/settings.html` | 设置页面 |
| `static/js/pages/settings-page.js` | 设置逻辑 |
| `static/js/core/dom.js` | DOM helper |
| `static/js/core/dialog.js` | dialog/confirm/alert |
| `static/js/core/format.js` | 格式化 helper |
| `static/js/core/common_elements.js` | 通用元素 |
| `static/js/core/events.js` | 事件 helper |
| `static/js/locales/i18n.js` | i18n helper |
| `static/js/locales/zh.js` | 中文文案 |
| `static/js/locales/en.js` | 英文文案 |
| `static/js/locales/ja.js` | 日文文案 |
| `static/css/style.css` | 全局样式 |

---

## media_engine

| 文件 | 作用 |
|---|---|
| `media_engine/main.py` | 整理任务 CLI 入口 |
| `media_engine/services/organizer.py` | 整理流程 |
| `media_engine/core/hash_db.py` | hash DB |
| `media_engine/core/duplicate_detector.py` | 重复检测 |
| `media_engine/core/exif_reader.py` | EXIF 读取 |
| `media_engine/core/file_transfer.py` | copy/move 文件 |
| `media_engine/core/date_classifier.py` | 日期分类 |
| `media_engine/locales/*.py` | CLI 多语言输出 |

---

## 测试

| 文件 | 覆盖范围 |
|---|---|
| `tests/conftest.py` | api_client fixture，隔离测试 workspace |
| `tests/test_api_boundaries.py` | 安全边界、删除、open path、root 移除、任务参数 |
| `tests/test_api_user_flow.py` | 图片列表、EXIF、时间线、复制/删除/恢复 |
| `tests/test_api_duplicates.py` | duplicates 选择、active root 匹配、分页 |
| `tests/test_api_tasks.py` | 任务生命周期、并发限制、hash/duplicates root 隔离 |
| `tests/test_root_context.py` | root workspace 布局与 root_id |
