"""Fast lesion-mask annotation with GrabCut assist. Uses tkinter (ships with Python); no extra installs.

    python sample_for_annotation.py --metadata data/pad_ufes_20/metadata.csv --images data/pad_ufes_20/images --n 150 --out data/to_annotate
    python annotate_masks.py --images data/to_annotate --masks data/masks --prefill

Workflow per photo (about 20-40 seconds; a few seconds when --prefill got it right):
  0. With --prefill the old detector's outline is shown first: press S if it is right, otherwise fix it with strokes (step 2)
     or press D and draw a box (step 1).
  1. Drag a box around the lesion with the LEFT mouse button -> GrabCut outlines it.
  2. Fix mistakes: LEFT-drag paints "this is lesion", RIGHT-drag paints "this is not lesion". The outline updates on release.
  3. Press S or Enter to save and go to the next photo.
Keys:  S/Enter save+next   K skip (no clear lesion)   B back   D redraw box   U undo last stroke   [ ] brush size   Space hide overlay   Q quit
Saves <masks>/<image stem>.png (white = lesion, original resolution). Progress is kept: run it again to continue.
Then train with:  python train_seg.py --images data/to_annotate --masks data/masks --out runs/seg/unet --export-dir ../backend/models
"""
import argparse
import sys
import tkinter as tk
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageTk

WORK = 512                  # GrabCut works on a copy no larger than this
VIEW_W, VIEW_H = 900, 680
EXTS = (".png", ".jpg", ".jpeg")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


