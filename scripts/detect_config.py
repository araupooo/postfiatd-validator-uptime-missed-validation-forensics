#!/usr/bin/env python3
"""detect_config.py — configuration-error detector.

Usage: detect_config.py [fixture-name]   (default: config-error)
Reads fixtures/<name>.log + fixtures/<name>-ledger-state.json, applies
validation_lib.detect_config(), writes
outputs/detector-config.log and outputs/detector-config.json.

Rule: no 'Validator identity' line at startup (RCLConsensus.cpp:107-112)
AND 'ValidatorKeys not set' warnings from propose()/validate()
(RCLConsensus.cpp:231, 826-830) AND zero validations issued
=> CONFIG_ERROR. Config sections: [validation_seed] / [validator_token]
(ConfigSections.h:89,96). This script is invoked by scripts/run_all.sh.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation_lib import (DETECTORS, load_ledger_state,  # noqa: E402
                            parse_log)


def main(argv):
    name = argv[0] if argv else "config-error"
    root = Path(__file__).resolve().parent.parent
    state = load_ledger_state(root / "fixtures" / ("%s-ledger-state.json" % name))
    events = parse_log(root / "fixtures" / ("%s.log" % name), state)
    events["_ledger_state"] = state
    ev = DETECTORS["config"](events)
    lines = ["=== detector: config-error ===",
             "fixture: %s (synthetic)" % name,
             "rule: no Validator identity + ValidatorKeys warnings + zero "
             "validations (see docs/methodology.md)",
             "--- evidence ---",
             "validator identity lines: %d" % ev["validator_identity_lines"],
             "validate ValidatorKeys warnings: %d" % ev["validate_nokeys_warnings"],
             "propose ValidatorKeys warnings: %d" % ev["propose_nokeys_warnings"],
             "validated ledgers: %d of %d expected"
             % (ev["validated_ledgers"], ev["expected_ledgers"]),
             "--- verdict (OBSERVED) ---",
             "verdict: %s" % ev["verdict"],
             "reason: %s" % ev["reason"]]
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "detector-config.log").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "detector-config.json").write_text(
        json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
