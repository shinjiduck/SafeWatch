"""Quay video sinh hoạt bình thường (không ngã) từ webcam để đo BÁO NHẦM MỖI GIỜ.

Ghi thành từng đoạn 10 phút (H.264, 640x480, 30 fps) vào thư mục ra, kèm labels.csv
(mỗi đoạn = 1 dòng loai=adl). Đóng app SafeWatch trước (webcam chỉ mở được ở 1 chương trình).

Chạy:   python record_adl.py <thư mục ra> [phút, mặc định 60] [số camera, mặc định 0]
Dừng sớm: bấm Q ở cửa sổ xem trước (hoặc Ctrl+C) — đoạn đang quay vẫn được lưu.
"""

import csv
import os
import subprocess
import sys
import time

import cv2
import numpy as np

W, H, FPS = 640, 480, 30
CHUNK_S = 600


def ffmpeg_exe():
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def open_chunk(path):
    return subprocess.Popen(
        [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
         path],
        stdin=subprocess.PIPE,
    )


def main(out_dir, minutes=60, cam=0):
    minutes, cam = float(minutes), int(cam)
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(cam, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(cam)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    if not cap.isOpened():
        sys.exit("Không mở được webcam — đóng app SafeWatch / Zoom / Camera rồi thử lại.")
    stamp = time.strftime("%Y%m%d_%H%M")
    labels = os.path.join(out_dir, "labels.csv")
    new_file = not os.path.exists(labels)
    start = time.time()
    chunk, proc, chunk_start, next_frame = 0, None, 0.0, start
    written = []
    try:
        while time.time() - start < minutes * 60:
            ok, img = cap.read()
            if not ok:
                print("Mất tín hiệu webcam — dừng.")
                break
            now = time.time()
            if proc is None or now - chunk_start >= CHUNK_S:
                if proc:
                    proc.stdin.close()
                    proc.wait()
                chunk += 1
                name = f"adl_{stamp}_{chunk:02d}.mp4"
                proc, chunk_start = open_chunk(os.path.join(out_dir, name)), now
                written.append(name)
                print(f"Đang quay {name} ...", flush=True)
            img = cv2.resize(img, (W, H))
            # giữ đúng 30 fps theo thời gian thực (webcam có thể chậm hơn): lặp/bỏ frame cho khớp đồng hồ
            while next_frame <= now:
                proc.stdin.write(np.ascontiguousarray(img).tobytes())
                next_frame += 1.0 / FPS
            left = minutes * 60 - (now - start)
            preview = img.copy()
            cv2.putText(preview, f"REC  con {int(left // 60)}:{int(left % 60):02d}  (Q = dung)", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.imshow("Quay sinh hoat", preview)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
    except KeyboardInterrupt:
        pass
    finally:
        if proc:
            proc.stdin.close()
            proc.wait()
        cap.release()
        cv2.destroyAllWindows()
    with open(labels, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["video", "nguoi", "loai", "fall_start_s", "fall_end_s", "mo_ta"])
        for name in written:
            w.writerow([name, f"nhom-{stamp}", "adl", "", "", "sinh hoạt bình thường (tự quay)"])
    print(f"Xong: {len(written)} đoạn, {(time.time() - start) / 60:.0f} phút -> {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(*sys.argv[1:])
