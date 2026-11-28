"""Lesion segmentation models (brief section 5): U-Net, Attention U-Net, DeepLabV3 (MobileNetV3 backbone).
Mask R-CNN / YOLO / U-Net++ / transformer segmenters are not included. All models map (B,3,H,W) -> (B,1,H,W) logits."""
import torch
from torch import nn
import torch.nn.functional as F

SEG_ARCHS = ["unet_resnet34", "unet", "attention_unet", "deeplabv3_mobilenet"]


def _block(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                         nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class AttentionGate(nn.Module):
    """Additive attention gate (Oktay et al. 2018): re-weights skip features using the coarser decoder signal."""
    def __init__(self, f_skip, f_gate, f_int):
        super().__init__()
        self.ws = nn.Sequential(nn.Conv2d(f_skip, f_int, 1), nn.BatchNorm2d(f_int))
        self.wg = nn.Sequential(nn.Conv2d(f_gate, f_int, 1), nn.BatchNorm2d(f_int))
        self.psi = nn.Sequential(nn.Conv2d(f_int, 1, 1), nn.BatchNorm2d(1), nn.Sigmoid())

    def forward(self, skip, gate):
        return skip * self.psi(F.relu(self.ws(skip) + self.wg(gate), inplace=True))


class UNet(nn.Module):
    def __init__(self, base: int = 32, depth: int = 4, attention: bool = False):
        super().__init__()
        ch = [base * 2 ** i for i in range(depth + 1)]
        self.enc = nn.ModuleList([_block(3 if i == 0 else ch[i - 1], ch[i]) for i in range(depth + 1)])
        self.up = nn.ModuleList([nn.ConvTranspose2d(ch[i + 1], ch[i], 2, stride=2) for i in range(depth)])
        self.att = nn.ModuleList([AttentionGate(ch[i], ch[i], max(ch[i] // 2, 8)) if attention else nn.Identity() for i in range(depth)])
        self.dec = nn.ModuleList([_block(ch[i] * 2, ch[i]) for i in range(depth)])
        self.out = nn.Conv2d(ch[0], 1, 1)
        self.attention, self.depth = attention, depth

    def forward(self, x):
        skips = []
        for i, e in enumerate(self.enc):
            x = e(x if i == 0 else F.max_pool2d(x, 2))
            skips.append(x)
        x = skips[-1]
        for i in reversed(range(self.depth)):
            up = self.up[i](x)
            s = self.att[i](skips[i], up) if self.attention else skips[i]
            x = self.dec[i](torch.cat([up, s], 1))
        return self.out(x)


class DeepLab(nn.Module):
    def __init__(self, pretrained: bool):
        super().__init__()
        from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large
        self.m = deeplabv3_mobilenet_v3_large(weights=None, weights_backbone="DEFAULT" if pretrained else None, num_classes=1, aux_loss=False)

    def forward(self, x):
        return self.m(x)["out"]


class UNetResNet34(nn.Module):
    """U-Net with an ImageNet-pretrained ResNet34 encoder. With only ~150 annotated photos the pretrained encoder matters a lot."""
    def __init__(self, pretrained: bool = True):
        super().__init__()
        from torchvision.models import resnet34
        r = resnet34(weights="DEFAULT" if pretrained else None)
        self.stem = nn.Sequential(r.conv1, r.bn1, r.relu)            # /2, 64
        self.pool, self.l1, self.l2, self.l3, self.l4 = r.maxpool, r.layer1, r.layer2, r.layer3, r.layer4   # /4 64, /8 128, /16 256, /32 512
        up = lambda i, o: nn.ConvTranspose2d(i, o, 2, stride=2)
        self.u4, self.d4 = up(512, 256), _block(512, 256)
        self.u3, self.d3 = up(256, 128), _block(256, 128)
        self.u2, self.d2 = up(128, 64), _block(128, 64)
        self.u1, self.d1 = up(64, 64), _block(128, 64)
        self.u0, self.d0 = up(64, 32), _block(32, 32)
        self.out = nn.Conv2d(32, 1, 1)

    def forward(self, x):
        s0 = self.stem(x); s1 = self.l1(self.pool(s0)); s2 = self.l2(s1); s3 = self.l3(s2); s4 = self.l4(s3)
        y = self.d4(torch.cat([self.u4(s4), s3], 1))
        y = self.d3(torch.cat([self.u3(y), s2], 1))
        y = self.d2(torch.cat([self.u2(y), s1], 1))
        y = self.d1(torch.cat([self.u1(y), s0], 1))
        return self.out(self.d0(self.u0(y)))


def build_seg_model(arch: str, pretrained: bool = True) -> nn.Module:
    if arch == "unet_resnet34":
        return UNetResNet34(pretrained)
    if arch == "unet":
        return UNet()
    if arch == "attention_unet":
        return UNet(attention=True)
    if arch == "deeplabv3_mobilenet":
        return DeepLab(pretrained)
    raise ValueError(f"unknown segmentation arch {arch!r}; choose from {SEG_ARCHS}")


def dice_bce_loss(logits, target, smooth=1.0):
    bce = F.binary_cross_entropy_with_logits(logits, target)
    p = torch.sigmoid(logits)
    inter = (p * target).sum((1, 2, 3))
    dice = 1 - (2 * inter + smooth) / (p.sum((1, 2, 3)) + target.sum((1, 2, 3)) + smooth)
    return bce + dice.mean()

