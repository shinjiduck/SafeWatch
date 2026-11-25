# Kiểm định theo yêu cầu của Ban tổ chức

> Yêu cầu: *"Thử chuỗi chuyển động độc lập có người, góc camera / ánh sáng / vật cản đa dạng; tách dữ liệu theo
> người và phiên quay, không dùng tập test để chọn mô hình."*

## 1. Tách dữ liệu theo người và phiên quay

| Bộ | Đơn vị tách | Ghi chú |
|---|---|---|
| CAUCAFall | người (10 người) | không có người nào vừa ở train vừa ở test |
| GMDCSA-24 | người (4 người) | thêm bài "để riêng từng người" (`results_holdout_gmdcsa24`) |
| URFD | lần quay | bộ không ghi mã người → mỗi lần quay là 1 nhóm |
| UP-Fall *(khi có)* | người + lần quay | 17 người × 3 lần quay × 2 camera — nhãn OmniFall có sẵn mã người, camera |

Code: `train_eval.py` → `stratified_folds` (chia theo `group`), kiểm định chéo 5 phần.

## 2. Không dùng tập test để chọn mô hình

- Trong mỗi lần kiểm định chéo: ngưỡng, số lần liên tiếp và số epoch chọn trên **validation tách từ phần
  train** (4 phần còn lại chia tiếp); phần test chỉ dùng để chấm.
- Model cuối: train trên toàn bộ, thông số = **trung vị** các lựa chọn trên validation (không nhìn test).
- **Nói thẳng chỗ chưa sạch:** vài thông số thiết kế đã được chọn sau khi xem kết quả kiểm định chéo / bài thử:
  nối khoảng mất người 0.4 s (so 0.2 / 0.4 / 0.6 s), luật khuất sau vật cản 10%, sửa "người ma" ở chế độ
  nhiều người. Với các con số trên các bộ đó, đó là chọn trên chính dữ liệu chấm.
- **Cách khắc phục:** đóng băng toàn bộ hệ thống (tag git `dong-bang-v1`) rồi chấm **một lần** trên dữ liệu
  **chưa từng dùng cho bất kỳ quyết định nào** (mục 4). Mọi thay đổi sau đó phải chấm lại trên dữ liệu mới nữa.
- Với thay đổi mới, tiêu chí chấp nhận được **ghi và commit trước khi chạy** (VD `KIEM_DINH_NHIEU_NGUOI.md`).

## 3. Góc camera / ánh sáng / vật cản đa dạng

| Yếu tố | Đã thử | Kết quả |
|---|---|---|
| Ánh sáng, vật cản thật | CAUCAFall (tối, vật cản trong phòng) | trong kiểm định chéo |
| Vật cản (giả lập) | che 1 góc / che dải dưới 40% khung hình | `results_che_goc_tong_hop.md` |
| Nhà thật, người lạ | GMDCSA-24, Charades (5 giờ sinh hoạt, ~500 nhà) | `MODEL_VERSIONS.md` |
| **Góc camera** (độ cao × hướng × khoảng cách) | **OF-Syn** — 12.000 video tổng hợp có ghi góc camera | mục 4 |
| Góc camera thật, phòng / ánh sáng thật | Le2i, UP-Fall, MCFD, CMDFall | **cần tải tay** — mục 5 |

## 4. Chấm trên dữ liệu chưa từng dùng (hệ thống đã đóng băng)

### OF-Syn (OmniFall, video tổng hợp bằng Wan 2.2; nhãn CC BY-NC-SA 4.0)
- Có ghi sẵn: độ cao camera (thấp / ngang mắt / cao / từ trên xuống), hướng (trước / trái / phải / sau), khoảng
  cách (vừa / xa), trong nhà / ngoài trời, 6 nhóm tuổi.
- 82% clip ngã **bắt đầu ngay giây 0** (camera thật luôn thấy người trước khi ngã) → chỉ lấy 193 clip ngã có
  >= 1 s trước cú ngã. Sinh hoạt: 9.569 clip (ngồi, đứng, đi, **nằm xuống chủ động**, nằm...).
- Hạn chế: video do AI tạo, chỉ là bài thử bổ trợ cho dữ liệu thật.

(kết quả: điền sau khi chạy)

## 5. Dữ liệu thật cần tải tay (trang chặn tải tự động)

| Bộ | Vì sao cần | Tải ở đâu | Ghi chú |
|---|---|---|---|
| **Le2i** | 9 người, 6 phòng, ánh sáng + vật cản khác nhau; 190 video (130 có ngã) | https://search-data.ubfc.fr/imvia/FR-13002091000019-2024-04-09_Fall-Detection-Dataset.html | mở bằng trình duyệt, tải bản video |
| **UP-Fall** | 17 người × 3 lần quay × 2 góc camera → tách đúng theo người + phiên | https://sites.google.com/up.edu.mx/har-up/ | chỉ cần các file *Camera1/Camera2* (ảnh zip) |
| **MCFD** | 8 góc camera quay cùng lúc | http://www.iro.umontreal.ca/~labimage/Dataset/ | 24 kịch bản |
| **CMDFall** | 50 người, 7 góc camera (MICA, ĐH Bách khoa Hà Nội) | gửi email xin: thanh-hai.tran@mica.edu.vn | miễn phí cho nghiên cứu; ~7 GB/người → xin một phần |

Nhãn thống nhất (mốc bắt đầu/kết thúc ngã, mã người, mã camera) đã tải sẵn từ OmniFall:
`D:/DeTaiAI/datasets/omnifall/labels/` (`le2i.csv`, `up_fall.csv`, `mcfd.csv`, `cmdfall.csv`).
Tải xong để vào `D:/DeTaiAI/datasets/<tên bộ>/` là chấm được ngay bằng `replay_eval.py`.
