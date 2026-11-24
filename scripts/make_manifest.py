#!/usr/bin/env python3
"""make_manifest.py — write run-manifest.json deterministically.

Lists the pinned commit, the fixture digests, and the SHA-256 of every
file in outputs/ except the transient logs (run_all.log,
fresh-clone-reproduction.log). No timestamps: re-running produces a
byte-identical manifest when the outputs are identical.
"""

import hashlib
import json
import sys
from pathlib import Path

EXCLUDE = {"run_all.log", "fresh-clone-reproduction.log"}


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv):
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "outputs"
    manifest = {
        "pack": "postfiatd validator uptime and missed-validation forensics",
        "pinned_commit": "0085a1ff885d6a446369cf73a4430f75af22be55",
        "pinned_commit_subject": "Merge pull request #50 from "
                                 "postfiatorg/hotfix/upstream-hardening-1.0.9",
        "pinned_commit_date": "2026-10-10T16:53:26Z",
        "fixtures": {},
        "outputs": {},
    }
    for p in sorted((root / "fixtures").glob("*")):
        manifest["fixtures"]["fixtures/" + p.name] = sha256_file(p)
    for p in sorted(out_dir.glob("*")):
        if p.name in EXCLUDE or p.name == "SHA256SUMS":
            continue
        manifest["outputs"]["outputs/" + p.name] = sha256_file(p)
    text = json.dumps(manifest, indent=2) + "\n"
    (root / "run-manifest.json").write_text(text, encoding="utf-8")
    print("run-manifest.json written: %d fixtures, %d outputs"
          % (len(manifest["fixtures"]), len(manifest["outputs"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
