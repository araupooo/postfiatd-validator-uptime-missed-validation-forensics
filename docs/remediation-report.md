# Operator remediation report — severity-ranked

Severity is ranked by blast radius (how many validations the fault
silently removes) and by detectability (whether the operator would
notice without this pack's detectors). Each item names the detector
that catches it, the log signature, and the fix. All source citations
are to the pinned commit (`0085a1ff885d6a446369cf73a4430f75af22be55`;
see `docs/source-inventory.md`).

## P0 — silent total validation loss

### P0-1. Validator keys not configured (config-error)

- **Blast radius:** 120/120 validations missed (uptime 0%) while the
  node otherwise looks healthy: ledgers close, peers are connected,
  no fatal line is emitted.
- **Signature:** no `Validator identity:` line after `Consensus engine
  started` (`RCLConsensus.cpp:107-112`); `RCLConsensus::Adaptor::propose:
  ValidatorKeys not set` (`RCLConsensus.cpp:231`) and
  `RCLConsensus::Adaptor::validate: ValidatorKeys not set`
  (`RCLConsensus.cpp:826-830`) on every ledger.
- **Detector:** `scripts/detect_config.py` → `CONFIG_ERROR`
  (fixture: 0 identity lines, 120 + 120 warnings, 0/120 validated).
- **Fix:** configure `[validation_seed]` or `[validator_token]`
  (`ConfigSections.h:89,96`) and restart. **Verify after restart:**
  the `Validator identity:` line must appear and `CNF Val` lines must
  follow on the next closed ledger. Add a startup check to the
  operator runbook: if no `Validator identity` line appears within
  one minute of `Consensus engine started`, the node is not
  validating — stop and fix the config instead of assuming it is.
- **Prevention:** fail the deployment if the config lacks a validator
  key section; never ship a validator image with the key section
  commented out.

## P1 — silent partial validation loss

### P1-1. Clock skew beyond the acceptance window (clock-skew)

- **Blast radius:** 20/120 validations rejected by the network in the
  fixture (local uptime still reads 100% — the most misleading case
  in this pack).
- **Signature:** validation `signTime` more than 180 s before close
  time or more than 300 s after it (`Validations.h:56,71`;
  `ConsensusParms.h:51,66`); non-monotonic signTime across consecutive
  validations (`RCLConsensus.cpp:821-824`).
- **Detector:** `scripts/detect_clock_skew.py` → `CLOCK_SKEW`
  (fixture: 21 flagged of 120 — 20 at +400 s, 1 monotonicity break).
- **Fix:** run NTP/chrony with monitoring and alerting on offset;
  alert when |offset| exceeds 60 s (well inside the 180 s / 300 s
  acceptance bounds, so there is margin). After any clock step,
  restart the node so `lastValidationTime_` is re-established; do not
  trust validations issued across a clock jump.
- **Monitoring change (the key recommendation):** count **accepted**
  validations (validations for ledgers the network validates), not
  locally issued `CNF Val` lines. A node can issue 100% of its
  validations and have 0% accepted.

### P1-2. Total peer loss (connectivity-loss)

- **Blast radius:** 25/120 validations missed in the fixture (100 s
  partition, uptime 79.1667%).
- **Signature:** `<peer> failed: <reason>` + `Closed` lines for all
  peers (`PeerImp.cpp:596-638`); `Need consensus ledger`
  (`RCLConsensus.cpp:137`) when the node cannot acquire the consensus
  ledger.
- **Detector:** `scripts/detect_connectivity.py` →
  `CONNECTIVITY_LOSS` (fixture: 24 peer events overlapping the missed
  window [900050, 900074]).
- **Fix:** keep the peer port (2559, `docs/NodeSetup.md:26-65`)
  reachable and rate-limited, not firewalled shut; maintain peer
  diversity (multiple upstreams, not one); alert when the peer count
  drops to zero — a validator with zero peers cannot validate, and
  the log's only sign is the `Closed` lines. After a partition,
  verify the first `CNF Val` after reconnect; the recovery time in
  the simulated matrix is 8 s (2 slots) once peers return.

## P2 — visible faults with bounded loss

### P2-1. Consensus stall (consensus-stall)

- **Blast radius:** 20/120 validations missed in the fixture (2 × 40 s
  stall windows, uptime 83.3333%).
- **Signature:** `Consensus detects as stalled with <agree>/<proposers>
  proposers, and <n> stalled disputed transactions.`
  (`Consensus.h:1736-1743`, error level — the only stall signal in
  the pack that is already logged at error severity).
- **Detector:** `scripts/detect_consensus_stall.py` →
  `CONSENSUS_STALL` (fixture: 2 stall lines).
- **Fix:** stalls mean peers agree on close time but cannot agree on
  disputed transactions; the operator action is usually to wait —
  rounds longer than `ledgerABANDON_CONSENSUS` (120 s,
  `ConsensusParms.h:113`) are abandoned and consensus restarts. If
  stalls repeat, check for a peer running divergent transaction
  logic or a network partition splitting proposers; alert on any
  stall line (it is already error-level, so it should page, not sit
  in a log file).

### P2-2. Disk exhaustion (resource-exhaustion)

- **Blast radius:** 30/120 validations missed in the fixture (120 s
  halted, uptime 75.0000%).
- **Signature:** fatal `Remaining free disk space is less than 512MB`
  (`Node.cpp:1309`; threshold 512 MB, `Node.cpp:1307`).
- **Detector:** `scripts/detect_resource.py` →
  `RESOURCE_EXHAUSTION` (fixture: 1 fatal line, 30 missed after it).
- **Fix:** alert at 2 GB free, not at 512 MB — the code's fatal line
  fires when the database already refuses to start. Keep the ledger
  store on a separate volume from logs; rotate logs. After freeing
  disk, verify `CNF Val` resumes; the simulated recovery is 16 s
  (4 slots) once space is available.

## P3 — process restart (no detector class)

- **Blast radius (simulated):** 45/600 missed (7.50%), uptime 92.50%,
  recovery 12 s (`outputs/matrix.csv`, process-restart row).
- **Signature:** a second `Consensus engine started` line mid-window.
  No detector in this pack fires on a clean restart, and none should:
  a restart is an operator-visible event, not a fault class. The
  missed validations are the cost of the downtime itself.
- **Fix:** minimise restart frequency (config changes batched, not
  per-change restarts); after any restart, verify the first `CNF Val`
  and the `Validator identity` line before declaring the node healthy.

## Runbook summary (one page)

1. At startup: `Validator identity:` present? If not — P0, stop.
2. Every minute: `CNF Val` count vs `CNF buildLCL` count — equal?
   If not, run the five detectors in this pack against the last
   hour of logs.
3. Alert on: any `Consensus detects as stalled` line (P2-1), any
   `Remaining free disk space` fatal (P2-2), peer count zero (P1-2),
   clock offset > 60 s (P1-1).
4. Report **accepted** validations, not issued ones (P1-1).
