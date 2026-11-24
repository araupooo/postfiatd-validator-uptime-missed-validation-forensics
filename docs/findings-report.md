# Findings report — OBSERVED detector results on fixtures

All numbers below are **OBSERVED**: parser and detector behaviour on
the synthetic fixtures in `fixtures/` (120 ledgers each, seq
900000–900119, nominal 4 s close interval). Raw outputs:
`outputs/parse-*.log`, `outputs/detector-*.log`, `outputs/detector-*.json`.
Scenario numbers are SIMULATED and live in `outputs/matrix.md`, not
here.

## Fixture parses

| Fixture | Expected | Built | Validated | Missed | Missed seqs | Uptime |
|---|---:|---:|---:|---:|---|---:|
| baseline-healthy | 120 | 120 | 120 | 0 | — | 100.0000% |
| connectivity-loss | 120 | 120 | 95 | 25 | 900050–900074 | 79.1667% |
| clock-skew | 120 | 120 | 120 | 0 | — (see detector) | 100.0000% |
| resource-exhaustion | 120 | 120 | 90 | 30 | 900060–900089 | 75.0000% |
| config-error | 120 | 120 | 0 | 120 | 900000–900119 | 0.0000% |
| consensus-stall | 120 | 120 | 100 | 20 | 900030–900039, 900070–900079 | 83.3333% |

Every parse reports 0 unparsed lines and "ledger-state JSON agrees
with log: True" (see `outputs/parse-*.log`).

## Detector verdicts

### 1. Connectivity loss — CONNECTIVITY_LOSS

- Fixture: `connectivity-loss`. Evidence: `outputs/detector-connectivity.log`.
- 12 peer `failed: Connection reset by peer` lines + 12 `Closed`
  lines at 2026-11-20T00:03:20.000Z, overlapping missed window
  [900050, 900074, 25]. 24 peer events inside the window.
- Missed window is exactly the partition: validations resume at seq
  900075 with no further peer events.

### 2. Clock skew — CLOCK_SKEW

- Fixture: `clock-skew`. Evidence: `outputs/detector-clock-skew.log`.
- 21 of 120 validations flagged:
  - 20 validations (seqs 900040–900059) with signTime offset **+400 s**
    vs close time — beyond `validationCURRENT_WALL` (300 s,
    `Validations.h:56` / `ConsensusParms.h:51`), so peers would treat
    them as stale.
  - 1 validation (seq 900060) breaking signTime monotonicity: its
    signTime (00:04:00Z) is earlier than the previous validation's
    signTime (00:07:16Z) after the clock jumps back — the condition
    `validate()` guards with the `lastValidationTime_ + 1 s` bump
    (`RCLConsensus.cpp:821-824`).
- Note the local view: all 120 validations were issued locally
  (uptime 100% in the parse). The skew is a **network-acceptance**
  failure, not a local-issuance failure. The +200 s offset originally
  modelled for this fixture was inside the pinned acceptance window
  ([−180 s, +300 s]) and correctly produced **zero** flags — the
  fixture was corrected to +400 s so the skew is actually detectable
  under the pinned parameters. That correction is documented here,
  not hidden.

### 3. Resource exhaustion — RESOURCE_EXHAUSTION

- Fixture: `resource-exhaustion`. Evidence: `outputs/detector-resource.log`.
- 1 fatal line `Remaining free disk space is less than 512MB` at
  2026-11-20T00:04:00.000Z (`Node.cpp:1309`); 30 validations missed
  after it (seqs 900060–900089), resuming at 900090.

### 4. Configuration error — CONFIG_ERROR

- Fixture: `config-error`. Evidence: `outputs/detector-config.log`.
- 0 `Validator identity` lines at startup; 120 `validate:
  ValidatorKeys not set` warnings and 120 `propose: ValidatorKeys
  not set` warnings; 0 of 120 expected validations issued.
- This is the worst case in the fixture set: a validator that closes
  ledgers but never validates is indistinguishable from offline to the
  network, while its own log looks busy (`CNF buildLCL` on every
  ledger).

### 5. Consensus stall — CONSENSUS_STALL

- Fixture: `consensus-stall`. Evidence: `outputs/detector-consensus-stall.log`.
- 2 stall lines (`3/12 proposers, 2 stalled disputed transactions`)
  at 2026-11-20T00:02:00.000Z and 00:04:40.000Z; missed windows
  [900030, 900039, 10] and [900070, 900079, 10] — 20 missed in total.
- Stall threshold reference: rounds longer than
  `ledgerABANDON_CONSENSUS` (120 s, `ConsensusParms.h:113`) are
  abandoned; the fixture's 10-ledger (40 s) stall windows are below
  that threshold, so the engine keeps disputing rather than
  abandoning — the missed validations are the observable cost.

## Cross-fixture reading

- The parser's missed-validation definition (built but not validated)
  separates cleanly across classes: every fixture's missed count
  equals the modelled fault duration divided by the 4 s close
  interval (25 = 100 s partition, 30 = 120 s halt, 20 = 2 × 40 s
  stalls, 120 = fully unconfigured).
- The clock-skew fixture is the only one where local uptime (100%)
  and network-accepted uptime diverge. Any monitoring that counts
  only locally issued validations would report this node healthy
  while the network rejects its validations. That is the single most
  important operational finding in this pack: **count accepted
  validations, not issued ones**.
- The config-error fixture shows the opposite failure mode: the node
  is fully up (ledgers close, peers connected) and validates nothing.
  Uptime measured from process liveness alone would also report it
  healthy.
