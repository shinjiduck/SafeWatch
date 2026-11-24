"""Số CẢNH BÁO THẬT SỰ GỬI ĐI (mức hệ thống), không chỉ số lần model phát hiện cú rơi.

App chỉ gửi cảnh báo khi sau lúc phát hiện, người đó KHÔNG đứng thẳng lại liên tục 2 s trong
suốt thời gian chờ (Cài đặt -> fall_grace_seconds, mặc định 120 s). Mô phỏng đúng luật đó trên
traces.json. Video kết thúc trước hết thời gian chờ mà chưa đứng dậy -> vẫn tính LÀ CÓ GỬI
(bất lợi cho mình: con số thật với thời gian chờ 120 s chỉ thấp hơn hoặc bằng).

Chạy: python -I system_level_eval.py <grace_s> <traces.json> [<traces.json> ...]
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import fall_v2 as fv  # noqa: E402

RECOVER_S = 2.0  # = detection_engine.FALL_V2_RECOVER_SECONDS


def upright_series(npz):
    d = np.load(npz)
    lm, fps = d["landmarks"], float(d["fps"])
    sampled, idx = fv.resample(lm, fps)
    feats = fv.sequence_features(sampled)
    up = np.array([(not np.isnan(f).any()) and fv.is_upright(f) for f in feats])
    return idx / fps, up, len(lm) / fps


def alert_sent(event_t, times, up, grace):
    since = None
    for t, u in zip(times, up):
        if t < event_t:
            continue
        if t > event_t + grace:
            break
        if u:
            since = t if since is None else since
            if t - since >= RECOVER_S:
                return False
        else:
            since = None
    return True


def main(grace, *paths):
    grace = float(grace)
    for path in paths:
        traces = json.load(open(path, encoding="utf-8"))
        res = {"moi": [0, 0, 0], "cu": [0, 0, 0]}  # [phát hiện ở sinh hoạt, gửi ở sinh hoạt, ca ngã gửi được]
        hours, falls = 0.0, 0
        for t in traces.values():
            times, up, dur = upright_series(t["npz"])
            for key, events in (("moi", t["events"]), ("cu", t["old_events"])):
                if t["is_fall"]:
                    lo, hi = t["fall_start_s"] - fv.MATCH_BEFORE_S, t["fall_end_s"] + fv.MATCH_AFTER_S
                    hits = [e for e in events if lo <= e <= hi]
                    res[key][2] += bool(hits) and alert_sent(hits[0], times, up, grace)
                else:
                    res[key][0] += len(events)
                    res[key][1] += sum(alert_sent(e, times, up, grace) for e in events)
            if t["is_fall"]:
                falls += 1
            else:
                hours += dur / 3600
        print(f"== {path}  (chờ {grace:g} s, {hours:.2f} giờ sinh hoạt, {falls} ca ngã)")
        for key, name in (("cu", "Model cũ"), ("moi", "Model mới")):
            det, sent, fall_sent = res[key]
            line = f"  {name}: phát hiện {det / hours:.0f}/giờ -> GỬI cảnh báo {sent / hours:.0f}/giờ"
            if falls:
                line += f"; ca ngã gửi được cảnh báo {fall_sent}/{falls}"
            print(line)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
