#!/usr/bin/env python3
"""validation_lib.py — shared parsing and detector logic for the
postfiatd validator uptime / missed-validation forensics pack.

All inputs are SYNTHETIC fixtures (see fixtures/README.md): log lines use
the JLOG message texts verbatim from postfiatd at the pinned commit, with
ISO-8601 UTC timestamps and a journal tag. Ledger state comes from the
committed JSON fixtures. Nothing here touches a live node or the network.

Definitions (see docs/methodology.md):
  - expected ledger: a ledger sequence listed in the fixture ledger state.
  - validated ledger: a sequence with a "CNF Val <hash>" line in the log
    (RCLConsensus.cpp:605 issues this line exactly when validate() runs).
  - missed validation: an expected sequence with a "CNF buildLCL" line but
    no "CNF Val" line (validate() is skipped when the node is not
    validating or canValidateSeq() refuses — RCLConsensus.cpp:601-608).
  - uptime: validated / expected, over the fixture window.
"""

import json
import re
import sys
from pathlib import Path

# Pinned postfiatd commit audited by this pack.
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"

# Timing parameters from the pinned source (see docs/source-inventory.md):
#   ValidationParms (Validations.h:56,64,71,79,89) and ConsensusParms
#   (ConsensusParms.h:51,59,66,69,72,79,82,86,95,99,102,105,113).
VALIDATION_CURRENT_WALL_S = 300    # 5 min, Validations.h:56
VALIDATION_CURRENT_LOCAL_S = 180   # 3 min, Validations.h:64
VALIDATION_CURRENT_EARLY_S = 180   # 3 min, Validations.h:71
VALIDATION_SET_EXPIRES_S = 600     # 10 min, Validations.h:79
VALIDATION_FRESHNESS_S = 20        # 20 s, Validations.h:89
PROPOSE_FRESHNESS_S = 20           # ConsensusParms.h:69
PROPOSE_INTERVAL_S = 12            # ConsensusParms.h:72
MIN_CONSENSUS_PCT = 67             # ConsensusParms.h:79
LEDGER_IDLE_INTERVAL_S = 15        # ConsensusParms.h:82
LEDGER_MIN_CONSENSUS_MS = 1950     # ConsensusParms.h:86
LEDGER_MAX_CONSENSUS_S = 15        # ConsensusParms.h:95
LEDGER_MIN_CLOSE_S = 2             # ConsensusParms.h:99
LEDGER_GRANULARITY_S = 1           # ConsensusParms.h:102
LEDGER_ABANDON_CONSENSUS_S = 120   # ConsensusParms.h:113
DISK_FREE_MINIMUM_MB = 512         # Node.cpp:1307-1309

# Log-line patterns. Message texts are verbatim from the pinned source;
# the timestamp + [Journal] prefix is the pack's synthetic log format
# (documented in fixtures/README.md).
TS = r"(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)"
RE_BUILD_LCL = re.compile(TS + r" \[RCLConsensus\] CNF buildLCL (?P<hash>[0-9a-f]{64})$")
RE_CNF_VAL = re.compile(TS + r" \[RCLConsensus\] CNF Val (?P<hash>[0-9a-f]{64})$")
RE_ENGINE_START = re.compile(TS + r" \[RCLConsensus\] Consensus engine started \(cookie: (?P<cookie>\d+)\)$")
RE_IDENTITY = re.compile(TS + r" \[RCLConsensus\] Validator identity: (?P<key>\S+)$")
RE_VALIDATE_NOKEYS = re.compile(
    TS + r" \[RCLConsensus\] RCLConsensus::Adaptor::validate: ValidatorKeys not set$")
RE_PROPOSE_NOKEYS = re.compile(
    TS + r" \[RCLConsensus\] RCLConsensus::Adaptor::propose: ValidatorKeys not set$")
RE_STALL = re.compile(
    TS + r" \[RCLConsensus\] Consensus detects as stalled with "
    r"(?P<agree>\d+)/(?P<proposers>\d+) proposers, and "
    r"(?P<disputes>\d+) stalled disputed transactions\.$")
