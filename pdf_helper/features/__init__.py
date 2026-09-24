"""Feature registry. To add a feature: create features/<name>.py exposing FEATURE, append it here.

Order is the button order, and the ``group`` of each feature is its tab, in first-appearance order.
"""

from pdf_helper.features import (
    add_image, add_text, compress, create_pdf, delete_pages, extract_content, extract_pages, find_text, grayscale,
    merge, nup, page_numbers, redact, replace_text, resize, rotate, split, split_bookmarks, tables, to_docx, to_images,
    watermark,
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
    # Stamp
    watermark.FEATURE,
    add_text.FEATURE,
    add_image.FEATURE,
    page_numbers.FEATURE,
    # Text
    replace_text.FEATURE,
    redact.FEATURE,
    find_text.FEATURE,
    # Output
    compress.FEATURE,
    grayscale.FEATURE,
    nup.FEATURE,
    resize.FEATURE,
]
