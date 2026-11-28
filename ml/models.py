"""Model zoo (transfer learning from ImageNet, plus a from-scratch baseline).

Milestone 2: simple_cnn, resnet18/50, densenet121, efficientnet_b0, mobilenet_v3_large, convnext_tiny.
Milestone 3 adds: convnext_small, efficientnet_v2_s (advanced CNNs) and swin_t, vit_b_16 (transformers).
Transformers are more sensitive to the learning rate: start with --lr 1e-4 for swin_t / vit_b_16.
"""
import torch
from torch import nn
from torch.nn.modules.batchnorm import _BatchNorm
import torchvision.models as tv

# Name of the classification head's top-level attribute (everything not listed uses "classifier").
HEAD_PREFIX = {"resnet18": "fc", "resnet50": "fc", "swin_t": "head", "vit_b_16": "heads"}
CLASSIFIER_LAST = ("efficientnet_b0", "mobilenet_v3_large", "convnext_tiny", "convnext_small", "efficientnet_v2_s")
ARCHS = ["simple_cnn", "resnet18", "resnet50", "densenet121", "efficientnet_b0", "mobilenet_v3_large", "convnext_tiny",
         "convnext_small", "efficientnet_v2_s", "swin_t", "vit_b_16"]


class SimpleCNN(nn.Module):
    """Plain 4-block CNN trained from scratch: the baseline every pretrained model must beat."""
    def __init__(self, num_classes: int, dropout: float = 0.3):
        super().__init__()
        def block(i, o):
            return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                                 nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True), nn.MaxPool2d(2))
        self.features = nn.Sequential(block(3, 32), block(32, 64), block(64, 128), block(128, 256), nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.classifier = nn.Sequential(nn.Dropout(dropout), nn.Linear(256, num_classes))

    def forward(self, x):
        return self.classifier(self.features(x))


def build_model(arch: str, num_classes: int, pretrained: bool = True, dropout: float = 0.2) -> nn.Module:
    w = "DEFAULT" if pretrained else None
    if arch == "simple_cnn":
        return SimpleCNN(num_classes)
    if arch in ("resnet18", "resnet50"):
        m = getattr(tv, arch)(weights=w)
        m.fc = nn.Sequential(nn.Dropout(dropout), nn.Linear(m.fc.in_features, num_classes))
    elif arch == "densenet121":
        m = tv.densenet121(weights=w)
        m.classifier = nn.Sequential(nn.Dropout(dropout), nn.Linear(m.classifier.in_features, num_classes))
    elif arch in CLASSIFIER_LAST:
        m = getattr(tv, arch)(weights=w)
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, num_classes)
    elif arch == "swin_t":
        m = tv.swin_t(weights=w)
        m.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(m.head.in_features, num_classes))
    elif arch == "vit_b_16":
        m = tv.vit_b_16(weights=w)                       # needs 224x224 input (the pipeline's default)
        m.heads = nn.Sequential(nn.Dropout(dropout), nn.Linear(m.heads.head.in_features, num_classes))
    else:
        raise ValueError(f"unknown arch {arch!r}; choose from {ARCHS}")
    return m


def head_prefix(arch: str) -> str:
    return HEAD_PREFIX.get(arch, "classifier")


def split_params(model: nn.Module, arch: str):
    pre = head_prefix(arch)
    head = [p for n, p in model.named_parameters() if n.startswith(pre + ".")]
    back = [p for n, p in model.named_parameters() if not n.startswith(pre + ".")]
    return back, head


def set_backbone_trainable(model: nn.Module, arch: str, trainable: bool) -> None:
    pre = head_prefix(arch)
    for n, p in model.named_parameters():
        if not n.startswith(pre + "."):
            p.requires_grad = trainable


def freeze_backbone_bn(model: nn.Module, arch: str) -> None:
    """While the backbone is frozen keep its BatchNorm statistics fixed (call after model.train()). No-op for transformers."""
    pre = head_prefix(arch)
    for n, m in model.named_modules():
        if isinstance(m, _BatchNorm) and not n.startswith(pre + "."):
            m.eval()

