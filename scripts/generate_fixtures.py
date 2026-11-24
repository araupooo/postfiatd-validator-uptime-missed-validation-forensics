#!/usr/bin/env python3
"""generate_fixtures.py — generate the synthetic log + ledger-state
fixtures for the validator uptime / missed-validation forensics pack.

Deterministic: every byte is derived from fixed parameters below; no
wall-clock time, no randomness, no network. Re-running produces
byte-identical fixtures (verified by run_all.sh via SHA-256).

SYNTHETIC-DATA DISCLOSURE: these fixtures are NOT real node logs. They
are synthetic logs whose message texts are verbatim JLOG strings from
postfiatd at the pinned commit (see fixtures/README.md for the
line-by-line source of every message format), with synthetic timestamps,
hashes, peer addresses (TEST-NET-3 203.0.113.0/24) and node keys. They
exist so the harness and detectors can be run and reproduced by anyone
without a live validator. Every claim in this pack that rests on these
fixtures is labelled OBSERVED (parser/detector behaviour on the
fixtures); scenario numbers are labelled SIMULATED.
"""

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_TIME = datetime(2026, 11, 20, 0, 0, 0, tzinfo=timezone.utc)
CLOSE_INTERVAL_S = 4          # nominal ledger close interval (model assumption)
FIRST_SEQ = 900000
N_LEDGERS = 120
COOKIE = 987654321
NODE_KEY = "n9SyntheticValidatorIdentity0000000000000000000"
NODE_ACCOUNT = "rSyntheticValidatorAccount0000000000000"
PEERS = ["203.0.113.%d:2559" % i for i in range(1, 13)]  # TEST-NET-3

PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"


def fmt(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (ts.microsecond // 1000)


def ledger_hash(seq):
    return hashlib.sha256(("postfiatd-ledger-%d" % seq).encode()).hexdigest()


def close_time(seq):
    return BASE_TIME + timedelta(seconds=CLOSE_INTERVAL_S * (seq - FIRST_SEQ))


def build_ledger_state(name, validated, sign_offsets):
    """validated: set of seqs the local node validates.
    sign_offsets: dict seq -> signTime offset in seconds vs close time."""
    ledgers = []
    for seq in range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS):
        ct = close_time(seq)
        st = ct + timedelta(seconds=sign_offsets.get(seq, 0))
        ledgers.append({
            "seq": seq,
            "hash": ledger_hash(seq),
            "close_time": fmt(ct),
            "sign_time": fmt(st),
            "validated": seq in validated,
        })
    return {
        "fixture": name,
        "synthetic": True,
        "generated_by": "scripts/generate_fixtures.py",
        "pinned_commit": PINNED_COMMIT,
        "base_close_time": fmt(BASE_TIME),
        "close_interval_s": CLOSE_INTERVAL_S,
        "first_seq": FIRST_SEQ,
        "ledgers": ledgers,
    }


def emit(lines, out_path):
    text = "\n".join(lines) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def header(name):
    return [
        "# SYNTHETIC FIXTURE — not a real node log. See fixtures/README.md.",
        "# fixture: %s" % name,
        "# pinned postfiatd commit: %s" % PINNED_COMMIT,
    ]


def engine_start(ts):
    return [
        "%s [RCLConsensus] Consensus engine started (cookie: %d)"
        % (fmt(ts), COOKIE),
        "%s [RCLConsensus] Validator identity: %s" % (fmt(ts), NODE_KEY),
    ]


def ledger_lines(seq, validated, state):
    """The two lines a closed ledger produces in the log. CNF Val appears
    only when validate() runs (RCLConsensus.cpp:601-608)."""
    ct = fmt(close_time(seq))
    h = ledger_hash(seq)
    lines = ["%s [RCLConsensus] CNF buildLCL %s" % (ct, h)]
    if validated:
        lines.append("%s [RCLConsensus] CNF Val %s" % (ct, h))
        lines.append(
            "%s [Validations] RCLValidations: Recording vote with signing key: "
            "%s -> Account: %s" % (ct, NODE_KEY, NODE_ACCOUNT))
    return lines


def build_baseline():
    name = "baseline-healthy"
    validated = set(range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS))
    state = build_ledger_state(name, validated, {})
    lines = header(name)
    lines += engine_start(BASE_TIME - timedelta(seconds=5))
    for seq in range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS):
        lines += ledger_lines(seq, True, state)
    return name, state, lines


