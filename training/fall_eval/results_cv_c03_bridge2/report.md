# URFD + CAUCAFall (CAUCAFall chia THEO NGƯỜI) — kiểm định chéo 5 phần (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)

| Chỉ số | Model cũ (LSTM 10 frame) | Model cũ (LSTM 10 frame) — URFD | Model cũ (LSTM 10 frame) — CAUCAFall | Model mới (v2) | Model mới (v2) — URFD | Model mới (v2) — CAUCAFall |
| --- | --- | --- | --- | --- | --- | --- |
| Số ca ngã | 80 | 30 | 50 | 80 | 30 | 50 |
| Bắt được | 60 | 18 | 42 | 57 | 24 | 33 |
| Bỏ sót | 20 | 12 | 8 | 23 | 6 | 17 |
| Tỉ lệ bắt được | 0.75 | 0.60 | 0.84 | 0.71 | 0.80 | 0.66 |
| Số chuỗi sinh hoạt | 90 | 40 | 50 | 90 | 40 | 50 |
| Chuỗi sinh hoạt bị báo nhầm | 44 | 17 | 27 | 5 | 4 | 1 |
| Số lần báo nhầm (sinh hoạt) | 51 | 18 | 33 | 5 | 4 | 1 |
| Giờ video sinh hoạt | 0.23 | 0.08 | 0.14 | 0.23 | 0.08 | 0.14 |
| Báo nhầm / giờ sinh hoạt | 226.09 | 217.43 | 231.11 | 22.17 | 48.32 | 7.00 |
| Báo nhầm (tất cả chuỗi) | 86 | 18 | 68 | 5 | 4 | 1 |
| Độ trễ phát hiện, trung vị (s) | 1.65 | 1.35 | 1.90 | 0.83 | 0.78 | 0.85 |
