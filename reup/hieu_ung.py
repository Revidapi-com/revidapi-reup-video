"""Hiệu ứng cho cảnh có người, dùng bộ mã nguồn mở claude-video-effects (MIT, Vibha Ramprakash).

Bộ hiệu ứng KHÔNG được chép vào repo này. `reup cai-hieu-ung` clone đúng một commit đã
kiểm, từ chối nếu có file nạp thêm (fx_private.py), rồi chạy setup trong venv riêng.
Mọi thứ chạy trên máy, 0 credit.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

NGUON = "https://github.com/Vibha-Ramprakash/claude-video-effects"
COMMIT = "93140a976dcd1c78bda8819fa432ca7b4f260bf7"  # đã đọc mã, 04/11/2026
# Hiệu ứng máy quay, không chèn chữ nên không đè phụ đề; xoay vòng theo cảnh
TU_DONG = ["lean-in", "slow-push", "spotlight", "locked-on"]
TEN_FX = re.compile(r"^[a-z][a-z0-9-]{1,30}$")


def thu_muc() -> Path:
    return Path(os.environ.get("REUP_HIEU_UNG") or "~/.revidapi/hieu-ung").expanduser()


def _python(d: Path) -> Path:
    win = d / ".venv" / "Scripts" / "python.exe"
    return win if win.exists() else d / ".venv" / "bin" / "python"


def _kiem(d: Path) -> None:
    if (d / "scripts" / "fx_private.py").exists():
        raise RuntimeError("Bộ hiệu ứng có fx_private.py (mã nạp thêm không rõ nguồn) — xoá thư mục rồi cài lại.")
    sha = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if sha != COMMIT:
        raise RuntimeError(f"Bộ hiệu ứng không đúng commit đã kiểm ({sha[:7] or '?'}). Chạy lại: reup cai-hieu-ung")


def _moi_truong(d: Path) -> dict:
    """PATH có ffprobe: dùng bản thật nếu có, không thì bản thay (ffprobe_thay.py)."""
    env = dict(os.environ)
    if shutil.which("ffprobe") or os.name == "nt":
        return env
    bin_ = d / ".bin"
    bin_.mkdir(exist_ok=True)
    sh = bin_ / "ffprobe"
    thay = Path(__file__).with_name("ffprobe_thay.py")
    sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{thay}" "$@"\n')
    sh.chmod(0o755)
    env["PATH"] = f"{bin_}{os.pathsep}{env.get('PATH', '')}"
    return env


def cai() -> Path:
    d = thu_muc()
    if not (d / ".git").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", NGUON, str(d)], check=True)
    subprocess.run(["git", "-C", str(d), "fetch", "-q", "origin", COMMIT], check=False)
    subprocess.run(["git", "-C", str(d), "checkout", "-q", COMMIT], check=True)
    _kiem(d)
    subprocess.run(["bash", str(d / "scripts" / "setup.sh")], check=True, timeout=1800, env=_moi_truong(d))
    return d


def san_sang() -> bool:
    d = thu_muc()
    return _python(d).exists() and (d / "scripts" / "fx.py").exists()


def ke_hoach_tu_dong(moc: list[dict], canh_nguoi: list[int]) -> dict:
    hu = []
    for i in sorted(canh_nguoi):
        a, b = moc[i]["bat_dau"], moc[i]["ket_thuc"]
        if b - a < 1.2:
            continue
        hu.append({"fx": TU_DONG[len(hu) % len(TU_DONG)], "start": round(a + 0.1, 2), "end": round(min(b - 0.1, a + 3.5), 2)})
    return {"effects": hu}


def doc_ke_hoach(p: Path, tong: float) -> dict:
    """Kế hoạch người dùng tự viết: kiểm tên, mốc, độ dài chữ trước khi đưa cho fx.py."""
    d = json.loads(p.read_text(encoding="utf-8"))
    ra = []
    for x in (d.get("effects") if isinstance(d, dict) else None) or []:
        if not isinstance(x, dict) or not TEN_FX.match(str(x.get("fx", ""))):
            raise ValueError(f"Hiệu ứng sai tên: {str(x)[:80]}")
        a, b = float(x["start"]), float(x["end"])
        if not 0 <= a < b <= tong + 0.01:
            raise ValueError(f"Mốc {a}-{b}s nằm ngoài video {tong:.1f}s")
        y = {"fx": x["fx"], "start": a, "end": b}
        for k, v in x.items():
            if k not in y and k != "images" and isinstance(v, (str, int, float)):
                y[k] = str(v)[:200] if isinstance(v, str) else v
        ra.append(y)
    return {"effects": ra[:30]}


def ap_dung(vao: Path, ke_hoach: dict, ra: Path) -> Path:
    if not ke_hoach["effects"]:
        return vao
    d = thu_muc()
    _kiem(d)
    kh = ra.with_suffix(".hieu-ung.json")
    kh.write_text(json.dumps(ke_hoach, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run([str(_python(d)), str(d / "scripts" / "fx.py"), "--plan", str(kh), str(vao), str(ra)],
                   check=True, timeout=3600, cwd=str(d), env=_moi_truong(d))
    return ra
