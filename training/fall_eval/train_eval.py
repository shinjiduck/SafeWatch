"""Train + đánh giá model ngã THEO SỰ KIỆN (yêu cầu cải tiến số 2).

Lệnh:
  python -I train_eval.py cv      <urfd_pose_dir> <urfd_labels_dir> <out_dir>
      Kiểm định chéo 5 phần, chia THEO CHUỖI QUAY (không chuỗi nào vừa ở train
      vừa ở test). Ngưỡng + số epoch chọn trên tập validation tách từ phần
      train; phần test chỉ dùng để chấm điểm. So sánh với model cũ trên cùng
      các chuỗi.
  python -I train_eval.py final   <urfd_pose_dir> <urfd_labels_dir> <out_dir>
      Train model cuối trên toàn bộ URFD, lưu vào models/ của app.
  python -I train_eval.py test    <recorded_pose_dir> <labels.csv> <out_dir>
      Chấm model cuối + model cũ trên bộ video tự quay (người mới hoàn toàn).
  python -I train_eval.py test_cauca <cauca_pose_dir> <cauca_root> <out_dir>
      Chấm model đang lưu (chỉ train URFD) trên CAUCAFall = test chéo bộ dữ liệu.
  cv / final thêm 2 tham số <cauca_pose_dir> <cauca_root> để train cùng CAUCAFall
  (CAUCAFall chia theo người: không người nào vừa ở train vừa ở test).
  python -I train_eval.py holdout <urfd_pose> <urfd_labels> <cauca_pose> <cauca_root> <rec_pose> <rec_labels.csv> <out_dir>
      Để riêng từng người của bộ có nhãn (GMDCSA-24 / tự quay), train trên phần còn lại, chấm người đó.
  final thêm tiếp <rec_pose> <rec_labels.csv> để train cả bộ đó.
"""

import json
import os
import random
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, APP_DIR)  # fall_v2.py nằm ở gốc app, dùng chung với lúc chạy thật

import fall_v2 as fv  # noqa: E402
import tensorflow as tf  # noqa: E402

MODELS_DIR = os.path.join(APP_DIR, "models")
OLD_MODEL = os.path.join(MODELS_DIR, "LSTM_model.h5")
NEW_MODEL = os.path.join(MODELS_DIR, "fall_v2.keras")
NEW_META = os.path.join(MODELS_DIR, "fall_v2_meta.json")
EXCEL_NOTFALL = os.path.join(os.path.dirname(APP_DIR), "NgaQuy", "Code", "Data_0_NotFall.xlsx")
SEED = 42
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98]
CONSECUTIVE = [1, 2, 3]  # số lần xử lý liên tiếp vượt ngưỡng mới báo — chọn cùng ngưỡng trên validation


def set_seed():
    random.seed(SEED)
    np.random.seed(SEED)
    tf.random.set_seed(SEED)


# ---------------------------------------------------------------- model cũ


def old_model():
    from keras.layers import LSTM, Dense, Dropout
    from keras.models import Sequential

    m = Sequential()
    m.add(tf.keras.Input((10, 99)))
    for last in (False, False, False, True):
        m.add(LSTM(50, return_sequences=not last))
        m.add(Dropout(0.2))
    m.add(Dense(1, activation="sigmoid"))
    m.load_weights(OLD_MODEL)
    return tf.function(lambda x: m(x, training=False))


def old_pipeline_events(fn, seq, landmarks_sampled, trace=None):
    """Mô phỏng ĐÚNG app hiện tại: cửa sổ 10 lần xử lý (x,y,z thô), xoá khi mất
    người, bỏ phiếu đa số 5 lần dự đoán gần nhất."""
    window, votes, voted = [], [], []
    for lm in landmarks_sampled:
        if np.isnan(lm[:, 0]).any():
            window, votes = [], []
            voted.append(0.0)
            continue
        window = (window + [lm[:, :3].reshape(-1)])[-10:]
        if len(window) == 10:
            p = float(fn(np.asarray([window], np.float32)).numpy()[0, 0])
            votes = (votes + [p > 0.5])[-5:]
        voted.append(1.0 if votes and sum(votes) > len(votes) / 2 else 0.0)
    if trace is not None:
        trace["old_voted"] = voted
    return fv.detect_events(voted, seq.sample_times, 0.5, consecutive=1)


def landmarks_sampled(seq_landmarks, fps):
    return fv.resample(seq_landmarks, fps)[0]


# ---------------------------------------------------------------- model mới


