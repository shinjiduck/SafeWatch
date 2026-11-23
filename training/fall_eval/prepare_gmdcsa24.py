"""Chuẩn bị GMDCSA-24 (4 người, 3 nhà, 81 ngã + 79 sinh hoạt; MIT) làm bộ TEST NGƯỜI MỚI.
Model chưa từng train trên bộ này.

  - Đổi tên video thành gmd_S<người>_<Fall|ADL>_<số>.mp4 (tên gốc 01.mp4... trùng giữa các người)
  - Ghi labels.csv đúng định dạng `train_eval.py test`: video,nguoi,loai,fall_start_s,fall_end_s,mo_ta

Nhãn gốc "Falling (SW)[a to b]" kéo dài tới hết video (gồm cả đoạn nằm sau ngã) -> lấy a làm lúc
bắt đầu ngã, pha ngã = [a, min(b, a + 1.5 s)] (giống cách xử lý CAUCAFall: chỉ pha chuyển động rơi).

Chạy: python -I prepare_gmdcsa24.py <thư mục giải nén (chứa 'Subject 1'...)> <thư mục ra>
"""

import csv
import os
import re
import shutil
import sys

FALL_PHASE_MAX_S = 1.5
# chịu được lỗi gõ trong nhãn gốc: thiếu ")" ("Falling (BW[5.9 to 10]") hoặc thiếu "to" ("[2.3 6]")
FALL_RE = re.compile(r"Fall(?:ing)?\s*\([^\[\];]*\)?\s*\[\s*([\d.]+)\s*(?:to\s*)?([\d.]+)\s*\]", re.I)


def main(src, out):
    os.makedirs(os.path.join(out, "videos"), exist_ok=True)
    rows = []
    for subject in sorted(d for d in os.listdir(src) if d.lower().startswith("subject")):
        sid = subject.split()[-1]
        for kind in ("Fall", "ADL"):
            with open(os.path.join(src, subject, f"{kind}.csv"), newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader)
                for rec in reader:
                    if not rec or not rec[0].strip():
                        continue
                    fname = rec[0].strip()
                    video = os.path.join(src, subject, kind, fname)
                    if not os.path.exists(video):
                        print(f"Thiếu video {video}")
                        continue
                    new = f"gmd_S{sid}_{kind}_{os.path.splitext(fname)[0]}.mp4"
                    target = os.path.join(out, "videos", new)
                    if not os.path.exists(target):
                        shutil.copyfile(video, target)
                    start = end = ""
                    if kind == "Fall":
                        m = FALL_RE.search(",".join(rec[5:]))
                        if not m:
                            print(f"{subject}/{fname}: không đọc được nhãn ngã: {rec[5:]} — bỏ")
                            os.remove(target)
                            continue
                        a, b = float(m.group(1)), float(m.group(2))
                        start, end = a, min(b, a + FALL_PHASE_MAX_S)
                    desc = rec[4].strip() if len(rec) > 4 else ""
                    rows.append([new, f"gmd-S{sid}", "fall" if kind == "Fall" else "adl", start, end, desc])
    with open(os.path.join(out, "labels.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["video", "nguoi", "loai", "fall_start_s", "fall_end_s", "mo_ta"])
        w.writerows(rows)
    n_fall = sum(r[2] == "fall" for r in rows)
    print(f"{len(rows)} video ({n_fall} ngã, {len(rows) - n_fall} sinh hoạt) -> {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
