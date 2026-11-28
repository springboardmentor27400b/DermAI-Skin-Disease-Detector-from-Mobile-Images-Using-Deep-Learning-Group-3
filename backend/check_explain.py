import traceback
from pathlib import Path
import numpy as np
import torch
from app.core.config import settings
from app.inference import classifier, explain

m = classifier.get_model()
print("torch:", torch.__version__)
print("model:", m.version if m else None, "| explain in meta:", m.meta.get("explain") if m else None)
d = Path(settings.model_dir) / m.version
print("files:", sorted(p.name for p in d.iterdir()))
for f in ("features.ts.pt", "head.ts.pt"):
    try:
        torch.jit.load(str(d / f)); print(f, "loads OK")
    except Exception:
        print(f, "FAILED to load"); traceback.print_exc()
print("explain.available():", explain.available())
try:
    print("heatmap shape:", explain.heatmap(np.full((256, 256, 3), 120, np.uint8), 0).shape)
except Exception:
    traceback.print_exc()
