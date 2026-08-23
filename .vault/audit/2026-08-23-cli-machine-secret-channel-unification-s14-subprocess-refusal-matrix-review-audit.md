---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:74cbdc1e607fdfe7f37ed99553ef5150bc868d7ae18a776016f3581deb37e1e4'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-adr]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace cli-machine-secret-channel-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-machine-secret-channel-unification` audit: `S14 subprocess refusal matrix review`

## Scope

Independent SOL review of the effective S14 fresh-process refusal matrix in
commit `af1b7f21bba` plus its current working-tree follow-up against the
accepted machine-secret ADR, both research records, the approved plan, the
S13 execution and closed review, the S19-S22 execution/review trail, and the
live selector, bounded reader, parsed root gate, Windows HANDLE bootstrap, and
subprocess harness. The audit covers refusal precedence, strict parsing,
descriptor lifecycle, mutation and disclosure oracles, target/session posture,
localization, and honest POSIX/Windows transport proof.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### S14 subprocess refusal matrix review | {level} | {summary}

     followed by a paragraph carrying the detail. S14 subprocess refusal matrix review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### conflict-precedence-oracles | high | Every conflict row can pass after source consumption and the Windows same-fd row never supplies equal descriptors

The five same-scope rows and both cross-scope rows supply the bare
`_REFUSAL_SECRET`, which is not a valid strict JSON payload, and assert only an
eventual exit-code-2 refusal, secret absence, prompt absence, and durable-state
equality. If conflict precedence regresses and dispatch reads either source,
the canonical parser will still produce exit code 2 before mutation, leaving
every asserted outcome unchanged; no row asserts an unread descriptor marker,
reader position, KDF prohibition, or session non-activation. The Windows
`same-fd` route is weaker still: `_run_windows_handles` passes the same HANDLE
as both bootstrap inputs, and `bootstrap_argv` converts it twice into distinct
CRT descriptor numbers. Production `_preflight_sources` therefore never sees
equal root and leaf descriptors; the case can refuse later because one mapping
invalidates or drains the shared HANDLE and still pass. Consequently S14 does
not prove its required same-scope or cross-scope conflict-before-read,
conflict-before-KDF/session, or cross-platform same-descriptor guarantees, and
would not catch a production precedence regression.

#### Closure

Closed in the current working tree. Both conflict families now use explicit
post-dispatch stdin and descriptor readback oracles and require the full planted
payload to remain. On Windows an equal root/leaf HANDLE is converted exactly
once, the same CRT descriptor number is injected at both scopes, and cleanup
deduplicates ownership. All seven strengthened conflict cases passed on the
current Windows host with the expected unread markers; the implementation is
also structured for the same anonymous-pipe readback on POSIX.

### posix-unread-source-oracle | high | The valid-session and self-authentication rows unconditionally fail on POSIX

The POSIX `_HARNESS` probes only descriptor numbers present in
`assert_closed_descriptors`, which `_run` populates from the explicit closure
arguments. Neither `test_live_session_makes_root_source_unused_and_leaves_it_unread`
nor `test_root_source_is_inapplicable_to_self_authenticating_rotation_and_unread`
requests such a probe, yet both require `S13_DESCRIPTOR_OPEN` in stderr. The
Windows harness happens to probe every converted descriptor, masking the
asymmetry on the current host. On POSIX no marker can be emitted and both tests
must fail regardless of production behavior, so the matrix is not portable and
does not provide the required POSIX unread-source proof for valid-session and
self-authenticating refusal.

#### Closure

Closed in the current working tree. Both rows now request
`assert_unread_indices=(0,)` and require `S14_DESCRIPTOR_UNREAD`, using the same
readback oracle on POSIX and Windows rather than the platform-asymmetric S13
marker. The two strengthened cases passed on the current Windows host.

### root-same-scope-conflict | medium | The subprocess matrix omits root-channel internal exclusivity

S14 exercises `--secrets-stdin` plus `--secrets-fd` on all five leaf commands
and exercises both root/leaf collision shapes, but never supplies
`--profile-secrets-stdin` together with `--profile-secrets-fd`. The accepted ADR
requires each scope to be internally exclusive before dispatch, and the root
selector is a distinct capability with its own diagnostics. Unit coverage from
S20 does not replace S14's required fresh-process proof. A root parser, option
wiring, localization, or dispatch regression could therefore consume or prefer
one root source while every S14 row remains green.

### strict-refusal-oracles | medium | Oversize, recursive-duplicate, typed-diagnostic, and leak assertions are independently satisfiable

