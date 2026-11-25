# Kiểm định chế độ theo dõi nhiều người

Bản cũ (1 người) được giữ nguyên: tag git `app-1nguoi-v1`, và vẫn chạy được trong app (Cấu hình → tắt
"Theo dõi nhiều người").

## Cách kiểm định (nâng hơn các lần trước)

1. **Chạy lại qua đúng code của app.** Khung xương đã trích được phát lại vào chính
   `DetectionVideoProcessor` (cùng bộ theo dõi ngã, xác minh sau ngã, luật khuất sau vật cản, gửi cảnh
   báo), thay vì chấm bằng hàm riêng. Đếm đúng những gì app làm: lúc bắt đầu theo dõi sau ngã và cảnh báo
   có gửi hay không.
2. **Lấy mẫu 10 lần/giây ngay lúc trích khung xương**, giống app (xử lý 1 frame trong 3), thay vì trích đủ
   mọi frame rồi mới lấy mẫu.
3. **Model chưa từng thấy dữ liệu được chấm:** `urfd_cauca` cho GMDCSA-24, `urfd_only` cho CAUCAFall,
   `all3` cho Charades (chỉ có sinh hoạt).
4. **Bài thử 2 người (mới):** ghép 2 clip GMDCSA-24 của 2 người KHÁC NHAU cạnh nhau thành 1 khung hình.
   - Ngã + sinh hoạt: 78 cặp, người ngã ở bên trái một nửa số cặp, bên phải nửa còn lại.
   - Sinh hoạt + sinh hoạt: 81 cặp, để đo báo nhầm.
   - Ghi thêm: cảnh báo có gắn đúng người ngã không (theo vị trí trong khung).
5. **So 2 chế độ trên cùng dữ liệu:** 1 người (MediaPipe Pose cũ) và nhiều người (MediaPipe
   PoseLandmarker, tối đa 3 người), đo cả thời gian xử lý mỗi frame.

## Tiêu chí (ghi TRƯỚC khi chạy)

Chế độ nhiều người được đặt làm mặc định chỉ khi đạt cả 3:

- (a) Cảnh 1 người (GMDCSA-24, CAUCAFall): số ca ngã bắt được không kém hơn bản 1 người quá 2 ca mỗi bộ.
- (b) Cảnh 1 người: cảnh báo gửi nhầm mỗi giờ (GMDCSA-24, CAUCAFall, Charades) không tăng quá 20%
  (hoặc quá 2/giờ nếu số gốc nhỏ).
- (c) Cảnh 2 người: bắt được nhiều ca ngã hơn bản 1 người.

Không đạt → vẫn giữ trong app nhưng là tuỳ chọn thử nghiệm, mặc định tắt.

## Kết quả (phát lại qua app, xác minh 30 s; "gửi" tính cả lúc clip hết khi đang chờ xác minh)

| Bài thử | Chế độ | Ngã bắt được | Gửi nhầm / giờ sinh hoạt | ms/frame* |
|---|---|---|---|---|
| **2 người ghép** (GMDCSA-24, model `urfd_cauca`) | 1 người | 44/78 (đúng người 36) | 77 | 87 |
| | nhiều người | **61/78 (đúng người 50)** | 154 | 177 |
| | nhiều người, bản sửa | 60/78 (đúng người 49) | 158 | 177 |
| **GMDCSA-24** 1 người/clip (`urfd_cauca`) | 1 người | **71/78** | 96 | 94 |
| | nhiều người | 68/78 | 106 | 149 |
| | nhiều người, bản sửa | 67/78 | 101 | 149 |
| **CAUCAFall** 1 người/clip (`urfd_only`) | 1 người | 21/50 | **14** (2 lần / 0.14 giờ) | 100 |
| | nhiều người | 22/50 | 77 (11 lần) | 166 |
| | nhiều người, bản sửa | 21/50 | 56 (8 lần) | 166 |
| **Charades** 5 giờ sinh hoạt (`all3`, bài thử sạch) | 1 người | — | **7.9** | 107 |
| | nhiều người | — | 52.1 | 127 |
| | nhiều người, bản sửa | — | 42.3 | 127 |

