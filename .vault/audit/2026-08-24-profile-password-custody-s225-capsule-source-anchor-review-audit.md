---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:04ac1f4d7d716a269d00e5121c2da6f6d5608f0cfb73b2e733b84cca8fd725ab'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S225 capsule source anchor review`

## Scope

Formal review of `W06.P12.S225` against the accepted custody decision, the
derived-close plan contract, the corrected S223 close review, the complete
capsule-source test module, and the anchored local-record reader it exercises.
The review checked that the witness uses real filesystem objects without mocks,
stubs, skips, xfails, or platform markers; that successful symlink construction
retains linked-content non-adoption coverage; that the directory fallback claims
only non-regular-file refusal; and that the asserted exception contract matches
both Windows and POSIX source behavior.

The supplied Windows evidence was considered: the focused module passed 3 tests,
the global no-skip/xfail ratchet passed 25 tests, and Ruff and ty were clean. A
reviewer WSL run of the focused module produced 2 passes and 1 failure, confirming
the source-derived portability issue below.

## Findings

### posix-symlink-exception-mismatch | medium | The claimed all-platform witness fails when POSIX creates the real symlink

The test unconditionally matches `reparse point or directory` after the symlink
attempt. That text belongs to the Windows anchored-handle branch. On POSIX,
`_read_regular_file_open` opens with `O_NOFOLLOW`; a real symlink is rejected by
`os.open`, and the `OSError` is deliberately translated to `profile capsule
record is unavailable`. The fallback directory branch would match `not a bounded
regular file` on POSIX, not the asserted Windows text. Because POSIX normally
creates the symlink successfully, the fallback is not reached and the focused WSL
gate fails with the actual unavailable-record message. The production primitive
still refuses without reading linked content, so this is not a demonstrated
custody bypass, but S225 does not deliver its deterministic cross-platform
witness and cannot close.

The witness otherwise remains honest: it uses real filesystem state, makes no
test-double or skip concession, retains the linked-content assertion only when a
symlink was actually created, and explicitly limits the fallback claim to
non-regular-file refusal.

## Recommendations

Block S225 until the test accepts the platform-appropriate anchored-refusal
contract without weakening the security property. The symlink branch should
prove refusal and non-adoption under the POSIX unavailable-record translation or
the Windows reparse translation; the directory fallback should prove the POSIX
bounded-regular-file or Windows reparse/directory translation. Re-run the focused
module on native Windows and WSL, plus the global no-skip/xfail ratchet, Ruff, and
ty, before review is repeated.

## Resolution review

### posix-symlink-exception-mismatch-resolved | resolved | The witness now matches the two exercised anchored-refusal translations

The amended assertion is limited to `reparse point or directory` and `record is
unavailable`, the two diagnostics produced by the supported native Windows and
POSIX symlink paths. It does not accept an arbitrary custody error. Windows
rejects either the real reparse point or the directory fallback through the
anchored-handle check; POSIX creates the real symlink and rejects its
`O_NOFOLLOW` open through the unavailable-record translation. In both paths the
exception must precede the independent assertion that linked payload text never
appears. The directory fallback still asserts that the object at the exact
member path is genuinely a directory and its prose claims only non-regular-file
refusal.

Fresh final evidence is green: the native focused module passed 3 of 3 tests in
1.12 seconds, the WSL/POSIX focused module passed 3 of 3 tests in 8.06 seconds,
and Ruff and ty were clean. The earlier global no-skip/xfail ratchet remains 25
of 25 with no skip-related delta in the resolution. No mock, stub, skip, xfail,
platform marker, or production-code change was introduced.

## Final disposition

PASS. The MEDIUM finding is resolved. S225 has no unresolved CRITICAL, HIGH,
MEDIUM, or LOW review finding and may close.
