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

## Kết quả

(điền sau khi chạy)
