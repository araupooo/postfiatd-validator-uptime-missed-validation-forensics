#!/usr/bin/env python3
"""detect_clock_skew.py — clock-skew detector.

Usage: detect_clock_skew.py [fixture-name]   (default: clock-skew)
Reads fixtures/<name>.log + fixtures/<name>-ledger-state.json, applies
validation_lib.detect_clock_skew(), writes
outputs/detector-clock-skew.log and outputs/detector-clock-skew.json.

Rule: a validation signTime outside the pinned acceptance window —
earlier than close time by more than validationCURRENT_EARLY (180 s,
Validations.h:71) or later than close time by more than
validationCURRENT_WALL (300 s, Validations.h:56) — or breaking
signTime monotonicity (RCLConsensus::validate(), RCLConsensus.cpp:821-824)
=> CLOCK_SKEW. This script is invoked by scripts/run_all.sh.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation_lib import (DETECTORS, load_ledger_state,  # noqa: E402
                            parse_log)


def main(argv):
    name = argv[0] if argv else "clock-skew"
    root = Path(__file__).resolve().parent.parent
    state = load_ledger_state(root / "fixtures" / ("%s-ledger-state.json" % name))
    events = parse_log(root / "fixtures" / ("%s.log" % name), state)
    events["_ledger_state"] = state
    ev = DETECTORS["clock-skew"](events)
    lines = ["=== detector: clock-skew ===",
             "fixture: %s (synthetic)" % name,
             "rule: signTime outside [close - 180 s, close + 300 s] or "
             "non-monotonic signTime (see docs/methodology.md)",
             "--- evidence ---",
             "validations checked: %d" % ev["validations_checked"],
             "flagged validations: %d" % ev["flagged_count"]]
    for f in ev["flagged"]:
        lines.append("  seq %d sign %s close %s offset %+d s"
                     % (f["seq"], f["sign_time"], f["close_time"], f["offset_s"]))
        for r in f["reasons"]:
            lines.append("    - %s" % r)
    lines += ["--- verdict (OBSERVED) ---",
              "verdict: %s" % ev["verdict"],
              "reason: %s" % ev["reason"]]
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "detector-clock-skew.log").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "detector-clock-skew.json").write_text(
        json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
