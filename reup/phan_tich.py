"""Phân tích video mẫu: cảnh, frame, lời (whisper), nhịp. Chạy hoàn toàn trên máy, 0 credit."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


def thoi_luong(p: Path) -> float:
    if shutil.which("ffprobe"):
        o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True)
        if o.returncode == 0 and o.stdout.strip():
            return float(o.stdout.strip())
    o = subprocess.run(["ffmpeg", "-i", str(p)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", o)
    if not m:
        raise ValueError("Không đọc được thời lượng — file không phải video?")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def cat_canh(vid: Path, nguong: float = 0.12, toi_da_giay: float = 4.0) -> list[list[float]]:
    D = thoi_luong(vid)
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(vid), "-vf", f"select='gt(scene,{nguong})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    cuts = sorted({0.0, *[round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", o)]})
    cuts = [c for c in cuts if c < D - 0.2]
    out = []
    for a, b in zip(cuts, cuts[1:] + [D]):
        if b - a < 0.25:
            continue
        n = max(1, int((b - a) // toi_da_giay))
        out += [[round(a + (b - a) * i / n, 2), round(a + (b - a) * (i + 1) / n, 2)] for i in range(n)]
    return out


def chup_frame(vid: Path, canh: list[list[float]], thu_muc: Path) -> list[Path]:
    thu_muc.mkdir(parents=True, exist_ok=True)
    ps = []
    for i, (a, b) in enumerate(canh):
        p = thu_muc / f"c{i:03d}.jpg"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{(a + b) / 2:.2f}", "-i", str(vid),
                        "-frames:v", "1", "-vf", "scale=540:-2", str(p)], check=True)
        ps.append(p)
    cot = 6
    hang = max(1, (len(ps) + cot - 1) // cot)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(thu_muc / "c%03d.jpg"), "-vf",
                    f"scale=180:-2,tile={cot}x{hang}", "-frames:v", "1", str(thu_muc.parent / "tong-quan.jpg")])
    return ps


def co_nguoi(anh: Path) -> bool:
    """Phát hiện người trong frame bằng OpenCV (trên máy, 0 credit): mặt chính diện, mặt nghiêng, nửa thân."""
    import cv2
    img = cv2.imread(str(anh))
    if img is None:
        return False
    xam = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    h = img.shape[0]
    for ten, toi_thieu in (("haarcascade_frontalface_default.xml", h // 12), ("haarcascade_profileface.xml", h // 12),
                           ("haarcascade_upperbody.xml", h // 5)):
        bo = cv2.CascadeClassifier(cv2.data.haarcascades + ten)
        if len(bo.detectMultiScale(xam, 1.1, 6, minSize=(toi_thieu, toi_thieu))):
            return True
    return False


def tong_quan(vid: Path, ra: Path, moi_giay: float = 1.0, cot: int = 8) -> Path:
    """Toàn bộ video thành MỘT khung lưới (mỗi giây 1 ô) để nhìn phong cách cả bài."""
    D = thoi_luong(vid)
    n = max(1, int(D * moi_giay))
    hang = (n + cot - 1) // cot
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-vf",
                    f"fps={moi_giay},scale=160:-2,tile={cot}x{hang}:padding=4:margin=8:color=0x111111",
                    "-frames:v", "1", str(ra)], check=True)
    return ra


def boc_loi(vid: Path, model: str = "small", ngon_ngu: str | None = None) -> tuple[list[dict], str]:
    from faster_whisper import WhisperModel  # nặng: chỉ nạp khi cần
    m = WhisperModel(model, compute_type="int8")
    segs, info = m.transcribe(str(vid), language=ngon_ngu, word_timestamps=True, vad_filter=True)
    words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in (s.words or [])]
    return words, info.language


def phan_tich(vid: Path, ra: Path, whisper_model: str = "small") -> dict:
    ra.mkdir(parents=True, exist_ok=True)
    D = thoi_luong(vid)
    canh = cat_canh(vid)
    frames = chup_frame(vid, canh, ra / "frames")
    tong_quan(vid, ra / "toan-bo.jpg")
    nguoi = [co_nguoi(f) for f in frames]
    words, lang = boc_loi(vid, whisper_model)
    lens = [b - a for a, b in canh] or [0]
    noi = sum(w["e"] - w["s"] for w in words)
    nhip = {"thoi_luong": round(D, 2), "so_canh": len(canh), "canh_tb_giay": round(sum(lens) / len(lens), 2),
            "tu_moi_giay": round(len(words) / D, 2) if D else 0, "ngon_ngu": lang,
            "ty_le_co_loi": round(noi / D, 2) if D else 0,
            "canh_co_nguoi": [i for i, x in enumerate(nguoi) if x],
            "hook_3s": " ".join(w["w"] for w in words if w["s"] < 3)}
    (ra / "canh.json").write_text(json.dumps(canh))
    (ra / "loi.json").write_text(json.dumps(words, ensure_ascii=False))
    (ra / "loi.txt").write_text(" ".join(w["w"] for w in words), encoding="utf-8")
    (ra / "nhip.json").write_text(json.dumps(nhip, ensure_ascii=False, indent=1), encoding="utf-8")
    return nhip