RE_PEER_FAIL = re.compile(
    TS + r" \[Peer\] (?P<peer>\S+) failed: (?P<reason>.+)$")
RE_PEER_CLOSED = re.compile(TS + r" \[Peer\] Closed$")
RE_DISK_FATAL = re.compile(
    TS + r" \[Node\] Remaining free disk space is less than 512MB$")
RE_ANCESTOR = re.compile(
    TS + r" \[Validations\] Ledger (?P<seq>\d+):(?P<hash>[0-9a-f]{64}) "
    r"missing recent ancestor hashes$")
RE_RECORDING_VOTE = re.compile(
    TS + r" \[Validations\] RCLValidations: Recording vote with "
    r"(?P<keytype>master key|signing key): (?P<key>\S+) -> Account: (?P<account>\S+)$")
RE_NEED_LEDGER = re.compile(
    TS + r" \[RCLConsensus\] Need consensus ledger (?P<hash>[0-9a-f]{64})$")


def parse_iso(ts):
    """Parse an ISO-8601 UTC timestamp with milliseconds to epoch seconds."""
    from datetime import datetime, timezone
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=timezone.utc).timestamp()


def load_ledger_state(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_log(path, ledger_state):
    """Parse one fixture log against its ledger state.

    Returns a dict with every extracted event class. The hash->seq map
    comes from the ledger-state fixture, so a 'CNF Val <hash>' line is
    attributed to its ledger sequence without inventing log syntax.
    """
    hash_to_seq = {l["hash"]: l["seq"] for l in ledger_state["ledgers"]}
    seq_to_ledger = {l["seq"]: l for l in ledger_state["ledgers"]}
    events = {
        "log_path": str(path),
        "engine_starts": [],
        "validator_identity": [],
        "build_lcl": [],       # (ts, seq, hash)
        "cnf_val": [],         # (ts, seq, hash)
        "peer_fail": [],       # (ts, peer, reason)
        "peer_closed": [],     # (ts,)
        "stalls": [],          # (ts, agree, proposers, disputes)
        "disk_fatal": [],      # (ts,)
        "validate_nokeys": [],  # (ts,)
        "propose_nokeys": [],   # (ts,)
        "ancestor_missing": [],  # (ts, seq)
        "recording_votes": [],   # (ts, keytype, key, account)
        "need_ledger": [],       # (ts, hash)
        "unparsed": [],
    }
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if line.startswith("#"):
            # fixture/scenario file header: synthetic-data disclosure, not
            # a log line. Skipped, not counted as unparsed.
            continue
        m = RE_BUILD_LCL.match(line)
        if m:
            events["build_lcl"].append(
                (m.group("ts"), hash_to_seq.get(m.group("hash")), m.group("hash")))
            continue
        m = RE_CNF_VAL.match(line)
        if m:
            events["cnf_val"].append(
                (m.group("ts"), hash_to_seq.get(m.group("hash")), m.group("hash")))
            continue
        m = RE_ENGINE_START.match(line)
        if m:
            events["engine_starts"].append((m.group("ts"), m.group("cookie")))
            continue
        m = RE_IDENTITY.match(line)
        if m:
            events["validator_identity"].append((m.group("ts"), m.group("key")))
            continue
        m = RE_VALIDATE_NOKEYS.match(line)
        if m:
            events["validate_nokeys"].append((m.group("ts"),))
            continue
        m = RE_PROPOSE_NOKEYS.match(line)
        if m:
            events["propose_nokeys"].append((m.group("ts"),))
            continue
        m = RE_STALL.match(line)
        if m:
            events["stalls"].append((m.group("ts"), int(m.group("agree")),
                                     int(m.group("proposers")),
                                     int(m.group("disputes"))))
            continue
        m = RE_PEER_FAIL.match(line)
        if m:
            events["peer_fail"].append(
                (m.group("ts"), m.group("peer"), m.group("reason")))
            continue
        m = RE_PEER_CLOSED.match(line)
        if m:
            events["peer_closed"].append((m.group("ts"),))
            continue
        m = RE_DISK_FATAL.match(line)
        if m:
            events["disk_fatal"].append((m.group("ts"),))
            continue
        m = RE_ANCESTOR.match(line)
        if m:
            events["ancestor_missing"].append((m.group("ts"), int(m.group("seq"))))
            continue
        m = RE_RECORDING_VOTE.match(line)
        if m:
            events["recording_votes"].append(
                (m.group("ts"), m.group("keytype"), m.group("key"),
                 m.group("account")))
            continue
        m = RE_NEED_LEDGER.match(line)
        if m:
            events["need_ledger"].append((m.group("ts"), m.group("hash")))
            continue
        events["unparsed"].append((n, line))

    expected = sorted(seq_to_ledger)
    validated = sorted({s for (_ts, s, _h) in events["cnf_val"] if s is not None})
    built = sorted({s for (_ts, s, _h) in events["build_lcl"] if s is not None})
    missed = [s for s in expected if s not in set(validated)]
    # Missed-with-build evidence: seqs that were built (closed) but never
    # validated. A seq absent from both lists is a gap in the fixture
    # itself and is reported separately, never silently counted.
    missed_with_build = [s for s in missed if s in set(built)]
    gaps_no_build = [s for s in missed if s not in set(built)]
    # Maximal runs of consecutive missed sequences (windows).
    windows = []
    for s in missed:
        if windows and s == windows[-1][-1] + 1:
            windows[-1].append(s)
        else:
            windows.append([s])
    summary = {
        "expected_ledgers": len(expected),
        "built_ledgers": len(built),
        "validated_ledgers": len(validated),
        "missed_validations": len(missed),
        "missed_with_build": len(missed_with_build),
        "gaps_no_build": gaps_no_build,
        "missed_sequences": missed,
        "missed_windows": [[w[0], w[-1], len(w)] for w in windows],
        "uptime_pct": round(100.0 * len(validated) / len(expected), 4)
        if expected else None,
        "first_seq": expected[0] if expected else None,
        "last_seq": expected[-1] if expected else None,
    }
    # Consistency check: the ledger-state JSON's validated flags must agree
    # with the log's CNF Val lines. Any disagreement is reported, not hidden.
    json_validated = sorted(l["seq"] for l in ledger_state["ledgers"]
                            if l.get("validated"))
    summary["json_log_agree"] = (json_validated == validated)
    if json_validated != validated:
        summary["json_validated_not_in_log"] = sorted(
            set(json_validated) - set(validated))
        summary["log_validated_not_in_json"] = sorted(
            set(validated) - set(json_validated))
    events["summary"] = summary
    return events


def missed_windows(events):
    """Maximal runs of consecutive missed sequences as (start, end, count)."""
    return [tuple(w) for w in events["summary"]["missed_windows"]]


# ---------------------------------------------------------------- detectors

def detect_connectivity(events):
    """Connectivity loss: peer disconnect/fail events overlapping a
    missed-validation window, with the peer set dropping to zero.

    Primary source: PeerImp::close() increments the disconnect counter and
    logs 'Closed' (PeerImp.cpp:596-616); PeerImp::fail() logs
    '<peer> failed: <reason>' (PeerImp.cpp:620-638). A validator that loses
    all peers cannot receive proposals, so consensus cannot close ledgers
    locally and validations stop (ConsensusParms.h ledgerMIN_CONSENSUS).
    """
    fails = events["peer_fail"]
    closed = events["peer_closed"]
    windows = missed_windows(events)
    evidence = {
        "peer_fail_lines": len(fails),
        "peer_closed_lines": len(closed),
        "missed_windows": windows,
        "overlapping_windows": [],
    }
    for (start, end, count) in windows:
        lo = parse_iso(next(
            (l["close_time"] for l in _ledgers(events) if l["seq"] == start),
            "1970-01-01T00:00:00.000Z"))
        hi = parse_iso(next(
            (l["close_time"] for l in _ledgers(events) if l["seq"] == end),
            "1970-01-01T00:00:00.000Z"))
        overlapping = [f for f in fails + [(t,) for (t,) in closed]
                       if lo - 30 <= parse_iso(f[0]) <= hi + 30]
        if overlapping:
            evidence["overlapping_windows"].append({
                "window": [start, end, count],
                "peer_events_in_window": len(overlapping),
                "first_peer_event": overlapping[0][0],
            })
    hit = bool(evidence["overlapping_windows"]) and bool(fails or closed)
    evidence["verdict"] = ("CONNECTIVITY_LOSS" if hit else "NO_CONNECTIVITY_LOSS")
    evidence["reason"] = (
        "Peer disconnect/fail lines overlap a missed-validation window."
        if hit else
        "No peer disconnect/fail line overlaps any missed-validation window.")
    return evidence


def _ledgers(events):
    return events.get("_ledger_state", {}).get("ledgers", [])


def detect_clock_skew(events):
    """Clock skew: validation signTime outside the acceptance window.

    Primary source: ValidationParms (Validations.h:56,64,71) — a validation
    is current only within validationCURRENT_EARLY (180 s before close) and
    validationCURRENT_WALL (300 s after close); RCLConsensus::validate()
    (RCLConsensus.cpp:821-824) forces signTime monotonic by bumping it to
    lastValidationTime_ + 1 s, so a jumped clock shows up as a signTime
    step plus stale rejections. Also checks the increasing-sequence
    invariant (SeqEnforcer, Validations.h:92-133).
    """
    ledgers = _ledgers(events)
    flagged = []
    prev_sign = None
    prev_sign_str = None
    prev_seq = None
    for l in ledgers:
        close = parse_iso(l["close_time"])
        sign = parse_iso(l["sign_time"])
        offset = sign - close
        reasons = []
        if offset < -VALIDATION_CURRENT_EARLY_S:
            reasons.append(
                "signTime %d s before close time (earlier than "
                "validationCURRENT_EARLY=%d s)" % (int(offset),
                                                   VALIDATION_CURRENT_EARLY_S))
        if offset > VALIDATION_CURRENT_WALL_S:
            reasons.append(
                "signTime %d s after close time (later than "
                "validationCURRENT_WALL=%d s)" % (int(offset),
                                                 VALIDATION_CURRENT_WALL_S))
        if prev_sign is not None and sign <= prev_sign:
            reasons.append(
                "signTime not monotonic vs seq %d (signTime %s <= previous %s)"
                % (prev_seq, l["sign_time"], prev_sign_str))
        if reasons:
            flagged.append({"seq": l["seq"], "sign_time": l["sign_time"],
                            "close_time": l["close_time"],
                            "offset_s": int(offset), "reasons": reasons})
        prev_sign = sign
        prev_sign_str = l["sign_time"]
        prev_seq = l["seq"]
    evidence = {
        "validations_checked": len(ledgers),
        "flagged": flagged,
        "flagged_count": len(flagged),
    }
    evidence["verdict"] = "CLOCK_SKEW" if flagged else "NO_CLOCK_SKEW"
    evidence["reason"] = (
        "%d of %d validations have signTime outside the pinned acceptance "
        "window (early >%d s or wall >%d s) or break signTime monotonicity."
        % (len(flagged), len(ledgers), VALIDATION_CURRENT_EARLY_S,
           VALIDATION_CURRENT_WALL_S) if flagged else
        "All validation signTimes are inside the pinned acceptance window "
        "and monotonic.")
    return evidence


def detect_resource(events):
    """Resource exhaustion: the fatal low-disk line and its aftermath.

    Primary source: dbHasSpace() (Node.cpp:1301-1311) logs at fatal level
    'Remaining free disk space is less than 512MB' when available space
    drops below 512 MB and refuses to start the database. A node that
    cannot write stops validating: missed validations after the fatal
    line are attributed to resource exhaustion.
    """
    fatals = events["disk_fatal"]
    windows = missed_windows(events)
    after = []
    for (ts,) in fatals:
        t = parse_iso(ts)
        ledgers = _ledgers(events)
        after_seqs = [l["seq"] for l in ledgers
                      if parse_iso(l["close_time"]) >= t
                      and l["seq"] in set(events["summary"]["missed_sequences"])]
        after.append({"fatal_at": ts, "missed_after_fatal": len(after_seqs),
                      "missed_sequences": after_seqs})
    evidence = {
        "disk_fatal_lines": len(fatals),
        "fatal_events": after,
        "missed_windows": windows,
    }
    hit = bool(fatals) and any(a["missed_after_fatal"] > 0 for a in after)
    evidence["verdict"] = ("RESOURCE_EXHAUSTION" if hit else "NO_RESOURCE_EXHAUSTION")
    evidence["reason"] = (
        "Fatal low-disk line present and %d validation(s) missed after it."
        % sum(a["missed_after_fatal"] for a in after) if hit else
        "No fatal low-disk line, or no missed validation after it.")
    return evidence


def detect_config(events):
    """Configuration error: validator keys missing at startup.

    Primary source: RCLConsensus::Adaptor::propose() warns
    'RCLConsensus::Adaptor::propose: ValidatorKeys not set'
    (RCLConsensus.cpp:231) and validate() warns the same and returns
    without issuing a validation (RCLConsensus.cpp:826-830); the engine
    logs 'Validator identity: ...' at startup only when keys are
    configured (RCLConsensus.cpp:107-112). Config sections are
    [validation_seed] / [validator_token] (ConfigSections.h:89,96).
    """
    identity = events["validator_identity"]
    v_warn = events["validate_nokeys"]
    p_warn = events["propose_nokeys"]
    validated = events["summary"]["validated_ledgers"]
    expected = events["summary"]["expected_ledgers"]
    evidence = {
        "validator_identity_lines": len(identity),
        "validate_nokeys_warnings": len(v_warn),
        "propose_nokeys_warnings": len(p_warn),
        "validated_ledgers": validated,
        "expected_ledgers": expected,
    }
    hit = (len(identity) == 0 and (v_warn or p_warn) and validated == 0)
    evidence["verdict"] = "CONFIG_ERROR" if hit else "NO_CONFIG_ERROR"
    evidence["reason"] = (
        "No 'Validator identity' line at startup, ValidatorKeys warnings "
        "present, and 0 of %d expected validations issued."
        % expected if hit else
        "Validator identity is configured or validations are being issued.")
    return evidence


def detect_consensus_stall(events):
    """Consensus stall: the engine's own stall detector firing.

    Primary source: Consensus::checkConsensus / dispute stall logic
    (Consensus.h:1722-1744) logs at error level
    'Consensus detects as stalled with <agree>/<proposers> proposers, and
    <n> stalled disputed transactions.' A stalled round cannot close a
    ledger, so no new validation is issued for its duration; rounds
    longer than ledgerABANDON_CONSENSUS (120 s, ConsensusParms.h:113)
    are abandoned. Also reports rounds implied by missed windows.
    """
    stalls = events["stalls"]
    windows = missed_windows(events)
    evidence = {
        "stall_lines": len(stalls),
        "stall_events": [
            {"at": ts, "agree": a, "proposers": p, "stalled_disputes": d}
            for (ts, a, p, d) in stalls],
        "missed_windows": windows,
        "abandon_threshold_s": LEDGER_ABANDON_CONSENSUS_S,
    }
    hit = bool(stalls)
    evidence["verdict"] = "CONSENSUS_STALL" if hit else "NO_CONSENSUS_STALL"
    evidence["reason"] = (
        "%d stall line(s) from the consensus engine; missed-validation "
        "windows during the stall: %s."
        % (len(stalls), windows) if hit else
        "No stall line from the consensus engine.")
    return evidence


DETECTORS = {
    "connectivity": detect_connectivity,
    "clock-skew": detect_clock_skew,
    "resource": detect_resource,
    "config": detect_config,
    "consensus-stall": detect_consensus_stall,
}


def main(argv):
    print("validation_lib is a library; run parse_validations.py, "
          "detect_<class>.py, or simulate_scenarios.py", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
