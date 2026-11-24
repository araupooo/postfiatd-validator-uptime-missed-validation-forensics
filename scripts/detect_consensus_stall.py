#!/usr/bin/env python3
"""detect_consensus_stall.py — consensus-stall detector.

Usage: detect_consensus_stall.py [fixture-name]   (default: consensus-stall)
Reads fixtures/<name>.log + fixtures/<name>-ledger-state.json, applies
validation_lib.detect_consensus_stall(), writes
outputs/detector-consensus-stall.log and
outputs/detector-consensus-stall.json.

Rule: the engine's own 'Consensus detects as stalled with ...' error
lines (Consensus.h:1736-1743) present => CONSENSUS_STALL. A stalled
round cannot close a ledger, so no validation is issued for its
duration; rounds longer than ledgerABANDON_CONSENSUS (120 s,
ConsensusParms.h:113) are abandoned. This script is invoked by
scripts/run_all.sh.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation_lib import (DETECTORS, load_ledger_state,  # noqa: E402
                            parse_log)


def main(argv):
    name = argv[0] if argv else "consensus-stall"
    root = Path(__file__).resolve().parent.parent
    state = load_ledger_state(root / "fixtures" / ("%s-ledger-state.json" % name))
    events = parse_log(root / "fixtures" / ("%s.log" % name), state)
    events["_ledger_state"] = state
    ev = DETECTORS["consensus-stall"](events)
    lines = ["=== detector: consensus-stall ===",
             "fixture: %s (synthetic)" % name,
             "rule: 'Consensus detects as stalled' error lines from the "
             "engine (see docs/methodology.md)",
             "--- evidence ---",
             "stall lines: %d" % ev["stall_lines"]]
    for s in ev["stall_events"]:
        lines.append("  stall at %s: %d/%d proposers, %d stalled disputes"
                     % (s["at"], s["agree"], s["proposers"], s["stalled_disputes"]))
    lines.append("abandon threshold: %d s (ledgerABANDON_CONSENSUS)"
                 % ev["abandon_threshold_s"])
    lines.append("missed windows [start, end, count]: %s" % ev["missed_windows"])
    lines += ["--- verdict (OBSERVED) ---",
              "verdict: %s" % ev["verdict"],
              "reason: %s" % ev["reason"]]
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "detector-consensus-stall.log").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "detector-consensus-stall.json").write_text(
        json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
