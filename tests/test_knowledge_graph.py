"""Tests for knowledge_graph module."""
import json
import os

import pytest
from knowledge_graph import (
    build_graph_prompt,
    parse_graph_response,
    validate_tree_json,
    skeleton_to_graph_tree,
)


SAMPLE_SKELETON = {
    "title": "深度学习",
    "chapters": [
        {
            "id": "ch1",
            "label": "第1章 基础",
            "summary": "本章打底",
            "kcs": [
                {"id": "kc1.1", "label": "感知机", "type": "concept",
                 "importance": "key", "deps": [], "is_hub": True,
                 "source_refs": ["slide_1"]},
                {"id": "kc1.2", "label": "反向传播", "type": "procedure",
                 "importance": "must", "deps": ["kc1.1"], "is_hub": False,
                 "source_refs": ["slide_3"]},
            ],
        },
        {
            "id": "ch2",
            "label": "第2章 进阶",
            "kcs": [
                {"id": "kc2.1", "label": "注意力", "type": "principle",
                 "importance": "must", "deps": ["kc1.2"]},
            ],
        },
    ],
}

# Richer skeleton that triggers type-group intermediate nodes (≥4 KCs, ≥2 types)
SAMPLE_SKELETON_DEEP = {
    "title": "算法设计",
    "chapters": [
        {
            "id": "ch1",
            "label": "第1章 分治",
            "summary": "分治策略",
            "kcs": [
                {"id": "k1", "label": "分治思想", "type": "concept", "importance": "key", "deps": []},
                {"id": "k2", "label": "递归树", "type": "concept", "importance": "freq", "deps": ["k1"]},
                {"id": "k3", "label": "主定理", "type": "principle", "importance": "must", "deps": ["k2"]},
                {"id": "k4", "label": "归并排序", "type": "procedure", "importance": "key", "deps": ["k2"]},
                {"id": "k5", "label": "快速排序", "type": "procedure", "importance": "must", "deps": ["k2"]},
            ],
        },
    ],
}


def test_skeleton_to_graph_tree_structure():
    tree = skeleton_to_graph_tree(SAMPLE_SKELETON)
    validate_tree_json(tree)
    assert tree["title"] == "深度学习"
    assert len(tree["nodes"]) == 2
    assert tree["nodes"][0]["label"] == "第1章 基础"
    assert len(tree["nodes"][0]["children"]) == 2  # 2 KCs, flat


def test_skeleton_to_graph_tree_folds_metadata_into_summary():
    tree = skeleton_to_graph_tree(SAMPLE_SKELETON)
    kc12 = tree["nodes"][0]["children"][1]
    assert kc12["label"] == "反向传播"
    assert "过程" in kc12["summary"]
    assert "必考" in kc12["summary"]
    # dep label resolved in summary
    assert "前置" in kc12["summary"]
    assert "感知机" in kc12["summary"]


def test_skeleton_to_graph_tree_carries_hub():
    tree = skeleton_to_graph_tree(SAMPLE_SKELETON)
    kc11 = tree["nodes"][0]["children"][0]
    assert kc11["is_hub"] is True
    assert "枢纽" in kc11["summary"]


def test_skeleton_to_graph_tree_no_deps_field():
    """Nodes should NOT carry a 'deps' field — no dashed lines in renderer."""
    tree = skeleton_to_graph_tree(SAMPLE_SKELETON)
    for node in tree["nodes"]:
        for child in node["children"]:
            assert "deps" not in child


def test_skeleton_to_graph_tree_ids_are_sequential():
    tree = skeleton_to_graph_tree(SAMPLE_SKELETON)
    ids = []
    def collect(nodes):
        for n in nodes:
            ids.append(n["id"])
            collect(n.get("children", []) or [])
    collect(tree["nodes"])
    assert all(id_.startswith("n") for id_ in ids)
    assert len(ids) == len(set(ids))


def test_skeleton_to_graph_tree_deep_with_type_groups():
    """A chapter with ≥4 KCs + ≥2 types should get type-group intermediate nodes."""
    tree = skeleton_to_graph_tree(SAMPLE_SKELETON_DEEP)
    validate_tree_json(tree)
    assert len(tree["nodes"]) == 1
    ch1 = tree["nodes"][0]
    # Should have type-group children (not flat KCs)
    assert len(ch1["children"]) >= 2
    group_labels = [c["label"] for c in ch1["children"]]
    assert any("概念" in l for l in group_labels)
    assert any("过程" in l for l in group_labels) or any("算法" in l for l in group_labels)
    # Each type group should have its KCs as children
    for grp in ch1["children"]:
        assert len(grp["children"]) >= 1
        for kc_node in grp["children"]:
            assert kc_node["children"] == []  # leaf


