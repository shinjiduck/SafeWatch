# Các phiên bản model ngã (fall v2)

App nạp `fall_v2.keras` + `fall_v2_meta.json`. Mỗi phiên bản được giữ nguyên ở `fall_v2_<tên>.keras` +
`fall_v2_<tên>_meta.json` để quay lại khi cần:

```
python training/fall_eval/use_model.py          # liệt kê, * = đang dùng
python training/fall_eval/use_model.py all3     # chuyển sang bản all3, rồi khởi động lại app
```

Mọi con số đều do model **không thấy** dữ liệu được chấm lúc train. Ngưỡng và epoch được chọn trên
tập validation tách riêng. Thư mục kết quả nằm trong `training/fall_eval/`.

Viết tắt: **ngã** = ca ngã bắt được · **SH nhầm** = chuỗi sinh hoạt bị báo nhầm · **/giờ** = số lần báo
nhầm mỗi giờ sinh hoạt (lúc model phát hiện) · **gửi/giờ** = số cảnh báo thật sự gửi đi, sau 30 s xác
nhận "không đứng dậy" (`system_level_eval.py`).

| Tên | Train trên | Cấu hình | Kết quả chính | Thư mục kết quả |
|---|---|---|---|---|
| `urfd_only` | URFD 70 + NotFall | ngưỡng 0.95, 2 lần liên tiếp | CV URFD: ngã 23/30, SH nhầm 2/40. Sang CAUCAFall: ngã 21/50, SH nhầm 10/50 | `results_urfd_cv`, `results_cauca_crossdataset` |
| `urfd_cauca` | + CAUCAFall 100 (10 người) | ngưỡng 0.98, 2 lần, 12 epoch | CV 2 bộ: ngã 63/80, SH nhầm 6/90. **Người mới (GMDCSA-24): ngã 64/78, SH nhầm 31/81 (~207/giờ)**, gần bằng model cũ | `results_cv_bridge4`, `results_test_gmdcsa24` |
| `all3` (**đang dùng**) | + GMDCSA-24 159 (4 người) | ngưỡng 0.95, 2 lần, 3 epoch | CV 3 bộ: ngã 122/158, SH nhầm 11/171, 25/giờ → **gửi 14/giờ** (model cũ 113). Charades 5 giờ: 32/giờ → **gửi 9/giờ** (cũ 61). Để riêng từng người GMDCSA: ngã 69/78, SH nhầm 17/81 | `results_cv_all3_k`, `results_holdout_gmdcsa24`, `results_test_charades`, `results_system_level_30s.txt` |

Model cũ của app (`LSTM_model.h5`, 10 frame) trên cùng các bộ: CV 3 bộ ngã 124/158, SH nhầm 75/171,
201/giờ → gửi 113/giờ. Charades 165/giờ → gửi 61/giờ.

## Thí nghiệm không dùng (giữ để đối chiếu)

| Thử | Kết quả | Thư mục |
|---|---|---|
| Ngưỡng tin cậy MediaPipe 0.3 | kém hơn 0.5 | `results_cv_c03_bridge2`, `results_cv_c03_bridge4` |
| Nối khoảng mất người 0.6 s | 57/80 so với 63/80 của 0.4 s | `results_cv_bridge6` |
| MediaPipe bản nặng (complexity 2) | ngã 60/80, SH nhầm 12/90 (bản thường: 63/80, 6/90) | `results_cv_c2_bridge4` |