def _fill_holes(m: np.ndarray) -> np.ndarray:
    flood = m.copy()
    h, w = m.shape
    cv2.floodFill(flood, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
    return m | (1 - flood)


def grabcut_mask(small_rgb: np.ndarray, rect, fg, bg, prev=None, iters: int = 4) -> np.ndarray:
    """rect=(x0,y0,x1,y1) in working coordinates; fg/bg = lists of (x, y, radius) brush strokes. Returns a {0,1} mask."""
    h, w = small_rgb.shape[:2]
    x0, y0, x1, y1 = rect
    gc = np.full((h, w), cv2.GC_BGD, np.uint8)
    inside = np.zeros((h, w), bool); inside[y0:y1, x0:x1] = True
    if prev is not None and prev.any():
        gc[inside & (prev > 0)] = cv2.GC_PR_FGD
        gc[inside & (prev == 0)] = cv2.GC_PR_BGD
    else:
        gc[inside] = cv2.GC_PR_FGD
    for x, y, r in fg:
        cv2.circle(gc, (int(x), int(y)), int(r), cv2.GC_FGD, -1)
    for x, y, r in bg:
        cv2.circle(gc, (int(x), int(y)), int(r), cv2.GC_BGD, -1)
    if not (gc == cv2.GC_PR_FGD).any() and not (gc == cv2.GC_FGD).any():
        return np.zeros((h, w), np.uint8)
    try:
        cv2.grabCut(cv2.cvtColor(small_rgb, cv2.COLOR_RGB2BGR), gc, None, np.zeros((1, 65)), np.zeros((1, 65)), iters, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return (gc == cv2.GC_FGD).astype(np.uint8)
    m = _fill_holes(((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n <= 1:
        return m
    keep = {1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))}
    for x, y, _ in fg:                                  # components the user painted on are kept too
        if 0 <= int(y) < h and 0 <= int(x) < w and lbl[int(y), int(x)] > 0:
            keep.add(int(lbl[int(y), int(x)]))
    return np.isin(lbl, list(keep)).astype(np.uint8)


class Annotator:
    def __init__(self, root: tk.Tk, files: list[Path], masks_dir: Path, prefill: bool = False, redo: bool = False):
        self.root, self.files, self.masks_dir, self.prefill, self.redo = root, files, masks_dir, prefill, redo
        self.skip_file = masks_dir / "skipped.txt"
        self.i, self.brush, self.show = 0, 14, True
        self.canvas = tk.Canvas(root, width=VIEW_W, height=VIEW_H, bg="#202020", cursor="crosshair", highlightthickness=0)
        self.canvas.pack()
        self.status = tk.Label(root, anchor="w", font=("Segoe UI", 10), padx=8)
        self.status.pack(fill="x")
        c = self.canvas
        c.bind("<ButtonPress-1>", lambda e: self.press(e, True)); c.bind("<B1-Motion>", lambda e: self.move(e, True)); c.bind("<ButtonRelease-1>", lambda e: self.release(e, True))
        for b in ("3", "2"):                          # right button is Button-3 on Windows/Linux, Button-2 on macOS
            c.bind(f"<ButtonPress-{b}>", lambda e: self.press(e, False)); c.bind(f"<B{b}-Motion>", lambda e: self.move(e, False)); c.bind(f"<ButtonRelease-{b}>", lambda e: self.release(e, False))
        for k, fn in (("s", self.save_next), ("<Return>", self.save_next), ("k", self.skip), ("b", self.back), ("d", self.reset), ("u", self.undo),
                      ("<space>", self.toggle), ("q", self.quit), ("<Escape>", self.quit), ("[", lambda: self.set_brush(-3)), ("]", lambda: self.set_brush(3))):
            root.bind(k, lambda e, fn=fn: fn())
        self.done = sum(1 for f in files if (masks_dir / f"{f.stem}.png").exists())
        self.load()

    # ---------- state ----------
    def load(self):
        while self.i < len(self.files) and self.is_finished(self.files[self.i]):
            self.i += 1
        if self.i >= len(self.files):
            self.status.config(text="All photos annotated or skipped. You can close this window.")
            self.canvas.delete("all"); return
        f = self.files[self.i]
        with Image.open(f) as im:
            full = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
        self.full_hw = full.shape[:2]
        s = min(1.0, WORK / max(self.full_hw))
        self.small = cv2.resize(full, (int(self.full_hw[1] * s), int(self.full_hw[0] * s)), interpolation=cv2.INTER_AREA) if s < 1 else full
        h, w = self.small.shape[:2]
        self.ds = min(VIEW_W / w, VIEW_H / h)
        self.rect, self.fg, self.bg, self.mask, self.strokes, self.drag0, self.painting = None, [], [], None, [], None, False
        existing = self.masks_dir / f"{f.stem}.png"
        if self.redo and existing.exists():
            self.load_existing(existing)
        elif self.prefill:
            self.prefill_from_detector(full)
        self.redraw()

    def load_existing(self, path: Path):
        """Re-check mode: start from the saved mask so it can be corrected or replaced."""
        h, w = self.small.shape[:2]
        m = cv2.resize((cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
        ys, xs = np.where(m > 0)
        self.mask = m
        if len(xs) >= 10:
            px, py = int(0.08 * w), int(0.08 * h)
            self.rect = (max(0, xs.min() - px), max(0, ys.min() - py), min(w, xs.max() + px), min(h, ys.max() + py))

    def prefill_from_detector(self, full: np.ndarray):
        """Start from the colour detector's outline (shown for the annotator to accept or fix)."""
        try:
            from app.preprocessing.lesion import detect_lesion
            les = detect_lesion(full)
        except Exception:
            return
        if not les.found or les.mask is None:
            return
        h, w = self.small.shape[:2]
        m = cv2.resize(les.mask, (w, h), interpolation=cv2.INTER_NEAREST)
        ys, xs = np.where(m > 0)
        if len(xs) < 10:
            return
        px, py = int(0.08 * w), int(0.08 * h)
        self.rect = (max(0, xs.min() - px), max(0, ys.min() - py), min(w, xs.max() + px), min(h, ys.max() + py))
        self.mask = m.astype(np.uint8)

    def is_finished(self, f: Path) -> bool:
        if self.redo:                                    # re-checking: show every listed photo, with its existing mask
            return False
        if (self.masks_dir / f"{f.stem}.png").exists():
            return True
        return self.skip_file.exists() and f.name in self.skip_file.read_text().split("\n")

    def to_small(self, e) -> tuple[int, int]:
        h, w = self.small.shape[:2]
        return int(np.clip(e.x / self.ds, 0, w - 1)), int(np.clip(e.y / self.ds, 0, h - 1))

    # ---------- mouse ----------
    def press(self, e, is_fg: bool):
        if self.i >= len(self.files):
            return
        if self.rect is None and is_fg:
            self.drag0 = (e.x, e.y)
        elif self.rect is not None:
            self.painting = True
            self.strokes.append((is_fg, len(self.fg if is_fg else self.bg)))
            self.paint(e, is_fg)

    def move(self, e, is_fg: bool):
        if self.rect is None and self.drag0:
            self.canvas.delete("band")
            self.canvas.create_rectangle(*self.drag0, e.x, e.y, outline="#40ff80", width=2, tags="band")
        elif self.rect is not None and self.painting:
            self.paint(e, is_fg)

    def release(self, e, is_fg: bool):
        if self.rect is None and self.drag0 and is_fg:
            x0, y0 = self.to_small(type("E", (), {"x": min(self.drag0[0], e.x), "y": min(self.drag0[1], e.y)}))
            x1, y1 = self.to_small(type("E", (), {"x": max(self.drag0[0], e.x), "y": max(self.drag0[1], e.y)}))
            self.drag0 = None
            if x1 - x0 >= 10 and y1 - y0 >= 10:
                self.rect = (x0, y0, x1, y1)
                self.run()
            else:
                self.redraw()
        elif self.rect is not None and self.painting:
            self.painting = False
            self.run()

    def paint(self, e, is_fg: bool):
        x, y = self.to_small(e)
        r = max(2, int(self.brush / self.ds))
        (self.fg if is_fg else self.bg).append((x, y, r))
        col = "#4080ff" if is_fg else "#ff4040"
        self.canvas.create_oval(e.x - self.brush, e.y - self.brush, e.x + self.brush, e.y + self.brush, outline=col, width=1, tags="stroke")

    # ---------- actions ----------
    def run(self):
        self.mask = grabcut_mask(self.small, self.rect, self.fg, self.bg, self.mask)
        self.redraw()

    def redraw(self):
        h, w = self.small.shape[:2]
        img = self.small.copy()
        if self.show and self.mask is not None and self.mask.any():
            tint = img.copy(); tint[self.mask > 0] = (0.55 * tint[self.mask > 0] + 0.45 * np.array([30, 220, 110])).astype(np.uint8)
            img = tint
            cnts, _ = cv2.findContours(self.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(img, cnts, -1, (20, 255, 120), 2)
        if self.rect:
            cv2.rectangle(img, self.rect[:2], self.rect[2:], (255, 255, 255), 1)
        disp = cv2.resize(img, (int(w * self.ds), int(h * self.ds)), interpolation=cv2.INTER_AREA if self.ds < 1 else cv2.INTER_LINEAR)
        self.photo = ImageTk.PhotoImage(Image.fromarray(disp))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        area = f"{self.mask.mean() * 100:.0f}% of photo" if self.mask is not None else "no outline yet"
        step = "drag a box around the lesion" if self.rect is None else ("RE-CHECK: S keeps/overwrites this mask, K leaves it, or fix it" if self.redo and not self.fg and not self.bg else None) or ("outline pre-filled: S to accept, or fix it" if self.prefill and not self.fg and not self.bg else "left-drag = lesion, right-drag = not lesion")
        self.status.config(text=f"{self.files[self.i].name}   {self.i + 1}/{len(self.files)}   saved {self.done}   outline: {area}   brush {self.brush}   |   {step}   |   S save  K skip  B back  D redraw  U undo  Q quit")

    def save_next(self):
        if self.i >= len(self.files) or self.mask is None or not self.mask.any():
            self.status.config(text="Draw a box around the lesion first (or press K to skip this photo).")
            return
        H, W = self.full_hw
        full = cv2.resize(self.mask, (W, H), interpolation=cv2.INTER_NEAREST)
        self.masks_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(self.masks_dir / f"{self.files[self.i].stem}.png"), full * 255)
        self.done += 1
        self.i += 1; self.load()

    def skip(self):
        if self.i >= len(self.files):
            return
        self.masks_dir.mkdir(parents=True, exist_ok=True)
        with open(self.skip_file, "a") as f:
            f.write(self.files[self.i].name + "\n")
        self.i += 1; self.load()

    def back(self):
        if self.redo:
            return
        j = self.i - 1
        while j >= 0 and not (self.masks_dir / f"{self.files[j].stem}.png").exists():
            j -= 1
        if j >= 0:
            (self.masks_dir / f"{self.files[j].stem}.png").unlink()
            self.done -= 1; self.i = j; self.load()

    def reset(self):
        if self.i < len(self.files):
            self.rect, self.fg, self.bg, self.mask, self.strokes, self.painting = None, [], [], None, [], False
            self.redraw()

    def undo(self):
        if not self.strokes:
            return
        is_fg, start = self.strokes.pop()
        del (self.fg if is_fg else self.bg)[start:]
        if self.rect:
            self.run()

    def toggle(self):
        self.show = not self.show; self.redraw()

    def set_brush(self, d):
        self.brush = int(np.clip(self.brush + d, 4, 60)); self.redraw()

    def quit(self):
        self.root.destroy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True); ap.add_argument("--masks", default="data/masks")
    ap.add_argument("--redo", default=None, help="text file of photo names to re-check (worst_cases.txt); each opens with its saved mask, S overwrites it")
    ap.add_argument("--prefill", action="store_true", help="start each photo from the old detector's outline")
    a = ap.parse_args()
    files = sorted(p for p in Path(a.images).iterdir() if p.suffix.lower() in EXTS)
    if a.redo:
        wanted = {l.strip() for l in Path(a.redo).read_text().splitlines() if l.strip()}
        files = [f for f in files if f.name in wanted]
    if not files:
        raise SystemExit(f"No images to annotate in {a.images}")
    root = tk.Tk(); root.title("DermAI lesion annotator")
    Annotator(root, files, Path(a.masks), a.prefill, bool(a.redo))
    root.mainloop()


if __name__ == "__main__":
    main()

