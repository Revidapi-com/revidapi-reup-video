import shutil, subprocess
import pytest
from reup import phan_tich

ff = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")

@ff
def test_tong_quan_va_khong_nguoi(tmp_path):
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=d=5:s=320x568:r=10", str(v)], check=True)
    ra = phan_tich.tong_quan(v, tmp_path / "t.jpg")
    assert ra.stat().st_size > 1000
    anh = tmp_path / "a.jpg"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(v), "-frames:v", "1", str(anh)], check=True)
    assert phan_tich.co_nguoi(anh) is False

def test_co_nguoi_file_hong(tmp_path):
    p = tmp_path / "x.jpg"; p.write_bytes(b"khong phai anh")
    assert phan_tich.co_nguoi(p) is False
