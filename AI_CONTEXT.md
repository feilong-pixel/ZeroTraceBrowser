# AI_CONTEXT.md - ZeroTraceBrowser 当前 AI 记忆摘要

这是给 AI 每次启动时快速读取的项目摘要。若和代码冲突，以代码和测试为准。

---

## 当前定位

ZeroTraceBrowser 是本地图片浏览/整理工具。用户价值是：

- 本地直读，不上传云端
- 明确显示与操作本地文件
- 批量复制、预览、删除等操作由用户主动触发
- 删除可恢复、可审计
- 重复图片检测用于辅助人工判断，不自动删除

---

## 当前架构状态

项目已经从早期简单结构重构为更清晰的 FastAPI + core 分层：

- `app.py` 很薄，只导出 app。
- `core/app/factory.py` 负责创建 FastAPI 应用。
- `core/routes/` 按功能拆分 API。
- `core/context.py` 仍是重要聚合层。
- `core/domain/root_context.py` 定义 root scoped workspace。
- `static/js/pages/` 按页面拆分前端逻辑。
- `static/js/locales/` 使用 ES Modules 管理 zh/en/ja 文案。

---

## 当前最容易出问题的点

1. 路径安全：所有 relative path 必须限制在 active root 或 result root 内。
2. 删除安全：不要直接删除用户原图。
3. root 隔离：新缓存/日志/任务/duplicates/hash DB 不要写回 legacy 全局目录。
4. i18n：新增文案要同步 zh/en/ja。
5. 前端性能：主图廊有虚拟列表、分页、后台扫描，不要用粗暴重渲染破坏滚动体验。
6. 任务系统：后台任务有并发限制和 root scoped outputs。

---

## 推荐工作方式

- 小任务：只读 `AGENTS.md` + `TASKS.md` + 目标文件 + 对应测试。
- 中任务：增加 `ARCHITECTURE.md` 和 `CODEMAP.md`。
- 大重构：先让 AI 输出影响分析，不直接改代码。

---

## 当前优先维护的质量线

- `tests/test_api_boundaries.py`
- `tests/test_api_user_flow.py`
- `tests/test_api_tasks.py`
- `tests/test_api_duplicates.py`
- `tests/test_root_context.py`

这些测试比 README 更能表达项目不变量。
