# Methodology

## Pinned source

- Repository: `postfiatorg/postfiatd`
- Pinned commit: `0085a1ff885d6a446369cf73a4430f75af22be55`
  ("Merge pull request #50 from postfiatorg/hotfix/upstream-hardening-1.0.9",
  2026-10-10T16:53:26Z; also the `main` HEAD at audit time)
- Every cited file was verified blob-by-blob against the GitHub API at
  this commit (SHA + size agree; see `docs/source-inventory.md`). Every
  cited line number comes from `grep -n` on a local checkout of this
  commit.

## Definitions

- **Expected ledger**: a ledger sequence listed in the fixture
  ledger-state JSON.
- **Validated ledger**: an expected sequence with a `CNF Val <hash>`
  line in the log. The node logs `CNF Val` exactly when `validate()`
  runs (`src/xrpld/app/consensus/RCLConsensus.cpp:601-608`).
- **Missed validation**: an expected sequence with a `CNF buildLCL`
  line but no `CNF Val` line. `validate()` is skipped when the node is
  not validating or when `canValidateSeq()` refuses the sequence
  (`RCLConsensus.cpp:601-604`; `src/xrpld/consensus/Validations.h:608-613`).
- **Uptime**: validated / expected over the fixture window.
- **Missed window**: a maximal run of consecutive missed sequences.
- **Accepted by network** (scenarios only): a locally issued validation
  whose `signTime` is inside the pinned acceptance window
  (see below). A validation issued with a skewed clock is issued
  locally but rejected by peers, so it counts as missed in the
  network view and as issued in the local view. The two views are
  kept apart and labelled wherever they appear.

## Pinned timing parameters

From `src/xrpld/consensus/Validations.h` (`ValidationParms`, lines
46-89) and `src/xrpld/consensus/ConsensusParms.h` (lines 51-114):

| Parameter | Value | Location |
|---|---|---|
| `validationCURRENT_WALL` | 5 min | Validations.h:56 |
| `validationCURRENT_LOCAL` | 3 min | Validations.h:64 |
| `validationCURRENT_EARLY` | 3 min | Validations.h:71 |
| `validationSET_EXPIRES` | 10 min | Validations.h:79 |
| `validationFRESHNESS` | 20 s | Validations.h:89 |
| `validationVALID_WALL` | 5 min | ConsensusParms.h:51 |
| `validationVALID_LOCAL` | 3 min | ConsensusParms.h:59 |
| `validationVALID_EARLY` | 3 min | ConsensusParms.h:66 |
| `proposeFRESHNESS` | 20 s | ConsensusParms.h:69 |
| `proposeINTERVAL` | 12 s | ConsensusParms.h:72 |
| `minCONSENSUS_PCT` | 67% | ConsensusParms.h:79 |
| `ledgerIDLE_INTERVAL` | 15 s | ConsensusParms.h:82 |
| `ledgerMIN_CONSENSUS` | 1950 ms | ConsensusParms.h:86 |
| `ledgerMAX_CONSENSUS` | 15 s | ConsensusParms.h:95 |
| `ledgerMIN_CLOSE` | 2 s | ConsensusParms.h:99 |
| `ledgerGRANULARITY` | 1 s | ConsensusParms.h:102 |
| `ledgerABANDON_CONSENSUS_FACTOR` | 10 | ConsensusParms.h:105 |
| `ledgerABANDON_CONSENSUS` | 120 s | ConsensusParms.h:113 |

Two consequences used by the detectors:

1. **Acceptance window.** A validation is current only if its signing
   time is within `validationCURRENT_EARLY` (180 s) before the ledger
   close time and within `validationCURRENT_WALL` (300 s) after it
   (`Validations.h:137-166`, `isCurrent()`; `add()` returns
   `ValStatus::stale` otherwise, `Validations.h:623-627`). The
   clock-skew detector flags signTime outside
   `[close − 180 s, close + 300 s]`.
2. **Increasing sequence.** A validator's validations must carry
   strictly increasing ledger sequences while unexpired
   (`SeqEnforcer`, `Validations.h:92-135`; enforced in `add()` via
   `canValidateSeq()`, `Validations.h:608-613`). `validate()` also
   forces signing time to be monotonic by bumping it to
   `lastValidationTime_ + 1 s` (`RCLConsensus.cpp:821-824`). The
   clock-skew detector also flags non-monotonic signTime.

## Model assumptions (stated, not measured)

