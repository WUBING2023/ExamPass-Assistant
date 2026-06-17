---
name: exampass-graph
description: 基于课程资料生成左根右叶的交互式知识图谱（依赖虚线、枢纽★、笔记卡、拖拽、搜索、缩放）。由 /exampass graph 调用。
---

# ExamPass 知识图谱（子 skill）

> 由 `/exampass graph <目录>` 调用。生成左根右叶的交互式知识图谱：可编辑、粘贴图片、搜索、缩放、左右面板拖拽调宽。

---

## 流程

1. **提取**：`python scripts/run_exampass.py <目录>`（`.epa_work` 已存在可复用）。
2. **骨架获取**（按优先级）：
   - `.epa_work/knowledge_skeleton.json` 已存在 → 直接读取（推荐先跑一次默认流程产骨架）。
   - 骨架不存在但子 Agent 可用 → 用 `agents/skeleton-agent.md` 现产一份。
   - 骨架不存在且子 Agent 不可用（Codex / 非 Claude 平台）→ **回退**：`build_fallback_tree(bundle_path, title)` 直接从提取文本生成树（保证 Codex 用户也能拿到图谱而非卡片）。
3. **转换 + 渲染**：
```python
import json, os
from scripts.knowledge_graph import skeleton_to_graph_tree, build_fallback_tree
from scripts.template_engine import save_graph_html

# 多章课程：bundle 在 .epa_work/chapters/<章>/_extraction_bundle.json
skeleton_path = '.epa_work/knowledge_skeleton.json'
title = '课程'

if os.path.exists(skeleton_path):
    with open(skeleton_path, encoding='utf-8') as f:
        skeleton = json.load(f)
    tree = skeleton_to_graph_tree(skeleton)
    title = skeleton.get('title', title)
else:
    # 回退：从任一 bundle 直接生成（无骨架 Agent 时）
    tree = build_fallback_tree('.epa_work/chapters/<某章>/_extraction_bundle.json', title)
    title = tree['title']

save_graph_html(tree, 'EPA/知识图谱.html', title)
```
4. **打开**：浏览器打开 HTML。

---

## 图谱特性

- **左根右叶树布局**：左=章节，右=知识组件，从上到下排开。
- **依赖虚线**（`deps`）：画成虚线次级连接，告诉你"学谁之前先学谁"。
- **枢纽概念**（`is_hub`）：加 ★ 标记——这些是考试重中之重。
- **节点 tooltip**：悬停显示「类型 · 重要度 · 依赖：xxx」。
- **叶节点笔记卡**：点击叶节点右侧弹出，可打字、Ctrl+V 粘贴图片，存 localStorage，刷新仍在。
- **左右占比可拖拽**：拖中间分隔条调整树/笔记宽度。
- **搜索**：顶部输入关键词高亮命中节点。
- **缩放**：底部缩放条 / +- 按钮。
- **重命名**：双击节点标签改成自己的话。

**回退树质量**：回退模式只生成章节→要点两层，不含 type/importance/deps/is_hub 元数据（这些需要骨架 Agent）。首次建议先跑 `/exampass <目录>` 产骨架，再 `/exampass graph` 复用。

**从已有 JSON 重新生成**：用户给 `--from-json <路径>` 时直接读取——已是 tree 格式（含 `nodes`）则跳过转换，是骨架格式（含 `chapters`）则先 `skeleton_to_graph_tree()` 再 `save_graph_html()`。
