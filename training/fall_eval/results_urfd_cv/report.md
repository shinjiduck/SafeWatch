# URFD — kiểm định chéo 5 phần theo chuỗi quay (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)

| Chỉ số | Model cũ (LSTM 10 frame) | Model mới (v2) |
| --- | --- | --- |
| Số ca ngã | 30 | 30 |
| Bắt được | 15 | 23 |
| Bỏ sót | 15 | 7 |
| Tỉ lệ bắt được | 0.50 | 0.77 |
| Số chuỗi sinh hoạt | 40 | 40 |
| Chuỗi sinh hoạt bị báo nhầm | 17 | 2 |
| Số lần báo nhầm (sinh hoạt) | 18 | 2 |
| Giờ video sinh hoạt | 0.08 | 0.08 |
| Báo nhầm / giờ sinh hoạt | 217.43 | 24.16 |
| Báo nhầm (tất cả chuỗi) | 18 | 2 |
| Độ trễ phát hiện, trung vị (s) | 1.30 | 0.77 |
