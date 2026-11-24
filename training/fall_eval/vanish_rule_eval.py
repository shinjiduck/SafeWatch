"""Đánh giá luật "ngã khuất sau vật cản" của app (framing.vanished_after_drop) trên traces.json có sẵn.

Luật: người mất dấu >= POSE_LOST_SECONDS, lần cuối thấy ở GIỮA khung hình và hông tụt nhanh ngay trước đó
-> nghi ngã, chạy quy trình xác minh như ngã thường (không đứng thẳng lại 2 s trong thời gian chờ -> gửi).
Chỉ tính những lần model CHƯA tự phát hiện (app cũng bỏ qua khi bộ theo dõi đã ở trạng thái ngã).

Đầu ra mỗi file traces: số ca ngã model bỏ sót mà luật cứu thêm, và số cảnh báo gửi THÊM mỗi giờ sinh hoạt.

Chạy: python -X utf8 -I vanish_rule_eval.py <grace_s> <traces.json> [<traces.json> ...]
"""

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fall_v2 as fv  # noqa: E402
import framing  # noqa: E402
from system_level_eval import alert_sent, upright_series  # noqa: E402

POSE_LOST_SECONDS = 1.5  # = detection_engine.POSE_LOST_SECONDS


def vanish_events(t):
    d = np.load(t["npz"])
    sampled, idx = fv.resample(d["landmarks"], float(d["fps"]))
    out, samples, last_t, last_lm, lost = [], [], None, None, False
    for frame, now in zip(sampled, idx / float(d["fps"])):
        if not np.isnan(frame[0, 0]):
            last_t, last_lm, lost = now, frame.tolist(), False
            samples.append((now, framing.hip_y(last_lm)))
        elif last_t is not None and not lost and now - last_t >= POSE_LOST_SECONDS:
            lost = True
            already = any(last_t - 5 <= e <= last_t + 2 for e in t["events"])
            if not already and framing.vanished_after_drop(samples, last_t, last_lm):
                out.append(last_t)
    return out


def main(grace, *paths):
    grace = float(grace)
    for path in paths:
        traces = json.load(open(path, encoding="utf-8"))
        falls = missed = saved = saved_sent = adl_det = adl_sent = 0
        hours = 0.0
        for t in traces.values():
            events = vanish_events(t)
            times, up, dur = upright_series(t["npz"])
            if t["is_fall"]:
                falls += 1
                if t["detected"]:
                    continue
                missed += 1
                hits = [e for e in events if t["fall_start_s"] - 0.5 <= e <= t["fall_end_s"] + 3]
                saved += bool(hits)
                saved_sent += bool(hits) and alert_sent(hits[0], times, up, grace)
            else:
                hours += dur / 3600
                adl_det += len(events)
                adl_sent += sum(alert_sent(e, times, up, grace) for e in events)
        line = f"{path}: ngã model bỏ sót {missed}/{falls} -> luật cứu thêm {saved} (gửi được {saved_sent})"
        if hours:
            line += f" | sinh hoạt {hours:.2f} giờ: thêm {adl_det / hours:.1f}/giờ nghi, {adl_sent / hours:.1f}/giờ GỬI"
        print(line, flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
