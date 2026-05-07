# PROMPTS.md - ZeroTraceBrowser 低 Token 开发提示词模板

这些模板用于 Codex / ChatGPT。目标是减少重复解释项目结构的 Token。

---

## 1. 通用最小改动模板

```text
请基于 AGENTS.md 和 TASKS.md 理解 ZeroTraceBrowser。
本次任务：<写任务>
任务类型：<TASKS.md 中的分类>

约束：
- 不要扫描全仓库，只读取 TASKS.md 对应文件。
- 最小改动，不做无关重构。
- 不引入新框架、新构建工具或复杂依赖。
- 保持 local-first、root-scoped data、安全删除、路径边界检查不变量。
- 完成后列出修改文件、影响范围、建议测试命令。
```

---

## 2. 后端 API 修改

```text
请阅读 AGENTS.md、TASKS.md 的“后端 API / 路由改动”。
我要修改 API：<API 路径>
目标行为：<目标>

请只读取：目标 route、core/context.py 相关函数、core/schemas.py、对应测试。
实现时不要绕过 `core/app/security.py` 或 `core/services/file_operations.py` 的路径边界检查，不要破坏 `data/roots/<root_id>/` 隔离。
请补充/更新 pytest。
```

---

## 3. 前端 UI 修改

```text
请阅读 AGENTS.md、TASKS.md 的“前端页面 UI 改动”。
页面：<index/viewer/duplicates/recycle/tasks/settings>
目标：<目标>

请只修改对应 html、page js、必要的 style.css 和 locales zh/en/ja。
不要引入框架，不要改变 API 协议，除非明确需要。
新增文案必须进入 i18n。
```

---

## 4. 路径安全 / 删除相关修改

```text
请阅读 AGENTS.md、TASKS.md 的“路径安全 / 删除 / 回收区”。
目标：<目标>

这是高风险改动，请重点保护：
- 用户原图不能直接 unlink。
- 删除必须进入应用内回收区。
- restore/purge/clear 只能作用于合法回收区文件。
- 所有 relative_path 必须经过 resolve_under_root。

请更新 tests/test_api_boundaries.py 或 tests/test_api_user_flow.py。
```

---

## 5. 性能 / 时间线 / 滚动问题

```text
请阅读 AGENTS.md、TASKS.md 的“图片列表 / 时间线 / 缩略图性能”。
问题现象：<例如滚动到底部反复刷新 / 时间线跳动 / 缩略图加载慢>

请优先检查 `static/js/pages/index-page.js`、`core/services/image_scan_service.py`、`core/services/image_index_service.py`、`core/services/thumbnail_service.py`。
不要重写整个 gallery，只做局部修复。
完成后说明是否影响 async_scan、include_total、timeline_index。
```

---

## 6. 任务系统 / 重复检测

```text
请阅读 AGENTS.md、TASKS.md 的“任务系统 / MediaArchiveOrganizer 集成”。
目标：<目标>

请保护：
- 同一时间一个任务。
- hash DB 按 root 隔离。
- duplicates 结果按 root 匹配。
- dst 不能是 src 或其子目录。

请运行或建议运行 tests/test_api_tasks.py 与 tests/test_api_duplicates.py。
```

---

## 7. 让 AI 先做影响分析，不改代码

```text
请基于 AGENTS.md、ARCHITECTURE.md、TASKS.md 做影响分析，不要修改代码。
需求：<需求>

请输出：
1. 应读取的最小文件集合
2. 可能影响的 API / 页面 / 测试
3. 风险点
4. 推荐最小实现方案
5. 建议测试命令
```

---

## 8. 让 AI 检查一次改动

```text
请作为 reviewer 检查本次 diff。
项目约束见 AGENTS.md。
重点检查：
- 是否破坏安全删除
- 是否破坏 root-scoped data
- 是否有路径穿越风险
- 前端文案是否同步 i18n
- 是否需要补测试

请只指出具体问题和建议补丁，不要泛泛而谈。
```
