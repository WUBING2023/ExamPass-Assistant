---
name: exampass
description: 将课程资料（PPT/Word/PDF）按章节生成知识清单和交互式章节测试，帮助高效期末复习。
---

## 命令路由

检查调用参数 `args`：
- **`"update"`**：执行「技能更新」，完成即结束。
- **`"final"` 或以 `"final "` 开头**：执行「期末整卷生成」（多 Agent），完成即结束。
- **`"graph"` 或以 `"graph "` 开头**：执行「知识图谱生成」（基于骨架 Agent），完成即结束。
- **`"fast"` 或以 `"fast "` 开头**：执行「快速流程（单 Agent）」，完成即结束。
- **其他情况**（空或目录路径）：执行「多 Agent 深度流程」（默认）。

> 五个子 Agent 的方法论与实际 prompt 见 `agents/` 下的卡片：`skeleton-agent.md`、`notes-agent.md`、`item-agent.md`、`solver-agent.md`、`reviewer-agent.md`。编排细节见 `docs/superpowers/specs/2026-06-08-multiagent-orchestration.md`。

---

## 多 Agent 深度流程（默认）

把「理解 + 生成」从单 Agent 升级为「骨架 → 并行创作 → 并行评审 → 一轮定向修订 → 渲染」。所有中间产物落在目标目录的 `.epa_work/`。编排器（你，主 Claude）只调度，不亲自创作内容——内容由子 Agent 按各自卡片的 Part 4 prompt 产出。

**Phase 0 · 提取**
```bash
python scripts/run_exampass.py <目标目录>
```
扫描目录，自动按**章节目录**或**文件名数字前缀**（如 `3 分治-1.pdf`、`3 分治-2.pdf`）拆分为多章，每章独立产 `_extraction_bundle.json` 放在 `.epa_work/chapters/<章节名>/`。同时写入 `.epa_work/chapter_manifest.json` 记录所有章节。最终 HTML 输出到 `<目标目录>/EPA/`（图片处理见下方「图片识别与平台适配」）。

**Phase 1 · 骨架（1 个子 Agent，读全局）**
用 `agents/skeleton-agent.md` 的 Part 4 prompt 起 1 个子 Agent，读 `.epa_work/chapter_manifest.json` + 各章的 `_extraction_bundle.json`，产出 `.epa_work/knowledge_skeleton.json`（章 → 知识组件 DAG，含 type / importance / deps / is_hub / source_refs）。再按 `source_refs` 把每章的知识组件 + 对应提取内容切片写入 `.epa_work/slices/<章名>_skeleton.json` 与 `_extract.json`。

**Phase 2 · 并行创作（按章，每章 2 个子 Agent）**
对每章并行起：
- 笔记 Agent（`agents/notes-agent.md` Part 4 + 该章切片）→ `.epa_work/notes/<章名>.html`
- 题目 Agent（`agents/item-agent.md` Part 4 + 该章切片）→ `.epa_work/questions/<章名>.json`

两者都只读切片、互不依赖。章数 >8 时分批（每批 ≤8 并行）。

**Phase 3 · 并行评审（按章，每章 2 个子 Agent）**
- 审查 Agent（`agents/reviewer-agent.md` Part 4 + 该章笔记）→ `.epa_work/reviews/<章名>.json`
- 做题 Agent（`agents/solver-agent.md` Part 4）跑两遍：先仅题干 → `<章名>_p1.json`，再题干+笔记 → `<章名>_p2.json`。两遍都不给标准答案；之后你对照标准答案打诊断标签。

**Phase 4 · 汇总反馈**
收集所有 `critical` + `important` 问题和可执行诊断标签（too_easy / leak / ambiguous / notes_gap / out_of_scope / answer_suspect），按章写入 `.epa_work/feedback/<章名>.json`。`minor` 只记录，不进修订。

**Phase 5 · 一轮定向修订（只重做受影响的章）**
- 有笔记反馈的章：带反馈重启笔记 Agent，覆盖 `notes/<章名>.html`。
- 有题目反馈的章：带反馈重启题目 Agent，覆盖 `questions/<章名>.json`。

一轮封顶：修订产物不再二次验证。

**Phase 6 · 渲染**
按骨架顺序拼接所有 `notes/*.html` 与 `questions/*.json`，调模板引擎按章渲染：
- `<目标目录>/EPA/<章节名>-知识清单.html`
- `<目标目录>/EPA/<章节名>-章节测试.html`
同时保存 `knowledge_skeleton.json` 到 `.epa_work/`。浏览器打开所有 HTML。

