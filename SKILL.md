---
name: exampass
description: 将课程资料（PPT/Word/PDF）按章节生成知识清单+原始PPT对照+自测答案+交互式章节测试，帮助高效期末复习。
---

## 命令路由

检查 `args`：
- `"update"` → 技能更新。
- `"final"` 或 `"final "` 开头 → 出题，详见 `exampass-final.md`。
- `"graph"` 或 `"graph "` 开头 → 知识图谱，详见 `exampass-graph.md`。
- `"grade"` 或 `"批改"` 开头 → **AI批改**（下面）。
- 其他 → **默认流程**（下面）。

> 你需要阅读的文件：`agents/skeleton-agent.md`、`agents/notes-agent.md`、`agents/item-agent.md`（每个的 Part 4 是实际 prompt）。写作规范在 `exampass-writing.md`（需要时读）。

---

## 默认流程

每章产出**一个合并页 HTML**：顶部 tab「📖 知识清单 | 📝 章节测试」。知识清单含右侧 PPT 对照栏（整页渲染图+原文）、目录、四色标签、易错 blockquote、折叠自测答案。章节测试交互答题+一键批改。

### Phase 0 · 提取

```bash
cd <skill目录>
python scripts/run_exampass.py <课程目录>
```

产 `.epa_work/chapter_manifest.json` + 每章 `chapters/<章名>/_extraction_bundle.json`。manifest 的每个条目有 `source_files`（该章源 PDF 绝对路径）。

### Phase 1 · 骨架

读 `agents/skeleton-agent.md` Part 4。核心规则：
- 读 manifest + 每章 bundle 的 merged_text 了解内容
- 输出 `knowledge_skeleton.json`：`{title, chapters:[{id:"ch1",label:"章名",kcs:[{id,label,type:"fact|concept|procedure|principle",importance:"must|key|freq|info",deps:[],is_hub:bool,source_refs:["PDF名/页码范围"]}]}]}`
- **source_refs 页码必须真实**（不能超过 PDF 实际页数；先确认 PDF 页数再写页码）
- 再写切片：`slices/<章id>_skeleton.json` + `slices/<章id>_extract.json`

### Phase 2 · 笔记 + 题目（每章并行）

**笔记 Agent prompt（精简）**：

```
你是讲解设计师。读 [骨架切片路径] 和 [提取切片路径]。
为每个知识组件写一段讲解，输出到 [.epa_work/notes/<章id>.html]。

规则：
1. 叙事弧：Hook（一句话场景/谜题）→ TL;DR（<div class="tldr">粗体一句话结论</div>）→ Why → What → How → Checkpoint自测（<div class="checkpoint">问题<details class="cp-answer"><summary>参考答案</summary>答案</details></div>）
2. 核心概念包 <span class="kp">…</span>，解释包 <span class="exp">…</span>
3. 每个H3末尾标四色标签（中文："必考""重点""高频""了解"），class用 tag-must/tag-key/tag-freq/tag-info
4. 易错用 <blockquote>易错：…</blockquote>
5. 公式 $$…$$ 或 $…$，引号用「」，箭头 --&gt;
6. 每个H2/H3末尾加 <span data-slides="页码"></span>（从 source_refs 取该KC的起始页码）
7. 只写H2/H3，不写H1。不要输出 <!DOCTYPE>/<html>/<head>/<style>/<body> 标签——只输出 body 内部片段
8. 每个概念必答"是什么/为什么需要它/怎么用"
```

**题目 Agent prompt（精简）**：

```
你是命题专家。读 [骨架切片路径] 和 [提取切片路径]。
为该章出一套题目，输出到 [.epa_work/questions/<章id>.json]。

规则：
1. 题型按学科选——算法课必须包含 calc 和 code，文科不出 calc/code
2. 题量：每个KC至少1题，枢纽概念至少2题。整章≥8题
3. choice：4个选项，正确答案 A/B/C/D 均匀分布（各字母次数差≤1），干扰项对应真实误解
4. 文本里不等号用 &lt; 和 &gt; 或 $...$，禁止裸 <
5. JSON字符串内引号用「」，禁止裸 "
6. 每题含 kc_id/cognitive_level(remember|understand|apply|analyze)/difficulty(basic|medium|hard)
7. 写完用 json.loads() 自检

JSON结构：{"chapter_id":"chX","questions":[{"type":"choice|tf|fill|calc|code|short","points":N,"kc_id":"kcX.Y","question":"...","options":["A","B","C","D"],"answer":0,"explanation":"...","cognitive":"...","difficulty":"...","pitfall":"..."}]}
对于 tf（判断）题：answer: true 表示命题正确（正确），answer: false 表示命题错误（错误）。禁止对 tf 题使用数字 0/1 —— 只用布尔值 true/false。
```

