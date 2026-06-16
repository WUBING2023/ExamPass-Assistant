"""Tests for slide_renderer.py — PPT cross-reference slide rail."""

import os
import json
import pytest

from slide_renderer import (
    parse_refs_by_pdf,
    select_key_pages_by_pdf,
    select_key_pages,
    _pages_from_spec,
)
from template_engine import save_knowledge_html


class TestPageParsing:
    def test_single_page(self):
        assert _pages_from_spec("25") == {25}

    def test_range(self):
        assert _pages_from_spec("19-24") == {19, 20, 21, 22, 23, 24}

    def test_chinese_page(self):
        assert _pages_from_spec("第55页") == {55}

    def test_mixed_range_and_single(self):
        assert _pages_from_spec("3-5, 9") == {3, 4, 5, 9}


class TestRefsByPdf:
    def test_pdf_slash_pages(self):
        refs = ["3 分治-1.pdf/19-24"]
        result = parse_refs_by_pdf(refs)
        assert result == {"3 分治-1.pdf": {19, 20, 21, 22, 23, 24}}

    def test_does_not_grab_filename_digits(self):
        # The '3' and '1' in "3 分治-1.pdf" must NOT become pages
        refs = ["3 分治-1.pdf/25"]
        result = parse_refs_by_pdf(refs)
        assert result == {"3 分治-1.pdf": {25}}

    def test_multiple_pdfs(self):
        refs = ["3 分治-1.pdf/19-20", "3 分治-2.pdf/5"]
        result = parse_refs_by_pdf(refs)
        assert result["3 分治-1.pdf"] == {19, 20}
        assert result["3 分治-2.pdf"] == {5}

    def test_no_pdf_split_fallback(self):
        refs = ["12-14"]
        result = parse_refs_by_pdf(refs)
        assert result[""] == {12, 13, 14}


class TestKeyPageSelection:
    SKELETON = {
        "title": "算法",
        "chapters": [
            {
                "id": "ch3", "label": "分治",
                "kcs": [
                    {"id": "kc3.1", "importance": "must", "source_refs": ["3 分治-1.pdf/19-21"]},
                    {"id": "kc3.2", "importance": "key", "source_refs": ["3 分治-1.pdf/25"]},
                    {"id": "kc3.3", "importance": "info", "source_refs": ["3 分治-1.pdf/99"]},
                ],
            }
        ],
    }

    def test_only_must_and_key(self):
        # info-level KC (page 99) must be excluded
        result = select_key_pages_by_pdf(self.SKELETON, "分治")
        assert result["3 分治-1.pdf"] == {19, 20, 21, 25}
        assert 99 not in result["3 分治-1.pdf"]

    def test_flat_key_pages(self):
        flat = select_key_pages(self.SKELETON, "分治")
        assert flat == {19, 20, 21, 25}

    def test_chapter_filter(self):
        # Non-matching chapter label yields nothing
        result = select_key_pages_by_pdf(self.SKELETON, "贪心")
        assert result == {}


