"""Page-range specification parsing."""


def parse_page_spec(spec: str, total: int) -> list[int]:
    """Parse a 1-based page spec like "1-3,5,8-" into 0-based indices.

    Supported items: "3", "1-4", "7-" (to end), "-2" (from start). Order and
    duplicates are preserved so "3,1,1" yields pages 3, 1, 1.
    """
    if total < 1:
        raise ValueError("document has no pages")
    pages: list[int] = []
    for raw in spec.split(","):
        item = raw.strip()
        if not item:
            continue
        try:
            if "-" in item:
                lo_s, hi_s = item.split("-", 1)
                lo = int(lo_s) if lo_s.strip() else 1
                hi = int(hi_s) if hi_s.strip() else total
            else:
                lo = hi = int(item)
        except ValueError:
            raise ValueError(f"'{item}' is not a page number") from None
        if lo < 1 or hi > total or lo > hi:
            raise ValueError(f"page range '{item}' outside 1-{total}")
        pages.extend(range(lo - 1, hi))
    if not pages:
        raise ValueError("no pages given")
    return pages