> 以上 prompt 中的文件路径：骨架切片在 `.epa_work/slices/<章id>_skeleton.json`，提取切片在 `.epa_work/slices/<章id>_extract.json`。笔记写入 `.epa_work/notes/<章id>.html`，题目写入 `.epa_work/questions/<章id>.json`。
> 
> 如果你自己能逐章写完（不调子Agent），**直接写就行**——质量优先，不要为了并行而并行。如果起子Agent，确保每个子Agent只拿自已那章的切片，不要读整个 bundle。

### Phase 3 · 评审+修订（可选）

如果时间允许，可以起 reviewer-agent + solver-agent 逐章审查。但**不是必须的**——如果 Phase 2 的笔记和题目已经认真写了，跳过评审直接渲染也没问题。

### Phase 4 · 渲染

```bash
python scripts/render_chapters.py <课程目录> full
```

这会把每章的 PDF **全部页**渲染成图贴进右栏（`full` 密度 = PPT 对照栏放全部原页）。如果文件太大想只放重点页，把 `full` 改成 `key`。渲染输出在 `<课程目录>/EPA/`，每个章一个 HTML 合并页。

浏览器打开 EPA/ 下任意 HTML 即可使用。

---

## AI批改流程

`args` 形如 `"grade <JSON路径>"` 或 `"批改 <JSON路径>"`。

**读取 answers JSON**（由交互式测试页的「AI一键批改」按钮生成，默认下载到下载文件夹）：
```json
{
  "chapter": "数据结构 - 第3章",
  "saved_at": "2026-06-25T14:30:00",
  "questions": [
    {
      "index": 0, "type": "tf", "question": "...",
      "options": null, "correct_answer": true,
      "user_answer": 0, "points": 2,
      "explanation": "...", "kc_id": "kc3.1", "images": []
    }
  ]
}
```

**Step 1 · 客观题自动批改**（choice / multi / tf / fill）：
- 按与 `test_js_template.js` 相同的逻辑（`tfAnswerIndex`/`choiceAnswerIndex`/`normText`）比对答案
- 得分：全对=满分，多选部分正确=按比例，填空按空批

**Step 2 · 主观题 AI 批改**（short / calc / code / essay / comprehensive）：
- 每题：读题目 + 用户作答 + 分析 `images`（如有）
- 给出 0～满分的得分和简短批改评语
- 参考 `explanation` 字段提供标准解析

**Step 3 · 统计**：
- 计算 total_score / objective_score / subjective_score
- 按 kc_id 分组求每个知识点的掌握度（得分/满分）

**Step 4 · 生成报告**：

```python
from scripts.template_engine import save_grade_report_html
import os, json
from datetime import datetime

# 构造 grade_data（见 save_grade_report_html 文档）
grade_data = {
    "chapter": answers["chapter"],
    "submitted_at": answers["saved_at"],
    "graded_at": datetime.now().isoformat(),
    "grade_count": 1,   # 根据已有批改报告数量+1
    "total_score": ...,
    "max_score": ...,
    "objective_score": ..., "objective_max": ...,
    "subjective_score": ..., "subjective_max": ...,
    "results": [...],  # 每题: index/type/question/options/user_answer/correct_answer/score/max_points/verdict/comment/explanation/kc_id/images
    "kc_mastery": {...},  # kc_id → {label, score, max, pct}
    "wrong_questions": [...]  # wrong/partial 题的 index 列表
}

# 输出到 answers JSON 所在目录
json_dir = os.path.dirname(json_path)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ch = answers["chapter"].replace(" ", "_").replace("/", "_")[:30]
out_path = os.path.join(json_dir, f"{ch}_批改_{ts}.html")
save_grade_report_html(grade_data, out_path)
print(f"报告已生成：{out_path}")
```

**判断 grade_count**：扫描同目录下 `*_批改_*.html` 文件数量 + 1。

**注意**：某些 tf 题的 `correct_answer` 字段可能存在数据问题（答案填反了），批改时如果确认 `correct_answer` 与 `explanation` 矛盾，以 `explanation` 为准，并在 `comment` 中注明"数据可能有误，请复核"。

---

## 技能更新

运行 `/exampass update` 时执行：

```powershell
$SkillDir = "$env:USERPROFILE\.claude\skills\exampass"
Push-Location $SkillDir
git fetch origin master 2>&1
$Behind = [int](git rev-list --count HEAD..origin/master 2>&1)
Write-Host "落后 origin/master：$Behind 个提交"
if ($Behind -eq 0) { Write-Host "已是最新！"; Pop-Location; return }
$Status = git status --porcelain
if ($Status) { git stash push --include-untracked -m "exampass-update-$(Get-Date -Format yyyyMMdd-HHmmss)" }
git pull origin master
git stash pop 2>$null
pip install -r requirements.txt
Write-Host "更新完成"; git log --oneline -5
Pop-Location
```
