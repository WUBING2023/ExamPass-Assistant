# EPA 多 Agent 编排方案

> 把 `/exampass` 从「单 Agent 一把梭」改成「骨架 → 并行创作 → 并行评审 → 一轮定向修订 → 渲染」。
> 五张 Agent 方法论卡片见 `agents/`，本文只管**它们之间怎么协作**。

## 决策基线（已确认）

| 维度 | 决策 |
|------|------|
| 骨架 | 加（共享契约，唯一通读全局） |
| 验证 | 不联网，PPT 为准 |
| 修订 | 一轮封顶 |
| 并行粒度 | **按章并行**（每章一个笔记 Agent + 一个题目 Agent） |
| 修订执行者 | **重启原创作 Agent**（带反馈重做受影响部分） |
| 做题验证 | **两遍都跑**（Pass1 仅题干 / Pass2 题干+笔记） |
| 触发方式 | 多 Agent 流程**设为默认**；老快流程降为 `/exampass fast` |

## 流程图

```
Phase 0  提取 (Python，不变)
         run_exampass.py <dir> → .epa_work/_extraction_bundle.json
                    │
Phase 1  骨架 (串行 · 1 Agent · 读全局)
         skeleton-agent → .epa_work/knowledge_skeleton.json (DAG + source_refs)
                    │   编排器按 source_refs 切片到 .epa_work/slices/chN_*.json
                    ▼
Phase 2  并行创作 (按章 · 2×N Agent)         ┌─ 每章并行 ─┐
         for 每章 N：                         │            │
           notes-agent(chN 切片)  → notes/chN.html        │
           item-agent (chN 切片)  → questions/chN.json    │
                    │   （两者都只读骨架切片+提取切片，互不依赖）
                    ▼
Phase 3  并行评审 (按章 · 2×N Agent)
         for 每章 N：
           reviewer-agent(notes/chN) → reviews/chN.json   (critical/important/minor)
           solver-agent (questions+notes/chN)             (两遍法 → 诊断标签)
             ├ Pass1 仅题干  → diagnostics/chN_p1.json
             └ Pass2 +笔记   → diagnostics/chN_p2.json
                    │   编排器对照标准答案打最终标签
                    ▼
Phase 4  汇总反馈 (编排器，无 Agent)
         收集所有 critical+important 问题 + 可执行诊断标签，按 kc_id/章分组
         minor 只记录，不进修订
                    ▼
Phase 5  一轮定向修订 (重启原创作 Agent · 只重做受影响的章)
         有笔记问题的章：重启 notes-agent(chN + 反馈) → 覆盖 notes/chN.html
         有题目问题的章：重启 item-agent (chN + 反馈) → 覆盖 questions/chN.json
                    │   一轮封顶：修订产物不再二次验证
                    ▼
Phase 6  渲染 (现有模板引擎，不变)
         按骨架顺序拼接 notes/*.html + questions/*.json
         → template_engine 渲染知识清单 HTML + 章节测试 HTML
         → 同时保存 knowledge_skeleton.json
```

## 数据工作区

所有中间产物落在目标目录下的 `.epa_work/`，便于断点续跑、调试、人工检查：

```
.epa_work/
  _extraction_bundle.json        # Phase0
  knowledge_skeleton.json        # Phase1（也作为最终产物保留）
  slices/chN_skeleton.json       # Phase1 切片：分给下游的知识组件
  slices/chN_extract.json        # Phase1 切片：对应提取内容（按 source_refs）
  notes/chN.html                 # Phase2/5
  questions/chN.json             # Phase2/5
  reviews/chN.json               # Phase3
  diagnostics/chN_p1.json        # Phase3 Pass1
  diagnostics/chN_p2.json        # Phase3 Pass2
  feedback/chN.json              # Phase4 汇总（喂给 Phase5）
```

**子 Agent 不把大块内容塞进 prompt**：编排器把切片写成文件，prompt 里只给文件路径，子 Agent 自己读。输出也写文件，编排器只收文件。省 token、好调试。

## 编排器职责（主 Agent 按 SKILL.md 执行）

编排器 = 跑 `/exampass` 的主 Claude。它不创作内容，只做调度：

1. 跑 Phase 0 脚本。
2. 用 `agents/skeleton-agent.md` 的 Part 4 prompt 起 1 个 Agent，产骨架。
3. 按 `source_refs` 切片写盘。
4. Phase 2：对每章并行起 notes/item Agent（用各卡 Part 4 prompt + 切片路径）。
5. Phase 3：对每章并行起 reviewer/solver Agent；solver 分两次调用（Pass1→Pass2）；对照答案打标签。
6. Phase 4：汇总 critical+important + 可执行标签 → `feedback/chN.json`。
7. Phase 5：**只对有反馈的章**重启对应创作 Agent。
8. Phase 6：拼接 → 调模板引擎渲染 → 打开。

## SKILL.md 路由骨架（待写，先给结构）

```
## 命令路由
- args == "update"            → 技能更新（不变）
- args == "graph" / "graph …" → 知识图谱（不变）
- args == "fast" / "fast …"   → 【新】老的单 Agent 快流程（原「执行流程」整段挪到这里）
- 其它（空 / 目录路径）        → 【新默认】多 Agent 深度流程（Phase 0–6）

## 多 Agent 深度流程
（Phase 0–6 的可执行说明 + 每个 Phase 引用 agents/*.md 的 Part 4 prompt）

## 快速流程（fast）
（现有「执行流程 / 内容质量要求 / 题目规范」整段，作为 fast 分支保留）
```

现有那一大段「内容质量要求」「题目编写规范」**不删**——它们降级成 `fast` 分支的指导，同时深度流程的卡片其实是它的升级版。两套共存。

## 成本与边界

- **成本**：一门 5 章的课 ≈ 1(骨架) + 10(创作) + 10(评审) + ≤10(修订) ≈ **30+ 次 Agent 调用**，比单 Agent 慢数倍、token 涨数倍。这就是它降为「默认但重」、另留 `fast` 快道的原因。
- **章数过多**：若章节 >8，编排器分批起 Agent（一批 ≤8 并行），避免调度过载。
- **子 Agent 失败**：按章独立，失败只重试该章，不影响其它章。
- **一轮封顶**：Phase 5 的修订产物**不再二次验证**。若修订引入新问题，本轮不兜——这是「一轮」的代价，可接受。
- **answer_suspect**：做题 Agent 算出的答案≠标准答案时，标记反馈给题目 Agent 复核；但因一轮封顶，复核后的答案不再过做题 Agent。
- **渲染接口不变**：模板引擎仍吃「完整笔记 + 题目集」，编排器只是在调它之前把按章产物按骨架顺序拼好。具体函数签名在接线时核对。

## 不做的事

- 不联网（已定）。
- 不做多轮迭代（已定一轮）。
- 不改提取管线和模板引擎（两头不动，只换中间的「理解+生成」内核）。
- 做题 Agent 不预测学生分数（卡片已写死）。
```
