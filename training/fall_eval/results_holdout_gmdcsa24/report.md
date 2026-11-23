# Để riêng từng người (người chấm KHÔNG có trong dữ liệu train, không dùng để chọn ngưỡng)

| Chỉ số | Model cũ (LSTM 10 frame) | Model mới (v2) |
| --- | --- | --- |
| Số ca ngã | 78 | 78 |
| Bắt được | 68 | 69 |
| Bỏ sót | 10 | 9 |
| Tỉ lệ bắt được | 0.87 | 0.88 |
| Số chuỗi sinh hoạt | 81 | 81 |
| Chuỗi sinh hoạt bị báo nhầm | 35 | 17 |
| Số lần báo nhầm (sinh hoạt) | 44 | 19 |
| Giờ video sinh hoạt | 0.21 | 0.21 |
| Báo nhầm / giờ sinh hoạt | 211.95 | 91.52 |
| Báo nhầm (tất cả chuỗi) | 64 | 19 |
| Độ trễ phát hiện, trung vị (s) | 1.48 | 0.58 |
