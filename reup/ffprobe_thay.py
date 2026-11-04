"""Thay ffprobe cho máy chỉ có ffmpeg (vd. ffmpeg từ imageio-ffmpeg).

Chỉ hỗ trợ đúng lệnh bộ hiệu ứng dùng: -show_entries stream=r_frame_rate:format=duration -of json.
"""
import json
import re
import shutil
import subprocess
import sys



def _ffmpeg() -> str:
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


tep = sys.argv[-1]
o = subprocess.run([_ffmpeg(), "-hide_banner", "-i", tep], capture_output=True, text=True).stderr
d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", o)
f = re.search(r"Video:.*?(\d+(?:\.\d+)?) fps", o)
if not d or not f:
    sys.stderr.write("khong doc duoc video\n")
    sys.exit(1)
fps = float(f.group(1))
ty = {23.98: "24000/1001", 29.97: "30000/1001", 59.94: "60000/1001"}.get(round(fps, 2), f"{fps:g}/1")
print(json.dumps({"streams": [{"r_frame_rate": ty}],
                  "format": {"duration": str(int(d[1]) * 3600 + int(d[2]) * 60 + float(d[3]))}}))
