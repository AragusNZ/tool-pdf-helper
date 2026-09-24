import io

from pdf_helper.core import update
from pdf_helper.core.update import is_newer, latest_version


def test_is_newer_compares_numerically():
    assert is_newer("1.2.0", "1.1.0")
    assert is_newer("1.10.0", "1.9.0")
    assert is_newer("v2.0.0", "1.9.9")
    assert not is_newer("1.1.0", "1.1.0")
    assert not is_newer("1.0.9", "1.1.0")


def test_latest_version_strips_tag_prefix_and_sends_user_agent(monkeypatch):
    seen: dict = {}

    def fake_urlopen(req, timeout):
        seen["url"], seen["ua"], seen["timeout"] = req.full_url, req.get_header("User-agent"), timeout
        return io.BytesIO(b'{"tag_name": "v1.2.0"}')

    monkeypatch.setattr(update, "urlopen", fake_urlopen)
    assert latest_version(timeout=3) == "1.2.0"
    assert seen["url"] == update.RELEASES_API and seen["ua"].startswith("pdf-helper/") and seen["timeout"] == 3