def build_connectivity():
    name = "connectivity-loss"
    gap = set(range(900050, 900075))  # 25 ledgers, 100 s partition
    validated = set(range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS)) - gap
    state = build_ledger_state(name, validated, {})
    lines = header(name)
    lines += engine_start(BASE_TIME - timedelta(seconds=5))
    for seq in range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS):
        ct = close_time(seq)
        if seq == 900050:
            # PeerImp::fail() (PeerImp.cpp:620-638) then close() (596-616).
            for peer in PEERS:
                lines.append(
                    "%s [Peer] %s failed: Connection reset by peer"
                    % (fmt(ct), peer))
                lines.append("%s [Peer] Closed" % fmt(ct))
            lines.append(
                "%s [RCLConsensus] Need consensus ledger %s"
                % (fmt(ct), ledger_hash(seq)))
        lines += ledger_lines(seq, seq in validated, state)
    return name, state, lines


def build_clock_skew():
    name = "clock-skew"
    # Local clock jumps +400 s for 20 ledgers. The node still issues
    # validations (CNF Val lines present), but their signTime is outside
    # the pinned acceptance window (validationCURRENT_EARLY=180 s,
    # validationCURRENT_WALL=300 s: +400 s exceeds the 300 s wall) and
    # breaks signTime monotonicity when the clock jumps back at seq 900060.
    skew = {seq: 400 for seq in range(900040, 900060)}
    validated = set(range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS))
    state = build_ledger_state(name, validated, skew)
    lines = header(name)
    lines += engine_start(BASE_TIME - timedelta(seconds=5))
    for seq in range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS):
        lines += ledger_lines(seq, True, state)
    return name, state, lines


def build_resource():
    name = "resource-exhaustion"
    gap = set(range(900060, 900090))  # 30 ledgers, 120 s halted
    validated = set(range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS)) - gap
    state = build_ledger_state(name, validated, {})
    lines = header(name)
    lines += engine_start(BASE_TIME - timedelta(seconds=5))
    for seq in range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS):
        ct = close_time(seq)
        if seq == 900060:
            # dbHasSpace() fatal (Node.cpp:1301-1311).
            lines.append(
                "%s [Node] Remaining free disk space is less than 512MB"
                % fmt(ct))
        lines += ledger_lines(seq, seq in validated, state)
    return name, state, lines


def build_config():
    name = "config-error"
    # No validator keys configured: no 'Validator identity' line, and
    # propose()/validate() warn on every ledger (RCLConsensus.cpp:231,
    # RCLConsensus.cpp:826-830). Ledgers still close (buildLCL) but no
    # validation is ever issued.
    validated = set()
    state = build_ledger_state(name, validated, {})
    lines = header(name)
    lines.append(
        "%s [RCLConsensus] Consensus engine started (cookie: %d)"
        % (fmt(BASE_TIME - timedelta(seconds=5)), COOKIE))
    for seq in range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS):
        ct = fmt(close_time(seq))
        lines.append(
            "%s [RCLConsensus] RCLConsensus::Adaptor::propose: "
            "ValidatorKeys not set" % ct)
        lines.append(
            "%s [RCLConsensus] RCLConsensus::Adaptor::validate: "
            "ValidatorKeys not set" % ct)
        lines += ledger_lines(seq, False, state)
    return name, state, lines


def build_stall():
    name = "consensus-stall"
    gap = set(range(900030, 900040)) | set(range(900070, 900080))
    validated = set(range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS)) - gap
    state = build_ledger_state(name, validated, {})
    lines = header(name)
    lines += engine_start(BASE_TIME - timedelta(seconds=5))
    for seq in range(FIRST_SEQ, FIRST_SEQ + N_LEDGERS):
        ct = close_time(seq)
        if seq in (900030, 900070):
            # Consensus::checkConsensus stall path (Consensus.h:1736-1743).
            lines.append(
                "%s [RCLConsensus] Consensus detects as stalled with 3/12 "
                "proposers, and 2 stalled disputed transactions." % fmt(ct))
        lines += ledger_lines(seq, seq in validated, state)
    return name, state, lines


BUILDERS = [build_baseline, build_connectivity, build_clock_skew,
            build_resource, build_config, build_stall]


def main(argv):
    root = Path(__file__).resolve().parent.parent
    fixtures = root / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    for build in BUILDERS:
        name, state, lines = build()
        log_path = fixtures / ("%s.log" % name)
        json_path = fixtures / ("%s-ledger-state.json" % name)
        log_sha = emit(lines, log_path)
        json_text = json.dumps(state, indent=2) + "\n"
        json_path.write_text(json_text, encoding="utf-8")
        json_sha = hashlib.sha256(json_text.encode()).hexdigest()
        print("fixture %s: %d log lines, %d ledgers" %
              (name, len(lines), len(state["ledgers"])))
        print("  sha256 %s  fixtures/%s.log" % (log_sha, name))
        print("  sha256 %s  fixtures/%s-ledger-state.json" % (json_sha, name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
