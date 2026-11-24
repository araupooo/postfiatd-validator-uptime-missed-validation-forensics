#!/usr/bin/env bash
# verify_digests.sh — verify every digest in SHA256SUMS (full 64-hex SHA-256).
# Exit 0 only if every entry verifies.
set -euo pipefail
cd "$(dirname "$0")/.."
sha256sum -c SHA256SUMS
