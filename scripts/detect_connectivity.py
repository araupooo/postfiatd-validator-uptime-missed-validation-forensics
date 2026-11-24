#!/usr/bin/env python3
"""detect_connectivity.py — connectivity-loss detector.

Usage: detect_connectivity.py [fixture-name]   (default: connectivity-loss)
Reads fixtures/<name>.log + fixtures/<name>-ledger-state.json, applies
validation_lib.detect_connectivity(), writes
outputs/detector-connectivity.log and outputs/detector-connectivity.json.

Rule: peer disconnect/fail lines (PeerImp::close/fail, PeerImp.cpp:596-638)
overlapping a missed-validation window => CONNECTIVITY_LOSS.
This script is invoked by scripts/run_all.sh; it performs no manual step.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation_lib import (DETECTORS, load_ledger_state,  # noqa: E402
                            parse_log)


def main(argv):
    name = argv[0] if argv else "connectivity-loss"
    root = Path(__file__).resolve().parent.parent
    state = load_ledger_state(root / "fixtures" / ("%s-ledger-state.json" % name))
    events = parse_log(root / "fixtures" / ("%s.log" % name), state)
    events["_ledger_state"] = state
    ev = DETECTORS["connectivity"](events)
    lines = ["=== detector: connectivity-loss ===",
             "fixture: %s (synthetic)" % name,
             "rule: PeerImp disconnect/fail lines overlapping a "
             "missed-validation window (see docs/methodology.md)",
             "--- evidence ---",
             "peer fail lines: %d" % ev["peer_fail_lines"],
             "peer closed lines: %d" % ev["peer_closed_lines"],
             "missed windows [start, end, count]: %s" % ev["missed_windows"],
             "overlapping windows: %s" % ev["overlapping_windows"],
             "--- verdict (OBSERVED) ---",
             "verdict: %s" % ev["verdict"],
             "reason: %s" % ev["reason"]]
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "detector-connectivity.log").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "detector-connectivity.json").write_text(
        json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
