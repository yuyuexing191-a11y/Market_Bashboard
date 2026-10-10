# 任务跟踪：GitHub

本项目的任务和需求规格记录在 GitHub Issues 中。使用 `gh` 命令行工具进行操作。

## 操作约定

- 创建任务：`gh issue create --title "..." --body-file <文件路径>`。多行正文先写入临时文件，再传入该文件路径。
- 读取任务：`gh issue view <编号> --comments`；同时获取标签，需要时使用 `jq` 筛选评论。
- 列出任务：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，按需要添加 `--label` 或调整 `--state`。
- 评论任务：`gh issue comment <编号> --body-file <文件路径>`。
- 添加或移除标签：`gh issue edit <编号> --add-label "..."` 或 `--remove-label "..."`。
- 关闭任务：`gh issue close <编号> --comment "..."`。

通过 `git remote -v` 确定仓库；在仓库目录中执行时，`gh` 会自动推断目标仓库。

## 是否将外部合并请求纳入任务分诊

当前设置：否。供技能识别的配置标记为 **PRs as a request surface: no.**

若以后希望将外部 PR 作为需求来源，将标记中的 `no` 改为 `yes`，`/triage` 会读取此设置。

启用后，PR 使用与任务相同的标签和状态，操作改用 `gh pr`：

- 读取：`gh pr view <编号> --comments`；查看变更：`gh pr diff <编号>`。
- 列出外部 PR：`gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，仅保留作者关系为 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE` 的记录。
- 评论：`gh pr comment <编号> --body-file <文件路径>`；调整标签：`gh pr edit`；关闭：`gh pr close`。

GitHub 的任务和 PR 共用编号。遇到单独的 `#42` 时，先用 `gh pr view 42` 判断是否为 PR，再按需用 `gh issue view 42` 读取任务。

## 技能要求“发布到任务跟踪系统”时

创建 GitHub Issue。

## 技能要求“读取相关任务”时

执行 `gh issue view <编号> --comments`。

## 路线探索操作

以下约定供 `/wayfinder` 使用。一个总览任务保存探索路线，子任务保存具体工作。

- 总览任务：标记为 `wayfinder:map`，正文包含笔记、已达成的决策和待探索问题。使用 `gh issue create --label wayfinder:map` 创建，正文通过 `--body-file` 传入。
- 子任务：使用 GitHub 子任务接口（通过 `gh api`）连接到总览任务。若仓库不支持子任务，在总览正文中添加任务清单，并在子任务开头写上 `Part of #<总览编号>`。标签使用 `wayfinder:<类型>`，类型为 `research`、`prototype`、`grilling` 或 `task`；认领后分配给负责的开发者。
- 阻塞关系：优先使用 GitHub 原生任务依赖。添加依赖：`gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<阻塞任务的数据库ID>`。数据库 ID 通过 `gh api repos/<owner>/<repo>/issues/<编号> --jq .id` 获取，与任务编号和 `node_id` 不同。`issue_dependencies_summary.blocked_by` 表示尚未关闭的阻塞任务数量。若不支持原生依赖，在子任务正文开头写 `Blocked by: #<编号>, #<编号>`。所有阻塞任务关闭后，该任务才可开始。
- 查询可开始的任务：列出总览下尚未关闭的子任务，排除仍有阻塞任务或已经分配负责人的记录；按总览顺序选择第一个。使用原生依赖摘要或正文中的 `Blocked by` 行判断阻塞情况。
- 认领：`gh issue edit <编号> --add-assignee @me`，作为该次路线探索的第一项写操作。
- 完成：用 `gh issue comment <编号> --body-file <文件路径>` 记录结果，再执行 `gh issue close <编号>`，最后在总览的已达成决策中补充结论摘要和链接。
