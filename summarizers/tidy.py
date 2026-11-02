"""Deterministic clean-up of the model's Korean before an edition is saved.

Prompt rules reduce these habits; this makes the few that matter most
certain. Each step is counted, so the evaluation can still report how often
the model itself wrote them (the raw output is kept in inputs/{team}.json).
"""

import re
from typing import Dict, Tuple

from summarizers.korean import fix_particles

# A news item's title line: "- **제목** (보도)".
_TITLE = r"[ \t]*[-*] \*\*[^\n]*?\*\*[ \t]*\((?:보도|가십|FotMob 공식)\)"
_TITLE_LINE_RE = re.compile(rf"^{_TITLE}[ \t]*$")
_TITLE_THEN_DASH_RE = re.compile(rf"^({_TITLE})[ \t]*(?:—|―|–|-{{1,2}})[ \t]*(?=\S)", re.MULTILINE)
_NOT_BODY_RE = re.compile(r"^\s*(?:[-*] |#|\||---|\[)")


def title_breaks(text: str) -> str:
    """Put each news item's body on its own line under the title.

    In Markdown a plain newline inside a list item is a soft break, so the
    title and body render as one run-on line; the em dash used to be the
    only thing between them. A line ending in two spaces is a hard break,
    and invisible in the plain-text part of the email.
    """
    text = _TITLE_THEN_DASH_RE.sub(lambda m: m.group(1) + "\n  ", text)
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if _TITLE_LINE_RE.match(line):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and not _NOT_BODY_RE.match(lines[j]):
                out += [line.rstrip() + "  ", "  " + lines[j].strip()]
                i = j + 1
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


def replace_dashes(text: str) -> Tuple[str, int]:
    """Em/horizontal-bar dashes (and spaced en dashes) become commas. A
    hyphen or en dash inside a score ("2-1", "2–1") is a score, not prose."""
    text = re.sub(r"(?<=\d)[ \t]*–[ \t]*(?=\d)", "-", text)
    pattern = re.compile(r"[ \t]*(?:—|―|[ \t]–[ \t])[ \t]*")
    count = len(pattern.findall(text))
    text = pattern.sub(", ", text)
    text = re.sub(r"^, |(?<=\()\s*, ", "", text, flags=re.MULTILINE)
    text = re.sub(r",[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r",[ \t]*,", ",", text)
    return text, count


def tidy(text: str) -> Tuple[str, Dict[str, int]]:
    """The model's section with dashes, title breaks and club particles fixed."""
    if not text:
        return text, {"dashes": 0, "particles": 0}
    text = title_breaks(text)
    text, dashes = replace_dashes(text)
    text, particles = fix_particles(text)
    return text, {"dashes": dashes, "particles": particles}
