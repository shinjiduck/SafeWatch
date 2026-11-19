# Hướng dẫn quay bộ test độc lập (yêu cầu BTC số 2)

Mục tiêu: thử model trên **người không có trong dữ liệu train**, với nhiều góc camera, ánh sáng và vật cản, gồm cả ngã thật và các động tác dễ gây báo nhầm.

## Cách quay

- Điện thoại hoặc webcam, đặt **cố định** ở độ cao 1,5–2,2 m (giống camera giám sát), quay ngang, 720p hoặc 1080p, 25–30 fps.
- Mỗi video **5–20 giây** cho một hành động. Riêng video sinh hoạt dài thì quay liền 10–30 phút.
- Thấy được **toàn thân** người trong phần lớn video.
- Ngã lên **nệm/chăn dày**. An toàn trước hết; người quay đứng cạnh.

## Số lượng tối thiểu (cả nhóm)

| Loại | Số video | Ghi chú |
| --- | --- | --- |
| Ngã (`fall`) | ≥ 20 | Ngã trước, ngã ngửa, ngã nghiêng, khuỵu từ từ, ngã từ ghế. Mỗi người ≥ 5 |
| Ca khó không phải ngã (`adl`) | ≥ 20 | Nằm xuống giường/sàn chủ động, ngồi phịch xuống ghế, cúi nhặt đồ, ngồi xổm, buộc dây giày |
| Sinh hoạt dài (`adl`) | ≥ 1 giờ tổng | Đi lại, ngồi, dọn dẹp, nằm nghỉ — dùng để đo báo nhầm mỗi giờ |

Thay đổi giữa các video: **≥ 3 người** (khác người trong dữ liệu cũ), **≥ 2 phòng**, **≥ 3 góc** (chính diện, chéo 45°, từ trên cao), **ánh sáng** (sáng, tối/đèn vàng, ngược sáng), **vật cản** (bàn ghế che một phần người).

## Đặt tên và ghi nhãn

Đặt tên file: `nguoiX_loai_STT.mp4`, ví dụ `tam_fall_03.mp4`, `thao_adl_12.mp4`.

Ghi vào `labels.csv` (UTF-8), mỗi video một dòng:

```csv
video,nguoi,loai,fall_start_s,fall_end_s,goc,anh_sang,vat_can
tam_fall_03.mp4,tam,fall,4.2,5.1,cheo45,sang,khong
thao_adl_12.mp4,thao,adl,,,chinh_dien,toi,ban
```

- `fall_start_s`: giây bắt đầu mất thăng bằng; `fall_end_s`: giây chạm sàn. Xem video rồi ghi gần đúng 0,2 s là được.
- Video `adl` để trống hai cột thời gian.

## Chạy đánh giá

```bash
cd D:\DeTaiAI\combined-demo-dev\training\fall_eval
python -I extract_pose.py <thư mục video> <thư mục pose>
python -I train_eval.py test <thư mục pose> <đường dẫn labels.csv> <thư mục kết quả>
```

Kết quả: `report.md` (bảng bỏ sót / báo nhầm mỗi giờ, model cũ so với model mới) và `per_sequence.csv` (từng video) — dùng để chọn ca khó làm video phân tích.
