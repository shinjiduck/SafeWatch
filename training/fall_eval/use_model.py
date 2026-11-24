"""Đổi model ngã đang dùng trong app (quay lại phiên bản cũ / thử phiên bản khác).

Mỗi phiên bản là 1 cặp models/fall_v2_<tên>.keras + fall_v2_<tên>_meta.json (xem models/MODEL_VERSIONS.md).
Lệnh chép cặp đó đè lên models/fall_v2.keras + fall_v2_meta.json (file app nạp), rồi khởi động lại app.

  python use_model.py            -> liệt kê phiên bản, cho biết bản nào đang dùng
  python use_model.py all3       -> dùng phiên bản "all3"
"""

import filecmp
import json
import os
import shutil
import sys

MODELS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")
ACTIVE, ACTIVE_META = os.path.join(MODELS, "fall_v2.keras"), os.path.join(MODELS, "fall_v2_meta.json")


def versions():
    out = []
    for n in sorted(os.listdir(MODELS)):
        if n.startswith("fall_v2_") and n.endswith(".keras"):
            name = n[len("fall_v2_"):-len(".keras")]
            if os.path.exists(os.path.join(MODELS, f"fall_v2_{name}_meta.json")):
                out.append(name)
    return out


def main(name=None):
    if name is None:
        for v in versions():
            path = os.path.join(MODELS, f"fall_v2_{v}.keras")
            active = os.path.exists(ACTIVE) and filecmp.cmp(path, ACTIVE, shallow=False)
            with open(os.path.join(MODELS, f"fall_v2_{v}_meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
            print(f"{'*' if active else ' '} {v:12s} ngưỡng {meta['threshold']}, liên tiếp {meta.get('consecutive', 2)}, "
                  f"cổng vai+hông {meta.get('gate_vis')} | {meta.get('trained_on', '')}")
        print("(* = đang dùng)")
        return
    if name not in versions():
        sys.exit(f"Không có phiên bản '{name}'. Có: {', '.join(versions())}")
    shutil.copyfile(os.path.join(MODELS, f"fall_v2_{name}.keras"), ACTIVE)
    shutil.copyfile(os.path.join(MODELS, f"fall_v2_{name}_meta.json"), ACTIVE_META)
    print(f"Đã chuyển sang '{name}'. Khởi động lại app (streamlit) để nạp model mới.")


if __name__ == "__main__":
    main(*sys.argv[1:2])
