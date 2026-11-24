#!/usr/bin/env bash
# make_sha256sums.sh — regenerate SHA256SUMS over outputs/ (deterministic).
# Excludes the transient logs outputs/run_all.log and
# outputs/fresh-clone-reproduction.log, which are not part of the
# reproducible output set (they carry wall-clock timestamps).
# Must be run AFTER every other output exists (see scripts/run_all.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
: > SHA256SUMS
for f in $(find outputs -type f ! -name run_all.log \
    ! -name fresh-clone-reproduction.log | LC_ALL=C sort); do
  sha256sum "$f" >> SHA256SUMS
done
echo "SHA256SUMS written: $(wc -l < SHA256SUMS) entries"
