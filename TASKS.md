# TASKS.md - ZeroTraceBrowser AI 低 Token 任务入口

本文件用于减少 Codex/AI 每次理解项目的 Token 消耗。
做任务时，先匹配任务类型，只读对应文件集合。

---

## 0. 通用流程

每次任务建议这样开始：

```text
请阅读 AGENTS.md、TASKS.md。
本次任务类型是：<下面某一类>。
请只读取该类列出的文件，除非发现必要依赖。
请最小改动，不做无关重构。
```

每次完成时建议输出：

```text
修改文件：
- ...

影响范围：
- ...

建议测试：
- .\venv\Scripts\python.exe -m pytest ...
```

---

## 1. 后端 API / 路由改动

优先读取：

- `AGENTS.md`
- `core/app/factory.py`
- `core/routes/<目标>_route.py`
- `core/context.py` 中被调用的相关函数
- `core/schemas.py`
- 对应测试文件

路由映射：

- 配置/语言/root：`core/routes/settings_route.py` + `tests/test_api_boundaries.py`
- 图片列表/缩略图/复制/删除：`core/routes/images_route.py` + `tests/test_api_user_flow.py` + `tests/test_api_boundaries.py`
- 回收区：`core/routes/recycle_route.py` + `tests/test_api_boundaries.py` + `tests/test_api_user_flow.py`
- 重复图片：`core/routes/duplicates_route.py` + `tests/test_api_duplicates.py`
- 任务：`core/routes/tasks_route.py` + `tests/test_api_tasks.py`

禁止：

- 为了小 API 改动扫描整个 `static/`。
- 在 route 中绕过 `core/app/security.py` 或 `resolve_under_root`。

---

## 2. 路径安全 / 删除 / 回收区

必须读取：

- `AGENTS.md`
- `core/app/security.py`
- `core/routes/images_route.py`
- `core/routes/recycle_route.py`
- `core/services/file_operations.py`
- `core/services/recycle_paths.py`
- `core/services/thumbnail_service.py`
- `core/services/recycle_service.py`
- `core/domain/root_context.py`
- `tests/test_api_boundaries.py`
- `tests/test_api_user_flow.py`

重点检查：

- 是否所有用户输入路径都经过 resolve / boundary check。
- 删除是否进入 `data/roots/<root_id>/deleted/`。
- restore/purge/clear 是否只作用于回收区文件。
- Windows 系统回收站能力是否保持平台判断。

建议测试：

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_api_boundaries.py tests/test_api_user_flow.py
```

---

## 3. root workspace / data/roots 隔离

必须读取：

- `core/domain/root_context.py`
- `core/config/app_config.py`
- `core/context.py`
- `core/services/settings_service.py`
- `tests/test_root_context.py`
- `tests/test_api_tasks.py`
- `tests/test_api_duplicates.py`

重点检查：

- 新数据是否写入 `data/roots/<root_id>/`。
- legacy path 是否只读/迁移用途。
- 多 root 切换时 hash DB、duplicates、indexes 是否隔离。

建议测试：

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_root_context.py tests/test_api_tasks.py tests/test_api_duplicates.py
```

---

## 4. 图片列表 / 时间线 / 缩略图性能

优先读取：

- `core/routes/images_route.py`
- `core/services/image_scan_service.py`
- `core/services/image_index_service.py`
- `core/services/thumbnail_service.py`
- `core/infrastructure/imaging/metadata_reader.py`
- `core/infrastructure/imaging/thumbnail_generator.py`
- `static/js/pages/index-page.js`
- `tests/test_api_user_flow.py`

重点检查：

- `include_total`、`async_scan`、`refresh_scan` 的行为不要破坏。
- 时间线排序应使用后端生成的 `timeline_time` / `timeline_ts`。
- 滚动加载不要在前端造成重复刷新或跳动。
- 缩略图并发控制在前端已有 `THUMBNAIL_CONCURRENCY`。

建议测试：

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_api_user_flow.py
```

---

## 5. 前端页面 UI 改动

根据页面读取：

- 主图廊：`static/index.html` + `static/js/pages/index-page.js`
- 查看器：`static/viewer.html` + `static/js/pages/viewer-page.js`
- 重复图片：`static/duplicates.html` + `static/js/pages/duplicates-page.js`
- 回收区：`static/recycle.html` + `static/js/pages/recycle-page.js`
- 任务：`static/tasks.html` + `static/js/pages/tasks-page.js`
- 设置：`static/settings.html` + `static/js/pages/settings-page.js`
- 样式：`static/css/style.css`
- 通用组件：`static/js/core/*.js`
- i18n：`static/js/locales/{zh,en,ja}.js`

规则：

- 不引入 React/Vue/构建工具。
- 不把大量样式塞进 HTML style 属性。
- 新文案必须同步 zh/en/ja。
- 保持工程风格：清爽、低噪音、明确状态、按钮语义清楚。

---

## 6. i18n 文案改动

必须读取：

- `static/js/locales/i18n.js`
- `static/js/locales/zh.js`
- `static/js/locales/en.js`
- `static/js/locales/ja.js`
- 使用该文案的页面 JS/HTML

规则：

- key 命名用层级结构，避免散乱。
- 不要使用 `MESSAGES_ZH-CN` 这类带 hyphen 的全局变量风格。
- 当前模块是 ES Module import/export。
- 语言值统一为 `zh`, `en`, `ja`。

---

## 7. 任务系统 / MediaArchiveOrganizer 集成

必须读取：

- `core/routes/tasks_route.py`
- `core/services/task_service.py`
- `core/context.py` 中 task/duplicates/hash 相关函数
- `MediaArchiveOrganizer/main.py`
- `MediaArchiveOrganizer/services/organizer.py`
- `MediaArchiveOrganizer/core/hash_db.py`
- `MediaArchiveOrganizer/core/duplicate_detector.py`
- `tests/test_api_tasks.py`

重点检查：

- 任务并发限制。
- task_id、log_path、outputs 是否正确。
- `IMAGE_ORGANIZER_HASH_DB` 是否指向 root scoped hash DB。
- duplicates 是否不会错误覆盖其他 root 的结果。

建议测试：

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_api_tasks.py tests/test_api_duplicates.py
```

---

## 8. 重复图片页面 / duplicates.json

必须读取：

- `core/routes/duplicates_route.py`
- `core/context.py` 中 duplicates 相关函数
- `static/duplicates.html`
- `static/js/pages/duplicates-page.js`
- `tests/test_api_duplicates.py`

重点检查：

- active root 必须匹配 duplicates 结果。
- 缩略图路径必须通过 duplicates result root 解析。
- 分页 offset/limit 不要一次性渲染过多。

---

## 9. 设置页 / root 管理

必须读取：

- `core/routes/settings_route.py`
- `core/services/settings_service.py`
- `core/domain/root_context.py`
- `static/settings.html`
- `static/js/pages/settings-page.js`
- `tests/test_api_boundaries.py`
- `tests/test_root_context.py`

重点检查：

- add root 必须要求已存在目录。
- active root 必须在 registered roots 里。
- remove root 如带清理数据，必须只清理对应 root workspace。
- open path 必须受 safe roots 限制。

---

## 10. README / 文档改动

优先读取：

- `README.md`
- `README_zh.md`
- `README_ja.md`
- `AGENTS.md`
- `ARCHITECTURE.md`
- `TASKS.md`

规则：

- 面向用户的 README 保持产品说明。
- 面向 AI 的说明放 AGENTS/TASKS/ARCHITECTURE。
- 不要让 README 变成超长内部实现文档。
