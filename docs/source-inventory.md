# Source inventory — pinned postfiatd commit

- Repository: `postfiatorg/postfiatd`
- Pinned commit: `0085a1ff885d6a446369cf73a4430f75af22be55`
  ("Merge pull request #50 from postfiatorg/hotfix/upstream-hardening-1.0.9",
  2026-10-10T16:53:26Z; also the `main` HEAD at audit time)
- Verification method: each file below was checked in two ways that
  must agree — `git hash-object` + `wc -c` on a local checkout of the
  pinned commit, and the GitHub API
  (`/repos/postfiatorg/postfiatd/contents/<path>?ref=<commit>`,
  `sha` + `size`). All 11 files agreed. Line numbers come from
  `grep -n` on the local checkout.

## Cited files

| File | Blob SHA | Size (bytes) | Cited lines |
|---|---|---|---|
| `src/xrpld/consensus/Validations.h` | `c333aeaefd7890bf1c7d19e56eadbae0b788602e` | 39557 | 46, 56, 64, 71, 79, 89, 92-135, 137-166, 169-180, 608-613, 623-627 |
| `src/xrpld/consensus/ConsensusParms.h` | `d565bd9a5228de171cc777a0a098592f9e8505df` | 8302 | 51, 59, 66, 69, 72, 79, 82-83, 86-87, 95-96, 99, 102, 105, 113-114 |
| `src/xrpld/consensus/Consensus.h` | `9ccc080857e2be382365dff5f349544b9907d9cf` | 65913 | 1722-1744 |
| `src/xrpld/app/consensus/RCLConsensus.cpp` | `457555cc1c83cb617a6838e0099fc93e1d715b49` | 37567 | 103-104, 107-112, 231, 601-608, 821-824, 826-830, 841-844 |
| `src/xrpld/app/consensus/RCLValidations.cpp` | `669d69957da77a68bb5ace92a5e0ff789572be85` | 9726 | 58-59, 210-215, 231 |
| `src/xrpld/overlay/detail/PeerImp.cpp` | `d823bf23a17e62172320628a800fdda92fbb2bcb` | 116691 | 596-616, 620-638, 639-651 |
| `src/xrpld/app/rdb/backend/detail/Node.cpp` | `88f11a272ba3509354772aa028842b760b6d9f6f` | 45474 | 1301-1311 |
| `src/libxrpl/protocol/STValidation.cpp` | `d2cb0586f261e9e06fa31f0da9c3fdc28cfc62ca` | 5493 | 64, 71, 113 |
| `src/xrpld/core/ConfigSections.h` | `db9937b7fa1cde49a0ebfec5f65ce6b353381d00` | 4258 | 88-97 |
| `docs/consensus.md` | `067e15d0c871020f1cbc86d28c503d6cf66b643f` | 30816 | 43-50, 145-166 |
| `docs/NodeSetup.md` | `43439b657115f7593513127651255b755a1f0e05` | 17500 | 26-65, 96-109 |

## What each citation supports

- **Validation timing / staleness** — `Validations.h:46-89`
  (`ValidationParms`: current wall 5 min, local 3 min, early 3 min,
  set expires 10 min, freshness 20 s); `Validations.h:137-166`
  (`isCurrent()`); `Validations.h:169-180` (`ValStatus`: current,
  stale, badSeq, multiple, conflicting); `Validations.h:92-135`
  (`SeqEnforcer`: strictly increasing validation sequences);
  `Validations.h:608-613` (`canValidateSeq()`); `Validations.h:623-627`
  (`add()` returns `stale`).
- **Consensus timing** — `ConsensusParms.h:51-114` (validation
  validity windows, propose freshness/interval, consensus
  percentages, idle/min/max consensus durations, abandon threshold
  120 s).
- **Validation issuance** — `RCLConsensus.cpp:601-608` (`validate()`
  gated by `validating_ && canValidateSeq()`; `CNF Val` log line);
  `RCLConsensus.cpp:821-824` (signing time forced monotonic);
  `RCLConsensus.cpp:826-830` (`validate()` warns and returns when
  keys are missing); `RCLConsensus.cpp:841-844` (validation fields:
  ledger hash, consensus hash, ledger sequence);
  `RCLConsensus.cpp:103-104,107-112` (engine start, validator
  identity); `RCLConsensus.cpp:231` (`propose()` warns when keys are
  missing).
- **Validation intake** — `RCLValidations.cpp:58-59` (missing ancestor
  hashes warning); `RCLValidations.cpp:210-215` (recording a vote);
  `RCLValidations.cpp:231` (bypassing `checkAccept`).
- **Validation wire format** — `STValidation.cpp:64,71,113`
  (`sfLedgerSequence` and `sfSigningTime` are required fields;
  `signTime()`).
- **Peer disconnects** — `PeerImp.cpp:596-616` (`close()` increments
  the disconnect counter, logs `Closed`); `PeerImp.cpp:620-638`
  (`fail(reason)` logs `<peer> failed: <reason>`); `PeerImp.cpp:639-651`
  (`fail(name, ec)`).
- **Disk pressure** — `Node.cpp:1301-1311` (`dbHasSpace()`: fatal
  `Remaining free disk space is less than 512MB` below 512 MB free).
- **Validator configuration** — `ConfigSections.h:88-97`
  (`[validation_seed]`, `[validator_keys]`, `[validator_token]`,
  `[validator_list_*]`).
- **Consensus stall** — `Consensus.h:1722-1744` (stall detection:
  close-time consensus reached but disputed transactions cannot
  agree; error line `Consensus detects as stalled with ...`).
- **Consensus / validation concepts** — `docs/consensus.md:43-50`
  (validation = agreement on what ledger was generated);
  `docs/consensus.md:145-166` (effective close time; clock
  disagreement handling).
- **Operator context** — `docs/NodeSetup.md:26-65` (firewall, peer
  port 2559, per-IP connection limits, rate limiting);
  `docs/NodeSetup.md:96-109` (Dynamic UNL validator selection).