def build_model():
    inp = tf.keras.Input((fv.WINDOW, fv.N_FEATURES))
    x = tf.keras.layers.Conv1D(32, 3, padding="same", activation="relu")(inp)
    x = tf.keras.layers.GRU(32)(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    out = tf.keras.layers.Dense(1, activation="sigmoid")(x)
    model = tf.keras.Model(inp, out)
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="binary_crossentropy")
    return model


def fit(train_seqs, val_seqs=None, epochs=None, extra_negatives=None):
    set_seed()
    X, y = fv.window_dataset(train_seqs, flip=True)
    if extra_negatives is not None and len(extra_negatives):
        X = np.concatenate([X, extra_negatives])
        y = np.concatenate([y, np.zeros(len(extra_negatives), np.float32)])
    mean, std = X.reshape(-1, X.shape[-1]).mean(0), X.reshape(-1, X.shape[-1]).std(0) + 1e-6
    pos = max(1.0, float(y.sum()))
    class_weight = {0: 1.0, 1: float((len(y) - pos) / pos)}
    model = build_model()
    kwargs = {"epochs": epochs or 60, "batch_size": 64, "verbose": 0, "class_weight": class_weight}
    if val_seqs is not None:
        Xv, yv = fv.window_dataset(val_seqs)
        kwargs["validation_data"] = ((Xv - mean) / std, yv)
        kwargs["callbacks"] = [tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True)]
    hist = model.fit((X - mean) / std, y, **kwargs)
    best_epoch = int(np.argmin(hist.history["val_loss"]) + 1) if val_seqs is not None else kwargs["epochs"]
    return model, mean, std, best_epoch


def predict_seq(model, mean, std, seq):
    """Xác suất tại mỗi lần xử lý (0 khi chưa đủ cửa sổ / mất người)."""
    probs = np.zeros(len(seq.features), np.float32)
    X, ends = fv.windows(seq.features)
    if len(X):
        probs[ends] = model.predict((X - mean) / std, verbose=0)[:, 0]
    return probs


def choose_threshold(model, mean, std, val_seqs):
    """Chọn (ngưỡng, số lần liên tiếp) trên VALIDATION: tối đa (số ca ngã bắt được - số báo nhầm).
    Hoà điểm thì lấy cấu hình chặt hơn (ngưỡng cao hơn, rồi nhiều lần liên tiếp hơn)."""
    best, best_score = (0.5, 2), -1e9
    preds = [(s, predict_seq(model, mean, std, s)) for s in val_seqs]
    for th in THRESHOLDS:
        for k in CONSECUTIVE:
            res = [fv.score_sequence(s, fv.detect_events(p, s.sample_times, th, k)) for s, p in preds]
            score = sum(r[0] for r in res) - sum(r[1] for r in res)
            if score >= best_score:
                best, best_score = (th, k), score
    return best


# ---------------------------------------------------------------- dữ liệu


def excel_negatives():
    """Dữ liệu NotFall tự quay của bản cũ: chỉ dùng làm mẫu âm khi TRAIN."""
    if not os.path.exists(EXCEL_NOTFALL):
        return None
    import pandas as pd

    raw = pd.read_excel(EXCEL_NOTFALL).iloc[:, 1:].to_numpy(np.float32).reshape(-1, 33, 3)
    sampled, _ = fv.resample(raw, 30.0)
    X, _ = fv.windows(fv.sequence_features(sampled))
    return X


def stratified_folds(seqs, k=5):
    rng = random.Random(SEED)
    groups = {}
    for s in seqs:
        groups.setdefault(s.group, []).append(s)
    # Chia đều theo từng (bộ dữ liệu, có ngã / không) — 10 người CAUCAFall rải đều các fold.
    # Thứ tự xáo giữ nguyên như bản chỉ có URFD để kết quả cũ tái lập được.
    fold_of = {}
    for source in ("urfd", "cauca", "gmd"):  # thêm nguồn mới ở CUỐI để thứ tự xáo của nguồn cũ không đổi
        mine = [g for g in groups if source_of(g) == source]
        falls = [g for g in mine if any(s.is_fall for s in groups[g])]
        adls = [g for g in mine if g not in falls]
        rng.shuffle(falls)
        rng.shuffle(adls)
        fold_of.update({g: i % k for i, g in enumerate(falls)})
        fold_of.update({g: i % k for i, g in enumerate(adls)})
    return [[s for s in seqs if fold_of[s.group] == f] for f in range(k)]


def raw_landmarks_for(seq):
    data = np.load(seq.npz)
    return landmarks_sampled(data["landmarks"], float(data["fps"]))


