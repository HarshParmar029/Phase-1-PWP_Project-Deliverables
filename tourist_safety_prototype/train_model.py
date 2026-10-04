"""train_model.py - Train the Isolation Forest on simulated NORMAL trajectories only.
Usage: python train_model.py [--n 150] [--seed 42]"""
import argparse
import numpy as np
import anomaly
import simulator
import config as C


def build_training_features(n_traj=150, seed=42):
    X = []
    for i in range(n_traj):
        tr = simulator.generate("normal", seed=seed * 100000 + i)
        recs = [anomaly.make_fix(f["lat"], f["lon"], f["timestamp"]) for f in tr.fixes]
        X.extend(anomaly.window_feature_matrix(recs)[1])
    return np.array(X)


def train_and_save(n_traj=150, seed=42, contamination=None):
    X = build_training_features(n_traj, seed)
    model = anomaly.train_isolation_forest([X], contamination=contamination, seed=seed)
    print(f"Trained Isolation Forest on {n_traj} normal trajectories = {len(X)} windows -> {C.MODEL_PATH}")
    return model


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    train_and_save(a.n, a.seed)
