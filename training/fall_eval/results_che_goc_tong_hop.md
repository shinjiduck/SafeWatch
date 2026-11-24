# Thử che 1 góc khung hình (GMDCSA-24, 159 clip, 4 người)

Mỗi frame được tô đen 1 góc rộng 40% x cao 40% khung hình (16% diện tích) **trước** khi đưa vào MediaPipe,
giống như có tủ / bàn / cánh cửa che. Model `urfd_cauca` (chưa từng thấy GMDCSA-24) và model cũ chấm trên
đúng các video đó; chỉ khác là có che hay không.

| Che góc | Thấy người | v2: ngã bắt được | v2: SH báo nhầm | v2: nhầm/giờ | Cũ: ngã | Cũ: SH nhầm | Cũ: nhầm/giờ |
|---|---|---|---|---|---|---|---|
| Không che | 96% | 64/78 | 31/81 | 207 | 68/78 | 35/81 | 212 |
| Trên-trái | 87% | 66/78 | 28/81 | 169 | 67/78 | 44/81 | 265 |
| Trên-phải | 92% | 67/78 | 33/81 | 198 | 69/78 | 36/81 | 212 |
| Dưới-trái | 83% | 54/78 | 38/81 | 246 | 42/78 | 34/81 | 188 |
| Dưới-phải | 92% | 62/78 | 35/81 | 222 | 50/78 | 35/81 | 212 |
| **Cả dải dưới 40%** (giường/sofa chắn trước) | 71% | **29/78** | 47/81 | 303 | 14/78 | 35/81 | 207 |

- Che góc **trên**: gần như không ảnh hưởng (chênh 1-3 ca là dao động ngẫu nhiên).
- Che góc **dưới** (nơi người ngã xuống sàn): v2 mất 2-10 ca ngã, model cũ mất 18-26 ca.
- Cách giảm thiệt hại: đặt camera cao, chéo góc, sao cho vùng sàn không bị đồ đạc che. Khi bị che một phần
  cơ thể, app nhắc người dùng bằng giọng nói (`framing.py`).

## Vì sao bỏ sót khi bị che

| Che | Bỏ sót | Trong đó: người khuất hẳn sau vật cản ngay sau cú ngã (mất dấu giữa khung hình) |
|---|---|---|
| Không che | 14 | 0 |
| Dưới-trái | 24 | 15 |
| Dưới-phải | 16 | 7 |
| Cả dải dưới | 49 | 39 (36 ở giữa khung) |

Khi người khuất hẳn, app hiện "Không có người — mất dấu giữa khung hình" nhưng **không báo động**.

## Luật "mất dấu giữa khung hình" — ĐÃ ĐƯA VÀO APP với điều kiện hông tụt >= 10%

Người mất dấu >= 1.5 s, lần cuối thấy ở giữa khung hình (không phải sát mép) và thoả điều kiện dưới -> coi như
nghi ngã, chạy đúng quy trình xác minh (không đứng thẳng lại 2 s trong 30 s -> gửi). Số ca cứu thêm / số cảnh
báo GỬI THÊM mỗi giờ sinh hoạt:

| Điều kiện | Cả dải dưới | Dưới-trái | Charades 5 giờ | CV 3 bộ |
|---|---|---|---|---|
| Model nghi (xác suất >= 0.5 trong 2 s trước) | +10 ca | +6 | +2.0/giờ | +9.2/giờ |
| Hông tụt >= 10% khung hình trong 1 s trước | +16 | +8 | +1.8/giờ | +4.6/giờ |
| Hông tụt >= 5% | +21 | +8 | +3.2/giờ | +9.2/giờ |
| Không điều kiện | +32 | +12 | +18.5/giờ | +23.1/giờ |

(v2 hiện gửi 9/giờ trên Charades, 14/giờ trên CV 3 bộ.) App dùng dòng "hông tụt >= 10%"
(`framing.VANISH_HIP_DROP`, chỉ với model v2): che dải dưới 29 -> **45/78**, Charades gửi 9 -> ~11/giờ.
Chấm lại đúng bằng hàm của app: `python -X utf8 -I vanish_rule_eval.py 30 <traces.json...>`
(kết quả: `results_vanish_rule_30s.txt`). Lưu ý: ngưỡng được xem trên chính các bộ thử này, nên
cần thử lại trên dữ liệu khác trước khi tin hẳn.

Tạo lại: `OCCLUDE=bl:0.4 python -X utf8 -I extract_pose.py <videos> <pose_che_bl>` rồi
`FALL_MODEL=urfd_cauca python -X utf8 -I train_eval.py test <pose_che_bl> <labels.csv> results_che_goc_bl`.