def test_skeleton_to_graph_tree_rejects_bad_input():
    with pytest.raises(ValueError):
        skeleton_to_graph_tree({"title": "x"})
    with pytest.raises(ValueError):
        skeleton_to_graph_tree("not a dict")


def test_build_graph_prompt_contains_text_summary():
    prompt = build_graph_prompt("第一章 深度学习基础\n神经网络概念")
    assert "第一章 深度学习基础" in prompt
    assert "神经网络概念" in prompt
    assert "知识树" in prompt or "tree" in prompt.lower()
    assert "JSON" in prompt


def test_build_graph_prompt_has_schema():
    prompt = build_graph_prompt("test content")
    assert '"id"' in prompt
    assert '"label"' in prompt
    assert '"children"' in prompt
    assert '"summary"' in prompt


def test_build_graph_prompt_empty_content():
    prompt = build_graph_prompt("")
    assert len(prompt) > 0


def test_parse_graph_response_valid_json():
    response = '''```json
{
  "title": "深度学习",
  "nodes": [
    {"id": "n1", "label": "第1章", "summary": "概述", "children": []}
  ]
}
```'''
    result = parse_graph_response(response)
    assert result["title"] == "深度学习"
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["id"] == "n1"


def test_parse_graph_response_no_code_block():
    response = '{"title": "test", "nodes": []}'
    result = parse_graph_response(response)
    assert result["title"] == "test"


def test_parse_graph_response_invalid_json():
    with pytest.raises(ValueError, match="JSON 解析失败"):
        parse_graph_response("this is not json at all")


def test_parse_graph_response_code_block_no_lang_tag():
    response = '```\n{"title": "t", "nodes": []}\n```'
    result = parse_graph_response(response)
    assert result["title"] == "t"


def test_validate_tree_json_valid():
    data = {
        "title": "课程",
        "nodes": [
            {"id": "n1", "label": "章", "summary": "s", "children": [
                {"id": "n2", "label": "节", "summary": "s2", "children": []}
            ]}
        ]
    }
    validate_tree_json(data)  # should not raise


def test_validate_tree_json_missing_title():
    with pytest.raises(ValueError, match="title"):
        validate_tree_json({"nodes": []})


def test_validate_tree_json_duplicate_ids():
    data = {
        "title": "t",
        "nodes": [
            {"id": "n1", "label": "a", "summary": "s", "children": []},
            {"id": "n1", "label": "b", "summary": "s", "children": []}
        ]
    }
    with pytest.raises(ValueError, match="重复"):
        validate_tree_json(data)


def test_save_graph_html_creates_file(tmp_path):
    from template_engine import save_graph_html

    tree = {
        "title": "测试课程",
        "nodes": [
            {"id": "n1", "label": "第1章", "summary": "概述", "children": [
                {"id": "n2", "label": "知识点1", "summary": "细节", "children": []}
            ]}
        ]
    }
    output = tmp_path / "知识图谱.html"
    save_graph_html(tree, str(output), "测试课程")

    assert output.exists()
    content = output.read_text(encoding='utf-8')
    assert "测试课程" in content
    assert "TREE_DATA" in content
    assert "n1" in content
    assert "n2" in content
    assert "graph-canvas" in content


def test_save_graph_html_creates_parent_dir(tmp_path):
    from template_engine import save_graph_html

    tree = {"title": "t", "nodes": []}
    output = tmp_path / "subdir" / "graph.html"
    save_graph_html(tree, str(output), "t")
    assert output.exists()


def test_save_graph_html_no_nested_script_tags(tmp_path):
    """Verify TREE_DATA is NOT wrapped in double script tags."""
    from template_engine import save_graph_html

    tree = {"title": "t", "nodes": [{"id": "n1", "label": "x", "summary": "y", "children": []}]}
    output = tmp_path / "graph.html"
    save_graph_html(tree, str(output), "t")
    content = output.read_text(encoding='utf-8')
    # Should NOT have nested script tags
    assert '<script><script>' not in content
    # Should have exactly one opening script tag around TREE_DATA
    assert content.count('<script>\nconst TREE_DATA') == 1