> 写作规范（kp/exp 双色、四色标签、blockquote 易错、公式、题型按学科选）沿用下方「内容质量要求」与「题目编写规范」——它们与各卡片的硬规则同源。

---

## 期末整卷生成（final）

`/exampass final <目录>` 生成一份仿真期末试卷（整卷，覆盖全部章节）+ 答案。复用多 Agent 内核，额外加一个「考试蓝图」环节。

**交互**：先问用户考试难度、时长、题型偏好。默认**联网**参考其他优秀大学的同类期末题（仅取出题灵感与难度参照，**内容仍以 PPT 为准**）；用户可关闭联网。

**流程**：
1. **骨架**：`.epa_work/knowledge_skeleton.json` 已存在则复用，否则用 `agents/skeleton-agent.md` 现产一份。
2. **联网参考**（默认开）：用 `scripts/web_research.py` / WebSearch 搜同类课程期末题，归纳常考题型与难度，写入 `.epa_work/exam_reference.md`。
3. **考试蓝图**：按 `重要度 × 布鲁姆认知层级 × 题型 × 分值` 排一张蓝图，分值合计 100，覆盖全章、枢纽概念权重更高。**难度配比硬约束：basic(送分) 25% / medium(中档) 45% / hard(拉分) 30%**，不得过度集中在任一档。写入 `.epa_work/exam_blueprint.json`。
4. **命题**：用 `agents/item-agent.md` Part 4，按蓝图全局命题（题型按学科选）。
5. **验证**：用 `agents/solver-agent.md` 两遍法验证整卷，重点抓 answer_suspect / ambiguous / leak。
6. **一轮修订**：修被标记的题；校验分值合计 = 100、覆盖无遗漏。
7. **渲染**：`save_test()` 生成交互式试卷 HTML，答案用 `save_knowledge_html()`（markdown 组装可参考 `scripts/exam_generator.py`）。浏览器打开，Ctrl+P 打印 PDF。

---

## 技能更新

当用户执行 `/exampass update` 时，按以下脚本将 ExamPass Assistant 更新到最新版本。全程使用绝对路径，不受当前工作目录影响。

```powershell
$SkillDir = "$env:USERPROFILE\.claude\skills\exampass"

# 1. 定位并验证技能仓库
if (-not (Test-Path "$SkillDir")) {
    Write-Host "错误：找不到技能目录 $SkillDir"
    Write-Host "请重新安装：git clone https://github.com/WUBING2023/ExamPass-Assistant.git $SkillDir"
    exit 1
}
if (-not (Test-Path "$SkillDir\.git")) {
    Write-Host "错误：$SkillDir 不是 git 仓库"
    exit 1
}
Push-Location $SkillDir
Write-Host "技能目录：$SkillDir"
Write-Host ""

# 2. 获取远程更新信息
Write-Host "正在获取远程更新..."
git fetch origin master 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误：无法连接 GitHub，请检查网络。"
    Pop-Location
    exit 1
}

$Behind = [int](git rev-list --count HEAD..origin/master 2>&1)
Write-Host "当前落后 origin/master：$Behind 个提交"

if ($Behind -eq 0) {
    Write-Host "已是最新版本！"
    Write-Host ""
    Write-Host "验证 Python 依赖..."
    pip install -r requirements.txt 2>&1
    Write-Host ""
    Write-Host "当前版本："
    git log --oneline -3
    Pop-Location
    exit 0
}

Write-Host ""
Write-Host "待拉取的提交："
git log --oneline HEAD..origin/master
Write-Host ""

# 3. 处理本地修改
$Status = git status --porcelain 2>&1
if ($Status) {
    Write-Host "工作树有本地修改，先 stash 保存..."
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    git stash push --include-untracked -m "exampass-update-$Stamp" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误：git stash 失败"
        Pop-Location
        exit 1
    }
    $Stashed = $true
    Write-Host "修改已暂存为：exampass-update-$Stamp"
} else {
    $Stashed = $false
    Write-Host "工作树干净。"
}
Write-Host ""

# 4. 拉取最新代码
Write-Host "正在拉取最新代码..."
git pull origin master 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误：git pull 失败"
    if ($Stashed) {
        Write-Host "尝试恢复你的本地修改..."
        git stash pop 2>&1
    }
    Pop-Location
    exit 1
}
Write-Host "拉取完成。"
Write-Host ""

# 5. 恢复本地修改
if ($Stashed) {
    Write-Host "正在恢复本地修改..."
    git stash pop 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "==========================================="
        Write-Host "警告：本地修改无法自动合并，有冲突！"
        Write-Host "你的修改安全保存在 stash 中。手动恢复："
        Write-Host "  cd $SkillDir"
        Write-Host "  git stash list"
        Write-Host "  git stash pop  （手动解决冲突后 commit）"
        Write-Host "==========================================="
        Write-Host ""
    } else {
        Write-Host "本地修改已自动恢复。"
    }
}
Write-Host ""

# 6. 安装/更新依赖
Write-Host "安装 Python 依赖..."
pip install -r requirements.txt 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "警告：pip install 有错误，部分功能可能不可用。"
    Write-Host "手动重试：pip install -r $SkillDir\requirements.txt"
}
Write-Host ""

# 7. 更新摘要
Write-Host "==========================================="
Write-Host "  ExamPass 更新完成！"
Write-Host "==========================================="
Write-Host ""
Write-Host "最新提交："
git log --oneline -5
Write-Host ""
Write-Host "技能目录：$SkillDir"
Pop-Location
```

