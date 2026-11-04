"""Lớp an toàn dùng chung: khoá, che khoá, kiểm URL, kiểm đường dẫn, tải file có giới hạn.

Nguyên tắc:
- Khoá chỉ đọc từ biến môi trường REVIDAPI_KEY hoặc file ~/.revidapi/khoa (quyền 600).
  Không nhận khoá qua tham số dòng lệnh (lộ trong `ps` và lịch sử shell).
- Khoá chỉ được gửi tới đúng máy chủ API (https://revidapi.com). Không bao giờ gửi kèm
  khi tải file media từ link kết quả.
- Mọi chuỗi in ra / ghi log đi qua che() để không lộ khoá.
- Link tải media phải là https, không trỏ vào IP nội bộ (chống SSRF), có trần dung lượng.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import stat
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://revidapi.com/v1"
API_HOST = "revidapi.com"
MAX_TAI = 1024 * 1024 * 1024  # 1GB / file
_KHOA_RE = re.compile(r"\b(sk|lk|rk)_[A-Za-z0-9]{8,}\b")


class LoiAnToan(Exception):
    pass


def doc_khoa() -> str:
    k = os.environ.get("REVIDAPI_KEY", "").strip()
    if not k:
        p = Path(os.environ.get("REVIDAPI_KEY_FILE") or Path.home() / ".revidapi" / "khoa")
        if p.is_file():
            mode = p.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                os.chmod(p, 0o600)  # tự siết lại: người khác trên máy không được đọc
            k = p.read_text(encoding="utf-8").strip()
    if not k:
        raise LoiAnToan("Chưa có khoá. Đặt biến REVIDAPI_KEY hoặc ghi vào ~/.revidapi/khoa (chmod 600).")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{10,200}", k):
        raise LoiAnToan("Khoá có ký tự lạ — kiểm lại (thường do dán thừa dấu cách/xuống dòng/ký tự che).")
    _DA_BIET.add(k)
    return k


_DA_BIET: set[str] = set()


def che(s: object) -> str:
    """Che mọi khoá trong chuỗi trước khi in/ghi."""
    t = str(s)
    for k in _DA_BIET:
        if k:
            t = t.replace(k, k[:3] + "***")
    return _KHOA_RE.sub(lambda m: m.group(0)[:3] + "***", t)


def _ip_cam(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return True
    return False


def kiem_url_media(url: str) -> str:
    """Link người dùng đưa (video mẫu) hoặc link kết quả API: chỉ https công khai."""
    if not isinstance(url, str) or len(url) > 4096:
        raise LoiAnToan("Link không hợp lệ.")
    u = urllib.parse.urlsplit(url.strip())
    if u.scheme != "https" or not u.hostname:
        raise LoiAnToan(f"Chỉ nhận link https: {che(url)[:120]}")
    if u.username or u.password:
        raise LoiAnToan("Link không được chứa tài khoản/mật khẩu.")
    if _ip_cam(u.hostname):
        raise LoiAnToan(f"Link trỏ vào địa chỉ nội bộ/không phân giải được: {u.hostname}")
    return url.strip()


class _ChanChuyenHuong(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        kiem_url_media(newurl)  # chuyển hướng cũng phải qua kiểm, chặn nhảy vào mạng nội bộ
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            new.headers.pop("X-api-key", None)
            new.headers.pop("Authorization", None)
        return new


def _ssl():
    """Python cài từ python.org trên macOS không có sẵn chứng chỉ: dùng certifi nếu có."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


HTTPS = urllib.request.HTTPSHandler(context=_ssl())
_opener = urllib.request.build_opener(HTTPS, _ChanChuyenHuong)


def tai_file(url: str, dich: Path, *, toi_da: int = MAX_TAI, timeout: int = 120) -> Path:
    """Tải media KHÔNG kèm khoá, có trần dung lượng, ghi file tạm rồi đổi tên."""
    kiem_url_media(url)
    dich = Path(dich)
    tam = dich.with_suffix(dich.suffix + ".tai")
    req = urllib.request.Request(url, headers={"User-Agent": "revidapi-reup-video/1.0"})
    n = 0
    with _opener.open(req, timeout=timeout) as r, open(tam, "wb") as f:
        cl = r.headers.get("Content-Length")
        if cl and cl.isdigit() and int(cl) > toi_da:
            raise LoiAnToan(f"File quá lớn ({int(cl) >> 20}MB).")
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            n += len(b)
            if n > toi_da:
                f.close(); tam.unlink(missing_ok=True)
                raise LoiAnToan("File vượt trần dung lượng, đã huỷ.")
            f.write(b)
    tam.replace(dich)
    return dich


def ten_an_toan(s: str, mac_dinh: str = "video") -> str:
    """Tên file/thư mục từ dữ liệu ngoài: bỏ ../, ký tự lạ."""
    t = re.sub(r"[^A-Za-z0-9._-]+", "-", s or "").strip(".-")[:60]
    return t or mac_dinh


def trong_thu_muc(goc: Path, p: Path) -> Path:
    goc, p = Path(goc).resolve(), Path(p).resolve()
    if goc != p and goc not in p.parents:
        raise LoiAnToan(f"Đường dẫn ra ngoài thư mục làm việc: {p}")
    return p
