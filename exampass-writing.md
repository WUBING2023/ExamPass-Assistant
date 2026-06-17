---
name: exampass-writing
description: 知识清单写作规范（深度学习模式、双色标注、四色标签、叙事弧、易错框、公式、图片识别）。被默认流程和笔记 Agent 引用。
---

# 知识清单写作规范

> 默认流程的笔记 Agent（`agents/notes-agent.md`）和渲染遵循本规范。核心硬规则也在 notes-agent 卡里同源。

## 根本原则：把逻辑嚼碎了喂给用户

PPT 的问题是信息碎片化、逻辑跳跃、缺少因果链。知识清单要做的不是「提炼要点」，而是**重构叙事**——把分散在几十张幻灯片的信息，重组成一条清晰的逻辑链：**「因为遇到什么问题 → 所以提出什么方法 → 核心思想是什么 → 具体怎么做 → 有什么局限 → 怎么改进」**。

目标不是「总结得短」，而是「读一遍就懂」。

## 叙事弧（每个 H3 知识点）

**Hook（一句话场景/谜题）→ TL;DR（`<div class="tldr">`粗体结论）→ Why（为什么需要它）→ What（是什么，此时才给定义）→ How（怎么用，例子/推导/范例）→ Checkpoint（`<div class="checkpoint">`自测，配可折叠 `<details class="cp-answer">` 参考答案）**。

每个概念至少回答：是什么 / 为什么需要它 / 怎么用·易错在哪。抽象定义永远不能出现在具体例子之前。

## 标注与格式

- **双色标注**：核心概念/定义/公式包 `<span class="kp">`（黑色加粗，扫读锚点）；解释/动机/举例包 `<span class="exp">`（浅灰细体）。
- **四色重要程度标签**（每个 H3 结尾）：
  | 标签 | class | 含义 |
  |------|-------|------|
  | 必考 | `tag-must` | 综合/问答核心，能默写+推导 |
  | 重点 | `tag-key` | 简答高频，能用自己话解释 |
  | 高频 | `tag-freq` | 选择/判断常考，记关键区别 |
  | 了解 | `tag-info` | 知道名字和作用 |
- **易错框**：`<blockquote>易错：XXX 和 YYY 的区别不在于 A，而在于 B。考试常设陷阱是…</blockquote>`
- **公式**：独立 `$$...$$`，行内 `$...$`，公式后紧跟文字解释每个符号的含义。
- **对比概念必配表格**。
- **PPT 页码标记**：每个 H2/H3 标题末尾追加 `<span data-slides="页码">`（取自该 KC 的 source_refs），渲染时变成 `[页N]` chip，点击滚到右侧对应幻灯片。
- 只写 H2/H3（引擎自动加 H1+目录）；箭头用 `--&gt;`，引号用「」，不用 Unicode 特殊字符。

## 深度示例

错误（太浅）：
```html
<h3>束搜索</h3>
<p>每步保留K个最优前缀。K=1退化为贪婪搜索。</p>
```

正确（嚼碎了，带叙事弧）：
```html
<h3>束搜索 <span class="tag-must">必考</span><span data-slides="42"></span></h3>
<p><strong>Hook：</strong>贪婪解码每步只留概率最高的一个词，选错了回不去——整句就毁了。</p>
<div class="tldr"><span class="kp">束搜索 = 每步多留 K 个候选，最后选整体最好的</span></div>
<p><strong>Why：</strong>「每步最优」不等于「整句最优」。<strong>What：</strong>每步保留 $K$ 个最可能前缀…<strong>How：</strong>第1步选概率最高的 $K$ 个；后续每步 $K$ 个前缀各扩展 $|V|$ 词，选 $K$ 个最优。复杂度 $O(K|V|)$/步。</p>
<blockquote>易错：束搜索是启发式，不保证全局最优。判断题「束搜索保证全局最优」是错的。</blockquote>
<div class="checkpoint">K=1 时束搜索退化成什么？<details class="cp-answer"><summary>参考答案</summary>退化为贪婪解码。</details></div>
```

## 图片识别与平台适配

非多模态模型读不了 PPT 里的图表/公式截图，会丢信息。处理：
1. **多模态（如 Claude）**：直接把提取图片作视觉输入分析。
2. **非多模态**：先 OCR/解析转文字——优先 **MinerU**（`pip install magic-pdf`，学术 PDF 公式表格识别最好），兜底 PaddleOCR/Tesseract。脚本已提取图片到临时目录。
3. **判断**：bundle 中 `images` 非空且模型非多模态 → 提示启用 MinerU/OCR。

## 常见技术坑

1. Python 内联代码过长 → 写成 .py 执行。
2. `$$` 内 `\text` → Python 字符串写 `\\\\text`。
3. 中文引号被转义 → 用「」。
4. Unicode `→` 导致 SyntaxError → 用 `--&gt;`。
5. 题目 explanation 内的 `$` → JSON 内无需转义。
6. tf 题 `"options": []`，模板自动显示「正确」「错误」。
