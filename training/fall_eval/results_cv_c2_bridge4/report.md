# URFD + CAUCAFall (CAUCAFall chia THEO NGƯỜI) — kiểm định chéo 5 phần (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)

| Chỉ số | Model cũ (LSTM 10 frame) | Model cũ (LSTM 10 frame) — URFD | Model cũ (LSTM 10 frame) — CAUCAFall | Model mới (v2) | Model mới (v2) — URFD | Model mới (v2) — CAUCAFall |
| --- | --- | --- | --- | --- | --- | --- |
| Số ca ngã | 80 | 30 | 50 | 80 | 30 | 50 |
| Bắt được | 60 | 18 | 42 | 60 | 26 | 34 |
| Bỏ sót | 20 | 12 | 8 | 20 | 4 | 16 |
| Tỉ lệ bắt được | 0.75 | 0.60 | 0.84 | 0.75 | 0.87 | 0.68 |
| Số chuỗi sinh hoạt | 90 | 40 | 50 | 90 | 40 | 50 |
| Chuỗi sinh hoạt bị báo nhầm | 41 | 17 | 24 | 12 | 7 | 5 |
| Số lần báo nhầm (sinh hoạt) | 47 | 18 | 29 | 12 | 7 | 5 |
| Giờ video sinh hoạt | 0.23 | 0.08 | 0.14 | 0.23 | 0.08 | 0.14 |
| Báo nhầm / giờ sinh hoạt | 208.35 | 217.43 | 203.09 | 53.20 | 84.55 | 35.02 |
| Báo nhầm (tất cả chuỗi) | 80 | 18 | 62 | 13 | 7 | 6 |
| Độ trễ phát hiện, trung vị (s) | 1.52 | 1.28 | 1.73 | 0.73 | 0.82 | 0.68 |
