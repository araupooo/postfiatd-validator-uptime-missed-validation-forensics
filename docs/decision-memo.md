# Decision memo — validator uptime and missed-validation forensics

## Question

How should a postfiatd validator operator observe, classify, and
diagnose missed validations — and what should be monitored — given
what the code actually emits?

## Decision

1. **Measure missed validations as built-but-not-validated ledgers.**
   A ledger the node closed (`CNF buildLCL`) but did not validate
   (`CNF Val`) is a missed validation. This is the only definition
   the code supports directly: `validate()` runs exactly when the
   node is validating and `canValidateSeq()` allows the sequence
   (`src/xrpld/app/consensus/RCLConsensus.cpp:601-608`;
   `src/xrpld/consensus/Validations.h:608-613`).
2. **Classify every missed-validation window with the five detectors
   in this pack** (connectivity, clock skew, resource exhaustion,
   configuration error, consensus stall), in that order. The order
   matters: configuration error is checked first in practice because
   it removes 100% of validations while the node looks healthy.
3. **Monitor accepted validations, not issued ones.** A validation
   issued with a skewed clock is issued locally and rejected by the
   network; local issuance alone cannot detect that failure mode.
4. **Treat the five detectors as the diagnostic standard for this
   audit.** They are scripted, re-runnable, and their outputs are
   committed (`outputs/detector-*.log`, `outputs/detector-*.json`).
   No manual diagnosis step is part of this pack.

## Evidence

- **Fixture parses (OBSERVED).** Six 120-ledger fixtures; missed
  counts 0 / 25 / 0 / 30 / 120 / 20; uptimes 100% / 79.1667% / 100% /
  75% / 0% / 83.3333% (`outputs/parse-*.log`;
  `docs/findings-report.md`). Every parse reports 0 unparsed lines
  and ledger-state/log agreement.
- **Detector verdicts (OBSERVED).** All five detectors fire on their
  designated fixture with the expected verdict
  (`outputs/detector-*.log`): `CONNECTIVITY_LOSS` (24 peer events
  overlapping the missed window), `CLOCK_SKEW` (21 flagged of 120:
  20 at +400 s, 1 monotonicity break), `RESOURCE_EXHAUSTION`
  (1 fatal line, 30 missed after it), `CONFIG_ERROR` (0 identity
  lines, 240 key warnings, 0/120 validated), `CONSENSUS_STALL`
  (2 stall lines).
- **Scenario matrix (SIMULATED).** Five 600-slot scenarios:
  baseline 100.00% uptime; network-partition 87.50% (75 missed,
  300 s downtime, 8 s recovery); process-restart 92.50% (45 missed,
  180 s, 12 s); clock-jump 90.00% (60 missed, 240 s, 4 s);
  disk-pressure 90.00% (60 missed, 240 s, 16 s)
  (`outputs/matrix.md`, `outputs/matrix.csv`).
- **Primary sources.** Pinned commit
  `0085a1ff885d6a446369cf73a4430f75af22be55`; 11 files verified
  blob-by-blob against the GitHub API (`docs/source-inventory.md`).

## Why this definition, and not the alternatives

- **Process liveness is not uptime.** A node with no validator keys
  configured closes ledgers, holds peers, and emits no fatal line —
  yet validates nothing (config-error fixture: uptime 0% with a
  healthy-looking process). Liveness checks would pass it.
- **Issued validations are not accepted validations.** The clock-skew
  fixture issues 120/120 validations locally while 20 are stale to
  the network (signTime +400 s vs the 300 s wall,
  `Validations.h:56`). Counting `CNF Val` lines would report 100%
  uptime for a node the network counts as absent.
- **Validation staleness is bounded by code, not by convention.** The
  acceptance window ([close − 180 s, close + 300 s]) and the
  increasing-sequence invariant are constants in the pinned source
  (`Validations.h:56,64,71,79,89`; `Validations.h:92-135`), not
  operator folklore. The detectors encode those constants, so a
  future change to the constants changes the detectors' verdicts in
  the open.
- **A stall is already logged at error level** (`Consensus.h:1742`),
  so it should page. The other four fault classes are logged at
  info/warning or not at all in a distinguishing way, which is why
  they need detectors rather than log greps.

## Risks and limits

- **Synthetic inputs.** All fixtures and scenarios are synthetic;
  no live-network rate was measured. The detectors are validated
  against fixtures modelled on real log formats, not against real
  incidents. A real incident log may contain lines this parser does
  not recognise (reported as unparsed, never silently dropped), and
  new message formats would need new parser rules.
- **Single-node view.** The pack analyses one node's logs. Whether
  the network accepted a validation ultimately depends on peers'
  validation stores; the clock-jump scenario models that acceptance,
  it does not measure it.
- **Close-interval assumption.** The 4 s nominal interval is a model
  choice (`ledgerMIN_CLOSE` is 2 s, `ledgerIDLE_INTERVAL` 15 s).
  Absolute downtime seconds in the matrix scale with it; missed
  counts and uptimes do not.
- **Dynamic UNL.** Validator selection on the testnet is by Dynamic
  UNL (`docs/NodeSetup.md:96-109`); sustained missed validations
  may affect a validator's standing in that pipeline. This pack
  measures the missed validations, not the scoring outcome.

## Recommendation

Adopt the five detectors as the standard diagnostic for missed
validations, add the runbook checks in `docs/remediation-report.md`
(startup identity check; per-minute `CNF Val` vs `CNF buildLCL`
comparison; alerts on stall lines, low-disk fatal, zero peers, and
clock offset > 60 s), and report accepted validations as the uptime
metric. Re-run this pack against real incident logs when they occur
and extend the parser with any unrecognised line formats found.
