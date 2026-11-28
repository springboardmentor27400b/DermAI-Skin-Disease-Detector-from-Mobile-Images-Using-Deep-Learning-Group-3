import { useEffect, useMemo, useRef, useState } from "react";

interface Rect { x: number; y: number; w: number; h: number }
const MIN_SIDE = 224;   // keep in step with the server's minimum resolution

function rotated(bmp: ImageBitmap, rot: number, maxSide?: number): HTMLCanvasElement {
  const swap = rot % 2 === 1;
  const fw = swap ? bmp.height : bmp.width, fh = swap ? bmp.width : bmp.height;
  const k = maxSide ? Math.min(1, maxSide / Math.max(fw, fh)) : 1;
  const c = document.createElement("canvas");
  c.width = Math.round(fw * k); c.height = Math.round(fh * k);
  const ctx = c.getContext("2d")!;
  ctx.translate(c.width / 2, c.height / 2); ctx.rotate((rot * Math.PI) / 2);
  const dw = (swap ? c.height : c.width), dh = (swap ? c.width : c.height);
  ctx.drawImage(bmp, -dw / 2, -dh / 2, dw, dh);
  return c;
}

/** Rotate in 90 degree steps and drag a rectangle to crop. Produces a new JPEG file; the server re-checks it. */
export default function ImageEditor({ file, onApply, onCancel }: { file: File; onApply: (f: File) => void; onCancel: () => void }) {
  const [bmp, setBmp] = useState<ImageBitmap | null>(null);
  const [rot, setRot] = useState(0);
  const [crop, setCrop] = useState<Rect | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    let alive = true;
    createImageBitmap(file, { imageOrientation: "from-image" }).then((b) => alive && setBmp(b)).catch(() => alive && setErr("This image cannot be edited here. You can still upload it as it is."));
    return () => { alive = false; };
  }, [file]);

  const preview = useMemo(() => (bmp ? rotated(bmp, rot, 560).toDataURL("image/jpeg", 0.9) : null), [bmp, rot]);
  const full = bmp ? (rot % 2 ? { w: bmp.height, h: bmp.width } : { w: bmp.width, h: bmp.height }) : null;
  const outW = full && Math.round((crop?.w ?? 1) * full.w), outH = full && Math.round((crop?.h ?? 1) * full.h);
  const tooSmall = outW != null && outH != null && Math.min(outW, outH) < MIN_SIDE;

  const pt = (e: React.PointerEvent) => {
    const r = box.current!.getBoundingClientRect();
    return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) };
  };
  const down = (e: React.PointerEvent) => { box.current!.setPointerCapture(e.pointerId); start.current = pt(e); };
  const move = (e: React.PointerEvent) => {
    if (!start.current) return;
    const p = pt(e), s = start.current;
    setCrop({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) });
  };
  const up = () => { start.current = null; setCrop((c) => (c && (c.w < 0.05 || c.h < 0.05) ? null : c)); };
  const turn = (d: number) => { setRot((r) => (r + d + 4) % 4); setCrop(null); };

  function apply() {
    if (!bmp || !full) return;
    const src = rotated(bmp, rot);
    const r = crop ?? { x: 0, y: 0, w: 1, h: 1 };
    const out = document.createElement("canvas");
    out.width = Math.round(r.w * src.width); out.height = Math.round(r.h * src.height);
    out.getContext("2d")!.drawImage(src, Math.round(r.x * src.width), Math.round(r.y * src.height), out.width, out.height, 0, 0, out.width, out.height);
    out.toBlob((b) => b && onApply(new File([b], file.name.replace(/\.\w+$/, "") + "-edited.jpg", { type: "image/jpeg" })), "image/jpeg", 0.95);
  }

  if (err) return <div><p role="alert" className="text-sm text-danger">{err}</p><button className="btn-ghost mt-3" onClick={onCancel}>Back</button></div>;
  if (!preview) return <p className="text-sm text-mute">Loading editor…</p>;
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        <button type="button" className="btn-ghost py-1" onClick={() => turn(-1)} aria-label="Rotate left">⟲ Rotate left</button>
        <button type="button" className="btn-ghost py-1" onClick={() => turn(1)} aria-label="Rotate right">⟳ Rotate right</button>
        <button type="button" className="btn-ghost py-1" onClick={() => setCrop(null)} disabled={!crop}>Reset crop</button>
      </div>
      <div ref={box} className="relative mx-auto w-full max-w-md cursor-crosshair touch-none select-none overflow-hidden rounded border border-line"
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
        <img src={preview} alt="Image being edited" className="block w-full" draggable={false} />
        {crop && (
          <>
            <div className="pointer-events-none absolute inset-0 bg-black/45" style={{ clipPath: `polygon(0 0,100% 0,100% 100%,0 100%,0 0,${crop.x * 100}% ${crop.y * 100}%,${crop.x * 100}% ${(crop.y + crop.h) * 100}%,${(crop.x + crop.w) * 100}% ${(crop.y + crop.h) * 100}%,${(crop.x + crop.w) * 100}% ${crop.y * 100}%,${crop.x * 100}% ${crop.y * 100}%)` }} />
            <div className="pointer-events-none absolute border-2 border-white" style={{ left: `${crop.x * 100}%`, top: `${crop.y * 100}%`, width: `${crop.w * 100}%`, height: `${crop.h * 100}%` }} />
          </>
        )}
      </div>
      <p className="mt-2 text-xs text-mute">Drag on the photo to choose the area to keep. Keep the whole lesion with some skin around it. Result: {outW}×{outH}px.</p>
      {tooSmall && <p role="alert" className="mt-1 text-sm text-danger">The shorter side must be at least {MIN_SIDE}px. Choose a larger area.</p>}
      <div className="mt-3 flex gap-2"><button type="button" className="btn-primary" disabled={tooSmall} onClick={apply}>Use this image</button><button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button></div>
    </div>
  );
}

