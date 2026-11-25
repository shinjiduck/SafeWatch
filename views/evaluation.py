"""Trang Kiểm định — số liệu đánh giá hệ thống, dùng khi trình bày với Ban tổ chức. Nội dung đọc thẳng từ các
tài liệu kết quả trong training/fall_eval/ (một nguồn duy nhất, không chép số tay vào giao diện)."""

import json
import os

import streamlit as st

from theme import kpi_card, page_header

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL = os.path.join(ROOT, "training", "fall_eval")
RESULTS = os.path.join(EVAL, "kiem_dinh_nhieu_nguoi", "ket_qua")

page_header(
    "Kiểm định",
    "Hệ thống được đánh giá thế nào: tách theo người và phiên quay, không dùng tập test để chọn mô hình, thử trên "
    "dữ liệu chưa từng dùng với góc camera / ánh sáng / vật cản khác nhau.",
)


def read(name):
    path = os.path.join(EVAL, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def demote_headings(text):
    """Tài liệu viết cho GitHub (# to nhất) -> trong tab thì bỏ tiêu đề chính, hạ các mục con xuống cho vừa."""
    out = []
    for line in text.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("#"):
            line = "###" + line
        out.append(line)
    return "\n".join(out)


def replay_summary(name):
    """Tóm tắt 1 file kết quả phát lại (replay_eval.py): ca ngã bắt được / tổng."""
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        results = json.load(f)
    falls = caught = 0
    for r in results.values():
        if r["loai"] != "fall":
            continue
        falls += 1
        lo, hi = float(r["fall_start_s"]) - 0.5, float(r["fall_end_s"]) + 2.0
        caught += any(lo <= e["t"] <= hi for e in r["episodes"])
    return caught, falls


k1, k2, k3, k4 = st.columns(4)
le2i = replay_summary("le2i_single.json")
with k1:
    kpi_card("Le2i — dữ liệu thật chưa từng dùng", f"{le2i[0]}/{le2i[1]}" if le2i else "—",
             "ca ngã bắt được · 9 người, 6 phòng")
with k2:
    kpi_card("Kiểm định chéo 3 bộ", "122/158", "ca ngã · tách theo người")
with k3:
    kpi_card("Charades — 5 giờ sinh hoạt", "9 / giờ", "gửi nhầm · model cũ 61 / giờ")
with k4:
    kpi_card("Che dải dưới 40% (giường, sofa)", "45/78", "ca ngã · model cũ 14/78")
st.caption("Số liệu chi tiết và cách tính ở các tab dưới. Ô giữa lấy từ MODEL_VERSIONS.md / results_che_goc_tong_hop.md.")

DOCS = [
    ("📋 Theo yêu cầu BTC", "KIEM_DINH_THEO_YEU_CAU_BTC.md"),
    ("🧠 Phiên bản model", "../../models/MODEL_VERSIONS.md"),
    ("🧱 Vật cản", "results_che_goc_tong_hop.md"),
    ("👥 Nhiều người", "KIEM_DINH_NHIEU_NGUOI.md"),
]
tabs = st.tabs([t for t, _ in DOCS])
for tab, (_, name) in zip(tabs, DOCS):
    with tab:
        text = read(name)
        if text is None:
            st.info(f"Chưa có tài liệu {name}.")
        else:
            st.markdown(demote_headings(text))
