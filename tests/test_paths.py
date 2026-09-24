"""Output naming: an existing file is never replaced."""

from pathlib import Path

from pdf_helper.core.paths import fresh


def test_free_name_is_returned_unchanged(tmp_path: Path):
    assert fresh(tmp_path / "a.pdf") == tmp_path / "a.pdf"


def test_taken_names_are_numbered(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"")
    assert fresh(tmp_path / "a.pdf") == tmp_path / "a (2).pdf"
    (tmp_path / "a (2).pdf").write_bytes(b"")
    assert fresh(tmp_path / "a.pdf") == tmp_path / "a (3).pdf"


def test_folders_and_double_suffixes(tmp_path: Path):
    (tmp_path / "out").mkdir()
    assert fresh(tmp_path / "out") == tmp_path / "out (2)"
    (tmp_path / "a.tar.gz").write_bytes(b"")
    assert fresh(tmp_path / "a.tar.gz") == tmp_path / "a.tar (2).gz"
