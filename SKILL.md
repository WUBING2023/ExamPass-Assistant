---
name: exampass
description: 将课程资料（PPT/Word/PDF）按章节生成知识清单+原始PPT对照+自测答案+交互式章节测试，帮助高效期末复习。
---

## 命令路由

检查调用参数 `args`：
- **`"update"`**：执行「技能更新」，完成即结束。
- **`"final"` 或以 `"final "` 开头**：执行「期末整卷生成」，详见 `exampass-final.md`。
- **`"graph"` 或以 `"graph "` 开头**：执行「知识图谱生成」，详见 `exampass-graph.md`。
- **其他情况**（空或目录路径）：执行「多 Agent 深度流程」（默认）——**产出含 PPT 对照栏的合并页**。

> 子 Agent 卡片见 `agents/`：`skeleton-agent.md`、`notes-agent.md`、`item-agent.md`、`solver-agent.md`、`reviewer-agent.md`。出题规范见 `exampass-final.md`。

---

## 默认流程

每章的最终产出是一个**合并页 HTML**：顶部 tab 切换「📖 知识清单 | 📝 章节测试」。
知识清单含：右侧 Notion 风**原始 PPT 对照栏**（整页渲染图 + 该页原文）、自动目录、Hook→TL;DR→Why→What→How→Checkpoint 叙事弧、四色标签、双色标注、易错 blockquote、**可折叠自测答案**。章节测试含：按学科智能选题型、ABCD 均匀分布、一键批改、逐题解析。

### Phase 0 · 提取

```bash
python scripts/run_exampass.py <目标目录>
```

产 `.epa_work/chapter_manifest.json` + 每章 `chapters/<章名>/_extraction_bundle.json`。

### Phase 1 · 骨架

用 `agents/skeleton-agent.md` Part 4 起 1 个子 Agent，读 manifest + 各章 bundle，产 `.epa_work/knowledge_skeleton.json`（章→KC DAG，含 type/importance/deps/is_hub/source_refs）。再按 `source_refs` 写 `.epa_work/slices/<章名>_skeleton.json` + `_extract.json`。

### Phase 2 · 并行创作

每章同时起笔记 Agent + 题目 Agent（读对应切片），并行、互不依赖。如果已有产出且比 bundle 新则缓存跳过。章数不限批次。

### Phase 3 · 流式评审+修订

每章产出后立即审查+做题验证（两遍法），有问题就修订。章间并行。

### Phase 4 · 渲染（含 PPT 对照栏——默认开启）

每章调 `slide_renderer.build_chapter_slides` 渲染该章 PDF 的 key 页 + 原文，再用 `save_combined_html` 产出合并页：

```python
import json, os
from scripts.slide_renderer import build_chapter_slides
from scripts.template_engine import save_combined_html

with open('.epa_work/knowledge_skeleton.json', encoding='utf-8') as f:
    skeleton = json.load(f)

for ch in skeleton['chapters']:
    cid = ch['id']; label = ch['label']
    note_html = open(f'.epa_work/notes/{cid}.html', encoding='utf-8').read()
    questions = json.load(open(f'.epa_work/questions/{cid}.json', encoding='utf-8'))

    # 从 manifest 找该章原 PDF（按章节 label 或文件名关键词匹配）
    pdf_paths = [...]   # 推导自 chapter_manifest + 课程目录
    slides_dir = f'.epa_work/chapters/{label}/_slides'
    slides = build_chapter_slides(pdf_paths, slides_dir, density='key',
                                  skeleton=skeleton, chapter_label=label)

    save_combined_html(note_html, questions,
                       f'EPA/{label}.html', label,
                       slides=slides, kcs=ch['kcs'],
                       subtitle=f'共 {len(questions)} 题')
```

**PPT 对照栏是默认行为——不需要用户额外指定。**

> **写作规范**见 `exampass-writing.md`（叙事弧、双色标注、四色标签、易错框、公式、图片识别、PPT 页码标记）。
> **出题规范**见 `exampass-final.md`（智能选题型、题目编写硬规则、JSON 安全）。
> 笔记 Agent 与题目 Agent 的完整 prompt 在各自的 `agents/*.md` 卡片 Part 4。

---

## 技能更新

执行 `/exampass update` 时，按以下脚本更新到最新版本：

```powershell
$SkillDir = "$env:USERPROFILE\.claude\skills\exampass"
if (-not (Test-Path "$SkillDir")) { Write-Host "错误：找不到技能目录 $SkillDir"; exit 1 }
if (-not (Test-Path "$SkillDir\.git")) { Write-Host "错误：$SkillDir 不是 git 仓库"; exit 1 }
Push-Location $SkillDir
Write-Host "技能目录：$SkillDir`n正在获取远程更新..."

git fetch origin master 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "错误：无法连接 GitHub，请检查网络。"; Pop-Location; exit 1 }

$Behind = [int](git rev-list --count HEAD..origin/master 2>&1)
Write-Host "当前落后 origin/master：$Behind 个提交"

if ($Behind -eq 0) {
    Write-Host "已是最新版本！`n验证 Python 依赖..."
    pip install -r requirements.txt 2>&1
    Write-Host "`n当前版本："; git log --oneline -3
    Pop-Location; exit 0
}

Write-Host "`n待拉取的提交："; git log --oneline HEAD..origin/master
Write-Host ""
$Status = git status --porcelain 2>&1
if ($Status) {
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    git stash push --include-untracked -m "exampass-update-$Stamp" 2>&1
    $Stashed = $true
    Write-Host "修改已暂存为：exampass-update-$Stamp"
} else { $Stashed = $false; Write-Host "工作树干净。" }
Write-Host "`n正在拉取最新代码..."
git pull origin master 2>&1
if ($Stashed) {
    Write-Host "正在恢复本地修改..."
    git stash pop 2>&1
}
Write-Host "`n安装 Python 依赖..."
pip install -r requirements.txt 2>&1
Write-Host "`n===========================================`n  ExamPass 更新完成！`n==========================================="
Write-Host "`n最新提交："; git log --oneline -5
Write-Host "`n技能目录：$SkillDir"
Pop-Location
```