def load_all(urfd_pose, urfd_labels, cauca_pose=None, cauca_root=None, rec_pose=None, rec_labels=None):
    seqs = fv.load_urfd(urfd_pose, urfd_labels)
    print(f"{len(seqs)} chuỗi URFD ({sum(s.is_fall for s in seqs)} ngã)")
    if cauca_pose:
        cauca = fv.load_caucafall(cauca_pose, cauca_root)
        people = sorted({s.group for s in cauca})
        print(f"{len(cauca)} chuỗi CAUCAFall ({sum(s.is_fall for s in cauca)} ngã, {len(people)} người)")
        seqs += cauca
    if rec_pose:
        rec = fv.load_recorded(rec_pose, rec_labels)
        people = sorted({s.group for s in rec})
        print(f"{len(rec)} chuỗi có nhãn từ {rec_labels} ({sum(s.is_fall for s in rec)} ngã, {len(people)} người)")
        seqs += rec
    return seqs


def source_of(group):
    return "cauca" if group.startswith("cauca-") else "gmd" if group.startswith("gmd-") else "urfd"


# ---------------------------------------------------------------- báo cáo


def write_report(out_dir, title, rows_by_model, per_seq):
    os.makedirs(out_dir, exist_ok=True)
    lines = [f"# {title}", "", "| Chỉ số | " + " | ".join(rows_by_model) + " |",
             "| --- | " + " | ".join("---" for _ in rows_by_model) + " |"]
    labels = {
        "so_ca_nga": "Số ca ngã", "bat_duoc": "Bắt được", "bo_sot": "Bỏ sót", "recall": "Tỉ lệ bắt được",
        "so_chuoi_sinh_hoat": "Số chuỗi sinh hoạt", "chuoi_sinh_hoat_bi_bao_nham": "Chuỗi sinh hoạt bị báo nhầm",
        "bao_nham_trong_sinh_hoat": "Số lần báo nhầm (sinh hoạt)", "gio_sinh_hoat": "Giờ video sinh hoạt",
        "bao_nham_moi_gio_sinh_hoat": "Báo nhầm / giờ sinh hoạt", "bao_nham_tong": "Báo nhầm (tất cả chuỗi)",
        "do_tre_trung_vi_s": "Độ trễ phát hiện, trung vị (s)",
    }
    for key, label in labels.items():
        cells = []
        for summary in rows_by_model.values():
            v = summary[key]
            cells.append(f"{v:.2f}" if isinstance(v, float) else str(v))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(out_dir, "per_sequence.csv"), "w", encoding="utf-8-sig") as f:
        f.write("chuoi,loai,mo_hinh,bat_duoc,so_bao_nham,do_tre_s\n")
        for model_name, seq, det, nfalse, lat in per_seq:
            f.write(f"{seq.name},{'nga' if seq.is_fall else 'sinh_hoat'},{model_name},{int(det)},{nfalse},"
                    f"{'' if lat is None else f'{lat:.2f}'}\n")
    print("\n".join(lines))


# ---------------------------------------------------------------- lệnh


def score_both(seqs, model, mean, std, threshold, old_fn, new_results, old_results, per_seq, traces=None,
               consecutive=2):
    for s in seqs:
        probs = predict_seq(model, mean, std, s)
        events = fv.detect_events(probs, s.sample_times, threshold, consecutive)
        r = fv.score_sequence(s, events)
        new_results.append((s, *r))
        per_seq.append(("moi", s, *r))
        trace = {}
        events_old = old_pipeline_events(old_fn, s, raw_landmarks_for(s), trace)
        r_old = fv.score_sequence(s, events_old)
        if traces is not None:  # để dựng video phân tích ca khó (make_case_videos.py)
            traces[s.name] = {
                "npz": s.npz, "is_fall": s.is_fall, "times": s.sample_times.tolist(),
                "fall_start_s": None if s.fall_start_s is None else float(s.fall_start_s),
                "fall_end_s": None if s.fall_end_s is None else float(s.fall_end_s), "threshold": float(threshold),
                "consecutive": int(consecutive),
                "probs": [float(p) for p in probs], "events": [float(t) for t in events], "detected": bool(r[0]),
                "n_false": int(r[1]), "old_voted": [float(v) for v in trace["old_voted"]],
                "old_events": [float(t) for t in events_old], "old_detected": bool(r_old[0]),
                "old_n_false": int(r_old[1]),
            }
        old_results.append((s, *r_old))
        per_seq.append(("cu", s, *r_old))


