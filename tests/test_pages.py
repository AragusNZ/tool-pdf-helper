import pytest

from pdf_helper.core.pages import parse_page_spec


def test_single_and_ranges():
    assert parse_page_spec("1-3,5", 10) == [0, 1, 2, 4]
    assert parse_page_spec("8-", 10) == [7, 8, 9]
    assert parse_page_spec("-2", 10) == [0, 1]
    assert parse_page_spec(" 3 , 1 ", 10) == [2, 0]


@pytest.mark.parametrize("spec", ["0", "11", "5-3", "", "abc", "1-99"])
def test_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        parse_page_spec(spec, 10)


def test_rejects_empty_document():
    with pytest.raises(ValueError, match="no pages"):
        parse_page_spec("1", 0)


def test_non_numeric_item_message():
    with pytest.raises(ValueError, match="'abc' is not a page number"):
        parse_page_spec("1,abc", 5)
    with pytest.raises(ValueError, match="'1-x' is not a page number"):
        parse_page_spec("1-x", 5)
