#!/usr/bin/env python3
"""detect_resource.py — resource-exhaustion detector.

Usage: detect_resource.py [fixture-name]   (default: resource-exhaustion)
Reads fixtures/<name>.log + fixtures/<name>-ledger-state.json, applies
validation_lib.detect_resource(), writes
outputs/detector-resource.log and outputs/detector-resource.json.

Rule: the fatal 'Remaining free disk space is less than 512MB' line
(dbHasSpace(), Node.cpp:1301-1311) followed by missed validations
=> RESOURCE_EXHAUSTION. This script is invoked by scripts/run_all.sh.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation_lib import (DETECTORS, load_ledger_state,  # noqa: E402
                            parse_log)


def main(argv):
    name = argv[0] if argv else "resource-exhaustion"
    root = Path(__file__).resolve().parent.parent
    state = load_ledger_state(root / "fixtures" / ("%s-ledger-state.json" % name))
    events = parse_log(root / "fixtures" / ("%s.log" % name), state)
    events["_ledger_state"] = state
    ev = DETECTORS["resource"](events)
    lines = ["=== detector: resource-exhaustion ===",
             "fixture: %s (synthetic)" % name,
             "rule: fatal low-disk line (Node.cpp:1309) followed by missed "
             "validations (see docs/methodology.md)",
             "--- evidence ---",
             "disk fatal lines: %d" % ev["disk_fatal_lines"]]
    for f in ev["fatal_events"]:
        lines.append("  fatal at %s: %d missed after it: %s"
                     % (f["fatal_at"], f["missed_after_fatal"],
                        f["missed_sequences"] or "none"))
    lines.append("missed windows [start, end, count]: %s" % ev["missed_windows"])
    lines += ["--- verdict (OBSERVED) ---",
              "verdict: %s" % ev["verdict"],
              "reason: %s" % ev["reason"]]
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "detector-resource.log").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "detector-resource.json").write_text(
        json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
