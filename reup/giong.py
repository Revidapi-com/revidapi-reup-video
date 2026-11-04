"""Lồng giọng từng đoạn rồi nối với nhịp tự nhiên.

TTS ngừng sau mọi dấu chấm nên nghe đứt quãng. Ở đây mỗi đoạn kịch bản đọc riêng,
khoảng lặng bên trong đoạn được rút về 0,15s, giữa hai đoạn giữ 0,6s. Không chèn
im lặng số: khoảng nghỉ giữa đoạn lấy từ chính tiếng thở/đuôi âm của bản đọc.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import api
from .phan_tich import thoi_luong

NGHI_TRONG = 0.15
NGHI_CUOI = 0.6


def _khoang_lang(p: Path, db: int = -38, toi_thieu: float = 0.2) -> list[tuple[float, float]]:
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", f"silencedetect=n={db}dB:d={toi_thieu}",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    s = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", o)]
    e = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", o)]
    return list(zip(s, e))


def rut_nhip(vao: Path, ra: Path, giu_cuoi: float = NGHI_CUOI) -> float:
    """Rút khoảng lặng trong đoạn về NGHI_TRONG, cắt đuôi còn giu_cuoi. Trả về thời lượng mới."""
    D = thoi_luong(vao)
    giu: list[tuple[float, float]] = []
    t = 0.0
    for a, b in _khoang_lang(vao):
        if a <= 0.05:  # im đầu bài: bỏ, giữ 0,05s
            t = max(t, b - 0.05)
            continue
        if b >= D - 0.05:  # im cuối: xử lý sau
            break
        if b - a > NGHI_TRONG:
            giua = (a + b) / 2
            giu.append((t, giua - NGHI_TRONG / 2))
            t = giua + NGHI_TRONG / 2
    cuoi = D
    lang = _khoang_lang(vao)
    if lang and lang[-1][1] >= D - 0.05:
        cuoi = min(D, lang[-1][0] + giu_cuoi)
    giu.append((t, cuoi))
    loc = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in giu if b > a)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(vao), "-af",
                    f"aselect='{loc}',asetpts=N/SR/TB,afade=t=out:st={max(0, sum(b - a for a, b in giu) - 0.05):.3f}:d=0.05",
                    "-ar", "44100", "-ac", "1", str(ra)], check=True)
    return thoi_luong(ra)


def long_tieng(kb: dict, voice_id: int, thu_muc: Path, speed: float = 1.0) -> list[dict]:
    """Đọc từng đoạn, trả danh sách {file, bat_dau, ket_thuc} — mốc cảnh lấy từ giọng thật."""
    thu_muc.mkdir(parents=True, exist_ok=True)
    moc, t = [], 0.0
    for i, d in enumerate(kb["doan"]):
        tho = thu_muc / f"tho{i:02d}.mp3"
        sach = thu_muc / f"doan{i:02d}.wav"
        if not tho.exists():
            api.doc_giong(d["doc"], voice_id, tho, speed)
        dai = rut_nhip(tho, sach)
        moc.append({"file": sach.name, "bat_dau": round(t, 3), "ket_thuc": round(t + dai, 3)})
        t += dai
    danh_sach = thu_muc / "noi.txt"
    danh_sach.write_text("".join(f"file '{m['file']}'\n" for m in moc))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(danh_sach),
                    "-c:a", "pcm_s16le", str(thu_muc / "giong.wav")], check=True)
    (thu_muc / "moc.json").write_text(json.dumps(moc, indent=1))
    return moc
