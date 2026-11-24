"""Lấy một phần Charades (AI2, giấy phép phi thương mại — chỉ dùng ĐÁNH GIÁ, không phát tán)
làm bộ test SINH HOẠT nhiều giờ để đo báo nhầm / giờ. Charades không có cảnh ngã.

Không tải cả file zip 16 GB: đọc mục lục zip rồi tải từng video bằng HTTP Range.
Chọn: mọi video tập test (đã xác minh, chất lượng >= 5) có cảnh NẰM (giường / sofa / sàn)
+ N video ngẫu nhiên khác (seed 42).

Chạy: python -I fetch_charades_subset.py <Charades_v1_test.csv> <thư mục ra> [N ngẫu nhiên, mặc định 500]
Ghi <ra>/videos/*.mp4 và <ra>/labels.csv (loai=adl, mo_ta = kịch bản gốc).
"""

import csv
import io
import os
import random
import sys
import threading
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

URL = "https://ai2-public-datasets.s3-us-west-2.amazonaws.com/charades/Charades_v1_480.zip"
LYING = {"c122", "c124", "c133", "c134"}  # nằm sofa / nằm sàn / thức dậy trên giường / nằm giường
CHUNK = 1 << 20


class HttpFile(io.RawIOBase):
    """File chỉ đọc, seek được, đọc qua HTTP Range — đủ cho zipfile."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Length"])
        self.buf_start, self.buf = 0, b""

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def _fetch(self, start, end):
        req = urllib.request.Request(self.url, headers={"User-Agent": "curl/8.0", "Range": f"bytes={start}-{end - 1}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        lo, hi = self.pos, self.pos + n
        if not (self.buf_start <= lo and hi <= self.buf_start + len(self.buf)):
            self.buf_start = lo
            self.buf = self._fetch(lo, min(self.size, lo + max(n, CHUNK)))
        out = self.buf[lo - self.buf_start:hi - self.buf_start]
        self.pos += len(out)
        return out

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def pick(test_csv, n_random):
    rows = [r for r in csv.DictReader(open(test_csv, encoding="utf-8"))
            if r["verified"] == "Yes" and r["quality"] and int(r["quality"]) >= 5]
    lying = [r for r in rows if any(a.split()[0] in LYING for a in r["actions"].split(";") if a)]
    others = [r for r in rows if r not in lying]
    random.Random(42).shuffle(others)
    return lying + others[:n_random], {r["id"] for r in lying}


def main(test_csv, out_dir, n_random=500):
    chosen, lying_ids = pick(test_csv, int(n_random))
    os.makedirs(os.path.join(out_dir, "videos"), exist_ok=True)
    names = {}
    zf = zipfile.ZipFile(HttpFile(URL))
    for info in zf.infolist():
        names[os.path.splitext(os.path.basename(info.filename))[0]] = info.filename
    local = threading.local()

    def get(row):
        target = os.path.join(out_dir, "videos", f"charades_{row['id']}.mp4")
        if os.path.exists(target):
            return True
        if row["id"] not in names:
            return False
        if not hasattr(local, "zf"):
            local.zf = zipfile.ZipFile(HttpFile(URL))
        with local.zf.open(names[row["id"]]) as src:
            data = src.read()
        with open(target + ".part", "wb") as f:
            f.write(data)
        os.replace(target + ".part", target)
        return True

    done = 0
    with ThreadPoolExecutor(8) as pool:
        for row, ok in zip(chosen, pool.map(get, chosen)):
            done += ok
            if done % 50 == 0:
                print(f"{done}/{len(chosen)}", flush=True)
    with open(os.path.join(out_dir, "labels.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["video", "nguoi", "loai", "fall_start_s", "fall_end_s", "mo_ta"])
        for row in chosen:
            if os.path.exists(os.path.join(out_dir, "videos", f"charades_{row['id']}.mp4")):
                tag = "[nằm] " if row["id"] in lying_ids else ""
                w.writerow([f"charades_{row['id']}.mp4", f"charades-{row['subject']}", "adl", "", "",
                            f"{tag}{row['scene']}: {row['script'][:120]}"])
    print(f"Xong {done}/{len(chosen)} video ({len(lying_ids)} có cảnh nằm) -> {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
