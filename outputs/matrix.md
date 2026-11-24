# Reproducibility matrix — SIMULATED fault scenarios

All numbers below are SIMULATED: they come from the documented model in `scripts/simulate_scenarios.py` (600 slots x 4 s close interval, first seq 910000, base 2026-11-20T00:00:00Z). Detectors were run on the simulated timelines with the same code as on the fixtures, so the 'detectors fired' column is OBSERVED detector behaviour on SIMULATED timelines.

| scenario | expected | issued locally | accepted by network | missed | missed % | uptime % | downtime (s) | recovery (s) | detectors fired |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 600 | 600 | 600 | 0 | 0.00 | 100.00 | 0 |  | none |
| network-partition | 600 | 525 | 525 | 75 | 12.50 | 87.50 | 300 | 8 | connectivity=CONNECTIVITY_LOSS |
| process-restart | 600 | 555 | 555 | 45 | 7.50 | 92.50 | 180 | 12 | none |
| clock-jump | 600 | 600 | 540 | 60 | 10.00 | 90.00 | 240 | 4 | clock-skew=CLOCK_SKEW |
| disk-pressure | 600 | 540 | 540 | 60 | 10.00 | 90.00 | 240 | 16 | resource=RESOURCE_EXHAUSTION |

Definitions: *missed* = expected − accepted by network; *uptime %* = accepted / expected; *downtime* = missed × 4 s; *recovery* = modelled time from fault end to the first accepted validation (see simulate_scenarios.py model parameters). In the clock-jump scenario the node issues validations locally but the network rejects them as stale, so issued locally (600) exceeds accepted (540).

Primary causes (modelled):

- **baseline**: none — healthy control
- **network-partition**: all 12 peers disconnect at once; no proposals reach the node, so no ledger closes locally and no validation is issued for 75 slots
- **process-restart**: process down for 180 s (45 slots); engine restarts and re-validates 3 slots after the restart line
- **clock-jump**: local clock jumps +400 s for 240 s (60 slots); validations are issued locally but their signTime is outside the pinned acceptance window, so the network rejects them
- **disk-pressure**: fatal low-disk line at slot 300; the node keeps validating for a 60 s grace period, then halts for 240 s (60 slots) until disk space is freed