def by_source(results_by_model):
    """Thêm cột tách riêng URFD / CAUCAFall nếu có cả hai."""
    out = {}
    for name, res in results_by_model.items():
        out[name] = fv.summarize(res)
        names = {"urfd": "URFD", "cauca": "CAUCAFall", "gmd": "GMDCSA-24"}
        parts = {names[k]: [r for r in res if source_of(r[0].group) == k] for k in names}
        parts = {k: v for k, v in parts.items() if v}
        if len(parts) > 1:
            for src, rr in parts.items():
                out[f"{name} — {src}"] = fv.summarize(rr)
    return out


def cmd_cv(urfd_pose, urfd_labels, out_dir, cauca_pose=None, cauca_root=None, rec_pose=None, rec_labels=None):
    seqs = load_all(urfd_pose, urfd_labels, cauca_pose, cauca_root, rec_pose, rec_labels)
    negatives = excel_negatives()
    folds = stratified_folds(seqs)
    old_fn = old_model()
    new_results, old_results, per_seq, chosen, traces = [], [], [], [], {}
    for f, test in enumerate(folds):
        rest = [s for g, fold in enumerate(folds) if g != f for s in fold]
        inner = stratified_folds(rest, k=4)
        val, train = inner[0], [s for fold in inner[1:] for s in fold]
        model, mean, std, best_epoch = fit(train, val, extra_negatives=negatives)
        th, k = choose_threshold(model, mean, std, val)
        chosen.append((best_epoch, th, k))
        score_both(test, model, mean, std, th, old_fn, new_results, old_results, per_seq, traces, k)
        print(f"fold {f + 1}/5: epoch={best_epoch}, ngưỡng={th}, liên tiếp={k}", flush=True)
    data = "URFD + CAUCAFall (CAUCAFall chia THEO NGƯỜI)" if cauca_pose else "URFD"
    if rec_pose:
        data += " + GMDCSA-24 (chia THEO NGƯỜI)"
    write_report(
        out_dir,
        f"{data} — kiểm định chéo 5 phần (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)",
        by_source({"Model cũ (LSTM 10 frame)": old_results, "Model mới (v2)": new_results}),
        per_seq,
    )
    with open(os.path.join(out_dir, "cv_choices.json"), "w") as f:
        json.dump({"epoch_threshold_per_fold": chosen, "data": data}, f)
    with open(os.path.join(out_dir, "traces.json"), "w", encoding="utf-8") as f:
        json.dump(traces, f)


def cmd_holdout(urfd_pose, urfd_labels, cauca_pose, cauca_root, rec_pose, rec_labels, out_dir):
    """Để riêng TỪNG NGƯỜI của bộ video có nhãn (GMDCSA-24 / tự quay): train trên mọi dữ liệu còn lại
    (URFD + CAUCAFall + các người khác), chấm trên người để riêng. Ngưỡng + epoch chọn trên validation
    tách từ phần train — người để riêng không tham gia chọn gì."""
    base = load_all(urfd_pose, urfd_labels, cauca_pose, cauca_root)
    rec = fv.load_recorded(rec_pose, rec_labels)
    people = sorted({s.group for s in rec})
    print(f"{len(rec)} chuỗi, {len(people)} người: {people}")
    negatives = excel_negatives()
    old_fn = old_model()
    new_results, old_results, per_seq, chosen, traces = [], [], [], [], {}
    for person in people:
        test = [s for s in rec if s.group == person]
        rest = base + [s for s in rec if s.group != person]
        inner = stratified_folds(rest, k=4)
        val, train = inner[0], [s for fold in inner[1:] for s in fold]
        model, mean, std, best_epoch = fit(train, val, extra_negatives=negatives)
        th, k = choose_threshold(model, mean, std, val)
        chosen.append((best_epoch, th, k))
        score_both(test, model, mean, std, th, old_fn, new_results, old_results, per_seq, traces, k)
        r = fv.summarize([x for x in new_results if x[0].group == person])
        print(f"{person}: epoch={best_epoch}, ngưỡng={th}, liên tiếp={k}, bắt {r['bat_duoc']}/{r['so_ca_nga']}, "
              f"sinh hoạt báo nhầm {r['chuoi_sinh_hoat_bi_bao_nham']}/{r['so_chuoi_sinh_hoat']}", flush=True)
    write_report(
        out_dir,
        "Để riêng từng người (người chấm KHÔNG có trong dữ liệu train, không dùng để chọn ngưỡng)",
        {"Model cũ (LSTM 10 frame)": fv.summarize(old_results), "Model mới (v2)": fv.summarize(new_results)},
        per_seq,
    )
    with open(os.path.join(out_dir, "cv_choices.json"), "w") as f:
        json.dump({"epoch_threshold_per_fold": chosen, "data": "holdout theo người"}, f)
    with open(os.path.join(out_dir, "traces.json"), "w", encoding="utf-8") as f:
        json.dump(traces, f)


