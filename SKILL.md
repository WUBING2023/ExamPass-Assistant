---
name: exampass
description: 将课程资料（PPT/Word/PDF）按章节生成知识清单和交互式章节测试，帮助高效期末复习。
---

# ExamPass Assistant

## 执行流程

### 第一步：提取（~30s）
```bash
python scripts/run_exampass.py <目标目录>
```
产出每个章节文件夹下的 `_extraction_bundle.json`。

### 第二步：分析（Claude，仅首次）
Claude 读取 `_extraction_bundle.json`，深度分析后输出 `_exam_cache.json`：

```python
{
  "knowledge_body": "<h2>一、...</h2>\n<h3>1.1 ...</h3>\n<p>...</p>\n...",
  "questions": [
    {"type":"choice","points":2,"question":"...","options":["A","B","C","D"],"answer":0,"explanation":"...","pitfall":"..."},
    ...
  ]
}
```

### 第三步：渲染（<1s，每次）
```python
from scripts.template_engine import save_knowledge_html, save_test
import json

with open('_exam_cache.json') as f:
    cache = json.load(f)
save_knowledge_html(cache['knowledge_body'], '知识清单.html', '章节标题')
save_test(cache['questions'], '章节测试.html', '章节标题', '满分100分', duration_minutes=30)
```

### 第四步
浏览器打开 HTML。Ctrl+P 打印为 PDF。

## 缓存策略

- 首次运行：执行全部四步（~2 分钟）
- 再次运行同目录：跳过第二步，直接从 `_exam_cache.json` 渲染（<1 秒）

## 内容生成规范

### knowledge_body 格式
- 只写 H2/H3/p/table/blockquote，引擎自动加 H1 + 目录
- 公式用 `$$...$$`（独立行）和 `$...$`（行内）
- 箭头用 `--&gt;`，引号用「」，不用中文弯引号
- 每个章节配对比表格和重点 blockquote

### questions 格式
- 28 题：10 choice(2pt) + 10 tf(1pt) + 4 short(6pt) + 3 essay(8+8+10) + 1 comprehensive(20pt) = 100pt
- 题干不加编号（模板自动加），选项不加 A/B/C/D 前缀（模板自动加）
- explanation 支持 HTML，公式中的反斜杠需写成 `\\`
- pitfall 可选，写常见易错点
- choice 的每个选项应有迷惑性，正确选项唯一
- tf 题覆盖易混淆概念
- short/essay 的 explanation 需包含评分要点

## 常见错误及避免方法

1. **Python 内联代码过长** → 写成 .py 文件再执行，绝不在 shell 中内联超 200 行 Python
2. **`$$` 内的 `\\text` 等命令** → Python 字符串中写成 `\\\\text`（四重反斜杠）
3. **中文引号被转义** → 使用「」替代 ""
4. **Unicode `→` 导致 SyntaxError** → 使用 `--&gt;` 或文字"到"
5. **题目 explanation 中的 `$`** → JSON 内无需转义，但在 Python 字符串中注意与 f-string 冲突
