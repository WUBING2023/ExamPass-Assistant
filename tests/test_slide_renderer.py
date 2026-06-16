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
