"""Source tags for the news section.

The model never copies URLs (Google News links are ~300 characters and come
back mangled). Each headline goes in as [N1], [N2], …; the model ends every
item with the tag(s) it used; link_citations() then replaces the tags with
links to the stories, so every link in a newsletter is one we collected.
"""

import re
from typing import List, Sequence, Tuple

# One or more tags in a row: "[N2]", "[N1][N3]", "[N1, N3]".
_TAGS_RE = re.compile(r"(?:\s*\[\s*N\d+(?:\s*,\s*N?\d+)*\s*\])+")
_NUM_RE = re.compile(r"\d+")


def format_news_input(items: Sequence) -> str:
    """One line per headline: '- [N1] 2026-10-20 · BBC · 보도 · headline'."""
    lines = []
    for i, item in enumerate(items, 1):
        day = item.published.date() if item.published else item.collected
        lines.append(f"- [N{i}] {day:%Y-%m-%d} · {item.outlet or '출처 미상'} · {item.kind} · {item.title}")
    return "\n".join(lines)


def link_citations(text: str, items: Sequence) -> Tuple[str, List[str]]:
    """Replace each run of tags with ' ([Outlet](url), …)'. Returns the new
    text and the tags that matched no input headline (removed from the text)."""
    unknown: List[str] = []

    def replace(match):
        links: List[str] = []
        seen_urls, outlet_count = set(), {}
        for n in _NUM_RE.findall(match.group(0)):
            index = int(n) - 1
            if not 0 <= index < len(items):
                unknown.append(f"N{n}")
                continue
            if items[index].link in seen_urls:
                continue
            seen_urls.add(items[index].link)
            outlet = items[index].outlet or "출처"
            outlet_count[outlet] = outlet_count.get(outlet, 0) + 1
            # Two stories from one outlet: "Sky Sports, Sky Sports 2", not two identical labels.
            label = outlet if outlet_count[outlet] == 1 else f"{outlet} {outlet_count[outlet]}"
            links.append(f"[{label}]({items[index].link})")
        return f" ({', '.join(links)})" if links else ""

    return _TAGS_RE.sub(replace, text), unknown
