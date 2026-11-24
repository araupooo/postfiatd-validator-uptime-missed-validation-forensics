#!/usr/bin/env python3
"""parse_validations.py — harness: extract validation events, missed
validations, and uptime windows from a fixture log + ledger state.

Usage: parse_validations.py <fixture-name>
  reads  fixtures/<name>.log and fixtures/<name>-ledger-state.json
  writes outputs/parse-<name>.log (human-readable, unedited)
         outputs/parse-<name>.json (machine-readable summary)

Definitions (docs/methodology.md): a validation is issued when the log
has a 'CNF Val <hash>' line (RCLConsensus.cpp:605); a missed validation
is an expected ledger sequence with a 'CNF buildLCL' line but no
'CNF Val' line. Uptime = validated / expected.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation_lib import load_ledger_state, parse_log  # noqa: E402


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv):
    if len(argv) != 1:
        print("usage: parse_validations.py <fixture-name>", file=sys.stderr)
        return 2
    name = argv[0]
    root = Path(__file__).resolve().parent.parent
    log_path = root / "fixtures" / ("%s.log" % name)
    state_path = root / "fixtures" / ("%s-ledger-state.json" % name)
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    state = load_ledger_state(state_path)
    events = parse_log(log_path, state)
    # Record the input path relative to the pack root so the output is
    # identical no matter where the pack is checked out.
    events["log_path"] = "fixtures/%s.log" % name
    events["_ledger_state"] = state
    s = events["summary"]
    lines = []
    lines.append("=== parse_validations: fixture %s ===" % name)
    lines.append("input log:    fixtures/%s.log" % name)
    lines.append("  sha256: %s" % sha256_file(log_path))
    lines.append("input state:  fixtures/%s-ledger-state.json" % name)
    lines.append("  sha256: %s" % sha256_file(state_path))
    lines.append("synthetic fixture: %s" % state.get("synthetic"))
    lines.append("pinned commit: %s" % state.get("pinned_commit"))
    lines.append("--- event counts ---")
    lines.append("engine starts: %d" % len(events["engine_starts"]))
    lines.append("validator identity lines: %d" % len(events["validator_identity"]))
    lines.append("buildLCL lines: %d" % len(events["build_lcl"]))
    lines.append("CNF Val lines: %d" % len(events["cnf_val"]))
    lines.append("recording-vote lines: %d" % len(events["recording_votes"]))
    lines.append("peer fail lines: %d" % len(events["peer_fail"]))
    lines.append("peer closed lines: %d" % len(events["peer_closed"]))
    lines.append("stall lines: %d" % len(events["stalls"]))
    lines.append("disk fatal lines: %d" % len(events["disk_fatal"]))
    lines.append("validate ValidatorKeys warnings: %d" % len(events["validate_nokeys"]))
    lines.append("propose ValidatorKeys warnings: %d" % len(events["propose_nokeys"]))
    lines.append("ancestor-missing warnings: %d" % len(events["ancestor_missing"]))
    lines.append("need-ledger warnings: %d" % len(events["need_ledger"]))
    lines.append("unparsed lines: %d" % len(events["unparsed"]))
    for (n, line) in events["unparsed"]:
        lines.append("  UNPARSED line %d: %s" % (n, line))
    lines.append("--- validation summary (OBSERVED: parser behaviour on this fixture) ---")
    lines.append("expected ledgers: %d (seq %s..%s)"
                 % (s["expected_ledgers"], s["first_seq"], s["last_seq"]))
    lines.append("built ledgers (CNF buildLCL): %d" % s["built_ledgers"])
    lines.append("validated ledgers (CNF Val): %d" % s["validated_ledgers"])
    lines.append("missed validations: %d" % s["missed_validations"])
    lines.append("missed with buildLCL evidence: %d" % s["missed_with_build"])
    lines.append("missed sequences: %s" % (s["missed_sequences"] or "none"))
    lines.append("missed windows [start, end, count]: %s"
                 % (s["missed_windows"] or "none"))
    lines.append("uptime: %.4f%%" % s["uptime_pct"])
    lines.append("ledger-state JSON agrees with log: %s" % s["json_log_agree"])
    if not s["json_log_agree"]:
        lines.append("  json-validated-not-in-log: %s"
                     % s.get("json_validated_not_in_log"))
        lines.append("  log-validated-not-in-json: %s"
                     % s.get("log_validated_not_in_json"))
    if s["gaps_no_build"]:
        lines.append("WARNING gaps with no buildLCL line: %s" % s["gaps_no_build"])
    text = "\n".join(lines) + "\n"
    (out_dir / ("parse-%s.log" % name)).write_text(text, encoding="utf-8")
    serialisable = {k: v for k, v in events.items() if k != "_ledger_state"}
    (out_dir / ("parse-%s.json" % name)).write_text(
        json.dumps(serialisable, indent=2, default=str) + "\n", encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
