import numpy as np
import torch
import torch.nn.functional as F
from torch import nn


def class_weights(counts: np.ndarray, power: float = 1.0) -> torch.Tensor:
    """Inverse-frequency weights (power 1) or softened (0.5 = square-root), normalised to mean 1."""
    c = np.maximum(np.asarray(counts, dtype=np.float64), 1)
    w = (c.sum() / (len(c) * c)) ** power
    return torch.tensor(w / w.mean(), dtype=torch.float32)


class FocalLoss(nn.Module):
    """Focal loss (Lin et al.): down-weights easy examples. alpha = optional per-class weights."""
    def __init__(self, gamma: float = 2.0, alpha: torch.Tensor | None = None, label_smoothing: float = 0.0):
        super().__init__()
        self.gamma, self.label_smoothing = gamma, label_smoothing
        self.register_buffer("alpha", alpha if alpha is not None else None)

    def forward(self, logits, target):
        ce = F.cross_entropy(logits, target, reduction="none", label_smoothing=self.label_smoothing)
        pt = torch.exp(-F.cross_entropy(logits, target, reduction="none"))
        loss = (1 - pt) ** self.gamma * ce
        if self.alpha is not None:
            loss = loss * self.alpha[target]
        return loss.mean()


def make_loss(kind: str, counts: np.ndarray, weight_power: float = 1.0, gamma: float = 2.0, label_smoothing: float = 0.0) -> nn.Module:
    """kind: none | weighted_loss | focal | sampler.  (sampler balances the batches instead; the loss is then plain CE.)"""
    if kind == "weighted_loss":
        return nn.CrossEntropyLoss(weight=class_weights(counts, weight_power), label_smoothing=label_smoothing)
    if kind == "focal":
        return FocalLoss(gamma, class_weights(counts, weight_power), label_smoothing)
    return nn.CrossEntropyLoss(label_smoothing=label_smoothing)

