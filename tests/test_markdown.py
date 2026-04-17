from app.services.markdown import render_markdown


def test_renders_headings_and_paragraphs():
    html = render_markdown("# Title\n\nBody paragraph.")
    assert "<h1>Title</h1>" in html
    assert "<p>Body paragraph.</p>" in html


def test_renders_fenced_code_blocks():
    html = render_markdown("```python\nprint('hi')\n```")
    assert "<pre" in html
    assert "print(" in html


def test_strips_script_tags():
    html = render_markdown("Hello <script>alert(1)</script> world")
    assert "<script>" not in html
    assert "alert(1)" in html  # text is kept, tag is stripped


def test_renders_tables():
    md = "| a | b |\n|---|---|\n| 1 | 2 |"
    html = render_markdown(md)
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_empty_input_returns_empty_string():
    assert render_markdown("") == ""
    assert render_markdown(None) == ""
