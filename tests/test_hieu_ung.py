import json
import subprocess
import sys
from pathlib import Path

import pytest

from reup import hieu_ung

MOC = [{"bat_dau": 0, "ket_thuc": 3}, {"bat_dau": 3, "ket_thuc": 4}, {"bat_dau": 4, "ket_thuc": 9}]


def test_tu_dong_chi_canh_nguoi_du_dai():
    kh = hieu_ung.ke_hoach_tu_dong(MOC, [0, 1, 2])
    assert [e["fx"] for e in kh["effects"]] == ["lean-in", "slow-push"]  # cảnh 1 chỉ 1s: bỏ
    assert kh["effects"][0]["start"] == pytest.approx(0.1) and kh["effects"][1]["end"] <= 8.9


def _kh(tmp_path, d):
    p = tmp_path / "k.json"
    p.write_text(json.dumps(d))
    return p


@pytest.mark.parametrize("e", [{"fx": "../x", "start": 0, "end": 1}, {"fx": "lean-in", "start": 2, "end": 1},
                               {"fx": "lean-in", "start": 0, "end": 99}, {"fx": "lean-in", "start": -1, "end": 1}])
def test_ke_hoach_sai_bi_chan(tmp_path, e):
    with pytest.raises(ValueError):
        hieu_ung.doc_ke_hoach(_kh(tmp_path, {"effects": [e]}), 9)


def test_ke_hoach_bo_images(tmp_path):
    kh = hieu_ung.doc_ke_hoach(_kh(tmp_path, {"images": ["/etc/passwd"],
                                              "effects": [{"fx": "spotlight", "start": 1, "end": 2}]}), 9)
    assert "images" not in kh and kh["effects"][0]["fx"] == "spotlight"


def test_ffprobe_thay(tmp_path):
    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        pytest.skip("không có ffmpeg")
    v = tmp_path / "v.mp4"
    subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=d=2:r=25:s=64x64", str(v)], check=True)
    o = subprocess.run([sys.executable, "-I", str(Path(hieu_ung.__file__).with_name("ffprobe_thay.py")),
                        "-v", "error", "-of", "json", str(v)], capture_output=True, text=True)
    d = json.loads(o.stdout)
    assert d["streams"][0]["r_frame_rate"] in ("25/1", "25") and abs(float(d["format"]["duration"]) - 2) < 0.1
