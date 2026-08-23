---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0f0ad0a6dc989f640d4c621df3217f0a47d304715c8712d1bfff28b8106723de'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]"
---
# `secure-storage-performance-hardening` audit: `s59 review b shipping installed runtime`

## Scope

This independent Reviewer B pass audited the effective post-cutover build,
shipping, and installed-runtime architecture governed by the accepted
production-authored `CommandSpec` decision and plan step `W02.P03a.S59`.

The review covered the clean Git-archive build root; wheel, sdist, retained
source archive, Python cohort, and release-cohort provenance; installed-runtime
origin confinement; exhaustive command identity, localized metadata, policy,
schema, deferred-target, and selected-path import-budget attestations; and the
Scoop, Homebrew, MCPB, Claude plugin, marketplace, readiness, promotion, and
publish consumers. It also checked that production carries neither development
imports nor cohort/runtime-cache authority and that downstream lanes cannot
rebuild or regenerate command authority.

## Findings

### cross-cohort-evidence-binding | critical | Same-version foreign bytes can be recorded as the sealed release cohort

The Scoop, Homebrew, and Claude shipping workflows execute the separately
built per-OS Python cohort (`cadrumo-python-cohort-linux`) while also downloading
the immutable release cohort. They then pass oracle output from the former to
`distribution_evidence_emit` with the latter as `--release-cohort-dir`.
`_assert_oracle_bound_to_cohort` accepts that pairing when the captured
`aeat --version` text contains the release cohort version; it compares no wheel,
executable, Python-cohort-manifest, or release-cohort digest. Consequently two
different builds of the same version are indistinguishable at the evidence
boundary.

An independent exploit probe constructed a planted release cohort at version
`0.2.1`, supplied oracle evidence whose resolved executable was the current
worktree `.venv` Python rather than a planted cohort member, and successfully
minted a passing record carrying the planted release cohort ID. Existing
negatives reject `0.1.0`, `0.2.10`, and prerelease version strings, but do not
plant equal-version unequal-byte evidence. This violates the accepted
byte-identical tested-cohort promotion constraint and makes affected readiness
rows capable of attesting bytes that were never in the promoted cohort.

### clean-archive-gates | high | Both explicit clean-source and built-artifact CommandSpec lanes fail

The two archive/install tests normally excluded by the repository's unit-only
pytest selection were run explicitly with the integration marker. Both failed.
The clean tracked-checkout/direct-source/editable lane hard-codes `361` nodes
while the archived production graph contains `364`, so it rejects the current
complete graph rather than dynamically enforcing its exact set. The wheel,
sdist, and sdist-to-wheel lane separately found eight missing localized rows in
the archived commit for the root custody secret-channel help keys. The live
worktree currently reports `364` nodes and zero missing locale rows, proving the
locale repair exists only outside the clean archived commit used by the shipping
lane; the stale `361` assertion remains in the test source. Thus S56/S57 cannot
currently provide the checked clean-checkout and installed-artifact evidence
claimed by the completed plan steps.

Exact execution result: `2 failed in 406.18s`; the failures were
`test_clean_tracked_checkout_direct_source_and_editable_install` (`364 != 361`)
and `test_wheel_sdist_and_sdist_wheel_preserve_command_spec_authority` (eight
missing locale rows).

Final severity census: critical 1, high 1, medium 0, low 0.

The remaining focused unit evidence passed: 109 source/distribution/cohort and
publish tests passed with the two integration tests deselected by the normal
unit marker. Running those two explicitly produced the failures above. The
canonical audit frontmatter, required sections, annotations, and edited-file
whitespace checks passed; unrelated pre-existing markdown warnings remain in
the earlier S56-S58 audit and execution records.

## Recommendations

For `cross-cohort-evidence-binding`, require evidence to bind the executed
installed bytes to the exact release-cohort artifacts by digest, and route
Scoop, Homebrew, Claude plugin, marketplace, and MCPB execution directly from
the sealed cohort. Add a fail-loud equal-version/different-wheel negative and
prevent readiness from accepting a row whose executable or source manifest
cannot be traced to that cohort.

For `clean-archive-gates`, replace the obsolete scalar node assertion with an
independently derived exact-set comparison, ensure all locale changes are part
of the clean source commit, and require the explicit integration lane to pass
before S56/S57/S58 evidence or S59 reconciliation is accepted.
