# URFD + CAUCAFall (CAUCAFall chia THEO NGƯỜI) — kiểm định chéo 5 phần (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)

| Chỉ số | Model cũ (LSTM 10 frame) | Model cũ (LSTM 10 frame) — URFD | Model cũ (LSTM 10 frame) — CAUCAFall | Model mới (v2) | Model mới (v2) — URFD | Model mới (v2) — CAUCAFall |
| --- | --- | --- | --- | --- | --- | --- |
| Số ca ngã | 80 | 30 | 50 | 80 | 30 | 50 |
| Bắt được | 56 | 15 | 41 | 63 | 28 | 35 |
| Bỏ sót | 24 | 15 | 9 | 17 | 2 | 15 |
| Tỉ lệ bắt được | 0.70 | 0.50 | 0.82 | 0.79 | 0.93 | 0.70 |
| Số chuỗi sinh hoạt | 90 | 40 | 50 | 90 | 40 | 50 |
| Chuỗi sinh hoạt bị báo nhầm | 40 | 17 | 23 | 6 | 6 | 0 |
| Số lần báo nhầm (sinh hoạt) | 43 | 18 | 25 | 6 | 6 | 0 |
| Giờ video sinh hoạt | 0.23 | 0.08 | 0.14 | 0.23 | 0.08 | 0.14 |
| Báo nhầm / giờ sinh hoạt | 190.62 | 217.43 | 175.08 | 26.60 | 72.48 | 0.00 |
| Báo nhầm (tất cả chuỗi) | 75 | 18 | 57 | 6 | 6 | 0 |
| Độ trễ phát hiện, trung vị (s) | 1.75 | 1.30 | 1.90 | 0.85 | 0.77 | 0.85 |
