"""Package a trained model for the API (TorchScript, so the backend needs only `torch`, not this folder).

    python export_model.py --run runs/final/convnext_tiny --version v1.1-convnext_tiny --models-dir ../backend/models \
           --comparison reports/m2_sampler/comparison.json --risk risk.json
Writes model.ts.pt, meta.json and active.json. Milestone 3 additions:
  * features.ts.pt + head.ts.pt : the same network split in two, so the API can compute Grad-CAM on the deployed model
    (supported: convnext, efficientnet, mobilenet, resnet, densenet121, swin_t; not vit_b_16 / simple_cnn, which export without maps)
  * risk.json (--risk)          : the risk protocol fitted by risk_protocol.py
Prefer a --final model (train.py --final) for deployment; a fold model also works.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.preprocessing.pipeline import PIPELINE_VERSION   # noqa: E402

from models import build_model                              # noqa: E402


class DenseHead(nn.Module):
    def __init__(self, classifier):
        super().__init__(); self.classifier = classifier

    def forward(self, x):
        return self.classifier(torch.flatten(F.adaptive_avg_pool2d(F.relu(x), 1), 1))


class SwinFeatures(nn.Module):
    """Swin keeps features channel-last; expose them as B,C,H,W so Grad-CAM treats every architecture the same."""
    def __init__(self, features):
        super().__init__(); self.features = features

    def forward(self, x):
        return self.features(x).permute(0, 3, 1, 2)


class SwinHead(nn.Module):
    def __init__(self, norm, head):
        super().__init__(); self.norm, self.head = norm, head

    def forward(self, x):
        x = self.norm(x.permute(0, 2, 3, 1)).permute(0, 3, 1, 2)
        return self.head(torch.flatten(F.adaptive_avg_pool2d(x, 1), 1))


def split_for_cam(arch: str, m: nn.Module):
    """(features, head) with head(features(x)) == m(x) in eval mode and features(x) shaped B,C,H,W; None if unsupported."""
    if arch in ("convnext_tiny", "convnext_small"):
        return m.features, nn.Sequential(m.avgpool, m.classifier)
    if arch in ("efficientnet_b0", "efficientnet_v2_s", "mobilenet_v3_large"):
        return m.features, nn.Sequential(m.avgpool, nn.Flatten(1), m.classifier)
    if arch in ("resnet18", "resnet50"):
        return nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1, m.layer2, m.layer3, m.layer4), nn.Sequential(m.avgpool, nn.Flatten(1), m.fc)
    if arch == "densenet121":
        return m.features, DenseHead(m.classifier)
    if arch == "swin_t":
        return SwinFeatures(m.features), SwinHead(m.norm, m.head)
    return None


def export_cam(arch: str, model: nn.Module, dest: Path, size: int) -> bool:
    """Write features.ts.pt and head.ts.pt into dest after checking they reproduce the model. False if the arch is unsupported."""
    parts = split_for_cam(arch, model)
    if parts is None:
        return False
    feats, head = (p.eval() for p in parts)
    ex = torch.randn(1, 3, size, size)
    with torch.no_grad():
        a = feats(ex)
        assert a.dim() == 4, f"{arch}: feature map must be B,C,H,W, got {tuple(a.shape)}"
        assert torch.allclose(model(ex), head(a), atol=1e-4), f"{arch}: split network differs from the original model"
    dest.mkdir(parents=True, exist_ok=True)
    torch.jit.trace(feats, ex, check_trace=False).save(str(dest / "features.ts.pt"))
    torch.jit.trace(head, a, check_trace=False).save(str(dest / "head.ts.pt"))
    return True


def check_preprocessing(meta: dict, force: bool) -> None:
    trained_with = next((tok.split("=", 1)[1] for tok in str(meta.get("preprocessing", "")).split() if tok.startswith("pipeline=")), None)
    if trained_with != PIPELINE_VERSION and not force:
        raise SystemExit(f"Preprocessing mismatch: this model was trained on pipeline '{trained_with or 'unstamped (older)'}' but the API runs '{PIPELINE_VERSION}'.\n"
                         "Re-run precompute_rois.py and retrain (train.py --final), otherwise accuracy in the app will be lower than the CV results. "
                         "Pass --force-preproc only if you know the difference does not matter.")


def load_run(run: Path, force: bool):
    meta = json.loads((run / "meta.json").read_text())
    check_preprocessing(meta, force)
    model = build_model(meta["arch"], len(meta["classes"]), pretrained=False)
    model.load_state_dict(torch.load(run / "best.pt", map_location="cpu"))
    return meta, model.eval()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="folder with best.pt and meta.json from train.py")
    ap.add_argument("--version", required=True)
    ap.add_argument("--models-dir", default="../backend/models")
    ap.add_argument("--comparison", default=None, help="comparison.json from compare_models.py (stored as the model's evaluation)")
    ap.add_argument("--risk", default=None, help="risk.json from risk_protocol.py")
    ap.add_argument("--force-preproc", action="store_true", help="deploy even if the training preprocessing version does not match the API")
    ap.add_argument("--no-cam", action="store_true", help="skip the Grad-CAM split")
    ap.add_argument("--no-activate", action="store_true")
    a = ap.parse_args()

    meta, model = load_run(Path(a.run), a.force_preproc)
    ex = torch.randn(1, 3, meta["img_size"], meta["img_size"])
    ts = torch.jit.trace(model, ex, check_trace=False)
    with torch.no_grad():
        assert torch.allclose(model(ex), ts(ex), atol=1e-4), "TorchScript output differs from the original model"
    dest = Path(a.models_dir) / a.version
    dest.mkdir(parents=True, exist_ok=True)
    ts.save(str(dest / "model.ts.pt"))
    meta["version"] = a.version
    if not a.no_cam:
        if export_cam(meta["arch"], model, dest, meta["img_size"]):
            meta["explain"] = {"method": "grad-cam", "members": [""]}
            print("Grad-CAM modules written")
        else:
            print(f"Grad-CAM export is not supported for {meta['arch']}; the model works without attention maps.")
    if a.comparison:
        comp = json.loads(Path(a.comparison).read_text())
        key = next((k for k in comp if k == meta["arch"] or k.startswith(meta["arch"])), None)
        if key:
            c = comp[key]
            meta["evaluation"] = {"source": "pooled out-of-fold test predictions (patient-grouped 5-fold CV)", "accuracy": c["accuracy"], "balanced_accuracy": c["balanced_accuracy"],
                                  "macro_f1": c["macro_f1"], "macro_auc_ovr": c["macro_auc_ovr"], "mcc": c["mcc"], "ece": c["ece"], "per_class": c["per_class"]}
    if a.risk:
        shutil.copy(a.risk, dest / "risk.json")
    (dest / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    if not a.no_activate:
        (Path(a.models_dir) / "active.json").write_text(json.dumps({"version": a.version}))
    print(f"exported {a.version} -> {dest}" + ("" if a.no_activate else " (active)"))


if __name__ == "__main__":
    main()

