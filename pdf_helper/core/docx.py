"""PDF -> DOCX via pdf2docx (heavy dependency: numpy + opencv)."""

from pathlib import Path


def to_docx(src: Path, out: Path) -> None:
    from pdf2docx import Converter  # imported lazily: slow import, optional at runtime

    cv = Converter(str(src))
    try:
        cv.convert(str(out))
    finally:
        cv.close()
