"""Knowledge graph prompt builder and JSON utilities.

Generates the prompt that asks Claude to structure extracted course
content into a hierarchical knowledge tree, then parses and validates
the response.
"""

import json
import re


def build_graph_prompt(text_summary: str) -> str:
    return f"""你是一位资深的大学课程辅导专家。请根据以下课程资料，生成一份**知识树结构**，用作交互式知识图谱。

## 输出要求

输出严格的 JSON 格式，不含其他文字：

```json
{{
  "title": "课程名称",
  "nodes": [
    {{
      "id": "n1",
      "label": "第1章 XXX",
      "summary": "从PPT原文提取的章节概述，1-2句话",
      "children": [
        {{
          "id": "n2",
          "label": "核心概念/知识点",
          "summary": "PPT关于该知识点的关键表述",
          "children": [
            {{"id": "n3", "label": "具体公式/方法", "summary": "关键细节", "children": []}}
          ]
        }}
      ]
    }}
  ]
}}
```

## 构建规则

1. **根节点**：`title` 是课程名称，`nodes` 是顶层章节列表。
2. **Lv1 章节**：每个章节目录对应一个 Lv1 节点。单章课程也正常只有 1 个 Lv1 节点。
3. **Lv2+ 知识点**：逐层细化。中间节点带 `children`，叶子节点 `children: []`。
4. **深度**：3-5 层为宜。每个 Lv1 章节下至少 2 个 Lv2 知识点。
5. **id 唯一**：使用 "n1", "n2" ... 全局递增，不可重复。
6. **summary**：每个节点必须从 PPT 原文提取摘要，1-2 句话。
7. **叶子节点**：深入到具体概念、公式、方法、题型。

## 课程资料

{text_summary}
"""


def parse_graph_response(response: str) -> dict:
    """Extract and parse JSON from Claude's response (may contain markdown fences)."""
    json_str = None

    # Strategy 1: markdown code block with optional json tag
    m = re.search(r'```(?:json)?\s*\n(.*?)\n```', response, re.DOTALL)
    if m:
        json_str = m.group(1)
    else:
        # Strategy 2: find JSON object with title and nodes (non-greedy)
        m = re.search(r'\{[\s\S]*?"title"[\s\S]*?"nodes"[\s\S]*?\}', response)
        if m:
            # Safety: verify only one top-level { in match
            candidate = m.group(0)
            if candidate.count('{') == 1 or candidate.strip().count('\n{') == 0:
                json_str = candidate

    if not json_str:
        json_str = response

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}. 原始响应前200字符: {response[:200]}")

    validate_tree_json(data)
    return data


def validate_tree_json(data: dict):
    """Validate knowledge tree JSON structure. Raises ValueError on problems."""
    if not isinstance(data, dict):
        raise ValueError("根必须是 JSON 对象")
    if "title" not in data:
        raise ValueError("缺少 'title' 字段")
    if "nodes" not in data:
        raise ValueError("缺少 'nodes' 字段")
    if not isinstance(data["nodes"], list):
        raise ValueError("'nodes' 必须是数组")

    ids = set()

    def walk(nodes):
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError(f"节点必须是对象: {node}")
            if "id" not in node:
                raise ValueError(f"节点缺少 id: {node}")
            if "label" not in node:
                raise ValueError(f"节点 {node.get('id', '?')} 缺少 label")
            if "summary" not in node:
                raise ValueError(f"节点 {node.get('id', '?')} 缺少 summary")
            nid = node["id"]
            if nid in ids:
                raise ValueError(f"重复 id: {nid}")
            ids.add(nid)
            if "children" in node:
                if not isinstance(node["children"], list):
                    raise ValueError(f"节点 {nid} 的 children 必须是数组")
                walk(node["children"])

    walk(data["nodes"])


_TYPE_CN = {"fact": "事实", "concept": "概念", "procedure": "过程", "principle": "原理"}
_IMPORTANCE_CN = {"must": "必考", "key": "重点", "freq": "高频", "info": "了解"}
_TYPE_GROUP_LABEL = {
    "concept": "📐 核心概念",
    "principle": "🔬 原理与推导",
    "procedure": "⚙ 算法与过程",
    "fact": "📋 关键事实",
}


def _next_id(counter):
    """Generate a sequential node id: n1, n2, ..."""
    nid = f"n{counter[0]}"
    counter[0] += 1
    return nid


def _kc_summary(kc, label_by_id):
    """Build a tooltip summary string for a knowledge component."""
    parts = []
    t = _TYPE_CN.get(kc.get("type"), kc.get("type"))
    if t:
        parts.append(t)
    imp = _IMPORTANCE_CN.get(kc.get("importance"))
    if imp:
        parts.append(imp)
    deps = kc.get("deps") or []
    if deps:
        parts.append("前置：" + "、".join(label_by_id.get(d, d) for d in deps))
    if kc.get("is_hub"):
        parts.append("枢纽概念")
    return " · ".join(parts)


def skeleton_to_graph_tree(skeleton: dict) -> dict:
    """Convert a knowledge skeleton into a *deep* graph tree JSON.

    Produces a 3–4 level tree: chapter → type-group → KC (leaf). When a chapter
    has too few KCs or only one type, type-group nodes are skipped (2-level fallback).
    No dependency dashed lines — color alone distinguishes branches.
    """
    if not isinstance(skeleton, dict):
        raise ValueError("骨架必须是 JSON 对象")
    chapters = skeleton.get("chapters")
    if not isinstance(chapters, list):
        raise ValueError("骨架缺少 'chapters' 数组")

    label_by_id = {}
    for ch in chapters:
        for kc in ch.get("kcs", []) or []:
            label_by_id[kc.get("id")] = kc.get("label", kc.get("id"))

    counter = [1]
    nodes = []
    for ch in chapters:
        kcs = ch.get("kcs", []) or []
        groups = {}
        for kc in kcs:
            t = kc.get("type", "concept")
            groups.setdefault(t, []).append(kc)

        # Decide whether to insert type-group level:
        # use groups when ≥2 distinct types *and* ≥2 KCs per group on average.
        use_groups = len(groups) >= 2 and len(kcs) >= 4

        if use_groups:
            children = []
            for typ, group_kcs in groups.items():
                group_node = {
                    "id": _next_id(counter),
                    "label": _TYPE_GROUP_LABEL.get(typ, typ),
                    "summary": f"{len(group_kcs)} 个知识组件",
                    "children": [],
                }
                for kc in group_kcs:
                    group_node["children"].append({
                        "id": _next_id(counter),
                        "label": kc.get("label", kc.get("id")),
                        "summary": _kc_summary(kc, label_by_id),
                        "is_hub": bool(kc.get("is_hub", False)),
                        "children": [],
                    })
                children.append(group_node)
        else:
            children = []
            for kc in kcs:
                children.append({
                    "id": _next_id(counter),
                    "label": kc.get("label", kc.get("id")),
                    "summary": _kc_summary(kc, label_by_id),
                    "is_hub": bool(kc.get("is_hub", False)),
                    "children": [],
                })

        nodes.append({
            "id": _next_id(counter),
            "label": ch.get("label", ch["id"]),
            "summary": ch.get("summary", ""),
            "children": children,
        })

    tree = {"title": skeleton.get("title", "课程"), "nodes": nodes}
    validate_tree_json(tree)
    return tree
