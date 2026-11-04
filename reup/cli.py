"""reup — tải video mẫu, phân tích, viết lại kịch bản bằng AI, lồng giọng RevidAPI, dựng video mới."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import api, dung, giong, kich_ban, phan_tich
from .an_toan import LoiAnToan, che, kiem_url_media, ten_an_toan, trong_thu_muc

CREDIT_1K_KY_TU = 15  # giọng đọc, theo bảng giá công khai
CREDIT_ANH = 18
CREDIT_VIDEO = 23


def _in(*a):
    print(che(" ".join(str(x) for x in a)))


def _chuan_bi(args) -> tuple[Path, Path]:
    goc = Path(args.thu_muc).expanduser().resolve()
    goc.mkdir(parents=True, exist_ok=True)
    return goc, trong_thu_muc(goc, goc / ten_an_toan(args.ten, "du-an"))


def lay_mau(nguon: str, da: Path) -> Path:
    da.mkdir(parents=True, exist_ok=True)
    p = Path(nguon).expanduser()
    if p.is_file():
        dich = da / "mau.mp4"
        shutil.copyfile(p, dich)
        return dich
    kiem_url_media(nguon)
    dich = da / "mau.mp4"
    _in("Đang tải video mẫu qua RevidAPI…")
    info = api.tai_video(nguon, dich)
    (da / "nguon.json").write_text(json.dumps({"link": nguon, **info}, ensure_ascii=False, indent=1))
    return dich


def chay(args) -> None:
    _, da = _chuan_bi(args)
    mau = lay_mau(args.nguon, da)
    _in("Phân tích (trên máy, 0 credit)…")
    nhip = phan_tich.phan_tich(mau, da / "phan-tich", args.whisper)
    _in(json.dumps(nhip, ensure_ascii=False))
    loi = (da / "phan-tich" / "loi.txt").read_text(encoding="utf-8")
    _in(f"Viết kịch bản bằng {args.model}…")
    kb = kich_ban.viet(nhip, loi, args.yeu_cau or "", args.model, args.giay)
    (da / "kich-ban.json").write_text(json.dumps(kb, ensure_ascii=False, indent=1), encoding="utf-8")
    n = kich_ban.so_ky_tu(kb)
    so_ai = len(_canh_can_ai(da, kb, args.hinh))
    uoc = round(n / 1000 * CREDIT_1K_KY_TU + so_ai * (CREDIT_ANH + (CREDIT_VIDEO if args.video_ai else 0)))
    _in(f"Kịch bản: {len(kb['doan'])} đoạn, {n} ký tự; {so_ai} cảnh có người sẽ vẽ lại bằng AI"
        f"{' + video AI' if args.video_ai else ''} → ước tính ~{uoc} credit "
        f"(chưa gồm lượt tải và viết kịch bản đã chạy). Xem/sửa: {da / 'kich-ban.json'}")
    if not args.dong_y:
        _in("Dừng ở cổng duyệt. Sửa kịch bản nếu cần rồi chạy: reup dung", da, "--dong-y")
        return
    _dung(da, args)


def _canh_goc(da: Path, kb: dict) -> list[int]:
    """Đoạn kịch bản i ứng với cảnh gốc nào (chia theo tỉ lệ)."""
    n = len(sorted((da / "phan-tich" / "frames").glob("c*.jpg"))) or 1
    return [min(n - 1, i * n // len(kb["doan"])) for i in range(len(kb["doan"]))]


def _canh_can_ai(da: Path, kb: dict, che_do: str) -> list[int]:
    if che_do == "ai":
        return list(range(len(kb["doan"])))
    if che_do != "goc":
        return []
    nhip = json.loads((da / "phan-tich" / "nhip.json").read_text(encoding="utf-8"))
    nguoi = set(nhip.get("canh_co_nguoi") or [])
    return [i for i, j in enumerate(_canh_goc(da, kb)) if j in nguoi]


def _dung(da: Path, args) -> None:
    kb = json.loads((da / "kich-ban.json").read_text(encoding="utf-8"))
    kb = kich_ban.lam_sach(kb)
    moc = giong.long_tieng(kb, args.giong, da / "giong", args.toc_do)
    frames = sorted((da / "phan-tich" / "frames").glob("c*.jpg"))
    goc = _canh_goc(da, kb)
    can_ai = set(_canh_can_ai(da, kb, args.hinh))
    hinh_dir = da / "hinh"
    hinh_dir.mkdir(exist_ok=True)
    hinh = []
    for i, d in enumerate(kb["doan"]):
        p = hinh_dir / f"h{i:02d}.png"
        v = hinh_dir / f"v{i:02d}.mp4"
        if i in can_ai:
            if v.exists():
                hinh.append(v); continue
            if not p.exists():
                if args.hinh == "goc" and frames:
                    # Giữ phong cách gốc: AI tả frame gốc rồi vẽ cảnh mới cùng bố cục, người khác (không chép người thật)
                    mo_ta = api.mo_ta_frame(args.model, frames[goc[i]])
                    prompt = f"{mo_ta}. Scene content: {d.get('mo_ta_hinh', '')}. A different, fictional person. No text."
                else:
                    prompt = d.get("mo_ta_hinh") or d["loi"]
                _, url = api.tao_anh(args.model_anh, prompt + ", vertical 9:16", p)
                (hinh_dir / f"h{i:02d}.url").write_text(url)
            if args.video_ai:
                url = (hinh_dir / f"h{i:02d}.url").read_text().strip()
                dai = moc[i]["ket_thuc"] - moc[i]["bat_dau"]
                api.tao_video(args.model_video, "subtle natural motion, same style, " + (d.get("mo_ta_hinh") or ""),
                              url, v, duration="8s" if dai > 6 else "5s")
                hinh.append(v); continue
            hinh.append(p)
        elif args.hinh in ("goc", "frame") and frames:
            hinh.append(frames[goc[i]])
        else:
            hinh.append(dung.the_chu(d.get("chu_tren_hinh", ""), p))
    ass = dung.phu_de(kb, moc, da / "phu-de.ass")
    nhac = Path(args.nhac).expanduser() if args.nhac else None
    if nhac and not nhac.is_file():
        raise LoiAnToan("Không thấy file nhạc")
    ra = da / f"{ten_an_toan(kb.get('tieu_de') or 'video')}.mp4"
    dung.dung(hinh, moc, da / "giong" / "giong.wav", ass, ra, da / "tam", nhac)
    _in("Xong:", ra, f"({moc[-1]['ket_thuc']:.1f}s)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="reup", description=__doc__)
    ap.add_argument("--thu-muc", default="./reup-ra", help="nơi chứa dự án")
    sub = ap.add_subparsers(dest="lenh", required=True)

    c = sub.add_parser("chay", help="tải → phân tích → kịch bản → (duyệt) → dựng")
    c.add_argument("nguon", help="link TikTok/Douyin/FB/IG/YouTube hoặc file mp4")
    c.add_argument("--ten", default="du-an")
    c.add_argument("--yeu-cau", help="chủ đề/nội dung mới; bỏ trống = viết lại tương tự")
    c.add_argument("--giay", type=int, default=60)
    c.add_argument("--model", default="gpt-5.5", help="model viết kịch bản")
    c.add_argument("--whisper", default="small")
    c.add_argument("--giong", type=int, default=9055, help="voice_id (reup giong-list)")
    c.add_argument("--toc-do", type=float, default=1.0)
    c.add_argument("--hinh", choices=["goc", "frame", "ai", "nen"], default="goc",
                   help="goc = theo phong cách video gốc: cảnh có người vẽ lại bằng AI, cảnh khác giữ frame (mặc định)")
    c.add_argument("--video-ai", action="store_true", help="cảnh có người: biến ảnh AI thành video AI")
    c.add_argument("--model-anh", default="gpt-image-2")
    c.add_argument("--model-video", default="veo3.1-lite")
    c.add_argument("--nhac", help="file nhạc nền bạn có quyền dùng")
    c.add_argument("--dong-y", action="store_true", help="bỏ qua cổng duyệt, tiêu credit luôn")

    d = sub.add_parser("dung", help="dựng từ kich-ban.json đã duyệt")
    d.add_argument("du_an", help="thư mục dự án")
    for a, k in [("--giong", dict(type=int, default=9055)), ("--toc-do", dict(type=float, default=1.0)),
                 ("--hinh", dict(choices=["goc", "frame", "ai", "nen"], default="goc")),
                 ("--model-anh", dict(default="gpt-image-2")), ("--model-video", dict(default="veo3.1-lite")),
                 ("--model", dict(default="gpt-5.5")), ("--nhac", {})]:
        d.add_argument(a, **k)
    d.add_argument("--video-ai", action="store_true")
    d.add_argument("--dong-y", action="store_true", required=True)

    p = sub.add_parser("phan-tich", help="chỉ phân tích video (0 credit)")
    p.add_argument("nguon")
    p.add_argument("--ten", default="du-an")
    p.add_argument("--whisper", default="small")

    sub.add_parser("giong-list", help="danh sách giọng")
    sub.add_parser("so-du", help="xem số dư credit")

    args = ap.parse_args(argv)
    try:
        if args.lenh == "chay":
            chay(args)
        elif args.lenh == "dung":
            goc = Path(args.thu_muc).expanduser().resolve()
            _dung(trong_thu_muc(goc, Path(args.du_an).expanduser()), args)
        elif args.lenh == "phan-tich":
            _, da = _chuan_bi(args)
            _in(json.dumps(phan_tich.phan_tich(lay_mau(args.nguon, da), da / "phan-tich", args.whisper),
                           ensure_ascii=False, indent=1))
        elif args.lenh == "giong-list":
            _in(json.dumps(api.danh_sach_giong(), ensure_ascii=False, indent=1)[:20000])
        elif args.lenh == "so-du":
            kq = api.so_du()
            _in(json.dumps({k: kq.get(k) for k in ("credits", "plan", "email") if isinstance(kq, dict)},
                           ensure_ascii=False))
    except (LoiAnToan, api.LoiAPI, ValueError) as e:
        _in("Lỗi:", e)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
