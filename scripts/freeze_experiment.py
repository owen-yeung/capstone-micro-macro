"""Freeze one accepted run from runs/ into results/experiments/<id>/ (copy only; the run is not changed).

Run:  python -m scripts.freeze_experiment --run runs/<run> --id <experiment-id> --keep judge/REPORT.md,judge/summary.json

Writes  full_run.zip   every file of the run: inputs, raw model responses, audits, scores, logs
        (already Git LFS via results/experiments/*/full_run.zip; use this when the archive is 100MB+)
        the --keep files, unpacked, for reading without unzipping
        manifest.json  sha256 of the archive, of kept files and of the code and rubric that produced them
A target directory that already exists is refused; frozen evidence is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CODE = ["src/agent_runtime.py", "src/condition_review.py", "src/verification.py", "src/stages/bid_documents.py",
        "integration/sessions.py", "integration/planning.py", "scripts/micro_org_experiment.py",
        "scripts/micro_org_judge.py", "scripts/run_e2e_case.py", "config/micro_org_rubric.json",
        "scripts/run_baseline_slice_comparisons_20261125.py", "src/baselines/award_topsis.py",
        "src/baselines/contracts.py"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--keep", default="", help="Comma-separated run-relative files to also keep unpacked")
    parser.add_argument("--exclude", default="", help="Comma-separated file names to leave out of the archive")
    args = parser.parse_args()
    target = ROOT / "results/experiments" / args.id
    if target.exists():
        raise SystemExit(f"{target} already exists; frozen evidence is not overwritten")
    excluded = {name for name in args.exclude.split(",") if name}
    files = sorted(p for p in args.run.rglob("*") if p.is_file() and p.name not in excluded)
    target.mkdir(parents=True)
    archive = target / "full_run.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(args.run).as_posix())
    kept = {}
    for name in [item for item in args.keep.split(",") if item]:
        destination = target / Path(name).name
        shutil.copy2(args.run / name, destination)
        kept[destination.name] = sha256(destination)
    manifest = {"experiment_id": args.id, "source_run": args.run.as_posix(), "files_in_archive": len(files),
                "archive": {"name": archive.name, "bytes": archive.stat().st_size, "sha256": sha256(archive)},
                "kept_files_sha256": kept, "excluded_names": sorted(excluded),
                "code_sha256": {name: sha256(ROOT / name) for name in CODE if (ROOT / name).exists()}}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"target": str(target), "archive_mb": round(archive.stat().st_size / 1e6, 1), "files": len(files)}))


if __name__ == "__main__":
    main()