---

## 知识图谱生成（graph）

`/exampass graph <目录>` 生成左根右叶的交互式知识图谱（可编辑、粘贴图片、搜索、缩放）。**结构由骨架 Agent 产出**，比随手拆树更专业——带知识组件类型、重要度、依赖关系、枢纽概念。

1. **提取**：`python scripts/run_exampass.py <目录>`（`.epa_work/_extraction_bundle.json` 已存在可复用）。
2. **骨架**：`.epa_work/knowledge_skeleton.json` 已存在则复用，否则用 `agents/skeleton-agent.md` 现产一份。
3. **转换 + 渲染**：
```python
import json
from scripts.knowledge_graph import skeleton_to_graph_tree
from scripts.template_engine import save_graph_html

with open('.epa_work/knowledge_skeleton.json', encoding='utf-8') as f:
    skeleton = json.load(f)
tree = skeleton_to_graph_tree(skeleton)   # 章→组件两层树；deps 画依赖虚线，is_hub 标 ★ 枢纽
save_graph_html(tree, '知识图谱.html', tree['title'])
```
4. **打开**：浏览器打开 HTML。

依赖关系（`deps`）在图谱里画成**虚线次级连接**，枢纽概念（`is_hub`）加 ★ 标记，类型 / 重要度 / 依赖显示在节点 tooltip。

**从已有 JSON 重新生成**：用户给 `--from-json <路径>` 时直接读取——已是 tree 格式（含 `nodes`）则跳过转换，是骨架格式（含 `chapters`）则先 `skeleton_to_graph_tree()`，再调 `save_graph_html()`。

---

# ExamPass Assistant · 快速流程（fast 子命令）

> 以下是老的单 Agent 快流程，由 `/exampass fast <目录>` 触发。多 Agent 深度流程（默认）复用本节的「内容质量要求」与「题目编写规范」作为写作依据。

## 执行流程

### 第一步：提取（~30s）
```bash
python scripts/run_exampass.py <目标目录>
```
扫描目录、自动按章节拆分、提取 PPTX/DOCX/PDF 的文字、表格、图片。每章独立产 `_extraction_bundle.json` 在 `.epa_work/chapters/<章节名>/`。**图片处理见下方「图片识别与平台适配」。**

### 第二步：确认模式
默认使用**深度学习模式**作为主模式；只有当用户明确说「临考」「只要重点」「平衡一点」时，才切换到考试或平衡模式。

| 模式 | 知识清单风格 | 适用人群 |
|------|------------|---------|
| **考试** | 只列干货知识点（`.kp` 为主，极少 `.exp`），公式+结论+考点标签，删掉所有铺垫和推导过程，目标是最快过考试 | 临考突击 |
| **平衡** | 知识点 + 配套解释说明（`.kp` + `.exp` 双色），每个概念回答「是什么/为什么/怎么用」 | 常规复习 |
| **深度学习** | 主模式。把原理讲透：先用直觉类比铺路，再给正式定义、动机推演、数学推导、例题拆解、横向对比、易错辨析和记忆钩子，目标是再难的知识点也让用户读一遍就能理解 | 想真正学懂 |

