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
(điền sau khi chạy)
