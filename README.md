# Postfiatd Validator Uptime and Missed-Validation Forensics

A public, commit-pinned audit of how postfiatd validator uptime and
missed validations can be observed, classified, and diagnosed from
logs, ledger state, and primary sources.

- **Audited postfiatd commit:** `0085a1ff885d6a446369cf73a4430f75af22be55`
  ("Merge pull request #50 from postfiatorg/hotfix/upstream-hardening-1.0.9",
  2026-10-10T16:53:26Z; also the `main` HEAD at audit time)
- **Headline result (OBSERVED):** all five cause detectors fire on
  their designated fixture — connectivity loss, clock skew, resource
  exhaustion, configuration error, consensus stall — with missed
  counts 25 / 0-issued-but-21-flagged / 30 / 120 / 20 across six
  120-ledger fixtures.
- **Headline result (SIMULATED):** five 600-slot fault scenarios —
  baseline 100.00% uptime; network-partition 87.50% (75 missed);
  process-restart 92.50% (45 missed); clock-jump 90.00% (60 missed);
  disk-pressure 90.00% (60 missed). See `outputs/matrix.md`.
- **Key finding:** a validator can issue 100% of its validations
  locally and still have them rejected by the network (clock-skew
  fixture). Monitor **accepted** validations, not issued ones.

## What is in this repository

| Path | Contents |
|---|---|
| `scripts/run_all.sh` | Runs the whole pack end to end, offline |
| `scripts/parse_validations.py`, `scripts/validation_lib.py` | Harness: extract validation events, missed validations, uptime windows |
| `scripts/detect_*.py` (5) | One reproducible detector per cause class, each with its own log |
| `scripts/simulate_scenarios.py` | Fault-scenario simulator + reproducibility matrix |
| `scripts/generate_fixtures.py` | Deterministic generator for the synthetic fixtures |
| `scripts/make_manifest.py`, `make_sha256sums.sh`, `verify_digests.sh` | Manifest + SHA-256 digest tooling |
| `fixtures/` | Synthetic log + ledger-state fixtures (see `fixtures/README.md`) |
| `docs/methodology.md` | Definitions, pinned timing parameters, model assumptions |
| `docs/findings-report.md` | Observed detector results on fixtures |
| `docs/remediation-report.md` | Severity-ranked operator remediations (P0–P3) |
| `docs/decision-memo.md` | Sourced decision memo |
| `docs/source-inventory.md` | Pinned commit, cited files with blob SHA + size + lines |
| `outputs/` | Unedited logs, detector JSONs, scenario logs, matrix |
| `SHA256SUMS`, `run-manifest.json` | Digests for every output file |

## Reproduce

```sh
bash scripts/run_all.sh
bash scripts/verify_digests.sh
```

No network access is needed at run time. Every step is scripted —
there is no manual diagnosis step in this pack. Everything except
`outputs/run_all.log` (wall-clock start line) is byte-identical
across runs.

## Claim-to-evidence index

Labels: **[OBSERVED]** = parser/detector behaviour on the synthetic
fixtures; **[SIMULATED]** = output of the documented simulation model
in `scripts/simulate_scenarios.py`. No claim in this pack rests on a
live network measurement.

