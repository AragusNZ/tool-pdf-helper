# Footnote comments

- [ ] *Gap* — Acrobat "insert/replace text" comments vanish: a Caret is not in `NOTE_TYPES` and its grouped StrikeOut is treated as a reply to a missing root and dropped — pdf_helper/core/notes.py:16, pdf_helper/core/notes.py:89
- [ ] *Gap* — a markup annotation with no QuadPoints raises and fails the whole file instead of being skipped — pdf_helper/core/notes.py:66
- [ ] *Gap* — margin numbers stack downward without limit and run off the bottom of a page with many notes near it — pdf_helper/core/notes.py:126
- [ ] *Gap* — `set_toc` after inserting notes pages rewrites every existing bookmark to page top, losing zoom and in-page position — pdf_helper/core/notes.py:281
