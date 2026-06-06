"""Knowledge graph prompt builder and JSON utilities.

Generates the prompt that asks Claude to structure extracted course
content into a hierarchical knowledge tree, then parses and validates
the response.
"""

import json
import re
import uuid


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
    # Try to find JSON in markdown code block
    m = re.search(r'```(?:json)?\s*\n(.*?)\n```', response, re.DOTALL)
    if m:
        json_str = m.group(1)
    else:
        # Try to find raw JSON object
        m = re.search(r'\{[\s\S]*"title"[\s\S]*"nodes"[\s\S]*\}', response)
        if m:
            json_str = m.group(0)
        else:
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
