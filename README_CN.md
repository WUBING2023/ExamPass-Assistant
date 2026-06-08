# ExamPass Assistant <sup>v0.2</sup>

**把课堂讲义变成考试利器。** 一键将 PPT、Word、PDF 课件转化为结构化知识清单、交互式测试题、知识图谱和仿真期末试卷。

> [English](./README.md)

> 📌 **期末季说明 · Finals-season note**
> 6 月中旬会有一次更新。作者正用 EPA 备考自己的期末，会同步分享实测体验；但近期没精力一一答疑，Issue / 私信会延迟回复，感谢理解 🙏
> One update is planned for **mid-June**. I'm using EPA for my own finals right now and will share real usage notes along the way — but I won't have time to answer questions for a while, so issues / DMs may be delayed. Thanks for understanding 🙏

---

### 适用场景

| 角色 | 用途 |
|------|------|
| 大学生 | 上传课程 PPT/讲义，自动生成知识清单 + 交互式章节测试 + 知识图谱 + 仿真期末卷，高效通过期末考试 |
| 授课教师 | 课件一键转化为结构化知识总结，自动生成配套习题+答案解析，直接用于课堂教学或课后作业 |
| 考研/考证 | 参考书 PDF 转为精简知识清单，配合自测题检验掌握程度 |

### 核心功能

- 支持 PPTX / DOCX / PDF，递归扫描目录，按章节自动分组
- 提取文字、表格、图片（Claude 多模态分析；非多模态模型自动走 MinerU/PaddleOCR 回退）
- **多 Agent 深度流程**（默认）：骨架 Agent → 笔记+题目并行创作 → 审查+做题并行验证 → 定向修订 → 渲染
- **快速流程** (`fast`)：单 Agent 直接产出，适合快速迭代
- 生成**知识清单 HTML**：MathJax 公式完美渲染，双色标注（知识点黑色加粗 + 解释浅灰细体），四色重要程度标签（必考/重点/高频/了解），自动目录导航
- 生成**交互式章节测试 HTML**：9 种题型（选择/多选/判断/填空/简答/计算/代码/问答/综合），**按学科自动选题型**——算法课出 calc+code，文科不出计算题。点击选项→一键批改→逐题解析+易错提醒
- 生成**交互式知识图谱 HTML**：左章右组件树布局，依赖虚线连接，枢纽概念 ★ 标记，悬停 tooltip，叶节点可编辑笔记卡（支持粘贴图片、刷新保留），顶部搜索高亮，底部缩放
- 生成**仿真期末试卷**：交互式询问难度/时长/偏好，联网参考名校同科期末题，蓝图分值恰好 100 分、全章覆盖、枢纽权重更高、难度有梯度，做题 Agent 两遍验证
- 分析结果自动缓存，同目录再次运行秒级出结果
- 浏览器打开即用，Ctrl+P 打印为 PDF

### 快速开始

```bash
git clone https://github.com/WUBING2023/ExamPass-Assistant.git
cd ExamPass-Assistant
pip install -r requirements.txt
```

### 命令列表

| 命令 | 说明 |
|------|------|
| `/exampass <目录>` | **多 Agent 深度流程**（默认）— 骨架→并行创作→并行评审→定向修订→渲染 |
| `/exampass fast <目录>` | **快速流程** — 单 Agent 直接产出，跳过子 Agent 编排 |
| `/exampass graph <目录>` | **知识图谱** — 交互式树图：依赖虚线、枢纽★、笔记卡、搜索、缩放 |
| `/exampass final <目录>` | **期末整卷** — 交互式询问→联网参考→蓝图(100分)→命题→验证→交互试卷+答案 |
| `/exampass update` | 一键更新到最新版本（拉取代码+安装依赖） |

### 多 Agent 编排流程

默认 `/exampass` 命令调度 5 个专业子 Agent：

| 阶段 | Agent | 产物 |
|------|-------|------|
| 0. 提取 | `run_exampass.py` | `_extraction_bundle.json` |
| 1. 骨架 | `skeleton-agent` | `knowledge_skeleton.json`（章→KC 依赖图）+ 按章切片 |
| 2. 并行创作 | `notes-agent` + `item-agent`（每章并行） | `notes/chN.html` + `questions/chN.json` |
| 3. 并行评审 | `reviewer-agent` + `solver-agent`（两遍法） | `reviews/chN.json` + 诊断标签 |
| 4. 汇总反馈 | 编排器聚合 critical/important | `feedback/chN.json` |
| 5. 定向修订 | 仅重做受影响章节 | 修订后的笔记和题目 |
| 6. 渲染 | `template_engine` | 知识清单 HTML + 章节测试 HTML |

