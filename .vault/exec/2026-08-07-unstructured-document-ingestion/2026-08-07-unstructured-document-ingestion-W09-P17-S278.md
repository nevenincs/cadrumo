---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:11dfe123ac90af0dc7f18a3158ce626c40ca89a6c3c9d5dad136bd882c6b7937'
step_id: 'S278'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Stop the NIF arm hashing the app own work-unit names, since admitting separators makes modelo-year-period normalise to eight digits plus a trailing letter which is the personal identity shape exactly - 303-2026-1T becomes 13020261T - so every modelo family and both period shapes are hashed and an operator is handed a digest where the export filename should be - the arm is unconditional SHA256_PREFIX on the stated premise that a long digit-led run rarely collides with ordinary text, which separators falsified, and validate_identity cleanly separates the two populations by refusing all fourteen collisions while accepting all eleven real identities

## Scope

- `src/cadrumo/core/redaction/__init__.py`

## Description

- Reproduce the over-redaction at HEAD and confirm the discriminator: `validate_identity` refuses every work-unit name (`13020261T`, `39020260A`, `10020260A`) and accepts every real printed identity.
- Confirm the defect predates this campaign's own commits: the separator-bearing personal-identity pattern is byte-identical across the two commits that closed the neighbour-swallow and the printed-account leaks.
- Split the personal-identity arm into two rules rather than weakening one. The unbroken form keeps the ungated shape-only strategy; the separator-bearing form takes the validity-gated strategy and therefore runs behind the re-reading scanner.
- Enrol the new rule in every classification policy that already named the unbroken one, since an unresolvable rule name is refused rather than skipped.

## Outcome

Every work-unit name in the corpus reaches the operator intact across all six modelo families present and both period shapes. Every real identity still redacts, including the separator-bearing spellings a printed invoice produces and the checksum-invalid lookalike the err-wide arm exists for.

The reason the split is the right shape rather than a compromise: err-wide was justified by a collision claim, and separators falsified that claim for one population and not the other. Withdrawing it everywhere would lose the mistyped-identity catch the claim still earns on unbroken runs; keeping it everywhere costs the filing surface its own naming. The population that disproved the claim is the population that loses the exemption.

A UUID rendered through the log funnel also stops being touched by the identity arm, so the purpose-built identifier rule is no longer contradicted by a second rule about the same value.

## Verification

Reproduction at HEAD, before the change:

    'modelo-130-2026-1T.boe' -> 'modelo-sha256:44bc266f.boe'
    '303-2026-1T'            -> 'sha256:05c1ac79'
    '390-2026-0A'            -> 'sha256:3a9bca9c'

After, with the identity controls beside them:

    'modelo-130-2026-1T.boe' -> unchanged
    '390-2026-0A'            -> unchanged
    '12.345.678-Z'           -> 'sha256:8d2cc42c'
    '12345678Z'              -> 'sha256:1c9f9632'
    '12345678A'              -> 'sha256:cb6f3ba1'

Recorded operator output, the corpus that found this:

    files 497 | lines 725141 | changed 94 | distinct tokens 16
    correctly redacted 16 | over-redacted 0

Redaction suites:

    uv run --no-sync pytest <seven redaction suites> -m unit -q -p no:randomly
    269 passed in 23.96s

Consumers of the funnel:

    uv run --no-sync pytest <llm, cli output surface, storage redaction typing> -m unit -q -p no:randomly
    93 passed in 21.69s

    uv run --no-sync pytest <evidence review, censo pull, atomic create> -m integration -q -p no:randomly
    27 passed in 14.60s

Wider core suite:

    uv run --no-sync pytest src/cadrumo/core -m unit -q -p no:randomly
    3 failed, 1749 passed in 158.01s

Soundness sweep over the locale corpus, unchanged by the split:

    strings 70409 | funnel-changed emissions 24 | digests recovered 48 | unsound 0

Mutation G, applied by a plugin outside the repository, restores the shape-only arm over separators:

    MUTATION G APPLIED. over-redaction restored: 'modelo-sha256:44bc266f.boe'
    2 failed, 1 passed

Its positive controls stay live in both directions: an unbroken identity and a separator-bearing identity both still hash under the mutation, so the red cannot be read as "the identity rules stopped running".

## Notes

The three failures in the wider core run are the same tree-wide peer gates recorded against the sibling Steps: an AEAT route literal in an adapter auth test, two M036 refusal codes with no authored suggestion, and year-qualified period tokens in adapter and registry fixtures. None touches redaction.

The brief reported a UUID being caught by the identity arm. Measured, it was not: the CLI funnel routed it to the purpose-built identifier placeholder and the log funnel left it intact. The split removes the latent contradiction regardless.

The brief's corpus figures and mine differ (210 files and about a million lines against 497 files and 725,141 lines), so the two sweeps were scoped differently. The finding reproduces either way; only the denominator moved.

A deliberate asymmetry now ships: a checksum-invalid lookalike hashes unbroken and survives separator-bearing. That is the trade the split makes, and it is the direction the measurement supports.

The source change was landed by an automated sweep commit rather than by this session, together with the sibling gate, in one commit. The three files went in atomically, so no window existed where a policy named a rule the registry did not declare.
