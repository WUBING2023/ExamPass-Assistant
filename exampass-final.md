---
name: exampass-final
description: 基于课程资料生成仿真期末整卷 + 答案（多 Agent + 考试蓝图）。
---

# ExamPass Final Exam

> 期末整卷生成已并入 `SKILL.md` 的「期末整卷生成（final）」章节，通过 `/exampass final <目录>` 调用。
> 复用多 Agent 内核（骨架 → 考试蓝图 → 题目 Agent → 做题 Agent 两遍验证 → 一轮修订 → 渲染）。

## 使用方式

```
/exampass final <课程目录>
```

## 出题流程

1. 交互询问难度、时长、题型偏好
2. 复用或现产知识骨架（`knowledge_skeleton.json`）
3. 默认联网参考其他名校同类期末题（仅取灵感，内容以 PPT 为准；可关闭）
4. 排考试蓝图（重要度 × 布鲁姆层级 × 题型 × 分值 = 100，覆盖全章、难度有梯度）
5. 题目 Agent 按蓝图全局命题，做题 Agent 两遍法验证，一轮定向修订
6. `save_test()` 生成试卷 HTML，`save_knowledge_html()` 生成答案 HTML，Ctrl+P 打印 PDF

详情见 `SKILL.md` 中的 `## 期末整卷生成（final）` 章节；子 Agent 方法论见 `agents/`。
