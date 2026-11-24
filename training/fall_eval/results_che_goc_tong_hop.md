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

- Che góc **trên**: gần như không ảnh hưởng (chênh 1-3 ca là dao động ngẫu nhiên).
- Che góc **dưới** (nơi người ngã xuống sàn): v2 mất 2-10 ca ngã, model cũ mất 18-26 ca.
- Cách giảm thiệt hại: đặt camera cao, chéo góc, sao cho vùng sàn không bị đồ đạc che. Khi bị che một phần
  cơ thể, app nhắc người dùng bằng giọng nói (`framing.py`).

Tạo lại: `OCCLUDE=bl:0.4 python -X utf8 -I extract_pose.py <videos> <pose_che_bl>` rồi
`FALL_MODEL=urfd_cauca python -X utf8 -I train_eval.py test <pose_che_bl> <labels.csv> results_che_goc_bl`.
