# Chạy video theo kịch bản trên cấu hình trình diễn (28/11/2026)

Thay cho buổi thử với người thật (chưa làm): đưa từng video có sẵn qua **đúng code app** với cấu hình mặc định
(`detection_engine.SETTINGS_DEFAULTS`, model `all3`), rồi tách kết quả theo kịch bản. Đây là kiểm định trên
**dữ liệu độc lập**, không phải **người thử độc lập**.

## Cách chạy

```bash
# Ngã: phát lại khung xương 10 Hz, giữ khung cuối thêm 40 s để chấm trọn 30 s xác minh sau ngã
cd training/fall_eval
REPLAY_GIU_CUOI=40 python -X utf8 -I replay_eval.py replay single all3 kiem_dinh_nhieu_nguoi/lists/le2i.csv \
    D:/DeTaiAI/datasets/replay10hz/le2i_single results_kich_ban/le2i_giu40.json

# Cả ngã + cử chỉ tay, từ điểm ảnh (MediaPipe thật), 1 video
cd training/hand_eval
python -X utf8 -I video_cau_hinh.py <video> <ra.json> [cat=x0,y0,x1,y1] [sos_filter=1]
```

Kịch bản lấy từ nhãn hoạt động của OmniFall cho Le2i (`fall`, `fallen`, `stand_up`, `sit_down`...).

## Kết quả

| Kịch bản | Video | Mong đợi | Kết quả |
|---|---|---|---|
| Ngã rồi nằm yên (giữ tư thế cuối 40 s) | Le2i, 122 ca | Cảnh báo sau ~30 s | Bắt được 115; **gửi cảnh báo 94** (trung vị 30,8 s, chậm nhất 32,7 s sau cú ngã). Phát hiện cú ngã: trung vị 0,76 s, 90% trong 1,18 s |
| Ngã rồi tự đứng dậy | Le2i, 7 ca có nhãn `stand_up` | Không cảnh báo | 6 bắt được; 4 không gửi (đúng), 2 vẫn gửi (`Home_01_video_3`, `Office_video_2`: clip hết lúc vừa đứng lên) |
| Ngồi xuống | Le2i, 35 clip sinh hoạt có `sit_down` | Không cảnh báo | 5 clip bị nghi ngã, **2 clip gửi cảnh báo** |
| Đi lại, đứng | Le2i, 25 clip sinh hoạt khác | Không cảnh báo | 5 clip bị nghi ngã, **0 clip gửi cảnh báo** |
| Sinh hoạt tại nhà | Charades, 629 clip, 5,03 giờ | Không cảnh báo | Nghi ngã 28,4 / giờ, **gửi 7,9 / giờ** (code hiện tại) |
| Cử chỉ SOS (Need Help, Need Ambulance, Signal For Help) | `NCKH SV 2024/Demo/SOS_HandDetection.mp4` | Cảnh báo SOS | **Không dùng được**: video quay màn hình app cũ, các chấm và đường landmark vẽ đè lên bàn tay -> MediaPipe Hands không thấy tay ở khung nào (0/25 khung lấy mẫu, cả độ phân giải gốc). Chưa có video cử chỉ thật hợp lệ |
| Đứng quá gần camera, che camera, rời khung hình | — | Không báo ngã, không hiện "An toàn" | Chưa có video; kiểm bằng ca kiểm thử tự động (`tests/test_observation_safety.py`, `tests/test_framing.py`) |

## Phát hiện mới: nằm dọc hướng camera bị coi là đã đứng dậy

21/115 ca ngã đã bắt được nhưng không gửi cảnh báo dù người vẫn nằm trên sàn (nhãn `fallen`, vẫn thấy người trong
khung). Nguyên nhân: `fall_v2.is_upright` xét tư thế trên ảnh 2D (thân lệch < 35° so với phương thẳng đứng và khung
người cao hơn rộng). Người nằm dọc theo hướng nhìn của camera (đầu hoặc chân hướng về camera) trên ảnh trông như thân
thẳng đứng -> sau 2 s, `FallV2Tracker` coi là đã đứng dậy và huỷ ca theo dõi.

Đã thử sửa ngày 28/11, chạy lại bằng `replay_eval.py` (thư mục `sau_sua/`, `sau_sua_drop1/`):

| Phương án | Ngã nằm yên 40 s: gửi cảnh báo | Le2i sinh hoạt: clip gửi nhầm | Charades: gửi nhầm / giờ |
|---|---|---|---|
| **Bản hiện tại** (thân thẳng 2 s là đã dậy) | 94 / 115 ca bắt được | 2 / 60 | **7,9** |
| A. Phải nâng hông ≥ 0,3 chiều dài thân so với lúc nằm | **114** / 115 | 6 / 60 | 14,1 |
| B. Như A, trừ khi hông chưa tụt quá 1 chiều dài thân so với lúc đứng | 108 / 115 | 3 / 60 | 9,3 |

Phương án A làm báo nhầm tăng gần gấp đôi: người ngồi phịch xuống ghế bị model nghi ngã, ngồi thẳng trên ghế thì hông không
"nâng lên" nữa -> không bao giờ được tính là đã dậy. Phương án B giảm bớt nhưng độ tụt của hông trên ảnh không tách sạch
"xuống sàn" với "xuống ghế" (ngã ra xa camera thì hông có thể đi LÊN trên ảnh). **Chưa đưa phương án nào vào bản trình
diễn**; giữ bản hiện tại và công bố đây là giới hạn đã biết. Lưu ý: các ngưỡng trên được thử trực tiếp trên Le2i và
Charades, nên nếu chọn một phương án thì hai bộ này không còn là bài thử sạch cho nó — cần dữ liệu thử mới.

## File

- `le2i_giu40.s*.json`: kết quả Le2i theo từng clip (có `t_sent` = lúc gửi cảnh báo).
- `sos_loc_tat.json`, `sos_loc_bat.json`: video SOS, bộ lọc tắt / bật (0 cảnh báo, không thấy tay).
- `charades_*`: chỉ giữ trên máy (giấy phép Charades chỉ cho đánh giá), không đưa lên repo.
