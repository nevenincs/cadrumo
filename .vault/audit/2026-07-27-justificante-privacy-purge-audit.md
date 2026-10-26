---
tags:
  - '#audit'
  - '#justificante-privacy-purge'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:b3223c99f74051736ce07dd5c7fc1329e05e14c5413800676579eddc750e22b5'
related: []
---

# `justificante-privacy-purge` audit: `history rewrite cutover: real-corpus justificante blobs stripped`

## Scope

Nine committed test fixtures under `src/cadrumo/tests/fixtures/justificantes/` were
real sanitised AEAT filings belonging to the operator. All nine were replaced with
generated synthetic parser anchors, and the pre-replacement blobs were then stripped
from git history with `git filter-repo`. This document records the cutover.

**Every commit SHA predating this rewrite is invalid.** The rewrite touched 17,319
commits. Vault documents across the corpus cite pre-rewrite SHAs; those citations are
knowingly dangling by operator decision, and were deliberately not swept. A SHA quoted
in any document dated on or before 2026-07-27 should be read as naming a commit that no
longer exists under that identity.

Pre-rewrite `main` was `78811c57fa94121809f2ba536a938e811d477756`. Post-rewrite `main`
is `bf7127e30b0e0707fdbb69ecc932a32c655b2c35`.

## Findings

### sanitiser-has-no-detection-stage | critical | the tool replaces only hand-listed values, so an unlisted identity passes through silently

The sanitiser is token replacement over an operator-supplied `TokenMap`; its own module
docstring makes that map the leak-detection boundary. Nothing scans a document for
identities the operator forgot to list. The failure is silent and unbounded: the tool
cannot report what it was never told about. This single defect produced every leak below.

### checksum-valid-identities-survived-sanitisation | critical | two fixtures retained a bank account and a third-party identity

`100/2021-0A` retained an IBAN passing the ES mod-97 checksum. `190/2024-0A` retained a
NIF/NIE passing the control-letter check, plus an email address and a phone number.
None appeared in either sidecar's `replacements_applied`, so the sanitiser did not write
them. Modelo 190 is a perceptor-level declaration built out of third-party records,
which is why an identity nobody listed survived there.

### names-survived-in-every-remaining-fixture | critical | 17 unexplained name-shaped strings across the other seven

The seven fixtures believed clean carried 17 distinct name-shaped strings that were not
sanitiser output, absent from the synthetic-fixture vocabulary, and absent from the
bundled AEAT normative corpus of roughly 8.8 million characters. One recurred across two
different modelos. Form chrome differs per modelo, so a string spanning both is a person
or an entity, not a label. One instance was confirmed by exhaustion: a three-word string
sitting immediately after the NIF placeholder, in a file that also contained the name
placeholder, i.e. one occurrence replaced and another missed.

### recurrence-heuristic-hid-the-broader-leak | high | the first scan assumed taxpayer data appears exactly once

The initial name scan discarded any candidate appearing in more than one fixture as
boilerplate. A filer's name across four quarterly filings recurs four times and was
therefore filtered out. The one confirmed leak was found only because it happened to be
confined to a single quarter. Re-scanning without that assumption exposed the other
sixteen strings. A discriminator that encodes an assumption about the adversary's shape
will miss every case that violates it.

### residual-gate-cannot-see-names | high | the new gate keys on checksums, which names do not have

The residual-identity gate detects NIF/NIE by control letter and IBAN by mod-97. That is
what keeps its false-positive rate near zero, and it is also why names, addresses and
postal codes are structurally outside it. A green gate is not evidence of a clean
fixture. Only the corpus-vocabulary method sees names, and it is materially noisier.

### verification-instruments-need-positive-controls | high | two checks in this campaign returned confident falsehoods

A PDF metadata scan reported all nine fixtures free of DocInfo; it was only trustworthy
once the same scanner was shown to find `/Producer` in the synthetic set. Later, a
byte-probe check of the filter-repo export reported the stripped blobs absent from the
filtered stream — but a positive control showed a blob that must survive was equally
"absent", so the instrument had never worked and its negative was meaningless. Both
checks would have been believed without a control.

## Recommendations

Give the sanitiser a detection stage rather than trusting the completeness of a
hand-written map. The pattern-based residual scan proves detection needs no cleartext:
anything identity-shaped that the sanitiser did not itself write is unaccounted for by
construction.

Add a name-oriented residual check alongside the checksum gate, using the
corpus-vocabulary method recorded here, and accept its higher noise rather than leaving
names unexamined.

Restore a live positive control for the residual gate. Its only current proof is a
planted-identity unit test, because the real leaks that served as its control were
consumed by the replacement that fixed them. A synthetic pre-sanitisation specimen would
restore an end-to-end subject and also return a genuine subject to the sanitiser pipeline
guard, which no longer runs against any real sanitiser output.

Treat unreachable-but-uncollected objects on the forge as still exposed. A force-push
does not garbage-collect the remote, and stripped objects may remain retrievable by
direct SHA until the host collects them. Ask the host to run garbage collection to close
that window.

Do not read this campaign's clean scans as proof the fixtures were ever safe. Nine of
nine leaked, in two distinct classes, past a gate whose name asserted it checked
absence while it checked presence.
