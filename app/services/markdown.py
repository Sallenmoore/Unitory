import bleach
import markdown2

_ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "del", "details", "em",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "kbd",
    "li", "ol", "p", "pre", "strong", "sub", "summary", "sup", "table",
    "tbody", "td", "th", "thead", "tr", "ul",
}
_ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
    "pre": ["class"],
}

_EXTRAS = [
    "fenced-code-blocks",
    "tables",
    "strike",
    "task_list",
    "cuddled-lists",
    "code-friendly",
    "break-on-newline",
]


def render_markdown(text: str | None) -> str:
    if not text:
        return ""
    html = markdown2.markdown(text, extras=_EXTRAS)
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)
