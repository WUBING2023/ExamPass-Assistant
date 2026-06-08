# ExamPass Assistant <sup>v1.0</sup>

**Turn lecture slides into exam-ready study materials.**

> [中文](./README_CN.md)

> 📌 **Finals-season note · 期末季说明**
> One update is planned for **mid-June**. I'm using EPA for my own finals right now and will share real usage notes along the way — but I won't have time to answer questions for a while, so issues / DMs may be delayed. Thanks for understanding 🙏
> 6 月中旬会有一次更新。作者正用 EPA 备考自己的期末，会同步分享实测体验；但近期没精力一一答疑，Issue / 私信会延迟回复，感谢理解 🙏

---

### What is this

An AI-powered exam prep assistant. Drop in lecture PPTs, Word handouts, or PDF readings — it generates:

- **Knowledge Guides** — structured review notes with MathJax formulas, dual-color highlighting (key points in bold black, explanations in lighter gray), priority tags (must-know / key / frequent / info), and auto-generated table of contents
- **Interactive Chapter Quizzes** — click to answer, one-click grading, per-question correct/incorrect badges, detailed explanations, and common mistake warnings. Supports 9 question types including calc and code — automatically chosen by subject
- **Knowledge Graph** — interactive left-root/right-leaf tree layout with dependency dashed lines, hub-concept stars, hover tooltips, persistent inline note cards (text + paste images), search, and zoom
- **Mock Final Exam** — full exam paper with answer key, blueprint scoring exactly 100 points, chapter coverage, difficulty gradient, and interactive answer sheet

Open in any browser. Ctrl+P to print as PDF. MathJax renders formulas perfectly.

### Why

The universal pain of finals week: scattered lecture files, no clear sense of exam priorities, no reliable practice questions.

ExamPass reads your course materials with Claude, extracts key concepts with logical narratives, and generates self-grading quizzes. Students use it to study smarter. Instructors use it to create exercises and assignments in seconds.

### Supported Formats

PPTX · DOCX · PDF (with image recognition via multimodal analysis)

### Quick Start

```bash
git clone https://github.com/WUBING2023/ExamPass-Assistant.git
cd ExamPass-Assistant
pip install -r requirements.txt
```

### Commands

| Command | Description |
|---------|-------------|
| `/exampass <dir>` | **Multi-agent deep pipeline** — skeleton → parallel notes & questions → parallel review & solve → targeted revision → render |
| `/exampass fast <dir>` | **Single-agent fast mode** — skip sub-agent orchestration, produce the same outputs faster |
| `/exampass graph <dir>` | **Knowledge graph** — interactive left-right tree with dependency edges, hub stars, inline note cards, search & zoom |
| `/exampass final <dir>` | **Mock final exam** — interactive difficulty/duration/preferences, web-referenced blueprint (100 pts), two-pass solver verification, answer key |
| `/exampass update` | Pull latest features, fixes, and dependencies from GitHub |

### Multi-Agent Pipeline (default)

The default `/exampass` command orchestrates 5 specialized sub-agents:

| Phase | Agent | Output |
|-------|-------|--------|
| 0. Extract | `run_exampass.py` | `_extraction_bundle.json` |
| 1. Skeleton | `skeleton-agent` | `knowledge_skeleton.json` (chapter → KC DAG) + per-chapter slices |
| 2. Create | `notes-agent` + `item-agent` (parallel per chapter) | `notes/chN.html` + `questions/chN.json` |
| 3. Review | `reviewer-agent` + `solver-agent` (two-pass) | `reviews/chN.json` + diagnostic labels |
| 4. Feedback | orchestrator aggregates critical/important issues | `feedback/chN.json` |
| 5. Revise | targeted re-run of affected chapters only | revised notes & questions |
| 6. Render | `template_engine` | knowledge list HTML + chapter test HTML |

All intermediate artifacts land in `.epa_work/`. The orchestrator (main Claude) only schedules — content is produced by sub-agents following agent cards in `agents/`.

### Use in Your Own Code

