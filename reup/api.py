"""Gọi RevidAPI: tải video, giọng đọc, chat, ảnh. Khoá chỉ đi tới revidapi.com."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .an_toan import API_BASE, LoiAnToan, che, doc_khoa, tai_file


class LoiAPI(Exception):
    pass


def _goi(method: str, path: str, *, body: dict | None = None, query: dict | None = None, timeout: int = 120) -> Any:
    if not path.startswith("/") or ".." in path or "://" in path:
        raise LoiAnToan("Đường dẫn API không hợp lệ")
    url = API_BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "X-API-Key": doc_khoa(), "Content-Type": "application/json",
        "User-Agent": "revidapi-reup-video/1.0"})
    # Không theo chuyển hướng ra máy khác khi đang mang khoá
    opener = urllib.request.build_opener(_KhongChuyenHuong)
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read(20 * 1024 * 1024)
    except urllib.error.HTTPError as e:
        try:
            chi_tiet = json.loads(e.read(65536) or b"{}")
            msg = chi_tiet.get("detail") or chi_tiet.get("message") or chi_tiet.get("error") or chi_tiet
        except Exception:
            msg = ""
        raise LoiAPI(che(f"HTTP {e.code} {path}: {msg}")[:500]) from None
    except urllib.error.URLError as e:
        raise LoiAPI(che(f"Không kết nối được {path}: {e.reason}")) from None
    try:
        return json.loads(raw)
    except ValueError:
        raise LoiAPI(f"{path} trả về không phải JSON") from None


class _KhongChuyenHuong(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        raise LoiAnToan("API chuyển hướng bất thường — dừng để không gửi khoá đi nơi khác.")


def so_du() -> Any:
    return _goi("GET", "/account")


# ---------- tải video ----------
NEN_TANG = {"tiktok": "/tiktok/download", "douyin": "/douyin/download", "instagram": "/instagram/download",
            "facebook": "/facebook/download"}


def tai_video(link: str, dich: Path) -> dict:
    host = (urllib.parse.urlsplit(link).hostname or "").lower()
    path = "/download"
    for k, p in NEN_TANG.items():
        if k in host or (k == "facebook" and host.endswith("fb.watch")):
            path = p
    kq = _goi("POST", path, query={"url": link}, timeout=300)
    url = kq.get("download_direct") or kq.get("video_url")
    if not url:
        raise LoiAPI(f"Không lấy được link tải (nguồn trả rỗng): {che(json.dumps(kq, ensure_ascii=False))[:300]}")
    tai_file(url, dich)
    return {k: kq.get(k) for k in ("title", "duration", "uploader", "format")}


# ---------- giọng ----------
def danh_sach_giong() -> Any:
    return _goi("GET", "/voice-library")


def doc_giong(text: str, voice_id: int, dich: Path, speed: float = 1.0) -> Path:
    if not str(voice_id).isdigit():
        raise LoiAPI("voice_id phải là số (xem: reup giong-list)")
    body: dict[str, Any] = {"voice_id": int(voice_id), "text": text}
    if speed != 1.0:
        body["speed"] = speed
    job = _goi("POST", "/text-to-speech", body=body).get("job_id")
    if not job or not str(job).replace("-", "").isalnum():
        raise LoiAPI("TTS không trả job_id")
    han = time.time() + 600
    while time.time() < han:
        time.sleep(2)
        kq = _goi("GET", f"/text-to-speech/{job}")
        st = kq.get("status")
        if st == "failed":
            raise LoiAPI(f"TTS lỗi: {che(kq.get('message') or kq.get('error') or '')}")
        if st == "completed":
            r = kq.get("result") or {}
            url = r.get("audio_url") or kq.get("audio_url")
            if not url:
                raise LoiAPI("TTS xong nhưng không có audio_url")
            return tai_file(url, dich, toi_da=200 * 1024 * 1024)
    raise LoiAPI("TTS quá 10 phút")


# ---------- chat ----------
def chat(model: str, messages: list[dict], max_tokens: int = 4000) -> str:
    kq = _goi("POST", "/chat/completions", body={"model": model, "messages": messages,
                                                 "max_tokens": max_tokens, "temperature": 0.7}, timeout=600)
    try:
        return kq["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise LoiAPI(f"Chat trả sai dạng: {che(json.dumps(kq, ensure_ascii=False))[:300]}") from None


# ---------- ảnh ----------
def tao_anh(model: str, prompt: str, dich: Path, aspect_ratio: str = "9:16") -> Path:
    kq = _goi("POST", "/images/generations", body={"model": model, "prompt": prompt[:2000],
                                                   "aspect_ratio": aspect_ratio}, timeout=300)
    han = time.time() + 600
    while not (kq.get("data") or []) and kq.get("id"):
        if time.time() > han:
            raise LoiAPI("Ảnh quá 10 phút")
        if kq.get("status") == "failed":
            raise LoiAPI(f"Ảnh lỗi: {che(kq.get('error') or '')}")
        time.sleep(3)
        kq = _goi("GET", f"/images/jobs/{urllib.parse.quote(str(kq['id']), safe='')}")
    d = kq.get("data") or []
    if not d or not d[0].get("url"):
        raise LoiAPI("Ảnh không trả url")
    return tai_file(d[0]["url"], dich, toi_da=50 * 1024 * 1024)
