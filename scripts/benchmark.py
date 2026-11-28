"""System performance (brief section 9): upload, preprocessing + inference, history, report generation, and concurrent users.

    python scripts/benchmark.py --base http://localhost:8000/api --image path/to/skin_photo.jpg --n 10 --concurrency 4
Creates a throwaway patient account and one case, uploads the photo --n times, and prints median and 95th-percentile times.
"Upload" includes validation, quality check, lesion detection, preprocessing, classification, risk and attention map on the server.
Run it on the machine that will host the demo, with the model deployed, otherwise inference time is not included.
Deactivate the bench-* account afterwards in Administration if you like.
"""
import argparse
import io
import statistics as st
import time
from concurrent.futures import ThreadPoolExecutor

import httpx


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000/api"); ap.add_argument("--image", default=None)
    ap.add_argument("--n", type=int, default=10); ap.add_argument("--concurrency", type=int, default=4)
    a = ap.parse_args()
    if a.image:
        data = open(a.image, "rb").read()
    else:                                   # synthetic skin-like photo: fine for timing, not for judging lesion detection
        import numpy as np
        from PIL import Image
        r = np.random.default_rng(0); h = w = 640
        arr = np.full((h, w, 3), (205, 150, 125), np.int16) + r.integers(-20, 20, (h, w, 3))
        yy, xx = np.ogrid[:h, :w]; arr[((yy - h // 2) ** 2 + (xx - w // 2) ** 2) < 90 ** 2] = (95, 60, 50)
        b = io.BytesIO(); Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(b, "JPEG"); data = b.getvalue()
        print("No --image given: using a synthetic photo (timings only).")
    c = httpx.Client(base_url=a.base, timeout=120)
    email, pw = f"bench.{int(time.time())}@example.com", "BenchPass1"
    t = time.perf_counter()
    c.post("/auth/register", json={"email": email, "full_name": "Benchmark User", "password": pw, "role": "patient"}).raise_for_status()
    tok = c.post("/auth/login", data={"username": email, "password": pw}); tok.raise_for_status()
    login_s = time.perf_counter() - t
    c.headers["Authorization"] = f"Bearer {tok.json()['access_token']}"
    case = c.post("/cases", json={"body_location": "arm"}); case.raise_for_status(); cid = case.json()["id"]

    def timed(fn):
        t0 = time.perf_counter(); r = fn(); r.raise_for_status(); return time.perf_counter() - t0, r

    quality, upload, history, case_get, report = [], [], [], [], []
    img_id, status = None, None
    for _ in range(a.n):
        quality.append(timed(lambda: c.post("/images/check-quality", files={"file": ("p.jpg", data, "image/jpeg")}))[0])
        s, r = timed(lambda: c.post(f"/cases/{cid}/images", files={"file": ("p.jpg", data, "image/jpeg")}, data={"image_source": "gallery"}))
        upload.append(s); img_id, status = r.json()["id"], r.json()["analysis_status"]
        history.append(timed(lambda: c.get("/images/history"))[0]); case_get.append(timed(lambda: c.get(f"/cases/{cid}"))[0])
    for fmt in ("json", "csv", "pdf"):
        report.append((fmt, [timed(lambda: c.get(f"/cases/{cid}/report?format={fmt}"))[0] for _ in range(max(3, a.n // 3))]))

    def one(_):
        cc = httpx.Client(base_url=a.base, timeout=300, headers=dict(c.headers))
        t0 = time.perf_counter(); cc.post(f"/cases/{cid}/images", files={"file": ("p.jpg", data, "image/jpeg")}).raise_for_status(); return time.perf_counter() - t0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(a.concurrency) as ex:
        conc = list(ex.map(one, range(a.concurrency * 2)))
    wall = time.perf_counter() - t0

    row = lambda name, v: print(f"{name:34s} median {st.median(v) * 1000:7.0f} ms   p95 {pct(v, 95) * 1000:7.0f} ms   (n={len(v)})")
    print(f"\nAnalysis status of uploads: {status} (pending = no model deployed, so inference time is NOT included)\n")
    print(f"{'Register + login':34s} {login_s * 1000:7.0f} ms")
    row("Image quality check", quality); row("Upload + full analysis", upload); row("Prediction history (list)", history); row("Case detail load", case_get)
    for fmt, v in report:
        row(f"Report generation ({fmt})", v)
    print(f"\n{a.concurrency} concurrent users, {len(conc)} uploads: {wall:.1f} s total, {len(conc) / wall:.2f} uploads/s, slowest {max(conc):.1f} s")
    print("Image id used for spot checks:", img_id)


if __name__ == "__main__":
    main()

