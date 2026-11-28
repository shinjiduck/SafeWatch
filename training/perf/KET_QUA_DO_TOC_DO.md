# Đo tốc độ xử lý khung hình (28/11/2026)

Script: `do_toc_do.py` — chạy đúng `DetectionVideoProcessor` của app, MediaPipe + model thật, video webcam nhóm tự quay
(`adl_quay_thu`, có người trong khung), giả lập camera 30 khung/giây, hàng đợi 1 khung (khung đến lúc đang bận thì bỏ).
Máy: laptop Intel Core i5-11300H, cắm sạc, chế độ High performance. "1 lõi" = chỉ cho tiến trình dùng 1 lõi CPU (gần
với máy chủ dùng chung trên Cloud, nhưng lõi laptop này vẫn nhanh hơn lõi máy chủ Cloud thường gặp). Số thô:
`ket_qua_do_toc_do.jsonl`.

## Theo độ phân giải (cấu hình mặc định)

| Độ phân giải | Khung có AI: trung vị / 90% / chậm nhất (ms) | Khung không AI (ms) | Khung hiển thị / giây | Nhịp AI (Hz) |
|---|---|---|---|---|
| 320×240 | 31,2 / 42,5 / 71,1 | 0,08 | 30,4 | 10,1 |
| 480×360 | 33,7 / 48,5 / 110,9 | 0,18 | 30,2 | 10,1 |
| **640×480 (mặc định)** | **34,3 / 49,7 / 82,5** | 0,30 | **30,3** | **10,1** |
| 1280×720 | 41,3 / 54,5 / 145,0 | 2,44 | 29,6 | 9,9 |

## Theo tính năng (640×480)

| Cấu hình | Khung có AI: trung vị / 90% (ms) | Khung / giây | Nhịp AI (Hz) |
|---|---|---|---|
| Chỉ phát hiện ngã | 20,3 / 28,4 | 30,7 | 10,2 |
| **Mặc định** (ngã + cử chỉ) | **34,3 / 49,7** | **30,3** | **10,1** |
| + bộ lọc SOS | 32,5 / 46,0 | 30,3 | 10,1 |
| + Signal for Help | 31,4 / 41,8 | 30,4 | 10,1 |
| + nhận tay ở xa | 39,6 / 54,3 | 30,1 | 10,0 |
| + nhiều người | 48,1 / 70,4 | 29,1 | 9,7 |
| Đầy đủ (bật hết) | 54,8 / 71,6 | 28,3 | 9,4 |

## Từng bước trong 1 khung có AI (640×480, mặc định, ms)

| Tìm khung xương (MediaPipe Pose) | Tìm bàn tay (MediaPipe Hands) | Mô hình ngã | Mô hình cử chỉ |
|---|---|---|---|
| 19,8 | 15,1 | 0,8 | 0,2 |

MediaPipe chiếm ~95% thời gian; hai mô hình của SafeWatch gần như không tốn gì. Nhiều người: tìm nhiều người 32–35 ms.

## Máy yếu (1 lõi CPU)

| Cấu hình | Khung có AI: trung vị / 90% / chậm nhất (ms) | Khung / giây | Nhịp AI (Hz) | CPU |
|---|---|---|---|---|
| 480×360 mặc định | 33,9 / 43,9 / 69,6 | 30,4 | 10,1 | 83% |
| 640×480 mặc định | 36,7 / 51,4 / 87,0 | 30,2 | 10,1 | 92% |
| 640×480 đầy đủ | 60,6 / 98,4 / 204,0 | 25,3 | 8,4 | 89% |

1 lõi vẫn giữ được 10 Hz ở cấu hình mặc định nhưng CPU gần chạm trần (92%); bật hết tính năng thì tụt còn 8,4 Hz.

## Phần đăng nhập / mã hoá mới thêm

| Việc | Thời gian |
|---|---|
| Băm / kiểm mật khẩu (scrypt, chủ ý chậm để chống dò mật khẩu) | ~130 ms, chỉ lúc đăng nhập |
| Đọc tài khoản mỗi lần chạy trang | 0,5 ms |
| Kiểm tra đồng ý + tạm dừng (trang Trực tiếp, 1 lần / giây) | 0,9 ms |
| Mã hoá / giải mã 1 trường | 0,015 / 0,021 ms |

Không ảnh hưởng tới tốc độ khung hình.

RAM: 0,6–1,3 GB tuỳ cấu hình (đo cuối mỗi lần chạy; TensorFlow + MediaPipe chiếm phần lớn).
