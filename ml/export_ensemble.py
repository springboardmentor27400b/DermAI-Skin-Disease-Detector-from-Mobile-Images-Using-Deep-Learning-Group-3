"""Package an ensemble of final models as ONE deployable model (Milestone 3).

    python export_ensemble.py --runs runs/final/convnext_tiny runs/final/swin_t --version v2.0-ensemble --models-dir ../backend/models \
           --evaluation runs/m3_ens/evaluation.json --eval-key ens_equal --risk risk.json
Each run is a train.py --final folder. The deployed network returns log(weighted mean of the members' calibrated probabilities), so the
API's existing temperature step (set to 1.0 here) reproduces exactly that mean and nothing in the backend changes. Grad-CAM maps are
computed per member and averaged. All members must share classes, input size, normalisation and preprocessing recipe.
Weights default to equal; pass --weights 0.6 0.4 to use others (choose them with ensemble.py, on validation data).
"""
import argparse
import json
import shutil
from pathlib import Path

import torch
from torch import nn

from export_model import check_preprocessing, export_cam, load_run


class EnsembleNet(nn.Module):
    def __init__(self, nets, temps, weights):
        super().__init__()
        self.nets = nn.ModuleList(nets)
        self.register_buffer("t", torch.tensor(temps, dtype=torch.float32))
        self.register_buffer("w", torch.tensor(weights, dtype=torch.float32))

    def forward(self, x):
        p = self.w[0] * torch.softmax(self.nets[0](x) / self.t[0], 1)
        for i in range(1, len(self.nets)):
            p = p + self.w[i] * torch.softmax(self.nets[i](x) / self.t[i], 1)
        return torch.log(p.clamp_min(1e-9))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--models-dir", default="../backend/models")
    ap.add_argument("--weights", nargs="+", type=float, default=None)
    ap.add_argument("--evaluation", default=None, help="evaluation.json written by ensemble.py")
    ap.add_argument("--eval-key", default="ens_equal", help="entry of evaluation.json that matches the weights you deploy")
    ap.add_argument("--risk", default=None)
    ap.add_argument("--force-preproc", action="store_true")
    ap.add_argument("--no-activate", action="store_true")
    a = ap.parse_args()
    if len(a.runs) < 2:
        raise SystemExit("Give at least two --runs.")
    w = a.weights or [1 / len(a.runs)] * len(a.runs)
    if len(w) != len(a.runs) or abs(sum(w) - 1) > 1e-6:
        raise SystemExit("--weights needs one value per run and must sum to 1.")

    loaded = [load_run(Path(r), a.force_preproc) for r in a.runs]
    ref = loaded[0][0]
    for meta, _ in loaded[1:]:
        for k in ("classes", "img_size", "mean", "std", "preprocessing"):
            if meta.get(k) != ref.get(k):
                raise SystemExit(f"Members disagree on {k!r}: {ref.get(k)} vs {meta.get(k)}. Ensemble members must share the preprocessing.")
    dest = Path(a.models_dir) / a.version
    dest.mkdir(parents=True, exist_ok=True)
    net = EnsembleNet([m for _, m in loaded], [float(meta.get("temperature", 1.0)) for meta, _ in loaded], w).eval()
    ex = torch.randn(1, 3, ref["img_size"], ref["img_size"])
    ts = torch.jit.trace(net, ex, check_trace=False)
    with torch.no_grad():
        assert torch.allclose(net(ex), ts(ex), atol=1e-4), "TorchScript output differs from the ensemble"
    ts.save(str(dest / "model.ts.pt"))

    subs = []
    for i, (meta, model) in enumerate(loaded):
        if export_cam(meta["arch"], model, dest / f"m{i}", ref["img_size"]):
            subs.append(f"m{i}")
        else:
            print(f"member {meta['arch']} has no Grad-CAM split and is left out of the attention map")
    out = {**{k: ref[k] for k in ("classes", "class_names", "img_size", "mean", "std", "dataset", "preprocessing", "created_at") if k in ref},
           "arch": "ensemble(" + "+".join(m["arch"] for m, _ in loaded) + ")", "version": a.version, "temperature": 1.0, "final_model": True,
           "members": [{"arch": m["arch"], "weight": wi, "temperature": m.get("temperature", 1.0), "run": str(r)} for (m, _), wi, r in zip(loaded, w, a.runs)]}
    if subs:
        out["explain"] = {"method": "grad-cam", "members": subs}
    if a.evaluation:
        ev = json.loads(Path(a.evaluation).read_text()).get(a.eval_key)
        if ev:
            out["evaluation"] = {k: ev[k] for k in ("source", "accuracy", "balanced_accuracy", "macro_f1", "macro_auc_ovr", "mcc", "ece", "per_class") if k in ev}
            out["evaluation"]["note"] = f"{a.eval_key}: member predictions averaged; weights as deployed must match this entry."
    if a.risk:
        shutil.copy(a.risk, dest / "risk.json")
    (dest / "meta.json").write_text(json.dumps(out, indent=2, default=str))
    if not a.no_activate:
        (Path(a.models_dir) / "active.json").write_text(json.dumps({"version": a.version}))
    print(f"exported {a.version} -> {dest}" + ("" if a.no_activate else " (active)"))


if __name__ == "__main__":
    main()

