# revidapi-reup-video

Đưa một video mẫu (link TikTok, Douyin, Facebook, Instagram, YouTube hoặc file mp4). Công cụ sẽ:

1. **Tải** video qua API tải của [RevidAPI](https://revidapi.com).
2. **Cắt cảnh và chụp frame** bằng ffmpeg, kèm ảnh `tong-quan.jpg` để xem nhanh bố cục.
3. **Bóc lời** bằng Whisper (faster-whisper) chạy ngay trên máy, có mốc thời gian từng từ.
4. **Đo nhịp**: số cảnh, số giây mỗi cảnh, số từ mỗi giây, câu hook 3 giây đầu.
5. **AI viết kịch bản mới**: giữ cấu trúc và nhịp của mẫu, nhưng là nội dung mới, hoặc theo đúng yêu cầu của bạn (`--yeu-cau`).
6. **Lồng giọng** bằng thư viện giọng RevidAPI. Mỗi đoạn đọc riêng, khoảng lặng được rút cho liền mạch, không chèn im lặng nhân tạo.
7. **Dựng video dọc 1080x1920**: Ken Burns, phụ đề theo cụm, chữ lớn trên hình, tiếng vút khi chuyển cảnh, nhạc nền (tuỳ chọn).

Mục đích là học **công thức** của video mẫu, không chép hình, nhạc hay câu chữ của người khác. Hãy tôn trọng bản quyền nội dung gốc.

## Cài đặt

Cần Python 3.10+ và ffmpeg (`brew install ffmpeg` / `apt install ffmpeg` / `winget install ffmpeg`).

```bash
git clone https://github.com/Revidapi-com/revidapi-reup-video
cd revidapi-reup-video
pip install -e .
```

## Khoá API

Lấy khoá ở https://revidapi.com/dashboard, rồi chọn **một** trong hai cách:

```bash
# Cách 1: file riêng, chỉ bạn đọc được
mkdir -p ~/.revidapi && printf '%s' 'sk_...' > ~/.revidapi/khoa && chmod 600 ~/.revidapi/khoa
# Cách 2: biến môi trường cho phiên hiện tại
export REVIDAPI_KEY=sk_...
```

Công cụ **không** nhận khoá qua tham số dòng lệnh, vì như thế khoá sẽ lộ trong `ps` và lịch sử shell.

## Dùng

```bash
reup so-du                 # xem credit
reup giong-list            # danh sách giọng (voice_id)

# Từ đầu đến cổng duyệt: tải, phân tích, viết kịch bản, báo ước tính credit rồi dừng
reup chay "https://www.tiktok.com/@.../video/..." --ten mau1 \
  --yeu-cau "Giới thiệu quán cà phê sách ở Đà Lạt" --giay 45

# Xem/sửa reup-ra/mau1/kich-ban.json, rồi dựng
reup dung reup-ra/mau1 --dong-y --giong 9055 --hinh frame --nhac ~/nhac-cua-toi.mp3

# Chỉ phân tích, 0 credit
reup phan-tich mau.mp4 --ten mau2
```

Chọn hình với `--hinh`:

| Giá trị | Hình mỗi cảnh | Chi phí |
|---|---|---|
| `frame` | frame cảnh tương ứng của video mẫu (nền mờ + phóng chậm) | 0 |
| `ai` | ảnh AI vẽ theo `mo_ta_hinh` của từng đoạn | theo bảng giá ảnh |
| `nen` | nền màu, chữ do phụ đề hiển thị | 0 |

Nếu video mẫu đã có sẵn chữ trên hình, nên dùng `ai` hoặc `nen` để chữ không đè lên nhau.

Kết quả nằm trong `reup-ra/<ten>/`:

- `phan-tich/` (nhip.json, canh.json, loi.json, frames/, tong-quan.jpg)
- `kich-ban.json`
- `giong/`
- `phu-de.ass`
- file `.mp4` cuối

**Chi phí.** Phân tích và dựng chạy trên máy nên không tốn credit. Chỉ các bước sau tốn credit:

- tải video
- viết kịch bản (chat)
- giọng đọc, khoảng 15 credit cho 1.000 ký tự
- ảnh AI, nếu chọn `--hinh ai`

Lệnh `chay` luôn dừng lại báo ước tính trước khi đọc giọng, trừ khi bạn thêm `--dong-y`.

## Bảo mật

- Khoá chỉ đọc từ `REVIDAPI_KEY` hoặc `~/.revidapi/khoa`. Nếu file khoá đang mở quyền cho người khác, công cụ tự siết lại về `600`.
- Khoá **chỉ** được gửi tới `https://revidapi.com/v1`. Gọi API thì không đi theo chuyển hướng. Tải file kết quả thì **không** kèm khoá, và nếu bị chuyển hướng thì header khoá bị bỏ.
- Mọi thông báo lỗi và log đều được che khoá (`sk_***`).
- Link tải phải là `https`, không chứa tài khoản/mật khẩu, không trỏ vào IP nội bộ, loopback hay metadata cloud (chống SSRF). Mỗi lần chuyển hướng cũng được kiểm lại. File tải về có trần dung lượng (video 1GB) và được ghi ra file tạm trước.
- Tên file và thư mục lấy từ dữ liệu ngoài đều được làm sạch, không thoát ra khỏi thư mục làm việc.
- ffmpeg được gọi bằng danh sách tham số, không qua shell. Phụ đề ASS được lọc ký tự `{ } \`, nên nội dung AI không chèn được mã định dạng.
- Lời của video mẫu được coi là **dữ liệu không tin cậy**: nó được bọc trong thẻ riêng, và AI được dặn không làm theo lệnh nằm bên trong. Kịch bản AI trả về (hoặc bạn sửa tay) được kiểm lại kiểu và độ dài trước khi tiêu credit.
- Repo không kèm nhạc. Tiếng vút được tạo bằng ffmpeg khi chạy. Nhạc nền do bạn tự đưa vào và phải là nhạc bạn có quyền dùng.

Gặp lỗ hổng bảo mật, xin báo riêng qua https://revidapi.com thay vì mở issue công khai.

## Kiểm thử

```bash
pip install pytest && pytest -q
```

## Giấy phép

MIT
