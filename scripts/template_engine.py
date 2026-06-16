"""Template engine for ExamPass HTML generation.

Architecture:
  templates/page_template.html  -- HTML shell (__TITLE__, __CSS__, __BODY__, __EXTRA_JS__)
  templates/base.css            -- shared styles
  templates/test.css            -- quiz-specific styles
  templates/test_js_template.js -- JS for interactive quiz (__QUESTIONS_PLACEHOLDER__, __LABELS_PLACEHOLDER__)
  templates/test_labels.json    -- Chinese UI labels
"""

import os
import json

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


def _read(filename):
    path = os.path.join(_TEMPLATES_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


_PAGE_TEMPLATE = _read('page_template.html')

_MATHJAX_CONFIG = '''<script>
MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']]
  }
};
</script>'''

_MATHJAX_SCRIPT = (
    '<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml-full.js"></script>'
)


def _build_page(title, body_html, css_extra='', js_extra=''):
    """Fill the page template. JS goes AFTER body -- critical for DOM access."""
    css = _read('base.css') + '\n' + css_extra
    return (
        _PAGE_TEMPLATE
        .replace('__TITLE__', title)
        .replace('__MATHJAX_CONFIG__', _MATHJAX_CONFIG)
        .replace('__MATHJAX_SCRIPT__', _MATHJAX_SCRIPT)
        .replace('__CSS__', css)
        .replace('__BODY__', body_html)
        .replace('__EXTRA_JS__', js_extra)
    )


# ─── Knowledge page ─────────────────────────────────────────────────

import re as _re

def _auto_toc_and_title(body_html, title):
    """Auto-inject H1 title + TOC block, and add anchor IDs to H2/H3 headings."""
    h1_html = '<h1>' + title + '</h1>\n'

    # Parse H2 and H3 headings, assign IDs
    toc_items = []

    def replace_heading(match):
        level = int(match.group(1))
        text = match.group(2).strip()
        # Remove HTML tags from text for clean TOC entry
        clean = _re.sub(r'<[^>]+>', '', text)
        # Generate anchor from a hash of the text (stable and safe)
        anchor = 's' + str(abs(hash(clean)))[:8]
        toc_items.append({'level': level, 'text': clean, 'anchor': anchor})
        return '<h' + str(level) + ' id="' + anchor + '">' + text + '</h' + str(level) + '>'

    body_html = _re.sub(r'<h([23])[^>]*?>(.+?)</h\1>', replace_heading, body_html, flags=_re.DOTALL)

    # Build TOC
    if toc_items:
        toc_html = '<div class="toc">\n<h2>目录</h2>\n<ul>\n'
        for item in toc_items:
            indent = '  ' if item['level'] == 3 else ''
            toc_html += indent + '<li><a href="#' + item['anchor'] + '">' + item['text'] + '</a></li>\n'
        toc_html += '</ul>\n</div>\n'
    else:
        toc_html = ''

    return h1_html + toc_html + body_html


def _build_slide_rail(slides):
    """Build the right-side Notion-style slide rail HTML from slide data.

    slides: list of {"page": str, "label": str, "img": data_uri, "text": str}
    Each card shows the rendered slide image + a collapsible original-text block.
    """
    cards = []
    for s in slides:
        page = s.get('page', '')
        label = s.get('label', f"第{page}页")
        img = s.get('img', '')
        text = (s.get('text') or '').strip()
        text_html = ''
        if text:
            # Escape minimal HTML, preserve line breaks
            safe = (text.replace('&', '&amp;').replace('<', '&lt;')
                        .replace('>', '&gt;').replace('\n', '<br>'))
            text_html = (
                '<details class="slide-text"><summary>原文文字</summary>'
                '<div class="slide-text-body">' + safe + '</div></details>'
            )
        cards.append(
            '<div class="slide-card" id="slide-p' + str(page) + '" data-page="' + str(page) + '">'
            '<div class="slide-card-label">' + label + '</div>'
            '<img class="slide-img" src="' + img + '" alt="' + label + '" loading="lazy" '
            'onclick="window.__epaLightbox&&window.__epaLightbox(this.src)">'
            + text_html +
            '</div>'
        )
    return '\n'.join(cards)


_SLIDE_CSS = """
/* ── Notion-style slide cross-reference layout ── */
/* Override base.css body max-width (860px); fill the viewport edge-to-edge,
   capped only on ultra-wide screens for readability. */
body { max-width: 2400px; width: 96vw; padding-left: 2vw; padding-right: 2vw; }
.kn-layout { display: flex; gap: 40px; align-items: flex-start; width: 100%; margin: 0 auto;
  overflow-x: hidden; }
.kn-main { flex: 1 1 56%; min-width: 0; overflow-x: hidden; }
.kn-main mjx-container[display="true"] { max-width: 100%; overflow-x: auto; overflow-y: hidden; }
.kn-rail { flex: 1 1 44%; max-width: 920px; position: sticky; top: 12px; align-self: flex-start;
  max-height: calc(100vh - 30px); overflow-y: auto; padding-right: 4px; }
.kn-rail-title { font-weight: 700; color: var(--ink-light); font-size: 0.9em; margin-bottom: 10px;
  padding-bottom: 6px; border-bottom: 1px solid var(--divider); }
.slide-card { border: 1px solid var(--card-border); border-radius: var(--radius);
  background: var(--card-bg); padding: 8px; margin-bottom: 14px; }
.slide-card-label { font-size: 0.78em; color: var(--ink-light); margin-bottom: 6px; }
.slide-img { width: 100%; border-radius: 4px; cursor: zoom-in; display: block;
  border: 1px solid var(--divider); }
.slide-text { margin-top: 6px; font-size: 0.85em; }
.slide-text summary { cursor: pointer; color: var(--accent); user-select: none; }
.slide-text-body { margin-top: 6px; color: var(--ink-light); line-height: 1.6;
  max-height: 220px; overflow-y: auto; padding: 6px 8px; background: #fff;
  border-radius: 4px; border: 1px solid var(--divider); }
/* heading-side page chips */
.pg-chip { display: inline-block; font-size: 0.72em; font-weight: 600; color: var(--accent);
  background: #eff4ff; border: 1px solid #cfe0ff; border-radius: 10px; padding: 0 7px;
  margin-left: 6px; cursor: pointer; vertical-align: middle; }
.pg-chip:hover { background: #dbe8ff; }
.slide-card.flash { animation: slideflash 1.2s ease; }
@keyframes slideflash { 0%,100%{box-shadow:none;} 30%{box-shadow:0 0 0 3px var(--accent);} }
/* lightbox */
#epa-lightbox { position: fixed; inset: 0; background: rgba(0,0,0,0.82); display: none;
  align-items: center; justify-content: center; z-index: 9999; cursor: zoom-out; }
#epa-lightbox img { max-width: 94vw; max-height: 94vh; border-radius: 6px; }
/* Tablet / narrow desktop: keep two columns but rebalance + tighten margins */
@media (max-width: 1280px) {
  body { width: 98vw; padding-left: 1vw; padding-right: 1vw; }
  .kn-layout { gap: 24px; }
  .kn-main { flex: 1 1 54%; }
  .kn-rail { flex: 1 1 46%; }
}
/* Mobile: stack the rail below the notes */
@media (max-width: 900px) {
  body { width: 100%; padding-left: 12px; padding-right: 12px; }
  .kn-layout { flex-direction: column; gap: 16px; }
  .kn-rail { position: static; flex: none; max-width: 100%; width: 100%; max-height: none; }
}
"""

_SLIDE_JS = """<script>
window.__epaLightbox = function(src){
  var lb = document.getElementById('epa-lightbox');
  if(!lb){ lb = document.createElement('div'); lb.id='epa-lightbox';
    lb.innerHTML='<img>'; document.body.appendChild(lb);
    lb.addEventListener('click', function(){ lb.style.display='none'; }); }
  lb.querySelector('img').src = src; lb.style.display='flex';
};
document.addEventListener('click', function(e){
  var chip = e.target.closest('.pg-chip'); if(!chip) return;
  var pg = chip.getAttribute('data-page');
  var card = document.getElementById('slide-p'+pg);
  if(card){ card.scrollIntoView({behavior:'smooth', block:'center'});
    card.classList.remove('flash'); void card.offsetWidth; card.classList.add('flash'); }
});
</script>"""


def _inject_heading_chips(body_html):
    """Turn heading-trailing <span data-slides="anchor1,anchor2"> markers into
    clickable [页N] chips that scroll the right rail to the matching slide.

    Notes agents may tag headings with data-slides; if absent this is a no-op.
    The chip label shows the trailing page number; data-page carries the full
    anchor id so the click handler can find the slide card.
    """
    def repl(m):
        anchors = m.group(1)
        chips = ''
        for a in anchors.split(','):
            a = a.strip()
            if not a:
                continue
            tail = _re.search(r'(\d+)\s*$', a)
            label = tail.group(1) if tail else a
            chips += ('<span class="pg-chip" data-page="' + a + '">页' + label + '</span>')
        return chips
    return _re.sub(r'<span\s+data-slides="([^"]*)"\s*></span>', repl, body_html)


def _norm_label(s):
    """Normalize a heading/KC label for fuzzy matching: strip tags, tag-words, spaces."""
    s = _re.sub(r'<[^>]+>', '', s)
    s = _re.sub(r'(必考|重点|高频|了解)', '', s)
    s = _re.sub(r'\s+', '', s)
    return s.strip()


def _auto_tag_headings(body_html, kcs, slides):
    """Auto-inject <span data-slides> into H2/H3 headings by matching their text
    to knowledge-component labels, mapping each KC's source_refs pages to the
    rendered slide anchors. Lets existing notes (no manual tags) get page chips.
    """
    if not kcs or not slides:
        return body_html

    # (pdf_basename, raw_page) -> anchor id
    anchor_of = {}
    for s in slides:
        anchor_of[(s.get('pdf', ''), int(s.get('raw_page', -1)))] = s.get('page')

    # Precompute each KC's available anchors (only pages that were actually rendered)
    from slide_renderer import parse_refs_by_pdf
    kc_anchors = []
    for kc in kcs:
        label = _norm_label(kc.get('label', ''))
        if not label:
            continue
        anchors = []
        by_pdf = parse_refs_by_pdf(kc.get('source_refs'))
        for pdf_name, pages in by_pdf.items():
            for pg in sorted(pages):
                # try exact pdf match, then any pdf (single-PDF chapters use '')
                anc = anchor_of.get((pdf_name, pg))
                if anc is None:
                    for (p2, pg2), a2 in anchor_of.items():
                        if pg2 == pg and (pdf_name == '' or p2 == pdf_name):
                            anc = a2
                            break
                if anc is not None and anc not in anchors:
                    anchors.append(anc)
        if anchors:
            kc_anchors.append((label, anchors))

    if not kc_anchors:
        return body_html

    def repl(m):
        level, attrs, inner = m.group(1), m.group(2), m.group(3)
        head_norm = _norm_label(inner)
        if not head_norm:
            return m.group(0)
        # find best KC whose label overlaps this heading
        best = None
        for label, anchors in kc_anchors:
            if label in head_norm or head_norm in label:
                if best is None or len(label) > len(best[0]):
                    best = (label, anchors)
        if not best:
            return m.group(0)
        marker = '<span data-slides="' + ','.join(best[1]) + '"></span>'
        return '<h' + level + attrs + '>' + inner + marker + '</h' + level + '>'

    return _re.sub(r'<h([23])([^>]*)>(.*?)</h\1>', repl, body_html, flags=_re.DOTALL)


def save_knowledge_html(body_html, output_path, title, slides=None, kcs=None):
    """Render the knowledge list. If `slides` is provided, add a Notion-style
    right-side slide rail (rendered PPT pages + collapsible original text).

    If `kcs` (the chapter's knowledge components) is also given, headings are
    auto-tagged with page chips that scroll the rail to the matching slide —
    so existing notes get the click-to-locate links without re-running agents.
    """
    if slides and kcs:
        body_html = _auto_tag_headings(body_html, kcs, slides)
    body_html = _inject_heading_chips(body_html)
    body_html = _auto_toc_and_title(body_html, title)

    css_extra = ''
    js_extra = ''
    if slides:
        rail = _build_slide_rail(slides)
        body_html = (
            '<div class="kn-layout"><div class="kn-main">' + body_html + '</div>'
            '<aside class="kn-rail"><div class="kn-rail-title">📑 原始幻灯片对照</div>'
            + rail + '</aside></div>'
        )
        css_extra = _SLIDE_CSS
        js_extra = _SLIDE_JS

    html = _build_page(title, body_html, css_extra=css_extra, js_extra=js_extra)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

# ─── Knowledge graph page ─────────────────────────────────────────

def save_graph_html(tree_json: dict, output_path: str, title: str):
    """Generate an interactive knowledge graph page.

    tree_json: {"title": "...", "nodes": [...]}
    """
    tree_data_js = 'const TREE_DATA = ' + json.dumps(tree_json, ensure_ascii=False) + ';'

    graph_css = _read('graph.css')
    graph_js = _read('graph.js')
    graph_template = _read('graph_template.html')

    html = graph_template
    html = html.replace('__TITLE__', title)
    html = html.replace('__MATHJAX_CONFIG__', _MATHJAX_CONFIG)
    html = html.replace('__MATHJAX_SCRIPT__', _MATHJAX_SCRIPT)
    html = html.replace('__CSS__', graph_css)
    html = html.replace('__TREE_DATA__', tree_data_js)
    html = html.replace('__JS__', graph_js)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


# ─── Interactive test page ──────────────────────────────────────────

def save_test(questions, output_path, title, subtitle='', duration_minutes=30):
    """Generate an interactive test page.

    questions: list of {type, points, question, options, answer, explanation, pitfall}
    subtitle: optional custom subtitle (overrides auto-generated duration subtitle)
    duration_minutes: used in auto-generated subtitle if subtitle is empty
    """
    questions_json = json.dumps(questions, ensure_ascii=False)
    labels = json.loads(_read('test_labels.json'))
    labels_json = json.dumps(labels, ensure_ascii=False)

    js_template = _read('test_js_template.js')
    js = js_template.replace('__QUESTIONS_PLACEHOLDER__', questions_json)
    js = js.replace('__LABELS_PLACEHOLDER__', labels_json)
    js = '<script>\n' + js + '\n</script>'

    # Subtitle
    if subtitle:
        sub_html = '<p style="text-align:center;color:var(--ink-light);font-size:0.95em">' + subtitle + '</p>'
    else:
        sub_html = '<p style="text-align:center;color:var(--ink-light);font-size:0.95em">' + labels['duration_prefix'] + str(duration_minutes) + labels['duration_suffix'] + '</p>'

    body = '\n'.join([
        '<h1>' + title + '</h1>',
        '<h2 style="text-align:center">' + labels['page_title'] + '</h2>',
        sub_html,
        '',
        '<div id="score-box"><div class="score-num" id="score-num">0</div><div class="score-label">' + labels['score_label'] + '</div></div>',
        '<div id="questions-container"></div>',
        '<div class="grading-bar no-print"><button onclick="gradeAll()" id="grade-btn">' + labels['grade_button'] + '</button></div>',
    ])

    html = _build_page(title, body, css_extra=_read('test.css'), js_extra=js)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
