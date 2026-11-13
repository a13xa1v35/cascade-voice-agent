#!/usr/bin/env python3
"""Pre-download model weights so the first evaluation does not stall (and so UTMOSv2,
which shells out to `wget` upstream, works on a Mac without wget)."""

import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download
from utmosv2.utils._constants import _UTMOSV2_CHACHE

dest = Path(_UTMOSV2_CHACHE) / "models" / "fusion_stage3" / "fold0_s42_best_model.pth"
if dest.exists() and dest.stat().st_size > 1_000_000:
    print(f"[prefetch] UTMOSv2 weights present: {dest}")
else:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = "https://huggingface.co/sarulab-speech/UTMOSv2/resolve/main/fold0_s42_best_model.pth"
    print(f"[prefetch] downloading {url}")
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)
    print(f"[prefetch] saved {dest} ({dest.stat().st_size / 1e6:.0f} MB)")

p = snapshot_download("nvidia/parakeet-tdt-0.6b-v2")
print(f"[prefetch] Parakeet in HF cache: {p}")