### 第三步：深度分析与生成（Claude）
Claude 逐章读取 `.epa_work/chapters/<章节名>/_extraction_bundle.json`，按所选模式深度理解内容，调用模板引擎渲染 HTML。输出到 `<目标目录>/EPA/`：
- `<章节名>-知识清单.html`
- `<章节名>-章节测试.html`

### 第四步：打开
浏览器打开所有 HTML。Ctrl+P 打印为 PDF。

## 图片识别与平台适配

不同 AI 编程平台（Claude Code / Codex / OpenClaw 等）背后的模型能力不同。**关键风险：非多模态模型读不了图片**，会丢失 PPT 里的图表、公式截图、示意图。处理策略：

1. **多模态模型（如 Claude）**：直接把提取的图片作为视觉输入分析，图表内容融入知识清单。
2. **非多模态模型**：调用 OCR/文档解析插件把图片转成文字再喂给模型。优先级：
   - **MinerU**（推荐）：`pip install magic-pdf` 或调用 MinerU skill，对学术 PDF 的公式、表格、图表识别最好
   - **PaddleOCR / Tesseract**：通用 OCR 兜底
   - `scripts/run_exampass.py` 已提取图片到临时目录，可接入上述任一后端
3. **判断逻辑**：脚本检测 `_extraction_bundle.json` 中 `images` 字段非空且当前模型非多模态时，提示用户启用 MinerU/OCR 后端。

平台调用差异（命令行入口一致，仅环境变量/路径不同）：
- **Claude Code**：`python scripts/run_exampass.py <dir>`，多模态直读图片
- **Codex / OpenClaw**：同命令，若模型非多模态则先跑 MinerU 预处理生成 `*_ocr.txt` 再分析

## 内容质量要求（核心）

### 根本原则：把逻辑嚼碎了喂给用户

PPT 的问题是：信息碎片化、逻辑跳跃、缺少因果链。知识清单要做的不是"提炼要点"，而是**重构叙事**——把 PPT 里分散在 72 张幻灯片的信息，重组成一条清晰的逻辑链：**"因为遇到了什么问题 → 所以提出了什么方法 → 方法的核心思想是什么 → 具体怎么做 → 有什么局限 → 怎么改进"**。

深度学习模式是默认主模式。写作目标不是「总结得短」，而是「读一遍就懂」：每个难点都要先给直觉，再给正式定义，再解释为什么需要它，然后逐步推导或拆流程，最后用例子、对比和易错点把边界讲清。禁止只写术语堆砌、结论罗列、公式孤立出现。

### 三种模式的写作差异

| 维度 | 考试模式 | 平衡模式 | 深度学习模式 |
|------|---------|---------|------------|
| `.kp` 知识点 | 全部用，密集罗列 | 用，作扫读锚点 | 用，但融入叙事 |
| `.exp` 解释 | 几乎不用 | 每个知识点配 1-2 句 | 大段展开，类比+推导 |
| 公式 | 只给结论公式 | 公式+一句话解释 | 公式+推导过程+物理意义 |
| 类比/举例 | 无 | 关键处 1 个 | 每个概念都有 |
| 篇幅 | 最短 | 中等 | 最长（可比平衡长 2-4 倍，但必须可读、分层、少废话） |
| blockquote 易错 | 保留（考点） | 保留 | 保留+扩展辨析 |

三种模式都保留：H2/H3 结构、四色重要程度标签、目录、考点标注。区别只在解释的**深度和篇幅**。

### knowledge_body 写作规范（默认深度学习；平衡模式可适当压缩）

**每个概念必须回答三个问题**：
1. **是什么**（定义，一句话）
2. **为什么**（动机，解决了什么问题/为什么需要它）
3. **怎么用/注意什么**（关键细节，易错点）

**深度学习模式必须额外回答五个问题**：
1. **直觉上怎么理解**：用一个小例子或类比先消除陌生感。
2. **它从哪里推出来**：公式、算法、流程都要逐步解释，不能只给结果。
3. **每一步在解决什么**：把变量、条件、约束、操作目的说清。
4. **和相邻概念有什么区别**：容易混淆就必须配对比表。
5. **考试怎么设陷阱**：指出常见错误答案为什么看似对、实际错。