```python
from scripts.template_engine import save_knowledge_html, save_test, save_graph_html
from scripts.knowledge_graph import skeleton_to_graph_tree

# Knowledge guide — pass HTML body directly (engine adds H1 + TOC)
body = '<h2>1. Sequence Modeling Basics</h2>\n<h3>1.1 What is Sequence Data</h3>\n<p>...</p>'
save_knowledge_html(body, 'knowledge.html', 'Chapter 15')

# Interactive quiz — pass question data, get a self-grading page
questions = [
    {"type": "choice", "points": 2,
     "question": "What is the core function of a language model?",
     "options": ["Translation", "Estimating sentence probability",
                 "Tokenization", "Object recognition"],
     "answer": 1,
     "explanation": "A language model computes P(w1,...,wT)...",
     "pitfall": "Don't confuse language models with translation systems."},
]
save_test(questions, 'quiz.html', 'Chapter 15', '100 points', duration_minutes=30)

# Knowledge graph — convert skeleton to interactive DAG visualization
import json
with open('knowledge_skeleton.json') as f:
    skeleton = json.load(f)
tree = skeleton_to_graph_tree(skeleton)
save_graph_html(tree, 'graph.html', tree['title'])
```

### Project Structure

```
EPA/
├── SKILL.md                    # /exampass entry point (command routing)
├── agents/                     # Sub-agent cards (methodology + prompt)
│   ├── skeleton-agent.md       # Knowledge architect — builds chapter→KC DAG
│   ├── notes-agent.md          # Note writer — deep-learning mode narratives
│   ├── item-agent.md           # Question writer — subject-aware question types
│   ├── reviewer-agent.md       # Content reviewer — correctness & completeness
│   └── solver-agent.md         # Exam solver — two-pass verification
├── scripts/                    # Core Python modules
│   ├── run_exampass.py         # Single-script extraction entry
│   ├── scanner.py              # Recursive scanning & grouping
│   ├── extractor.py            # Unified extraction dispatcher
│   ├── extract_pptx.py         # PPTX extraction (text + tables + images)
│   ├── extract_docx.py         # DOCX extraction
│   ├── extract_pdf.py          # PDF extraction
│   ├── image_extractor.py      # Image extraction for multimodal analysis
│   ├── ocr_backend.py          # OCR fallback for non-multimodal models
│   ├── template_engine.py      # HTML template engine (knowledge, test, graph)
│   ├── knowledge_graph.py      # Skeleton-to-graph-tree converter
│   ├── html_generator.py       # Fast generator
│   ├── generate_cached.py      # Cache-based instant re-runs
│   ├── knowledge_analyzer.py   # Knowledge list prompt builder
│   ├── test_generator.py       # Quiz generation prompt builder
│   ├── exam_generator.py       # Final exam prompt builder
│   ├── web_research.py         # Web research
│   └── utils.py                # Shared utilities
├── templates/                  # CSS, JS & HTML templates
│   ├── base.css                # Shared styles (warm paper, dual-color)
│   ├── test.css                # Interactive quiz styles
│   ├── graph.css               # Knowledge graph styles (tree layout)
│   ├── graph.js                # Graph renderer (D3 — dashed deps, tooltips, note cards)
│   ├── page_template.html      # HTML page shell
│   ├── graph_template.html     # Graph HTML shell
│   ├── test_js_template.js     # Quiz JS template
│   └── test_labels.json        # Chinese UI labels
├── tests/                      # 123 test cases
└── requirements.txt
```

### Contributors

- Development & Maintenance: [@WUBING2023](https://github.com/WUBING2023)
- Inspirational Contribution: yaxing@cvc.uab.es
- Testing: [@YeMoonlight](https://github.com/YeMoonlight)
- Testing: [@Yuzhihan-zyr](https://github.com/Yuzhihan-zyr)

### License

[CC BY-NC 4.0](./LICENSE) — free to use, modify, and share for non-commercial purposes. Commercial use requires a separate license.

Copyright (c) 2025 ExamPass Assistant Contributors
