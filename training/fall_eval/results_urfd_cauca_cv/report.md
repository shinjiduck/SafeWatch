# URFD + CAUCAFall (CAUCAFall chia THEO NGƯỜI) — kiểm định chéo 5 phần (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)

| Chỉ số | Model cũ (LSTM 10 frame) | Model cũ (LSTM 10 frame) — URFD | Model cũ (LSTM 10 frame) — CAUCAFall | Model mới (v2) | Model mới (v2) — URFD | Model mới (v2) — CAUCAFall |
| --- | --- | --- | --- | --- | --- | --- |
| Số ca ngã | 80 | 30 | 50 | 80 | 30 | 50 |
| Bắt được | 56 | 15 | 41 | 58 | 28 | 30 |
| Bỏ sót | 24 | 15 | 9 | 22 | 2 | 20 |
| Tỉ lệ bắt được | 0.70 | 0.50 | 0.82 | 0.72 | 0.93 | 0.60 |
| Số chuỗi sinh hoạt | 90 | 40 | 50 | 90 | 40 | 50 |
| Chuỗi sinh hoạt bị báo nhầm | 40 | 17 | 23 | 5 | 4 | 1 |
| Số lần báo nhầm (sinh hoạt) | 43 | 18 | 25 | 5 | 4 | 1 |
| Giờ video sinh hoạt | 0.23 | 0.08 | 0.14 | 0.23 | 0.08 | 0.14 |
| Báo nhầm / giờ sinh hoạt | 190.62 | 217.43 | 175.08 | 22.17 | 48.32 | 7.00 |
| Báo nhầm (tất cả chuỗi) | 75 | 18 | 57 | 5 | 4 | 1 |
| Độ trễ phát hiện, trung vị (s) | 1.75 | 1.30 | 1.90 | 0.90 | 0.83 | 0.93 |
