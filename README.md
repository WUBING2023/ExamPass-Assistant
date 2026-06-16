# ExamPass Assistant <sup>v0.1</sup>

**Turn lecture slides into exam-ready study materials.**

> [中文](./README_CN.md)

---

### What is this

An AI-powered exam prep assistant. Drop in lecture PPTs, Word handouts, or PDF readings — it generates:

- **Knowledge Guides** — structured review notes with MathJax formulas, dual-color highlighting (key points in bold black, explanations in lighter gray), priority tags (must-know / key / frequent / info), and auto-generated table of contents
- **Interactive Quizzes** — click to answer, one-click grading, per-question correct/incorrect badges, detailed explanations, and common mistake warnings

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

### Usage

**Generate chapter materials** — run `/exampass` in any course directory. The skill scans subfolders, groups files by chapter, extracts all content, performs deep analysis, and outputs knowledge guides + interactive quizzes into each folder.

**Keep up to date** — run `/exampass update` to pull the latest features and fixes from GitHub.

**Use in your own code**:

```python
from scripts.template_engine import save_knowledge_html, save_test

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
```

### Skills

| Command | Description |
|---------|-------------|
| `/exampass` | Generate knowledge guides and interactive chapter quizzes |
| `/exampass update` | Pull latest features, fixes, and dependencies |
| `/exampass-final` | Generate a full mock final exam with answer key |

### How It Works

1. **Scan & Group** — recursively finds all PPTX/DOCX/PDF files, groups by parent folder
2. **Extract** — pulls text, tables, and embedded images from each file
3. **Analyze** — Claude deeply reads the content, identifies concepts, motivations, and logical connections
4. **Generate** — produces styled HTML with dual-color highlighting, MathJax formulas, and interactive quiz logic

### Project Structure

```
EPA/
├── SKILL.md                    # /exampass entry point
├── exampass-update.md           # /exampass-update entry point
├── exampass-final.md           # /exampass-final entry point
├── scripts/                    # Core Python modules
│   ├── run_exampass.py         # Single-script extraction entry
│   ├── scanner.py              # Recursive scanning & grouping
│   ├── extractor.py            # Unified extraction dispatcher
│   ├── extract_pptx.py         # PPTX extraction
│   ├── extract_docx.py         # DOCX extraction
│   ├── extract_pdf.py          # PDF extraction
│   ├── image_extractor.py      # Image extraction for multimodal analysis
│   ├── ocr_backend.py          # OCR fallback for non-multimodal models
│   ├── template_engine.py      # HTML template engine
│   ├── html_generator.py       # Fast generator
│   ├── generate_cached.py      # Cache-based instant re-runs
│   ├── knowledge_analyzer.py   # Knowledge list prompt builder
│   ├── test_generator.py       # Quiz generation prompt builder
│   ├── exam_generator.py       # Final exam prompt builder
│   ├── web_research.py         # Web research
│   └── utils.py                # Shared utilities
├── templates/                  # CSS & HTML templates
│   ├── base.css                # Shared styles (warm paper, dual-color)
│   ├── test.css                # Interactive quiz styles
│   ├── page_template.html      # HTML page shell
│   ├── test_js_template.js     # Quiz JS template
│   └── test_labels.json        # Chinese UI labels
├── tests/                      # 102 test cases
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
