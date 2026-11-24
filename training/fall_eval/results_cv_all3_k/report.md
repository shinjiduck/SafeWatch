# URFD + CAUCAFall (CAUCAFall chia THEO NGƯỜI) + GMDCSA-24 (chia THEO NGƯỜI) — kiểm định chéo 5 phần (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)

| Chỉ số | Model cũ (LSTM 10 frame) | Model cũ (LSTM 10 frame) — URFD | Model cũ (LSTM 10 frame) — CAUCAFall | Model cũ (LSTM 10 frame) — GMDCSA-24 | Model mới (v2) | Model mới (v2) — URFD | Model mới (v2) — CAUCAFall | Model mới (v2) — GMDCSA-24 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Số ca ngã | 158 | 30 | 50 | 78 | 158 | 30 | 50 | 78 |
| Bắt được | 124 | 15 | 41 | 68 | 122 | 27 | 27 | 68 |
| Bỏ sót | 34 | 15 | 9 | 10 | 36 | 3 | 23 | 10 |
| Tỉ lệ bắt được | 0.78 | 0.50 | 0.82 | 0.87 | 0.77 | 0.90 | 0.54 | 0.87 |
| Số chuỗi sinh hoạt | 171 | 40 | 50 | 81 | 171 | 40 | 50 | 81 |
| Chuỗi sinh hoạt bị báo nhầm | 75 | 17 | 23 | 35 | 11 | 3 | 3 | 5 |
| Số lần báo nhầm (sinh hoạt) | 87 | 18 | 25 | 44 | 11 | 3 | 3 | 5 |
| Giờ video sinh hoạt | 0.43 | 0.08 | 0.14 | 0.21 | 0.43 | 0.08 | 0.14 | 0.21 |
| Báo nhầm / giờ sinh hoạt | 200.84 | 217.43 | 175.08 | 211.95 | 25.39 | 36.24 | 21.01 | 24.08 |
| Báo nhầm (tất cả chuỗi) | 139 | 18 | 57 | 64 | 11 | 3 | 3 | 5 |
| Độ trễ phát hiện, trung vị (s) | 1.56 | 1.30 | 1.90 | 1.48 | 0.79 | 0.90 | 0.90 | 0.68 |