\* đo trong lúc máy chạy song song nhiều tiến trình trích khung xương — chỉ so tương đối: nhiều người tốn
khoảng 1.6–2 lần.

**Theo tiêu chí đăng ký trước: CHƯA ĐẠT** → chế độ nhiều người giữ là tuỳ chọn thử nghiệm, **mặc định tắt**.
- (a) không đạt: GMDCSA-24 kém 3 ca (cho phép 2).
- (b) không đạt: CAUCAFall gửi nhầm 2 → 11 lần.
- (c) đạt: cảnh 2 người bắt được 61 so với 44 ca ngã.

**Vì sao:**
- Chênh lệch ca ngã ở cảnh 1 người KHÔNG do phần theo dõi nhiều người: ở các clip lệch nhau cả 2 chế độ đều
  thấy người gần như suốt lúc ngã. Bộ trích khung xương mới (PoseLandmarker) cho toạ độ hơi khác bộ cũ, mà
  model v2 được train trên bộ cũ → các ca sát ngưỡng lật cả 2 chiều (mất 6, được 3).
- Gửi nhầm ở CAUCAFall: ngưỡng phát hiện 0.3 thỉnh thoảng sinh "người ma" hiện vài frame rồi mất giữa khung →
  luật khuất sau vật cản tưởng là ngã (8 lần). **Bản sửa** (chỉ áp luật cho người đã thấy ổn định >= 2 s,
  `multi_person.MIN_TRACK_SECONDS`) bớt được 3 lần. Bản sửa làm SAU khi xem GMDCSA-24 / CAUCAFall nên 2 bộ
  này không còn khách quan cho nó; Charades (chưa xem khi sửa) là bài thử sạch.
- Ở cảnh 2 người, báo nhầm gấp đôi một phần là tự nhiên: có 2 người sinh hoạt thì gấp đôi cơ hội nhầm.

**Charades xác nhận: chưa dùng được làm mặc định.** Gửi nhầm tăng 5–6 lần (7.9 → 52/giờ; bản sửa 42/giờ).
Tách nguyên nhân (số lần bắt đầu theo dõi sau ngã trong 5 giờ):

| | 1 người | nhiều người | bản sửa |
|---|---|---|---|
| Do model v2 thấy cú rơi | 132 | 185 | 210 |
| Do luật khuất sau vật cản | 18 | **220** | **148** |

- PoseLandmarker mất dấu rồi bắt lại người thường xuyên hơn hẳn MediaPipe Pose cũ → luật khuất sau vật cản
  (vốn đo trên bộ cũ) nghi nhầm gấp 8–12 lần. Luật này chưa dùng được với bộ trích mới.
- Model v2 nhầm nhiều hơn ~40% trên toạ độ của bộ trích mới (chưa được train trên đó).
- Sau Charades, mọi bộ thử ở đây đều đã "được xem"; thay đổi tiếp theo cần dữ liệu thử MỚI (VD video 2 người
  tự quay) mới đánh giá khách quan được.

**Hạn chế thêm (phát hiện khi dùng thử, 25/11):** người bước vào SAU khi đã có 1 người trong khung thường không
được nhận ra — chế độ VIDEO của PoseLandmarker chỉ tìm người mới khi chưa bám ai. Đo: người thứ 2 xuất hiện ở giây
thứ 3, 2/3 clip không bao giờ nhận ra. Đã thử chạy thêm 1 lượt tìm từ đầu (chế độ IMAGE) mỗi giây: không lần nào
tìm thấy người mới trên 10 clip (bộ tìm người của MediaPipe cũng sót người nhỏ / bị che) mà máy chậm hơn
(~81 ms/frame) → đã bỏ, không đưa vào app.

**Khuyến nghị:** giữ chế độ 1 người làm mặc định. Khi có 2 người, người còn lại thường tự gọi giúp được (hoặc
làm cử chỉ SOS trước camera); chế độ nhiều người chỉ thật cần khi người kia không giúp được (trẻ nhỏ, người già
khác, người bị khống chế).

**Hướng tiếp theo đúng gốc:** train một phiên bản v2 trên khung xương của PoseLandmarker (cùng 3 bộ, kiểm định
chéo như cũ), dùng riêng cho chế độ nhiều người; kiểm lại bằng Charades + video 2 người tự quay.