def cmd_final(urfd_pose, urfd_labels, out_dir, cauca_pose=None, cauca_root=None, rec_pose=None, rec_labels=None):
    seqs = load_all(urfd_pose, urfd_labels, cauca_pose, cauca_root, rec_pose, rec_labels)
    with open(os.path.join(out_dir, "cv_choices.json")) as f:
        chosen = json.load(f)["epoch_threshold_per_fold"]
    epochs = int(np.median([c[0] for c in chosen]))
    threshold = float(np.median([c[1] for c in chosen]))
    consecutive = int(np.median([c[2] if len(c) > 2 else 2 for c in chosen]))
    model, mean, std, _ = fit(seqs, None, epochs=epochs, extra_negatives=excel_negatives())
    model.save(NEW_MODEL)
    trained_on = "URFD (70 chuỗi) + NotFall tự quay"
    if cauca_pose:
        trained_on += f" + CAUCAFall ({sum(s.group.startswith('cauca-') for s in seqs)} chuỗi, 10 người)"
    if rec_pose:
        rec = [s for s in seqs if source_of(s.group) == "gmd"]
        trained_on += f" + GMDCSA-24 ({len(rec)} chuỗi, {len({s.group for s in rec})} người)"
    with open(NEW_META, "w") as f:
        json.dump({"window": fv.WINDOW, "process_hz": fv.PROCESS_HZ, "threshold": threshold,
                   "consecutive": consecutive, "epochs": epochs,
                   "mean": mean.tolist(), "std": std.tolist(), "trained_on": trained_on}, f, ensure_ascii=False)
    print(f"Đã lưu {NEW_MODEL} (epoch={epochs}, ngưỡng={threshold}, liên tiếp={consecutive})")


def load_saved():
    model = tf.keras.models.load_model(NEW_MODEL)
    with open(NEW_META, encoding="utf-8") as f:
        meta = json.load(f)
    return model, np.asarray(meta["mean"], np.float32), np.asarray(meta["std"], np.float32), meta


def cmd_test(pose_dir, labels_csv, out_dir):
    seqs = fv.load_recorded(pose_dir, labels_csv)
    model, mean, std, meta = load_saved()
    new_results, old_results, per_seq, traces = [], [], [], {}
    score_both(seqs, model, mean, std, meta["threshold"], old_model(), new_results, old_results, per_seq, traces,
               meta.get("consecutive", 2))
    write_report(out_dir, "Bộ video tự quay — người không có trong dữ liệu train",
                 {"Model cũ (LSTM 10 frame)": fv.summarize(old_results), "Model mới (v2)": fv.summarize(new_results)},
                 per_seq)
    with open(os.path.join(out_dir, "traces.json"), "w", encoding="utf-8") as f:
        json.dump(traces, f)


def cmd_test_cauca(cauca_pose, cauca_root, out_dir):
    """Chấm model ĐANG LƯU trên CAUCAFall — chỉ là test độc lập khi model chưa train trên CAUCAFall."""
    model, mean, std, meta = load_saved()
    if "CAUCAFall" in meta.get("trained_on", ""):
        sys.exit("Model đang lưu đã train trên CAUCAFall — kết quả sẽ không còn là test độc lập.")
    seqs = fv.load_caucafall(cauca_pose, cauca_root)
    new_results, old_results, per_seq = [], [], []
    score_both(seqs, model, mean, std, meta["threshold"], old_model(), new_results, old_results, per_seq,
               consecutive=meta.get("consecutive", 2))
    write_report(out_dir, "CAUCAFall — 10 người, phòng, ánh sáng, che khuất KHÁC HẲN URFD; model chỉ train trên URFD",
                 {"Model cũ (LSTM 10 frame)": fv.summarize(old_results), "Model mới (v2)": fv.summarize(new_results)},
                 per_seq)


COMMANDS = {"cv": (cmd_cv, (3, 5, 7)), "final": (cmd_final, (3, 5, 7)), "test": (cmd_test, (3,)),
            "test_cauca": (cmd_test_cauca, (3,)), "holdout": (cmd_holdout, (7,))}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS or len(sys.argv) - 2 not in COMMANDS[sys.argv[1]][1]:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]][0](*sys.argv[2:])