所有中间产物在 `.epa_work/`。编排器（主 Claude）只调度不创作——内容由子 Agent 按 `agents/` 下的卡片产出。

### 在代码中调用

```python
from scripts.template_engine import save_knowledge_html, save_test, save_graph_html
from scripts.knowledge_graph import skeleton_to_graph_tree

# 知识清单：HTML body 直接传入（引擎自动加 H1 + 目录）
body = '<h2>一、序列建模基础</h2>\n<h3>1.1 什么是序列数据</h3>\n<p>...</p>'
save_knowledge_html(body, '知识清单.html', '第15章 序列生成模型')

# 交互式测试：题目列表直接传入
questions = [
    {"type": "choice", "points": 2,
     "question": "语言模型的核心功能是什么？",
     "options": ["翻译", "评估句子概率", "分词", "识别物体"],
     "answer": 1, "explanation": "语言模型计算词序列概率...",
     "pitfall": "注意区分语言模型和机器翻译"},
]
save_test(questions, '章节测试.html', '第15章', '满分 100 分', duration_minutes=30)

# 知识图谱：骨架转交互式 DAG 可视化
import json
with open('knowledge_skeleton.json') as f:
    skeleton = json.load(f)
tree = skeleton_to_graph_tree(skeleton)
save_graph_html(tree, '知识图谱.html', tree['title'])
```

### 项目结构

```
EPA/
├── SKILL.md                    # /exampass 入口（命令路由）
├── agents/                     # 子 Agent 卡片（方法论 + prompt）
│   ├── skeleton-agent.md       # 知识架构师 — 构建章→KC 依赖图
│   ├── notes-agent.md          # 笔记写手 — 深度学习模式叙事
│   ├── item-agent.md           # 命题专家 — 按学科自动选题型
│   ├── reviewer-agent.md       # 内容审查 — 正确性与完整性
│   └── solver-agent.md         # 做题验证 — 两遍法诊断
├── scripts/
│   ├── run_exampass.py         # 单脚本提取入口
│   ├── scanner.py              # 递归扫描与分组
│   ├── extractor.py            # 统一提取调度（PPTX/DOCX/PDF）
│   ├── extract_pptx.py         # PPTX 提取（文字+表格+图片）
│   ├── extract_docx.py         # DOCX 提取
│   ├── extract_pdf.py          # PDF 提取
│   ├── image_extractor.py      # 图片提取（供 Claude 多模态分析）
│   ├── ocr_backend.py          # OCR 回退（非多模态模型用）
│   ├── template_engine.py      # HTML 模板引擎（知识清单/测试/图谱）
│   ├── knowledge_graph.py      # 骨架→图谱树转换
│   ├── html_generator.py       # 快速生成器
│   ├── generate_cached.py      # 缓存加速（二次运行秒出）
│   ├── knowledge_analyzer.py   # 知识清单分析 prompt
│   ├── test_generator.py       # 测试题生成 prompt
│   ├── exam_generator.py       # 期末试卷 prompt
│   ├── web_research.py         # 网络调研
│   └── utils.py                # 通用工具
├── templates/
│   ├── base.css                # 共享样式（暖色纸张、双色标注）
│   ├── test.css                # 交互测试样式
│   ├── graph.css               # 知识图谱样式（树布局）
│   ├── graph.js                # 图谱渲染器（D3 — 虚线依赖/tooltip/笔记卡）
│   ├── page_template.html      # HTML 页面模板
│   ├── graph_template.html     # 图谱 HTML 模板
│   ├── test_js_template.js     # 测试页 JS 模板
│   └── test_labels.json        # 中文标签配置
├── tests/                      # 123 个测试用例
└── requirements.txt
```

### 贡献者

- 开发与维护：[@WUBING2023](https://github.com/WUBING2023)
- 启发性贡献：yaxing@cvc.uab.es
- 测试：[@YeMoonlight](https://github.com/YeMoonlight)
- 测试：[@Yuzhihan-zyr](https://github.com/Yuzhihan-zyr)

### 许可证

本软件采用 **Creative Commons BY-NC 4.0** 许可证。

- 允许自由使用、修改、再分发（需署名）
- **禁止商业用途**

完整条款见 [LICENSE](./LICENSE)。

Copyright (c) 2025 ExamPass Assistant Contributors
