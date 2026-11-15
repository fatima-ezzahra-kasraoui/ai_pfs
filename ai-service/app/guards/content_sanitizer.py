"""Nettoyage du contenu externe avant analyse (Guard B, AS-S2-003).

Retire ce qu'un humain ne voit pas mais qu'un LLM lit : balises ``script``/``style``,
commentaires HTML, éléments rendus invisibles (CSS ``display:none``, ``font-size:0``…),
caractères de largeur nulle, commentaires et liens Markdown masqués. Retourne le texte
visible et la liste des éléments retirés (extraits tronqués, utiles à l'audit).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from ..core.text import strip_invisible

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "blockquote", "pre", "table", "ul", "ol"}
ALWAYS_REMOVED = {"script", "style", "template", "noscript", "iframe", "object", "embed", "svg", "head", "title"}

_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$)|font-size\s*:\s*0(?:px|pt|em|rem|%)?\s*(?:;|$)"
    r"|height\s*:\s*0(?:px)?\s*;[^\"]*overflow\s*:\s*hidden|text-indent\s*:\s*-\d{3,}|left\s*:\s*-\d{4,}|color\s*:\s*(?:#fff(?:fff)?|white)\b[^\"]*background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white)",
    re.IGNORECASE,
)
_MD_COMMENT = re.compile(r"^\s*\[(?://|comment)\]\s*:\s*(?:#|<>)\s*(?:\(.*?\)|\".*?\"|'.*?')\s*$", re.MULTILINE | re.IGNORECASE)
_MD_EMPTY_LINK = re.compile(r"!?\[\s*\]\([^)]*\)")
_MD_TITLE_LINK = re.compile(r"(!?)\[([^\]]*)\]\(\s*([^)\s]+)\s+(?:\"([^\"]*)\"|'([^']*)')\s*\)")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_REFERENCE_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*\S+\s+(?:\"[^\"]+\"|'[^']+')\s*$", re.MULTILINE)
_LOOKS_LIKE_HTML = re.compile(r"<\s*/?\s*[a-zA-Z!][^>]*>|<!--")


@dataclass
class SanitizeResult:
    cleaned: str
    removed: list[dict[str, str]] = field(default_factory=list)
    # Texte complet (non tronqué) de ce qui a été retiré : sert à l'analyse, jamais à l'affichage.
    hidden_texts: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.removed)


def _excerpt(text: str, limit: int = 80) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.removed: list[dict[str, str]] = []
        self.hidden_texts: list[str] = []
        self._stack: list[tuple[str, str | None]] = []  # (tag, raison de masquage ou None)
        self._hidden_buffer: list[str] = []
        self._hidden_reason: str | None = None
        self._hidden_depth = 0

    # -- gestion de la pile ---------------------------------------------------------
    @property
    def _hidden(self) -> bool:
        return self._hidden_depth > 0

    def _flush_hidden(self) -> None:
        text = "".join(self._hidden_buffer).strip()
        if text:
            self.removed.append({"kind": self._hidden_reason or "hidden", "excerpt": _excerpt(text)})
            self.hidden_texts.append(text)
        self._hidden_buffer = []
        self._hidden_reason = None

    @staticmethod
    def _hidden_reason_for(tag: str, attrs: list[tuple[str, str | None]]) -> str | None:
        if tag in ALWAYS_REMOVED:
            return f"tag_{tag}"
        attr = {k.lower(): (v or "") for k, v in attrs}
        if "hidden" in attr and tag not in {"input"}:
            return "hidden_attribute"
        if attr.get("aria-hidden", "").lower() == "true":
            return "aria_hidden"
        if _HIDDEN_STYLE.search(attr.get("style", "") + ";"):
            return "css_hidden"
        return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in VOID_TAGS:
            if tag == "br" and not self._hidden:
                self.parts.append("\n")
            return
        reason = self._hidden_reason_for(tag, attrs)
        self._stack.append((tag, reason))
        if reason and not self._hidden:
            self._hidden_reason = reason
        if reason:
            self._hidden_depth += 1
        if tag in BLOCK_TAGS and not self._hidden:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "br" and not self._hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in VOID_TAGS:
            return
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                for _, reason in self._stack[i:]:
                    if reason:
                        self._hidden_depth -= 1
                        if self._hidden_depth == 0:
                            self._flush_hidden()
                del self._stack[i:]
                break
        if tag in BLOCK_TAGS and not self._hidden:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._hidden:
            self._hidden_buffer.append(data)
        else:
            self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        if data.strip():
            self.removed.append({"kind": "html_comment", "excerpt": _excerpt(data)})
            self.hidden_texts.append(data.strip())

    def close(self) -> None:
        super().close()
        if self._hidden:
            self._hidden_depth = 0
            self._flush_hidden()


def _clean_markdown(text: str, removed: list[dict[str, str]], hidden: list[str]) -> str:
    def drop(kind: str):
        def repl(match: re.Match[str]) -> str:
            removed.append({"kind": kind, "excerpt": _excerpt(match.group(0))})
            hidden.append(match.group(0))
            return ""

        return repl

    text = _MD_COMMENT.sub(drop("markdown_comment"), text)
    text = _MD_REFERENCE_DEF.sub(drop("markdown_reference_title"), text)
    text = _MD_EMPTY_LINK.sub(drop("markdown_empty_link"), text)

    def title_link(match: re.Match[str]) -> str:
        bang, label, _url, t1, t2 = match.groups()
        title = t1 or t2 or ""
        if title.strip():
            removed.append({"kind": "markdown_link_title", "excerpt": _excerpt(title)})
            hidden.append(title)
        return "" if bang else label

    text = _MD_TITLE_LINK.sub(title_link, text)
    text = _MD_IMAGE.sub(drop("markdown_image"), text)
    return text


def sanitize_content(content: str) -> SanitizeResult:
    """Retourne le texte visible d'un contenu externe et ce qui en a été retiré."""
    content = content or ""
    removed: list[dict[str, str]] = []
    hidden: list[str] = []

    content, n_invisible = strip_invisible(content)
    if n_invisible:
        removed.append({"kind": "zero_width_chars", "excerpt": f"{n_invisible} caractère(s)"})

    if _LOOKS_LIKE_HTML.search(content):
        parser = _VisibleTextParser()
        parser.feed(content)
        parser.close()
        removed.extend(parser.removed)
        hidden.extend(parser.hidden_texts)
        content = "".join(parser.parts)

    content = _clean_markdown(content, removed, hidden)
    content = re.sub(r"[ \t]+\n", "\n", content)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    return SanitizeResult(cleaned=content, removed=removed, hidden_texts=hidden)
