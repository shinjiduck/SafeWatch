"""Thử các luật lọc cử chỉ SOS trên dữ liệu từng frame (sos_frames.py) — đúng logic tay của app (webrtc_processor):
ngưỡng tin cậy -> bỏ phiếu đa số 5 lần -> nhãn SOS -> giữ báo động 2 s, đếm mỗi cạnh lên là 1 cảnh báo.

Luật thêm: ngưỡng tin cậy cao hơn · chỉ nhận khi bàn tay giơ cao hơn vai · nhãn SOS phải giữ liên tục >= hold_s.

Chạy: python -X utf8 -I sos_rules.py <danh sách dev.txt> <danh sách test.txt> <frames*.json ...>
"""

import glob
import json
import sys
from collections import Counter, deque
from itertools import product

SOS = {"Need Ambulance", "Need Help", "Signal For Help"}
VOTES = 5  # = engine.HAND_VOTE_WINDOW
HOLD_ALERT = 2.0  # = ALERT_HOLD_SECONDS


def count_alerts(frames, conf_thr, need_raised, hold_s):
    votes, label = deque(maxlen=VOTES), "No hands"
    alert_until, sos_since, alerts = -1.0, None, 0
    for t, raw, conf, raised in frames:
        if raw is None:
            votes.clear()
            label = "No hands"
        else:
            r = raw if conf >= conf_thr else "Uncertain"
            if need_raised and r in SOS and raised is not True:
                r = "Uncertain"
            votes.append(r)
            c = Counter(votes).most_common(1)[0][0]
            label = c
        if label in SOS:
            sos_since = t if sos_since is None else sos_since
            if t - sos_since >= hold_s:
                if t >= alert_until:
                    alerts += 1
                alert_until = t + HOLD_ALERT
        else:
            sos_since = None
    return alerts


def evaluate(data, keys, rule):
    hours = sum(data[k][-1][0] for k in keys if data[k]) / 3600
    alerts = sum(count_alerts(data[k], *rule) for k in keys)
    return alerts, hours


def main(dev_list, test_list, *patterns):
    data = {}
    for p in patterns:
        for f in glob.glob(p):
            data.update(json.load(open(f, encoding="utf-8")))
    dev = [k for k in (l.strip() for l in open(dev_list, encoding="utf-8")) if k in data]
    test = [k for k in (l.strip() for l in open(test_list, encoding="utf-8")) if k in data]
    base = (0.8, False, 0.0)
    b_dev, h_dev = evaluate(data, dev, base)
    print(f"dev {len(dev)} clip ({h_dev:.2f} giờ), test {len(test)} clip")
    print(f"HIỆN TẠI (ngưỡng 0.8, không lọc): dev {b_dev / h_dev:.1f}/giờ")
    rows = []
    for rule in product((0.8, 0.9, 0.95), (False, True), (0.0, 1.0, 1.5, 2.0)):
        a, h = evaluate(data, dev, rule)
        rows.append((a / h, rule))
    print("\nTrên dev (chọn luật):")
    for rate, (c, r, hs) in sorted(rows):
        print(f"  ngưỡng {c:.2f} · giơ tay {'có' if r else 'không'} · giữ {hs:.1f}s -> {rate:6.1f}/giờ "
              f"(giảm {100 * (1 - rate / (b_dev / h_dev)):.0f}%)")
    return data, dev, test


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
