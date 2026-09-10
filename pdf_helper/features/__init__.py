"""Feature registry. To add a feature: create features/<name>.py exposing FEATURE, append it here."""

from pdf_helper.features import (
    compress, create_pdf, extract_content, extract_pages, merge, replace_text, rotate, split, to_docx, to_images, watermark,
)

FEATURES = [
    create_pdf.FEATURE,
    merge.FEATURE,
    extract_pages.FEATURE,
    extract_content.FEATURE,
    split.FEATURE,
    rotate.FEATURE,
    compress.FEATURE,
    to_images.FEATURE,
    watermark.FEATURE,
    replace_text.FEATURE,
    to_docx.FEATURE,
]
