# URFD + CAUCAFall (CAUCAFall chia THEO NGƯỜI) — kiểm định chéo 5 phần (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)

| Chỉ số | Model cũ (LSTM 10 frame) | Model cũ (LSTM 10 frame) — URFD | Model cũ (LSTM 10 frame) — CAUCAFall | Model mới (v2) | Model mới (v2) — URFD | Model mới (v2) — CAUCAFall |
| --- | --- | --- | --- | --- | --- | --- |
| Số ca ngã | 80 | 30 | 50 | 80 | 30 | 50 |
| Bắt được | 60 | 18 | 42 | 55 | 24 | 31 |
| Bỏ sót | 20 | 12 | 8 | 25 | 6 | 19 |
| Tỉ lệ bắt được | 0.75 | 0.60 | 0.84 | 0.69 | 0.80 | 0.62 |
| Số chuỗi sinh hoạt | 90 | 40 | 50 | 90 | 40 | 50 |
| Chuỗi sinh hoạt bị báo nhầm | 44 | 17 | 27 | 6 | 3 | 3 |
| Số lần báo nhầm (sinh hoạt) | 51 | 18 | 33 | 6 | 3 | 3 |
| Giờ video sinh hoạt | 0.23 | 0.08 | 0.14 | 0.23 | 0.08 | 0.14 |
| Báo nhầm / giờ sinh hoạt | 226.09 | 217.43 | 231.11 | 26.60 | 36.24 | 21.01 |
| Báo nhầm (tất cả chuỗi) | 86 | 18 | 68 | 6 | 3 | 3 |
| Độ trễ phát hiện, trung vị (s) | 1.65 | 1.35 | 1.90 | 0.93 | 0.92 | 0.95 |
