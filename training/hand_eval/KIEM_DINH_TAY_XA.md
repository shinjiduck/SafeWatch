# Kiểm định: nhận cử chỉ tay khi đứng xa (hand_roi.py)

## Vấn đề (đo trên video quay thử của nhóm)
- Đứng quá gần: chỉ 10/123 frame thấy cả 2 cổ tay — tay thường ra ngoài khung hình.
- Đứng đúng chỗ cho phát hiện ngã (~2-3 m): bàn tay chỉ ~9% khung hình, Hands thấy tay 18-27% số frame.

## Cách làm
Hands trên cả khung không thấy tay -> cắt ô vuông quanh bàn tay theo cổ tay / ngón của Pose, phóng to 256 px,
chạy Hands trên ô; toạ độ đổi về khung gốc -> model cử chỉ dùng nguyên. Kèm: không nhắc "lùi ra xa" khi đang giơ
tay cao hơn vai.

## Tiêu chí (ghi TRƯỚC khi chạy)
Đo bằng đúng chuỗi xử lý tay của app (model 14 nhãn, ngưỡng 0.8, bỏ phiếu 5 lần, giữ báo động 2 s) trên video
sinh hoạt KHÔNG có cử chỉ cầu cứu (video quay thử + 200 clip Charades đầu danh sách):
- (a) Bật mặc định chỉ khi số lần báo SOS nhầm mỗi giờ tăng không quá 1/giờ VÀ không quá 20% so với không dùng.
- (b) Báo cáo thêm: tỉ lệ frame thấy tay tăng bao nhiêu (khi Pose thấy cổ tay).
- Chưa có video cử chỉ ở xa -> CHƯA kết luận được cử chỉ có nhận ĐÚNG ở xa không; cần nhóm quay thêm.

## Kết quả

| Video sinh hoạt (không ai ra hiệu cầu cứu) | Thấy tay khi Pose thấy cổ tay | SOS báo nhầm |
|---|---|---|
| Video quay thử (2 phút) | 19% → 34% | 6 → 11 lần |
| Charades 200 clip (1.62 giờ) | 36.4% → 43.4% | **132 → 184 / giờ** (+39%) |

**Không đạt tiêu chí (a)** → `hand_roi` để TẮT mặc định (Cấu hình → "Nhận cử chỉ khi đứng xa", thử nghiệm).

**Phát hiện quan trọng hơn:** ngay cả không có hand_roi, cử chỉ tay đã báo SOS nhầm ~132 lần / giờ sinh hoạt
(Need Ambulance 91, Need Help 72, Signal For Help 51 trên 1.62 giờ) — gấp ~15 lần báo nhầm của phát hiện ngã
(~9 / giờ trên Charades). Đây là nguồn báo nhầm lớn nhất của hệ thống.

## Bước tiếp: lọc cử chỉ SOS (tiêu chí ghi TRƯỚC khi chạy)
- Dữ liệu: Charades clip 0-199 (chọn luật) và 200-399 (chấm 1 lần, sạch). Lưu từng frame (nhãn, độ tin cậy, tay
  giơ cao hơn vai) rồi thử luật offline.
- Luật thử: tay giơ cao hơn vai · giữ cử chỉ >= 1.5 s · ngưỡng tin cậy cao hơn — và kết hợp.
- Chọn luật giảm báo nhầm nhiều nhất trên clip 0-199 mà vẫn hợp lý cho người ra hiệu thật (tay giơ, giữ vài giây).
- Đạt nếu trên clip 200-399 báo nhầm giảm >= 80% so với hiện tại. Nhận đúng cử chỉ thật phải kiểm bằng video cử
  chỉ do nhóm quay (>= 90% lần ra hiệu được nhận) trước khi đưa vào app.

## Kết quả lọc cử chỉ SOS

Dữ liệu: `sos_frames.py` lưu từng frame của 400 clip Charades; `sos_rules.py` thử luật (đúng logic tay của app).
Kiểm tra chéo: số "hiện tại" trên clip 0-199 = 132.0 / giờ, trùng với `roi_eval.py` (2 cách đo khớp nhau).

Chọn trên clip 0-199 (1.62 giờ): **giơ tay cao hơn vai + nhãn SOS giữ liên tục 2 s**, ngưỡng tin cậy giữ 0.8 (nâng
ngưỡng không giảm thêm). Một vài luật khác trên clip 0-199: chỉ giữ 2 s (không cần giơ tay) 5.6 / giờ; chỉ giơ tay
36.4 / giờ; giơ tay + giữ 1.5 s 3.7 / giờ.

**Chấm 1 lần trên clip 200-399 (1.58 giờ, chưa dùng để chọn): 209 -> 3 lần (132.0 -> 1.9 / giờ), giảm 99%** —
đạt tiêu chí (>= 80%).

Đã đưa vào app: Cấu hình → "Chống báo SOS nhầm" (`sos_filter`), trang Trực tiếp hiện "Giữ tay thêm x s để gửi".
Để TẮT mặc định cho tới khi kiểm bằng video cử chỉ thật của nhóm (>= 90% lần ra hiệu được nhận). Cần bật phát hiện
ngã (Pose) để biết vai ở đâu.