class TestSlideRailRendering:
    def test_knowledge_html_without_slides(self, temp_dir):
        """No slides → plain single-column layout, no rail."""
        out = os.path.join(temp_dir, "plain.html")
        save_knowledge_html("<h2>测试</h2><p>正文</p>", out, "测试")
        with open(out, encoding="utf-8") as f:
            html = f.read()
        assert "kn-rail" not in html
        assert "测试" in html

    def test_knowledge_html_with_slides(self, temp_dir):
        """Slides provided → Notion-style rail with cards + lightbox."""
        out = os.path.join(temp_dir, "rail.html")
        slides = [
            {"page": "12", "label": "第12页",
             "img": "data:image/jpeg;base64,AAAA", "text": "原始幻灯片文字"},
        ]
        save_knowledge_html("<h2>测试</h2>", out, "测试", slides=slides)
        with open(out, encoding="utf-8") as f:
            html = f.read()
        assert "kn-layout" in html
        assert "kn-rail" in html
        assert "slide-card" in html
        assert "__epaLightbox" in html
        assert "原始幻灯片文字" in html

    def test_stray_lt_escaped_in_questions(self, temp_dir):
        """A raw `<` in question text (e.g. low<high) must be escaped so it
        can't open a phantom tag that swallows later questions; real tags kept."""
        from template_engine import _escape_stray_lt, _sanitize_questions
        # literal inequality escaped
        assert _escape_stray_lt('low<high') == 'low&lt;high'
        assert _escape_stray_lt('i<n and a<b') == 'i&lt;n and a&lt;b'
        # real formatting tags preserved
        assert _escape_stray_lt('<pre><code>x</code></pre>') == '<pre><code>x</code></pre>'
        assert _escape_stray_lt('<strong>hi</strong>') == '<strong>hi</strong>'
        assert _escape_stray_lt('a <br> b') == 'a <br> b'
        # code with literal < inside a real tag: tag kept, inner < escaped
        assert _escape_stray_lt('<code>if x<n:</code>') == '<code>if x&lt;n:</code>'
        # sanitize_questions applies to all fields
        qs = [{"type": "choice", "question": "改为 low<high 会怎样?",
               "options": ["i<n", "正常"], "answer": 0, "explanation": "因为 a<b"}]
        s = _sanitize_questions(qs)
        assert "&lt;" in s[0]["question"]
        assert "&lt;" in s[0]["options"][0]
        assert "&lt;" in s[0]["explanation"]

    def test_combined_page_has_tabs(self, temp_dir):
        """Combined page holds both knowledge + test in tabbed panels."""
        from template_engine import save_combined_html
        out = os.path.join(temp_dir, "combined.html")
        questions = [{"type": "choice", "points": 2, "question": "Q1?",
                      "options": ["A", "B", "C", "D"], "answer": 0, "explanation": "e"}]
        save_combined_html("<h2>知识点</h2><p>讲解</p>", questions, out, "测试章")
        with open(out, encoding="utf-8") as f:
            html = f.read()
        assert 'id="epa-tabs"' in html
        assert 'data-tab="kn"' in html and 'data-tab="test"' in html
        assert 'id="panel-kn"' in html and 'id="panel-test"' in html
        assert "知识清单" in html and "章节测试" in html
        assert "知识点" in html  # knowledge content present
        assert "questions-container" in html  # test engine present

    def test_strips_full_document_note(self, temp_dir):
        """A note that arrives as a full dark-themed HTML document must have its
        <head>/<style>/<html> stripped so it can't override the page theme/layout."""
        out = os.path.join(temp_dir, "full.html")
        full_note = (
            '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<style>:root{--bg:#0d1117}body{background:var(--bg);max-width:740px}</style>'
            '</head><body><h2>归并排序</h2><p>正文内容</p></body></html>'
        )
        save_knowledge_html(full_note, out, "分治")
        with open(out, encoding="utf-8") as f:
            html = f.read()
        assert "#0d1117" not in html          # dark theme stripped
        assert "background: var(--bg)" not in html
        assert "归并排序" in html and "正文内容" in html  # content kept

    def test_slide_img_reserves_space(self, temp_dir):
        """Slide images carry width/height attrs (no collapsed short boxes)
        and are not lazy-loaded (base64 is already inline)."""
        out = os.path.join(temp_dir, "dims.html")
        slides = [{"page": "1", "label": "第1页", "img": "data:image/jpeg;base64,AAAA",
                   "iw": 900, "ih": 506, "text": ""}]
        save_knowledge_html("<h2>X</h2>", out, "X", slides=slides)
        with open(out, encoding="utf-8") as f:
            html = f.read()
        assert 'width="900"' in html and 'height="506"' in html
        assert 'loading=' not in html  # lazy removed — base64 needs no lazy
        assert "@media (max-width: 900px)" in html

    def test_heading_chip_injection(self, temp_dir):
        """<span data-slides="12,13"></span> becomes clickable page chips."""
        out = os.path.join(temp_dir, "chips.html")
        body = '<h2>分治法<span data-slides="12,13"></span></h2>'
        save_knowledge_html(body, out, "测试",
                            slides=[{"page": "12", "label": "第12页", "img": "x", "text": ""}])
        with open(out, encoding="utf-8") as f:
            html = f.read()
        assert 'class="pg-chip"' in html
        assert 'data-page="12"' in html
        assert 'data-page="13"' in html

    def test_auto_tag_headings_from_kcs(self, temp_dir):
        """Headings auto-get page chips by matching KC labels — no manual tags."""
        out = os.path.join(temp_dir, "auto.html")
        body = '<h3>归并排序 <span class="tag-must">必考</span></h3><p>正文</p>'
        slides = [
            {"page": "26", "pdf": "3 分治-1.pdf", "raw_page": 26,
             "label": "第26页", "img": "x", "text": "归并排序原文"},
        ]
        kcs = [
            {"id": "kc3.3", "label": "归并排序", "importance": "must",
             "source_refs": ["3 分治-1.pdf/26"]},
        ]
        save_knowledge_html(body, out, "分治", slides=slides, kcs=kcs)
        with open(out, encoding="utf-8") as f:
            html = f.read()
        # The 归并排序 heading should get a chip pointing at page 26
        assert 'class="pg-chip"' in html
        assert 'data-page="26"' in html

    def test_auto_tag_skips_unmatched_heading(self, temp_dir):
        """A heading with no matching KC gets no chip."""
        out = os.path.join(temp_dir, "nomatch.html")
        body = '<h3>完全不相关的标题</h3>'
        slides = [{"page": "5", "pdf": "x.pdf", "raw_page": 5,
                   "label": "第5页", "img": "x", "text": ""}]
        kcs = [{"id": "k1", "label": "归并排序", "importance": "must",
                "source_refs": ["x.pdf/5"]}]
        save_knowledge_html(body, out, "测试", slides=slides, kcs=kcs)
        with open(out, encoding="utf-8") as f:
            html = f.read()
        # Heading text present but no chip injected for it
        assert "完全不相关的标题" in html
        assert 'data-page="5"' not in html.split('kn-rail')[0]  # no chip in note area
