"""OPTIONAL deep-learning version of the delay model in PyTorch (needs: pip install torch).

    python -m ml.training.train_torch_mlp

It trains the same task as ml/training/train_delay_model.py with a small feed-forward network (embedding for the
transport mode + dense layers) and writes ml/models/delay_model_torch.pt. The app does not require it; the
scikit-learn MLP is used by default so the project runs without PyTorch.
"""
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

import settings
from ml.features import NUMERIC_FEATURES, build_features
from ml.traffic_data import MODE_PARAMS, generate_traffic_history


class DelayNet(nn.Module):
    def __init__(self, n_modes: int, n_numeric: int):
        super().__init__()
        self.embed = nn.Embedding(n_modes, 4)
        self.net = nn.Sequential(nn.Linear(4 + n_numeric, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, mode_idx, x):
        return self.net(torch.cat([self.embed(mode_idx), x], dim=1)).squeeze(1)


def main(epochs: int = 40, seed: int = 42):
    torch.manual_seed(seed)
    df = pd.read_csv(settings.TRAFFIC_CSV) if settings.TRAFFIC_CSV.exists() else generate_traffic_history()
    modes = sorted(set(MODE_PARAMS) | set(df["mode"]))
    mode_to_idx = {m: i for i, m in enumerate(modes)}
    X = build_features(df)
    mode_idx = torch.tensor(X["mode"].map(mode_to_idx).to_numpy(), dtype=torch.long)
    num = X[NUMERIC_FEATURES].to_numpy(dtype=np.float32)
    mean, std = num.mean(0), num.std(0) + 1e-6
    num_t = torch.tensor((num - mean) / std)
    y = torch.tensor(df["delay_ratio"].to_numpy(dtype=np.float32))

    n_train = int(0.8 * len(df))
    train_dl = DataLoader(TensorDataset(mode_idx[:n_train], num_t[:n_train], y[:n_train]), batch_size=256, shuffle=True)
    model = DelayNet(len(modes), len(NUMERIC_FEATURES))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.L1Loss()
    for epoch in range(epochs):
        model.train()
        for m, xb, yb in train_dl:
            opt.zero_grad()
            loss_fn(model(m, xb), yb).backward()
            opt.step()
        if epoch % 5 == 0 or epoch == epochs - 1:
            model.eval()
            with torch.no_grad():
                mae = loss_fn(model(mode_idx[n_train:], num_t[n_train:]), y[n_train:]).item()
            print(f"epoch {epoch:02d}  test MAE (ratio) = {mae:.4f}")
    torch.save({"state": model.state_dict(), "modes": modes, "mean": mean, "std": std}, settings.MODEL_DIR / "delay_model_torch.pt")
    print("saved", settings.MODEL_DIR / "delay_model_torch.pt")


if __name__ == "__main__":
    main()
