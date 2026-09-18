"""Markdown 图片文字化替换测试（纯函数，不触网）。"""

from app.services.image_enrichment import (
    EnrichmentResult,
    contains_image_placeholder,
    enrich_markdown_with_summaries,
    rename_image_refs,
)


def test_placeholder_detection_matches_flash_comment_forms() -> None:
    assert contains_image_placeholder("<!-- image-->\n\n正文")
    assert contains_image_placeholder("前言\n\n<!-- image -->\n")
    assert not contains_image_placeholder("# 纯文本\n\n没有图片")
    assert not contains_image_placeholder("")


def test_markdown_image_reference_replaced_with_summary() -> None:
    markdown = "前文\n\n![](images/a.png)\n\n后文"
    result = enrich_markdown_with_summaries(markdown, {"a.png": "总结A"})
    assert isinstance(result, EnrichmentResult)
    assert result.replaced == 1
    assert result.appended == 0
    assert "![](images/a.png)" not in result.markdown
    assert "总结A" in result.markdown


def test_html_img_replaced() -> None:
    markdown = '<p>说明<img src="images/b.jpg" alt="图"/></p>'
    result = enrich_markdown_with_summaries(markdown, {"b.jpg": "总结B"})
    assert result.replaced == 1
    assert "总结B" in result.markdown
    assert "<img" not in result.markdown


def test_unknown_refs_stay_untouched() -> None:
    markdown = "![](images/x.png)"
    result = enrich_markdown_with_summaries(markdown, {"a.png": "总结A"})
    assert result.replaced == 0
    assert "![](images/x.png)" in result.markdown
    assert result.markdown.endswith("图片说明：总结A\n")


def test_unreferenced_summary_appended_at_end() -> None:
    markdown = "# 只有文字\n"
    result = enrich_markdown_with_summaries(markdown, {"a.png": "总结A"})
    assert result.replaced == 0
    assert result.appended == 1
    assert result.markdown.endswith("图片说明：总结A\n")


def test_mixed_refs_and_unreferenced() -> None:
    markdown = '![](images/a.png)\n\n<img src="images/b.png" />\n\n![](images/c.png)'
    result = enrich_markdown_with_summaries(
        markdown, {"a.png": "总结A", "b.png": "总结B", "d.png": "总结D"}
    )
    assert result.replaced == 2
    assert result.appended == 1
    assert "总结A" in result.markdown
    assert "总结B" in result.markdown
    assert "![](images/c.png)" in result.markdown
    assert "总结D" in result.markdown


def test_empty_summaries_returns_unchanged() -> None:
    markdown = "![](images/a.png)"
    result = enrich_markdown_with_summaries(markdown, {})
    assert result.replaced == 0
    assert result.appended == 0
    assert result.markdown == markdown


def test_rename_image_refs_rewrites_markdown_and_html_refs() -> None:
    markdown = '![](images/a.png)\n\n<img src="images/b.jpg">\n\n![](images/c.png)'

    renamed = rename_image_refs(markdown, {"a.png": "p0001-a.png", "b.jpg": "p0001-b.jpg"})

    assert "![](images/p0001-a.png)" in renamed
    assert '<img src="images/p0001-b.jpg">' in renamed
    assert "![](images/c.png)" in renamed  # 未命中映射的原样保留


def test_rename_image_refs_keeps_alt_text() -> None:
    assert (
        rename_image_refs("![a.png](images/a.png)", {"a.png": "p0001-a.png"})
        == "![a.png](images/p0001-a.png)"
    )


def test_rename_image_refs_empty_inputs_are_noop() -> None:
    assert rename_image_refs("", {"a.png": "p0001-a.png"}) == ""
    assert rename_image_refs("![](images/a.png)", {}) == "![](images/a.png)"