- Nominal ledger close interval **4 s** and fixture window **120
  ledgers** (seq 900000–900119, base 2026-11-20T00:00:00Z). The code
  only bounds the interval (`ledgerMIN_CLOSE` 2 s,
  `ledgerIDLE_INTERVAL` 15 s); 4 s is a modelling choice, not a
  measured network interval.
- Scenario window **600 ledgers** (40 minutes) per scenario.
- Ledger hashes are `sha256("postfiatd-ledger-<seq>")` — synthetic,
  deterministic, clearly not real ledger hashes.
- The fixture log format (ISO-8601 UTC + `[Journal]` tag) is the
  pack's own synthetic format; the message texts are verbatim from
  the pinned source (see `fixtures/README.md`).

## Harness

`scripts/parse_validations.py` (`scripts/validation_lib.py:parse_log`)
extracts every event class from a fixture log: engine starts,
validator identity, `CNF buildLCL` / `CNF Val` lines, peer fail/close,
stall lines, disk fatal, `ValidatorKeys` warnings, ancestor-missing
warnings, need-ledger warnings. It maps hashes to sequences through
the ledger-state JSON and reports: expected / built / validated /
missed counts, missed windows, uptime, and whether the JSON
`validated` flags agree with the log. Unparsed lines are counted and
listed, never silently dropped.

## Detectors

One script per cause class; each writes its own log and JSON under
`outputs/` and is invoked by `scripts/run_all.sh` — there is no
manual diagnosis step in this pack.

| Detector | Script | Rule (primary source) |
|---|---|---|
| connectivity loss | `scripts/detect_connectivity.py` | Peer `fail`/`Closed` lines (`PeerImp.cpp:596-638`) overlapping a missed-validation window |
| clock skew | `scripts/detect_clock_skew.py` | signTime outside `[close − 180 s, close + 300 s]` or non-monotonic (`Validations.h:56,71`; `RCLConsensus.cpp:821-824`) |
| resource exhaustion | `scripts/detect_resource.py` | Fatal `Remaining free disk space is less than 512MB` (`Node.cpp:1301-1311`) followed by missed validations |
| configuration error | `scripts/detect_config.py` | No `Validator identity` line at startup (`RCLConsensus.cpp:107-112`) + `ValidatorKeys not set` warnings (`RCLConsensus.cpp:231,826-830`) + zero validations issued |
| consensus stall | `scripts/detect_consensus_stall.py` | `Consensus detects as stalled with ...` error lines (`Consensus.h:1722-1744`) |

## Scenarios (SIMULATED)

`scripts/simulate_scenarios.py` builds five 600-slot timelines from
the documented model parameters in the script (no randomness, no
network). The matrix (`outputs/matrix.md`, `outputs/matrix.csv`) is
the simulator's output; the detectors are run on the simulated
timelines with the same code as on the fixtures, so the "detectors
fired" column is observed detector behaviour on simulated timelines.

- **baseline**: healthy control, 0 missed.
- **network-partition**: all 12 peers disconnect at slot 200; 300 s
  partition = 75 missed slots; resume lag 2 slots = 8 s recovery.
- **process-restart**: process down 180 s = 45 missed slots; engine
  restarts; first validation 3 slots after the restart line = 12 s
  recovery. No detector class applies to a clean restart — the
  matrix records that honestly (detectors fired: none; the restart is
  identified by the second `Consensus engine started` line).
- **clock-jump**: clock +400 s for 240 s = 60 slots; validations are
  issued locally but their signTime exceeds the 300 s wall, so the
  network rejects them: 600 issued locally, 540 accepted, 60 missed;
  resync lag 1 slot = 4 s recovery.
- **disk-pressure**: fatal low-disk line at slot 300; 60 s grace (15
  slots still validating), then 240 s halted = 60 missed slots;
  recovery lag 4 slots = 16 s.

## What this pack does NOT measure (UNMEASURED)

- Live-network validation rates, real ledger close intervals, real
  peer counts, or real operator incidents. All inputs are synthetic
  fixtures and a documented simulation model.
- Full-node behaviour under real load (disk I/O, memory pressure,
  CPU saturation) — the resource detector keys on the single fatal
  log line the code emits, not on measured resource usage.
- The Dynamic UNL scoring pipeline's effect on validator selection
  (see `docs/NodeSetup.md:96-109`); it is cited as context, not
  measured.

## Reproduction

```sh
bash scripts/run_all.sh
```

Re-runs the whole pack offline. Everything except
`outputs/run_all.log` (wall-clock start line) is byte-identical across
runs; `bash scripts/verify_digests.sh` checks all 35 digests in
`SHA256SUMS`.
