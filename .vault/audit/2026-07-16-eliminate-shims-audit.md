---
tags:
  - '#audit'
  - '#eliminate-shims'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:8aec57198bbbf675a68c8ad30249de6889953a3df0c535769ab31be8ad53b30f'
related:
  - "[[2026-06-04-eliminate-shims-adr]]"
---

# `eliminate-shims` audit: `CI closure code review`

## Scope

Review the CI-closure changes made after hosted run `29464082572` exposed
cross-platform browser provisioning, terminal-styled CLI help assertions,
normative sidecar provenance, and real-pipe scheduling failures. The review
also checks the touched surfaces against the codified hard-cut rules:
no legacy authorities, no duplicate runtime paths, and no weakened tests.

## Findings

### html-attribution-authority | high | Retired manifest remains an extractor dependency

`dev/docs/preprocess/_html.py` still resolves the BOE permalink from a
`normatives/<stem>.json` sibling. Commit `b791f52011` deliberately deleted the
last such file as a retired summary straggler, and the corpus gate prohibits
restoring it. The real extractor test consequently loses the official URL and
fails. The authoritative consolidated HTML already carries a canonical BOE
link, so the manifest reader and its JSON dependency are dead architecture.

Resolution on 2026-07-16: resolved. The extractor now reads the authoritative
BOE canonical link from the HTML before content clipping; the JSON import and
sibling-manifest resolver were deleted, and the genuine fragment fallback was
retained.

### atomic-short-write-proof | medium | Completion harness misses the production loop

The revised pipe harness forces a short `os.write` before calling `_write_all`,
then switches the descriptor to blocking mode. A one-call mutant of
`_write_all` can therefore pass because its own blocking write may accept the
entire remaining suffix. Replace the scheduling lottery with a deterministic
real-descriptor proof in which `_write_all` itself commits a positive partial
write and then makes the next call, while retaining the separate immediate
full-pipe `BlockingIOError` contract.

Resolution on 2026-07-16: resolved. The harness now separates blocking
byte-exact completion from a deterministic nonblocking proof where `_write_all`
itself commits a positive prefix and must make the next call before
`BlockingIOError` propagates.

### extractor-terminology | low | Retired manifest wording survived the hard cut

After the implementation fix, developer comments and the extractor test name
still described the deleted manifest path. That wording would misdirect future
maintainers toward an authority that no longer exists.

Resolution on 2026-07-16: resolved. The remaining comments, test description,
and test name now describe the canonical-link authority and canonical-less
fragment fallback.

### atomic-offset-mutation | medium | Continuation proof did not pin the resumed offset

The first deterministic replacement proved that `_write_all` made another
call after a positive partial write, but a mutant that resent the full view
would encounter the same immediate backpressure and still pass. The test did
not yet prove that continuation begins at the recorded offset.

Resolution on 2026-07-16: resolved. On POSIX, a timer signal interrupts a
blocking real-pipe write after a positive prefix and releases the reader; the
same `_write_all` call must resume and deliver the byte-exact payload. Resending
the full view duplicates the prefix and fails. Windows retains the real
nonblocking next-call/backpressure proof alongside blocking byte-exact
completion. The production loop has no platform-specific branch: Ubuntu CI
pins its exact resumed offset and both hosted platforms pin their real
descriptor contracts.

### canonical-provenance-mutation | medium | BOE host assertion allowed the wrong document

The attribution test asserted only that `boe.es` appeared, so a BOE root URL
or a different legal document could satisfy it.

Resolution on 2026-07-16: resolved. The test now requires the exact canonical
permalink embedded by the authoritative Ley 37/1992 HTML.

### duplicate-example-extractor | medium | Test-only parser duplicated production logic

`dev/docs/preprocess/_example.py` carried a second HTML tag parser, provenance
identifier, and attribution string solely for the sidecar contract tests. It
also directed consumers to the retired sibling manifest.

Resolution on 2026-07-16: resolved. The duplicate module was deleted and its
contract tests now import the production HTML extractor directly.

### retired-sidecar-producer | medium | Shipped sidecars named the deleted example extractor

Ten committed normative sidecars still declared
`normatives-html-example` after that duplicate producer was deleted. Their
payload attribution also directed maintainers toward the retired sibling
manifest, leaving dead architecture embedded in the shipped corpus despite
the live extractor and tests being reconciled.

Resolution on 2026-07-16: resolved. All ten sources were regenerated through
the production HTML extractor. The corpus freshness gate now requires every
normative HTML sidecar to declare the live `HTML_EXTRACTOR_ID`, so neither the
retired producer nor an unreviewed alias can return.

### sidecar-production-drift | medium | Legacy sidecars did not equal the live extractor

Full-record parity found another 42 normative sidecars whose source hashes
were current but whose attribution still predated canonical-link extraction.
Hash freshness alone could not detect that derived metadata had drifted from
the one production extractor.

Resolution on 2026-07-16: resolved. Every normative HTML source with committed
sidecars was regenerated through `extract_html`. A production-parity gate now
rebuilds each source with `build_outputs` and compares the complete typed
records, covering provenance, attribution, units, status, and version.

### duplicate-lifecycle-enum | high | Adapter mirror duplicated the domain authority

`BucketLifecycleStatus` repeated the exact values of the authoritative domain
`UserProfileStatus`. Application code mapped between them by string value and
a parity test existed only to keep the duplicate declarations synchronized.
Extracting `ProfileBucketPointer` into its leaf module also made the hidden
application-to-adapter dependency visible to the architecture gate.

Resolution on 2026-07-16: resolved. `BucketLifecycleStatus`, its facade export,
the value mapper, and the duplicate-enum parity test were deleted. The bucket
manifest and every consumer now use `UserProfileStatus` directly. The shared
fixture coverage test moved from the core package to the repository test
domain, eliminating its obsolete import-linter exception while preserving the
core inward-dependency boundary.

### ci-residual-repairs | low | Residual fixes preserve canonical authorities

The remaining changes introduce no compatibility aliases, production-path
duplication, fake collaborators, monkeypatching, skipped tests, or test-side
business logic. Chromium provisioning uses the existing `just env-playwright`
authority; CLI assertions remove terminal styling only at the test semantic
boundary; sidecar hashes remain raw-byte provenance; and atomic-write
production behavior is unchanged.

## Recommendations

Delete the retired sibling-manifest resolver and parse the BOE canonical link
from the authoritative HTML before content clipping. Retain only the generic
attribution fallback for genuine article slices that carry no canonical link.
Replace the atomic completion harness with deterministic blocking completion
plus an anti-mutation nonblocking proof that observes `_write_all` continuing
after a positive short write.
Re-run the extractor, corpus freshness, browser, CLI, atomic-write, static, and
Vault gates before publishing the replacement PR head.

All recommendations were completed on 2026-07-16 and re-entered formal review.