**结构要求**：
- 只写 H2/H3，引擎自动加 H1 + 目录
- 每个 H2 章节开头用 1-2 句话概括本章要解决的核心问题
- 公式后紧跟文字解释，说明每个符号的含义和直觉理解
- 对比概念必须配表格
- 每个 H3 结尾标注重要程度标签

**重要程度标签**（四色 CSS class）：
| 标签 | CSS class | 含义 |
|------|-----------|------|
| 必考 | `tag-must` | 综合题/问答题核心，必须能默写+推导 |
| 重点 | `tag-key` | 简答题高频，必须理解+能用自己的话解释 |
| 高频 | `tag-freq` | 选择/判断常考，记住关键区别即可 |
| 了解 | `tag-info` | 知道名字和作用，不考细节 |

**易错点标注**：容易混淆或考试常设陷阱的地方，用 blockquote 单独标出：
```html
<blockquote>易错：XXX 和 YYY 的区别不在于 A，而在于 B。考试常见陷阱是...</blockquote>
```

**公式规范**：
- 独立公式用 `$$...$$`，行内用 `$...$`
- 每个公式必须附带文字解释：这个公式在算什么？怎么算？为什么这样算？
- 关键公式用 blockquote 重复强调

**知识点 vs 解释的双色标注**：
- 核心概念、定义、公式用 `<span class="kp">...</span>` 包裹（黑色加粗，扫读锚点）
- 解释性文字、动机说明、举例用 `<span class="exp">...</span>` 包裹（浅灰色细体，辅助阅读）
- 例：`<span class="kp">束搜索每步保留 K 个最优前缀</span><span class="exp">——因为贪婪搜索没有后悔药，选错回不去</span>`

**箭头用 `--&gt;`，引号用「」**，不使用 Unicode 特殊字符

### 内容深度示例

错误写法（太浅）：
```html
<h3>束搜索</h3>
<p>每步保留K个最优前缀。K=1退化为贪婪搜索。通常K=3~10。</p>
```

正确写法（嚼碎了）：
```html
<h3>束搜索 <span class="tag-must">必考</span></h3>
<p><strong>动机</strong>：贪婪搜索每步只选概率最大的词，但「每步最优」不等于「整句最优」。比如第一步选了词A后，后面无论选什么词组合起来都很别扭——但贪婪搜索没有后悔药，选错了就回不去了。</p>
<p><strong>核心思想</strong>：别急着只留一个最好的，多留几个备选。每步保留 $K$ 个最可能的前缀序列，最后从 $K$ 个完整序列中选最好的。</p>
<p><strong>算法细节</strong>：第1步从 $|V|$ 个词中选概率最高的 $K$ 个。后续每步：当前 $K$ 个前缀各扩展 $|V|$ 个可能词，产生 $K\\cdot|V|$ 个候选，从中选 $K$ 个最优。复杂度 $O(K\\cdot|V|)$ 每步。</p>
<p><strong>K 的选择</strong>：$K=1$ 退化为贪婪。$K$ 越大搜索越全面，但计算量线性增长。通常 $K=3\\sim10$，翻译任务常用 $K=4\\sim6$。</p>
<blockquote>易错：束搜索是启发式方法，不能保证找到全局最优序列。考试常考判断题——说「束搜索保证全局最优」是错的。</blockquote>
```

### questions 题目编写规范

**支持的题型**（`type` 字段）：

| type | 题型 | 批改方式 | options 字段 | answer 字段 |
|------|------|---------|------------|------------|
| `choice` | 单选 | 自动 | `["选项A内容",...]`（不带ABC前缀） | 正确项索引 `0` 或 `"A"` |
| `multi` | 多选 | 自动（少选给部分分） | 同上 | `[0,2]` 或 `["A","C"]` |
| `tf` | 判断 | 自动 | `[]`（留空） | `0`(正确)/`1`(错误) 或 `true`/`false` |
| `fill` | 填空 | 自动（题干用 `____` 标记空位） | `[]` | `"答案"` 或 `["同义词"]` 或 `[["空1","空1同义"],["空2"]]` |
| `short` | 简答 | 显示参考答案 | `[]` | `-1` |
| `calc` | 计算题 | 显示参考答案 | `[]` | `-1` |
| `code` | 代码题（等宽深色输入框） | 显示参考答案 | `[]` | `-1` |
| `essay` | 问答 | 显示参考答案 | `[]` | `-1` |
| `comprehensive` | 综合题 | 显示参考答案 | `[]` | `-1` |

