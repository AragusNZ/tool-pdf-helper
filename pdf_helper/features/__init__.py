"""Feature registry. To add a feature: create features/<name>.py exposing FEATURE, append it here.

Order is the button order, and the ``group`` of each feature is its tab, in first-appearance order.
"""

from pdf_helper.features import (
    compress,
    create_pdf,
    delete_pages,
    edit,
    extract_content,
    extract_pages,
    find_text,
    footnotes,
    grayscale,
    merge,
    metadata,
    nup,
    protect,
    redact,
    resize,
    rotate,
    split,
    split_bookmarks,
    tables,
    to_docx,
    to_images,
    unlock,
)

FEATURES = [
    # Convert
    create_pdf.FEATURE,
    merge.FEATURE,
    to_images.FEATURE,
    to_docx.FEATURE,
    extract_content.FEATURE,
    tables.FEATURE,
    # Pages
    extract_pages.FEATURE,
    delete_pages.FEATURE,
    split.FEATURE,
    split_bookmarks.FEATURE,
    rotate.FEATURE,
    # Edit
    edit.FEATURE,
    # Text
    redact.FEATURE,
    find_text.FEATURE,
    footnotes.FEATURE,
    # Output
    compress.FEATURE,
    grayscale.FEATURE,
    nup.FEATURE,
    resize.FEATURE,
    protect.FEATURE,
    unlock.FEATURE,
    metadata.FEATURE,
]
