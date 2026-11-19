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


def old_pipeline_events(fn, seq, landmarks_sampled):
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
    """Chọn ngưỡng trên VALIDATION: tối đa (số ca ngã bắt được - số báo nhầm)."""
    best, best_score = 0.5, -1e9
    preds = [(s, predict_seq(model, mean, std, s)) for s in val_seqs]
    for th in THRESHOLDS:
        res = [fv.score_sequence(s, fv.detect_events(p, s.sample_times, th)) for s, p in preds]
        score = sum(r[0] for r in res) - sum(r[1] for r in res)
        if score >= best_score:
            best, best_score = th, score
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
    falls = [g for g, ss in groups.items() if any(s.is_fall for s in ss)]
    adls = [g for g in groups if g not in falls]
    rng.shuffle(falls)
    rng.shuffle(adls)
    fold_of = {g: i % k for i, g in enumerate(falls)}
    fold_of.update({g: i % k for i, g in enumerate(adls)})
    return [[s for s in seqs if fold_of[s.group] == f] for f in range(k)]


def raw_landmarks_for(seq_name, pose_dir):
    data = np.load(os.path.join(pose_dir, f"{seq_name}.npz"))
    return landmarks_sampled(data["landmarks"], float(data["fps"]))


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


def cmd_cv(pose_dir, labels_dir, out_dir):
    seqs = fv.load_urfd(pose_dir, labels_dir)
    print(f"{len(seqs)} chuỗi URFD ({sum(s.is_fall for s in seqs)} ngã)")
    negatives = excel_negatives()
    folds = stratified_folds(seqs)
    old_fn = old_model()
    new_results, old_results, per_seq, chosen = [], [], [], []
    for f, test in enumerate(folds):
        rest = [s for g, fold in enumerate(folds) if g != f for s in fold]
        inner = stratified_folds(rest, k=4)
        val, train = inner[0], [s for fold in inner[1:] for s in fold]
        model, mean, std, best_epoch = fit(train, val, extra_negatives=negatives)
        th = choose_threshold(model, mean, std, val)
        chosen.append((best_epoch, th))
        for s in test:
            ev = fv.detect_events(predict_seq(model, mean, std, s), s.sample_times, th)
            r = fv.score_sequence(s, ev)
            new_results.append((s, *r))
            per_seq.append(("moi", s, *r))
            r_old = fv.score_sequence(s, old_pipeline_events(old_fn, s, raw_landmarks_for(s.name, pose_dir)))
            old_results.append((s, *r_old))
            per_seq.append(("cu", s, *r_old))
        print(f"fold {f + 1}/5: epoch={best_epoch}, ngưỡng={th}", flush=True)
    write_report(
        out_dir,
        "URFD — kiểm định chéo 5 phần theo chuỗi quay (mỗi chuỗi được chấm đúng 1 lần, bởi model không thấy nó lúc train)",
        {"Model cũ (LSTM 10 frame)": fv.summarize(old_results), "Model mới (v2)": fv.summarize(new_results)},
        per_seq,
    )
    with open(os.path.join(out_dir, "cv_choices.json"), "w") as f:
        json.dump({"epoch_threshold_per_fold": chosen}, f)


def cmd_final(pose_dir, labels_dir, out_dir):
    seqs = fv.load_urfd(pose_dir, labels_dir)
    with open(os.path.join(out_dir, "cv_choices.json")) as f:
        chosen = json.load(f)["epoch_threshold_per_fold"]
    epochs = int(np.median([c[0] for c in chosen]))
    threshold = float(np.median([c[1] for c in chosen]))
    model, mean, std, _ = fit(seqs, None, epochs=epochs, extra_negatives=excel_negatives())
    model.save(NEW_MODEL)
    with open(NEW_META, "w") as f:
        json.dump({"window": fv.WINDOW, "process_hz": fv.PROCESS_HZ, "threshold": threshold, "epochs": epochs,
                   "mean": mean.tolist(), "std": std.tolist(), "trained_on": "URFD (70 chuỗi) + NotFall tự quay"}, f)
    print(f"Đã lưu {NEW_MODEL} (epoch={epochs}, ngưỡng={threshold})")


def cmd_test(pose_dir, labels_csv, out_dir):
    seqs = fv.load_recorded(pose_dir, labels_csv)
    model = tf.keras.models.load_model(NEW_MODEL)
    with open(NEW_META) as f:
        meta = json.load(f)
    mean, std = np.asarray(meta["mean"], np.float32), np.asarray(meta["std"], np.float32)
    old_fn = old_model()
    new_results, old_results, per_seq = [], [], []
    for s in seqs:
        r = fv.score_sequence(s, fv.detect_events(predict_seq(model, mean, std, s), s.sample_times, meta["threshold"]))
        new_results.append((s, *r))
        per_seq.append(("moi", s, *r))
        r_old = fv.score_sequence(s, old_pipeline_events(old_fn, s, raw_landmarks_for(s.name, pose_dir)))
        old_results.append((s, *r_old))
        per_seq.append(("cu", s, *r_old))
    write_report(out_dir, "Bộ video tự quay — người không có trong dữ liệu train",
                 {"Model cũ (LSTM 10 frame)": fv.summarize(old_results), "Model mới (v2)": fv.summarize(new_results)},
                 per_seq)


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] not in {"cv", "final", "test"}:
        sys.exit(__doc__)
    {"cv": cmd_cv, "final": cmd_final, "test": cmd_test}[sys.argv[1]](*sys.argv[2:])