### 题型按学科自动选择（重要）

题型**不是固定的**。Claude 先判断学科类型，再决定出哪些题型——数学才出计算题，编程课才出代码题，语文绝不出代码题。判断依据是提取内容里的关键词（公式/代码块/定理 vs. 文学/历史/概念）。

| 学科类型 | 典型特征 | 主力题型 | 不出的题型 |
|---------|---------|---------|-----------|
| **数学 / 物理 / 工程** | 大量公式、定理、求解 | choice + fill + **calc** + comprehensive | code（除非含编程内容） |
| **计算机 / 编程** | 代码块、算法、API | choice + multi + **code** + calc + short | —— |
| **理论计算机 / AI 理论**（如本例深度学习） | 公式推导 + 算法实现 | choice + tf + short + **calc** + **code** + essay + comprehensive | —— |
| **文科 / 语文 / 历史 / 政治** | 概念、论述、记忆 | choice + tf + **fill** + short + **essay** + comprehensive | **calc、code 不出** |
| **外语** | 词汇、语法、翻译 | choice + fill + short + essay | calc、code 不出 |
| **生物 / 化学 / 医学** | 概念 + 部分计算 | choice + multi + fill + short + 少量 calc + essay | code（除非生信） |

**默认题量**（100 分，按上表筛选后分配）：选择 20 + 判断 10 + 填空 10 + 简答/计算/代码（按学科取 2-3 类，共 30）+ 问答 + 综合 20。**没把握就只出通用题型（choice/tf/fill/short/essay/comprehensive），宁可不出 calc/code 也不要张冠李戴。**

**编写要求**：
- 题干不加编号，选项不加 A/B/C/D 前缀（模板自动添加）
- choice/multi：干扰项基于常见错误理解设计，有真实迷惑性；不能只写单个术语，选项要包含条件、原因、结论或应用场景，让学生必须理解后才能判断
- choice：【硬约束】出完所有 choice 题必须逐字母统计 A/B/C/D 出现次数，各字母差 ≤1 且无连续三题同一答案；不达标逐题重排直到通过，不可跳过
- choice：干扰项至少覆盖概念混淆、条件缺失、因果倒置、步骤缺环、适用场景错配中的 3 类；禁止「以上都对/以上都错」和明显荒谬选项
- fill：题干在空位处写 `____`（≥2 个下划线），多空按顺序对应
- calc：题干给完整已知条件，explanation 含完整解题步骤 + 评分要点
- code：题干说明输入输出，explanation 给参考代码（用 `<pre><code>...</code></pre>` 包裹）+ 关键点说明
- essay/comprehensive：需要跨概念串联，考察逻辑链条

**题目 explanation 格式**：
```json
{
  "type": "calc", "points": 8,
  "question": "已知 d_k=64，Q·K 点积的方差约为多少？为什么要除以 sqrt(d_k)？",
  "answer": -1,
  "explanation": "<strong>解</strong>：方差约为 d_k=64。<br><br><strong>步骤</strong>：(1) ... (2) ...<br><br><strong>评分要点</strong>：方差结论 3 分，缩放原因 5 分。",
  "pitfall": "常见错误：误以为缩放是为了归一化。"
}
```

代码题示例：
```json
{
  "type": "code", "points": 10,
  "question": "用 PyTorch 实现缩放点积注意力 scaled_dot_product_attention(Q, K, V)。",
  "answer": -1,
  "explanation": "<strong>参考代码</strong>：<pre><code>import torch, math\ndef attn(Q,K,V):\n    d_k = Q.size(-1)\n    s = Q @ K.transpose(-2,-1) / math.sqrt(d_k)\n    w = torch.softmax(s, dim=-1)\n    return w @ V</code></pre><strong>关键点</strong>：转置 K、除以 sqrt(d_k)、最后一维 softmax。",
  "pitfall": "易错：softmax 维度选错；忘记缩放。"
}
```

## 常见错误及避免方法

1. **Python 内联代码过长** → 写成 .py 文件执行
2. **`$$` 内的 `\\text`** → Python 字符串中写成 `\\\\text`
3. **中文引号被转义** → 使用「」替代 ""
4. **Unicode `→` 导致 SyntaxError** → 使用 `--&gt;`
5. **题目 explanation 中的 `$`** → JSON 内无需转义
6. **空 options 的 tf 题** → `"options": []`，模板自动显示「正确」「错误」
