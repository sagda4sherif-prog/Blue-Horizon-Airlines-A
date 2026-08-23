"""Shared helper for reading a LangChain chat response's `.content`.

Bug fix (see README Bug Fix Log): every call site in this package used to
assume `response.content` is always a plain `str`, which was true for
gemini-2.5-flash and earlier. Newer Gemini generations (3.x and later, e.g.
gemini-3.5-flash-lite) instead return content as a list of content blocks --
typically `[{"type": "text", "text": "..."}]` -- so `isinstance(content, str)`
silently went False and every affected call raised "the chat model returned
an empty or unsupported response" even on a perfectly normal reply. See
https://github.com/langchain-ai/langchain/issues/35571 for the upstream
report of this response-shape change.
"""

from __future__ import annotations


def extract_text(content: object) -> str:
    """Return the plain text of a chat response's `.content`, handling both
    the legacy plain-`str` shape and the newer list-of-content-blocks shape.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""