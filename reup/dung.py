"""Dựng video dọc 1080x1920 bằng ffmpeg: hình từng cảnh + Ken Burns + phụ đề + giọng + nhạc + tiếng vút."""
from __future__ import annotations

import subprocess
from pathlib import Path

W, H, FPS = 1080, 1920, 30


def _ass_chu(s: str) -> str:
    # Chặn chèn mã định dạng ASS từ nội dung AI
    return s.replace("\\", "⧵").replace("{", "(").replace("}", ")").replace("\n", " ")


def _gio(t: float) -> str:
    h, r = divmod(max(t, 0), 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def phu_de(kb: dict, moc: list[dict], ra: Path) -> Path:
    dong = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Sub,Arial,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,2,80,80,360,1",
            "Style: Big,Arial,92,&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,3,8,80,80,260,1",
            "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for d, m in zip(kb["doan"], moc):
        a, b = m["bat_dau"], m["ket_thuc"]
        if d.get("chu_tren_hinh"):
            dong.append(f"Dialogue: 0,{_gio(a)},{_gio(b)},Big,,0,0,0,,{{\\fad(150,100)}}{_ass_chu(d['chu_tren_hinh'])}")
        tu = d["loi"].split()
        cum = [tu[i:i + 6] for i in range(0, len(tu), 6)] or [[]]
        tong = sum(len(" ".join(c)) for c in cum) or 1
        t = a
        for c in cum:
            dt = (b - a) * len(" ".join(c)) / tong
            dong.append(f"Dialogue: 0,{_gio(t)},{_gio(t + dt)},Sub,,0,0,0,,{_ass_chu(' '.join(c))}")
            t += dt
    ra.write_text("\n".join(dong) + "\n", encoding="utf-8")
    return ra


def _canh(hinh: Path, dai: float, ra: Path, i: int) -> Path:
    n = max(1, round(dai * FPS))
    if hinh.suffix.lower() in (".mp4", ".mov", ".webm"):  # clip video AI: lặp/cắt cho vừa cảnh
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(hinh), "-an", "-vf",
                        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p",
                        "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(ra)], check=True)
        return ra
    huong = ["zoom+0.0006", "if(eq(on,0),1.06,zoom-0.0006)"][i % 2]
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.15[nen];"
          f"[0:v]scale={W}:-2:force_original_aspect_ratio=decrease[tren];"
          f"[nen][tren]overlay=(W-w)/2:(H-h)/2,scale={W * 2}:{H * 2},"
          f"zoompan=z='{huong}':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(hinh), "-filter_complex", vf,
                    "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(ra)], check=True)
    return ra


def the_chu(chu: str, ra: Path) -> Path:
    """Ảnh nền màu khi không có frame/ảnh AI (chữ do phụ đề lo)."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"gradients=s={W}x{H}:c0=0x101828:c1=0x1d3a6b:x0=0:y0=0:x1={W}:y1={H}",
                    "-frames:v", "1", str(ra)], check=True)
    return ra


def tieng_vut(ra: Path) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink:a=0.6", "-af",
                    "highpass=f=500,lowpass=f=6000,afade=t=in:d=0.3:curve=exp,afade=t=out:st=0.3:d=0.2",
                    str(ra)], check=True)
    return ra


def dung(hinh: list[Path], moc: list[dict], giong: Path, ass: Path, ra: Path, tam: Path,
         nhac: Path | None = None) -> Path:
    tam.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, (h, m) in enumerate(zip(hinh, moc)):
        dai = m["ket_thuc"] - m["bat_dau"]
        clips.append(_canh(h, dai, tam / f"canh{i:02d}.mp4", i))
    ds = tam / "canh.txt"
    ds.write_text("".join(f"file '{c.name}'\n" for c in clips))
    hinh_noi = tam / "hinh.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(ds), "-c", "copy",
                    str(hinh_noi)], check=True)
    vut = tieng_vut(tam / "vut.wav")
    vao = ["-i", str(hinh_noi), "-i", str(giong), "-i", str(vut)]
    if nhac:
        vao += ["-stream_loop", "-1", "-i", str(nhac)]
    moc_vut = [m["bat_dau"] for m in moc[1:]]
    loc = []
    for k, t in enumerate(moc_vut):
        loc.append(f"[2:a]adelay={max(0, int((t - 0.25) * 1000))}:all=1,volume=0.35[v{k}]")
    tong = moc[-1]["ket_thuc"]
    tron = ["[1:a]"] + [f"[v{k}]" for k in range(len(moc_vut))]
    if nhac:
        loc.append(f"[3:a]volume=0.13,afade=t=in:d=1,afade=t=out:st={max(0, tong - 1.5):.2f}:d=1.5,atrim=0:{tong:.2f}[bgm]")
        tron.append("[bgm]")
    loc.append(f"{''.join(tron)}amix=inputs={len(tron)}:normalize=0,alimiter=limit=0.89[a]")
    sub = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    loc.append(f"[0:v]subtitles='{sub}'[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *vao, "-filter_complex", ";".join(loc), "-map", "[v]", "-map", "[a]",
                    "-t", f"{tong:.2f}", "-c:v", "libx264", "-crf", "23", "-preset", "medium", "-c:a", "aac",
                    "-b:a", "160k", "-movflags", "+faststart", str(ra)], check=True)
    return ra