The oversize payload is 8,193 spaces, so increasing or deleting the 8 KiB bound
still reaches an invalid-JSON refusal with exit code 2 and passes. The recursive
duplicate is nested beneath the forbidden `extra` field, so deleting recursive
duplicate detection still reaches strict-model extra-field refusal and passes.
No malformed row asserts the expected too-large, invalid-JSON, or missing/extra
diagnostic, and payload-specific planted values such as `not-json`, `one`, and
`two` are not passed to `_assert_refused`'s leak census. Thus the matrix would
miss regressions in the named bound and recursive-key guards, could accept a
wrong refusal category as proof of a typed contract, and could emit or log the
malformed credential values without failing.

### target-refusal-partition | medium | Wrong, blank, absent, and bad-secret rows do not prove their distinct read ordering

The five target cases all use root stdin and assert only exit code 2, prompt and
static-secret absence, and durable-state equality. They do not assert the
missing-target or profile-not-found diagnostics for wrong, blank, and absent
targets, nor an authentication diagnostic for blank and nonblank wrong secrets;
stdin also has no post-dispatch unread/consumed oracle. A regression that reads
a valid root payload before resolving an exact target, or routes all five cases
through one unrelated refusal, leaves every assertion unchanged. The table
therefore does not prove that an exact target is required before source
consumption while valid targets with bad secrets actually reach bounded read
and authentication.

### parse-precedence-oracle | medium | The parse-error row can read the root descriptor and still pass

The parse-error case supplies only the closed number `999999`, expects exit
code 2, and asserts that the word `unreadable` is absent. The live English
descriptor diagnostic is “not an inherited readable profile authentication
channel,” which does not contain that substring. If parse precedence regresses
and dispatch attempts the descriptor read, the resulting typed descriptor
refusal still has exit code 2 and satisfies every assertion; the planted secret
absence is vacuous because no bytes were supplied. The row also does not scan
the prompt catalogue. Help's expected exit code 0 is useful, but the parse arm
does not prove source-read or prompt precedence.

### refusal-envelope-shape | medium | Most JSON refusal rows never validate a typed JSON envelope

`_assert_refused` checks exit code, prompt/secret absence, log contents, and an
optional storage snapshot, but does not parse the `--format json` error stream
or require its `status`, typed error object, code, and message fields. Only the
conflict callers add a raw status substring, and even that is not structural.
Consequently a regression to plain text, malformed JSON, a Click usage error,
or an unrelated typed refusal can leave most descriptor, payload, retired-field,
environment, target, and self-authentication rows green. This weakens the
matrix's claim to exercise the public typed refusal surfaces.

### non-tty-prompt-topology | medium | The only no-channel subprocess inherits the runner stdin instead of forcing a non-terminal

The hostile-environment row is also the only S14 leaf invocation with neither
explicit secret channel, but it calls `_run` with `stdin=None`. `subprocess.run`
therefore inherits the pytest process's stdin rather than creating a captured
pipe. On an interactive developer host, the production contract correctly sees
a verified terminal and prompts, causing this purported refusal test to block
or consume operator input; on the current non-interactive runner it happens to
refuse. The row must force a non-TTY/EOF input and assert the non-interactive
diagnostic and prompt absence to provide deterministic prompt-only-TTY proof.

### descriptor-refusal-partition | medium | Reserved and unreadable descriptor cases accept the same generic refusal

The leaf and root descriptor tables assert only exit code 2, generic leak and
prompt absence, and state equality for `-1`, `1`, `2`, and `999999`. If the
reserved-stream guard is deleted, reads of `-1`, stdout, and stderr fail as
ordinary unreadable descriptors under this captured subprocess topology and
still satisfy every assertion. The cases therefore do not prove the required
negative/1/2 reserved refusal separately from the genuinely unreadable-number
path; their test names' “typed” claim has no diagnostic oracle.

### retired-restore-field-oracle | medium | Reaccepting the legacy password field still leaves its test green

The restore hard-cut row supplies `{"password": _REFUSAL_SECRET}`, while the
source capsule is protected by `_PROFILE_SECRET`, and asserts only an eventual
refusal and no publication. If production reintroduces `password` as an alias,
the payload is accepted but the application rejects the deliberately wrong
credential, producing the same exit code 2, no mutation, and no leak. Without
the correct capsule passphrase under the retired name or an exact
unexpected-field diagnostic, this test does not prove the required hard cut.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