| # | Claim | Label | Script | Input fixture | Raw output |
|---|---|---|---|---|---|
| 1 | Baseline fixture: 120/120 validated, 0 missed, uptime 100.0000% | OBSERVED | `scripts/parse_validations.py` | `fixtures/baseline-healthy.log`, `fixtures/baseline-healthy-ledger-state.json` | `outputs/parse-baseline-healthy.log` |
| 2 | Connectivity fixture: 25 missed (900050–900074), uptime 79.1667% | OBSERVED | `scripts/parse_validations.py` | `fixtures/connectivity-loss.log`, `fixtures/connectivity-loss-ledger-state.json` | `outputs/parse-connectivity-loss.log` |
| 3 | Connectivity detector: CONNECTIVITY_LOSS — 24 peer events overlap the missed window | OBSERVED | `scripts/detect_connectivity.py` | `fixtures/connectivity-loss.log` | `outputs/detector-connectivity.log`, `outputs/detector-connectivity.json` |
| 4 | Clock-skew fixture: 120 issued locally, 0 missed locally | OBSERVED | `scripts/parse_validations.py` | `fixtures/clock-skew.log`, `fixtures/clock-skew-ledger-state.json` | `outputs/parse-clock-skew.log` |
| 5 | Clock-skew detector: CLOCK_SKEW — 21 of 120 flagged (20 at +400 s, 1 monotonicity break) | OBSERVED | `scripts/detect_clock_skew.py` | `fixtures/clock-skew.log` | `outputs/detector-clock-skew.log`, `outputs/detector-clock-skew.json` |
| 6 | Resource fixture: 30 missed (900060–900089), uptime 75.0000% | OBSERVED | `scripts/parse_validations.py` | `fixtures/resource-exhaustion.log`, `fixtures/resource-exhaustion-ledger-state.json` | `outputs/parse-resource-exhaustion.log` |
| 7 | Resource detector: RESOURCE_EXHAUSTION — 1 fatal low-disk line, 30 missed after it | OBSERVED | `scripts/detect_resource.py` | `fixtures/resource-exhaustion.log` | `outputs/detector-resource.log`, `outputs/detector-resource.json` |
| 8 | Config fixture: 0/120 validated, uptime 0.0000% | OBSERVED | `scripts/parse_validations.py` | `fixtures/config-error.log`, `fixtures/config-error-ledger-state.json` | `outputs/parse-config-error.log` |
| 9 | Config detector: CONFIG_ERROR — 0 identity lines, 120 + 120 key warnings | OBSERVED | `scripts/detect_config.py` | `fixtures/config-error.log` | `outputs/detector-config.log`, `outputs/detector-config.json` |
| 10 | Stall fixture: 20 missed (900030–900039, 900070–900079), uptime 83.3333% | OBSERVED | `scripts/parse_validations.py` | `fixtures/consensus-stall.log`, `fixtures/consensus-stall-ledger-state.json` | `outputs/parse-consensus-stall.log` |
| 11 | Stall detector: CONSENSUS_STALL — 2 stall lines (3/12 proposers, 2 disputes) | OBSERVED | `scripts/detect_consensus_stall.py` | `fixtures/consensus-stall.log` | `outputs/detector-consensus-stall.log`, `outputs/detector-consensus-stall.json` |
| 12 | Scenario baseline: 600/600 accepted, uptime 100.00%, 0 missed | SIMULATED | `scripts/simulate_scenarios.py` | — (model parameters in script) | `outputs/matrix.md`, `outputs/matrix.csv`, `outputs/scenario-baseline.log` |
| 13 | Scenario network-partition: 525/600, uptime 87.50%, 75 missed, 300 s downtime, 8 s recovery | SIMULATED | `scripts/simulate_scenarios.py` | — | `outputs/matrix.md`, `outputs/matrix.csv`, `outputs/scenario-network-partition.log` |
| 14 | Scenario process-restart: 555/600, uptime 92.50%, 45 missed, 180 s downtime, 12 s recovery | SIMULATED | `scripts/simulate_scenarios.py` | — | `outputs/matrix.md`, `outputs/matrix.csv`, `outputs/scenario-process-restart.log` |
| 15 | Scenario clock-jump: 600 issued / 540 accepted, uptime 90.00%, 60 missed, 240 s downtime, 4 s recovery | SIMULATED | `scripts/simulate_scenarios.py` | — | `outputs/matrix.md`, `outputs/matrix.csv`, `outputs/scenario-clock-jump.log` |
| 16 | Scenario disk-pressure: 540/600, uptime 90.00%, 60 missed, 240 s downtime, 16 s recovery | SIMULATED | `scripts/simulate_scenarios.py` | — | `outputs/matrix.md`, `outputs/matrix.csv`, `outputs/scenario-disk-pressure.log` |
| 17 | All 11 cited source files agree blob-by-blob (SHA + size) with the GitHub API at the pinned commit | OBSERVED | (manual verification at build time; method in `docs/source-inventory.md`) | postfiatd `0085a1ff...` | `docs/source-inventory.md` |
| 18 | Fresh-clone rerun reproduces all outputs byte-identically (except `run_all.log`) | OBSERVED | `bash scripts/run_all.sh` in a fresh copy | this repository | `outputs/fresh-clone-reproduction.log` |

## Scope and limits (UNMEASURED)

- No live-network validation rates, real close intervals, or real
  incidents were measured. Fixtures are synthetic (modelled on real
  log formats) and scenarios are a documented simulation model.
- Full-node behaviour under real load is not measured; the resource
  detector keys on the single fatal log line the code emits.
- See `docs/methodology.md` for the full list.
