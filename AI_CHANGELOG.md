# AI_CHANGELOG.md

用于记录给 AI 的工程上下文变化。每次较大重构后，把“为什么改、改了什么、不变量是否变化”写在这里，减少下一轮 AI 重新理解成本。

格式建议：

```text
## YYYY-MM-DD - 标题

背景：
- ...

改动：
- ...

不变量：
- 保持 / 新增 / 废弃 ...

相关文件：
- ...

建议测试：
- ...
```

---

## 2026-05-06 - 建立 AI 可持续开发文档包

背景：
- 项目重构后，Codex/AI 每次理解项目结构会消耗大量 Token。
- 需要把项目知识压缩成固定入口文档。

改动：
- 新增/更新 `AGENTS.md`：AI 总入口与开发不变量。
- 新增 `ARCHITECTURE.md`：低 Token 架构说明。
- 新增 `TASKS.md`：按任务类型列出最小读取文件集合。
- 新增 `PROMPTS.md`：Codex/ChatGPT 可复制提示词模板。
- 新增 `CODEMAP.md`：文件地图。
- 新增 `AI_CONTEXT.md`：当前项目摘要。
- 新增 `AI_CHANGELOG.md`：未来上下文变化记录。

不变量：
- local-first。
- 安全删除。
- root scoped data。
- 前端保持 Vanilla JS。
- 新 UI 文案同步 zh/en/ja。

建议测试：
- 文档改动不要求运行测试。
- 若同步做代码改动，按 `TASKS.md` 对应分类运行测试。
