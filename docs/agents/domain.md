# 领域文档

本文约定工程技能探索代码库时如何读取业务术语和设计决策。

## 探索前读取

- 根目录的 `CONTEXT.md`：记录项目业务背景及术语。
- 若存在根目录的 `CONTEXT-MAP.md`，则先读取它，再读取其中与当前任务相关的各份 `CONTEXT.md`。
- `docs/adr/`：读取涉及当前工作区域的架构决策记录。在多上下文项目中，也检查 `src/<context>/docs/adr/` 下的相关记录。

如果上述文件不存在，直接继续工作。领域建模技能 `/domain-modeling` 会在术语或决策明确后按需建立文档；`/grill-with-docs` 和 `/improve-codebase-architecture` 也可能调用它。

## 文档布局

本项目采用单一上下文布局：

```text
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-决策主题.md
│   └── 0002-决策主题.md
└── src/
```

如果项目以后拆分为多个业务上下文，可采用以下布局，并在根目录通过 `CONTEXT-MAP.md` 提供索引：

```text
/
├── CONTEXT-MAP.md
├── docs/adr/                  # 跨上下文的系统决策
└── src/
    ├── <context-a>/
    │   ├── CONTEXT.md
    │   └── docs/adr/          # 当前上下文的决策
    └── <context-b>/
        ├── CONTEXT.md
        └── docs/adr/
```

## 使用统一术语

在任务标题、重构建议、诊断假设和测试名称中提及业务概念时，使用 `CONTEXT.md` 中定义的术语。

如果所需概念尚未收录，先判断它是否属于项目已有业务概念。确有缺口时，记录下来，交由 `/domain-modeling` 补充。

## 明确指出决策冲突

如果建议与已有架构决策记录冲突，明确指出所冲突的记录，并说明重新讨论的理由，例如：

> 此建议与 ADR-0007 冲突；建议重新讨论，理由是……
