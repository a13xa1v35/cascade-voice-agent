#!/usr/bin/env python3
"""Download Full-Duplex-Bench v1/v1.5 data from Google Drive into evals/turn_taking/data/fdb/.

Usage (or `make eval-turn-taking-fetch-data`):
    uv run --project evals/turn_taking/scoring python evals/turn_taking/scoring/fetch_data.py \
        [--force] [--keep-zips] [--tasks v1/icc_backchannel,...]

The Drive folder ships one zip per task (v1.0/*.zip, v1.5/*.zip, plus an unrelated
v3.0 archive that is ignored). Zips are extracted to
    evals/turn_taking/data/fdb/<v1|v1.5>/<task>/<id>/...
(upstream folder "v1.0" is renamed to "v1"). Zips are untrusted: members are
validated against path traversal, and __MACOSX / ._* / .DS_Store entries are dropped.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

DRIVE_FOLDER = "https://drive.google.com/drive/folders/1DtoxMVO9_Y_nDs2peZtx3pw-U2qYgpd3"
# (upstream folder, our version, task) -> README sample count. Fallback Drive file ids are
# used only if listing the folder fails.
TASKS = {
    ("v1.0", "v1", "candor_pause_handling"): (216, "1uls3atEz7bZ1IkVq3Rw0yQyLAjjVkklc"),
    ("v1.0", "v1", "candor_turn_taking"): (119, "1sb9mwOqDCK9BEpMb6fDVYOJU1vd5RFlb"),
    ("v1.0", "v1", "icc_backchannel"): (55, "1HttNZbi0bYHe7a-CO_9vg_z7hMM8a5h0"),
    ("v1.0", "v1", "synthetic_user_interruption"): (200, "1I36wGbPtZObjqI_1h11Rb2s1ulerb65a"),
    ("v1.0", "v1", "synthetic_pause_handling"): (137, "1iV0X6z3Z9SrmJvxJ2Hkij3nb8iuWbJyv"),
    ("v1.5", "v1.5", "user_interruption"): (200, "1wqYcYS4-30W2YMc3TfeMeoiaW9PLf4yT"),
    ("v1.5", "v1.5", "user_backchannel"): (99, "1EGwCd9CdGuh8jeqwPENzbBs5FSEgnYL3"),
    ("v1.5", "v1.5", "talking_to_other"): (100, "1Jh6ER4AUmqGgEZBTV0pcbDaMMQIWA7Kt"),
    ("v1.5", "v1.5", "background_speech"): (100, "1W63k1BlQ0QCgvYCb_8YJNqFfUhBwI97W"),
}
DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
OUT_ROOT = DATA_ROOT / "fdb"
CACHE = DATA_ROOT / "_downloads"


def drive_ids() -> dict[str, str]:
    """Map 'v1.0/<task>.zip' -> Drive file id by listing the folder (no download)."""
    import gdown

    try:
        files = gdown.download_folder(url=DRIVE_FOLDER, skip_download=True, quiet=True)
        return {f.path: f.id for f in files or []}
    except Exception as e:
        print(f"[fetch] folder listing failed ({e!r}); using built-in file ids")
        return {}


def count_samples(task_dir: Path) -> int:
    return sum(1 for p in task_dir.iterdir() if p.is_dir()) if task_dir.is_dir() else 0


def safe_extract(zip_path: Path, task: str, dest_root: Path) -> None:
    """Extract '<task>/<id>/<file>' members into dest_root, rejecting anything odd."""
    root = dest_root.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            parts = PurePosixPath(info.filename).parts
            if not parts or parts[0] != task:
                continue  # __MACOSX/ etc.
            if info.is_dir() or any(p in ("..", "") or p.startswith("/") for p in parts):
                continue
            name = parts[-1]
            if name.startswith("._") or name == ".DS_Store":
                continue
            target = (dest_root / Path(*parts)).resolve()
            if root not in target.parents:
                raise RuntimeError(f"unsafe path in zip: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download and re-extract")
    ap.add_argument("--keep-zips", action="store_true")
    ap.add_argument("--tasks", help="comma list like v1/icc_backchannel,v1.5/user_interruption")
    args = ap.parse_args()

    import gdown

    wanted = set(args.tasks.split(",")) if args.tasks else None
    ids = drive_ids()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    rows, total_zip = [], 0
    for (up_dir, ver, task), (expected, fallback_id) in TASKS.items():
        if wanted and f"{ver}/{task}" not in wanted:
            continue
        task_dir = OUT_ROOT / ver / task
        have = count_samples(task_dir)
        if have >= expected and not args.force:
            print(f"[fetch] {ver}/{task}: already present ({have} samples)")
        else:
            key = f"{up_dir}/{task}.zip"
            fid = ids.get(key, fallback_id)
            zpath = CACHE / up_dir / f"{task}.zip"
            zpath.parent.mkdir(parents=True, exist_ok=True)
            if args.force or not zpath.exists():
                print(f"[fetch] downloading {key} ...")
                if not gdown.download(id=fid, output=str(zpath), quiet=True):
                    print(f"[fetch] FAILED to download {key} (Drive quota/permission?)")
                    rows.append((ver, task, expected, have, "download failed"))
                    continue
            if task_dir.exists():
                shutil.rmtree(task_dir)
            safe_extract(zpath, task, OUT_ROOT / ver)
            if not args.keep_zips:
                total_zip += zpath.stat().st_size
                zpath.unlink()
        n = count_samples(task_dir)
        rows.append((ver, task, expected, n, "ok" if n == expected else "COUNT MISMATCH"))

    print(f"\n{'version':8} {'task':30} {'README':>7} {'found':>6}  status")
    for ver, task, exp, n, st in rows:
        print(f"{ver:8} {task:30} {exp:7d} {n:6d}  {st}")
    size = sum(p.stat().st_size for p in OUT_ROOT.rglob("*") if p.is_file())
    print(f"\nextracted size on disk: {size / 1e6:.0f} MB  ({OUT_ROOT})")
    if total_zip:
        print(
            f"zip bytes downloaded this run: {total_zip / 1e6:.0f} MB "
            "(zips deleted; use --keep-zips)"
        )
    return 0 if all(r[4] == "ok" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
