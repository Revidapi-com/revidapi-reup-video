import os
import pytest
from reup import an_toan as a
from reup import dung, kich_ban


def test_che_khoa():
    assert "sk_abcdefgh1234" not in a.che("lỗi sk_abcdefgh1234 xyz")


def test_khoa_tu_env(monkeypatch):
    monkeypatch.setenv("REVIDAPI_KEY", "sk_testtesttest123")
    k = a.doc_khoa()
    assert k not in a.che(f"x {k} y")


def test_khoa_ky_tu_la(monkeypatch):
    monkeypatch.setenv("REVIDAPI_KEY", "sk_abc def\n")
    with pytest.raises(a.LoiAnToan):
        a.doc_khoa()


def test_file_khoa_bi_siet(tmp_path, monkeypatch):
    p = tmp_path / "khoa"; p.write_text("sk_filefilefile99"); os.chmod(p, 0o644)
    monkeypatch.delenv("REVIDAPI_KEY", raising=False)
    monkeypatch.setenv("REVIDAPI_KEY_FILE", str(p))
    a.doc_khoa()
    assert oct(p.stat().st_mode & 0o777) == "0o600"


@pytest.mark.parametrize("u", ["http://example.com/x.mp4", "https://127.0.0.1/x", "https://localhost/x",
                               "https://169.254.169.254/latest", "https://user:pw@example.com/", "file:///etc/passwd",
                               "https://10.0.0.1/a", "https://[::1]/a"])
def test_chan_url(u):
    with pytest.raises(a.LoiAnToan):
        a.kiem_url_media(u)


def test_ten_an_toan():
    assert "/" not in a.ten_an_toan("../../etc/passwd")
    assert a.ten_an_toan("") == "video"


def test_trong_thu_muc(tmp_path):
    with pytest.raises(a.LoiAnToan):
        a.trong_thu_muc(tmp_path, tmp_path / ".." / "x")


def test_ass_khong_chen_ma():
    s = dung._ass_chu("{\\pos(0,0)}hack\\N")
    assert "{" not in s and "\\" not in s


def test_kich_ban_lam_sach():
    kb = kich_ban.lam_sach({"tieu_de": "a\x00b", "doan": [{"loi": ""}, {"loi": "x" * 5000}, "rac"]})
    assert len(kb["doan"]) == 1 and len(kb["doan"][0]["loi"]) == 600 and "\x00" not in kb["tieu_de"]
    with pytest.raises(ValueError):
        kich_ban.lam_sach({"doan": []})
