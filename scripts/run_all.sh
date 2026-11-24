#!/usr/bin/env bash
# run_all.sh — run the whole pack end to end, offline and deterministically.
#
#   bash scripts/run_all.sh
#
# Steps (every step writes its own unedited log under outputs/; there is
# no manual follow-up step anywhere in this pack):
#   1. generate the synthetic fixtures (deterministic; byte-identical on
#      re-run)
#   2. parse every fixture (validation events, missed validations, uptime)
#   3. run all five detectors (one script + log per cause class)
#   4. run the fault-scenario simulator and build the matrix
#   5. write run-manifest.json (deterministic, no timestamps)
#   6. regenerate SHA256SUMS over outputs/ and verify it
#
# Outputs that carry wall-clock timestamps (outputs/run_all.log only) are
# excluded from SHA256SUMS; everything else must be byte-identical
# across runs. Invoke helpers with `bash scripts/...` (never by direct
# path) so a plain `git clone` — which drops executable bits — still runs.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."
mkdir -p outputs

# The whole run is tee'd to outputs/run_all.log. That log is transient
# (it carries a wall-clock start line) and is excluded from SHA256SUMS.
exec > >(tee outputs/run_all.log) 2>&1

echo "=== postfiatd validator uptime / missed-validation forensics ==="
echo "run started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "pinned postfiatd commit: 0085a1ff885d6a446369cf73a4430f75af22be55"

echo "--- 1. generate fixtures ---"
python3 scripts/generate_fixtures.py

echo "--- 2. parse fixtures ---"
for f in baseline-healthy connectivity-loss clock-skew resource-exhaustion \
         config-error consensus-stall; do
  python3 scripts/parse_validations.py "$f"
  echo "parsed $f"
done

echo "--- 3. run detectors ---"
python3 scripts/detect_connectivity.py connectivity-loss
python3 scripts/detect_clock_skew.py clock-skew
python3 scripts/detect_resource.py resource-exhaustion
python3 scripts/detect_config.py config-error
python3 scripts/detect_consensus_stall.py consensus-stall

echo "--- 4. simulate fault scenarios + matrix ---"
python3 scripts/simulate_scenarios.py

echo "--- 5. write manifest ---"
python3 scripts/make_manifest.py

echo "--- 6. digests ---"
bash scripts/make_sha256sums.sh
bash scripts/verify_digests.sh

echo "=== run_all finished: exit 0 ==="
