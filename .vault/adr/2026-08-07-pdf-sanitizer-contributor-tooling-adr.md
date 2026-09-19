---
tags:
  - "#adr"
  - "#pdf-sanitizer"
date: '2026-08-07'
related:
  - "[[2026-07-27-justificante-privacy-purge-audit]]"
supersedes:
  - '2026-04-25-pdf-sanitizer-adr'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:8dc0a6d37c0be386a73ffa6f9bf35f2c820e21b302b0b6cf8ce6758fee940e1f'
---
# `pdf-sanitizer` adr: `sanitiser-is-contributor-tooling-not-shipped-surface` | (**status:** `proposed`)

## Problem Statement

The PDF sanitiser ships inside the distributed package as ten modules under
the inbound-adapters tree, with a full error taxonomy, six localised operator
messages across four catalogues, and a committed table of test-fixture digests.
Nothing in the product reaches it: no CLI verb, no application service, no
adapter. The CLI bridge its own accepted record locks was never built.

Two independent readings of the same code are therefore both defensible today --
an unfinished operator capability awaiting its verb, or misplaced contributor
tooling -- and the codebase offers no signal that discriminates. The ambiguity is
not academic. Under the first reading the correct next action is to build
`aeat sanitize`; under the second it is to remove the package from the
distribution. A reader arriving at the module cannot tell which, and the record
that would tell them asserts a surface that does not exist.

The question needs deciding now because the sanitiser's stated product was
withdrawn from the repository, as recorded in the 2026-07-27 justificante
privacy purge audit, and no record reconciles the tool with the loss of its
output.

## Considerations

- The governing record `2026-04-25-pdf-sanitizer-adr` states the package is
  fixture-preparation infrastructure, not runtime import or general-purpose
  anonymisation. Its own module docstring repeats this verbatim.
- The same record locks an `aeat sanitize` group with four verbs, planned as the
  final phase of its companion plan. No such command group exists and no
  execution record for the phase was ever written.
- The purge audit records that all nine real sanitised fixtures leaked
  identities, in two distinct classes, and were stripped from history. Its
  root-cause finding is that the tool performs no detection: it replaces only
  hand-listed values and cannot report what it was never told about.
- Every committed justificante fixture at HEAD declares synthetic provenance;
  none declares real provenance. The corpus is generated, and the generator
  stamps a deliberately distinct sanitiser version to mark that no document
  passed through the redaction pipeline.
- Output redaction is separately owned and canonical for operator-facing text.
  It detects by pattern over rendered strings at emit time, under a closed
  output-sensitivity taxonomy in `core`. The sanitiser rewrites PDF bytes
  permanently from a declarative map with detection explicitly out of scope. The
  subject, lifetime, mechanism and trust boundary all differ; there is no shared
  concept to collapse.
- Encrypted secure storage governs sensitive artefacts at rest. It bears on data
  the operator holds, and says nothing about bytes a contributor is about to
  commit to a public repository.
- Three live consumers remain, all tests: the residual-identity gate's
  end-to-end control, an einvoice non-mutation contract test reaching the
  attachment-strip primitive, and the digest catalogue pinned by its own drift
  gate.
- Test modules are already excluded from the wheel; the ten source modules are
  not. The digest table of committed fixtures ships to installed operators
  today.
- Test modules under the product tree already import from the development tree
  in roughly a dozen places, so the relocation crosses no new boundary.

## Considered options

- **Build the locked CLI bridge and ship it as an operator capability.** Pro:
  discharges the standing accepted record; gives the machinery a consumer. Con:
  an operator has no need it serves, since storage covers data at rest and
  output redaction covers emitted text; and shipping it asserts a safety
  property the tool has failed on every real document it processed. Rejected on
  the knockout below.
- **Leave it in the package with no consumer.** Pro: zero work; preserves
  optionality. Con: the ambiguity that motivated this record persists and
  compounds, the unreachable digest table keeps shipping, and the stale
  locked-CLI claim keeps misdirecting readers. Rejected: this is the status quo
  the record exists to end.
- **Delete the package outright as legacy.** Pro: smallest surface. Con: three
  live consumers die with it, including the only end-to-end proof that the
  privacy gate and the redaction pipeline agree on a manifest; and the
  zero-legacy mandate governs code reading data an older version wrote, which
  this does not. Rejected as a net loss of coverage, not as wrong in principle
  -- see Consequences for the condition under which it becomes correct.
- **Merge the sanitiser into the output-redaction package.** Pro: one apparent
  home for "removing sensitive values". Con: the two differ in subject,
  lifetime, mechanism and trust boundary; merging would put a byte-rewriting
  artefact transform behind a string-emit API. Rejected as a false neighbour.
  This is the thinnest of the rejections: it rests on a reading of both
  packages rather than on a prior record, and is the one worth re-examining if
  a future outbound-document capability makes the boundary less obvious.
- **Relocate the package to the development tree as contributor tooling.**
  Chosen.

## Constraints

- The error-registry enforcement gate walks the product package only. Moving the
  modules removes their subclasses from that walk, at which point the six
  registered codes resolve to no subclass and the registry gate reds. The
  registry entries and the module move are therefore one atomic change, not a
  move followed by a cleanup.
- Locale removal must route through the locale CLI. Hand-editing the catalogues
  or the intentional-identical allowlist is refused by the shipped parity and
  honesty gates.
- The generated API stubs are CLI-owned. The stale stubs must be regenerated by
  the scaffold verb rather than hand-deleted, and the run sweeps peer modules,
  so only the sanitiser's own deltas are staged.
- The PDF library stays a runtime dependency regardless: the justificante
  extractor relies on it independently.
- **One open question gates the status.** Whether this project will ever again
  commit a real AEAT document as a test fixture is a product decision, not a
  code fact. A "yes" does not change this record's decision -- the tool belongs
  in the development tree either way -- but it makes the detection stage a
  prerequisite for using it again, and that work is currently unowned. The
  decision below is deliberately written to hold under either answer.

## Implementation

The ten sanitiser modules and their colocated tests move to the development tree
as a self-contained package, preserving the existing public-facade discipline:
the pipeline entry point, the token-map and result records, and the error
hierarchy stay the package's only exported surface, and the private modules
remain private.

Six error-registry entries leave the product error registry in the same change,
because the enforcement gate's product-package walk no longer reaches their
classes. Their six locale keys leave all four catalogues through the locale
CLI's removal verb, followed by a scaffold and a drift check.

The two out-of-package importers repoint at the new home: the einvoice
non-mutation test reaching the attachment-strip primitive, and its recorded
import-hygiene debt entry, whose stated rationale survives the move unchanged
while its path does not. The residual-identity gate moves with the package and
continues to walk the whole product tree for real-provenance artefacts, so its
scope is unaffected by its own relocation.

The generated API reference is refreshed through the documentation scaffold
verb, staging only the sanitiser's stubs.

No behavioural change is made to the pipeline. This record relocates a surface
and retires a planned command group; it does not alter what the sanitiser does,
and specifically does not attempt the detection stage the purge audit
recommends.

## Rationale

The knockout is that the sanitiser's threat model is a contributor's, not an
operator's. Its own governing record names the adversaries it defends against: a
reviewer reading a pull-request diff, an attacker cloning the public repository,
a contributor reusing a fixture in a demo. Every one of those is reached only by
committing bytes to version control. An operator never performs that action,
which is why no verb was ever found for a package that has waited four months
for one. The absence of a consumer is not an unfinished feature; it is the
correct behaviour of a product surface that has no product need.

The second, independent reason is that promoting it would be a safety claim the
evidence contradicts. The purge audit establishes that the tool leaked on nine
of nine real documents, that the failure is silent by construction, and that the
prior record's characterisation of its failure modes as loud was wrong. A verb
named for sanitisation, surfaced to an operator holding real filings, would
carry an implicit assurance the tool cannot honour until the detection stage
exists. Shipping it is worse than shipping nothing.

Relocation beats deletion because the three surviving consumers are real
coverage rather than inertia. One of them is the only end-to-end control proving
the residual-identity gate and the sanitiser agree on what a manifest records --
precisely the class of instrument the same audit found returning confident
falsehoods without a positive control. Deleting the sanitiser would remove that
control and leave the gate proved only against planted synthetic inputs.

Relocation also beats leaving it in place, because the ambiguity is itself the
cost. The record and the tree currently disagree about whether a command group
exists; every reader must re-derive the answer, and this record was commissioned
because a reader did.

## Consequences

The distribution loses ten modules, six registered error codes, twenty-four
catalogue entries and an unreachable digest table of committed test fixtures.
Installed operators lose nothing they could reach.

The four-verb command group locked by the superseded record is formally
withdrawn. Any future proposal to surface sanitisation to an operator starts
from a new decision rather than inheriting a standing mandate, which is the
correct default given the leak history.

The purge audit's recommendation to give the sanitiser a detection stage
survives this record and remains unowned. This decision neither performs that
work nor excuses it; it relocates the tool so the work has an honest home if it
is taken up. Stating this plainly is the point: the debt is not discharged by
the move, and a reader should not infer that it was.

The sanitiser becomes harder to reach from an operator context and easier to
reach from a contributor one, which matches who can use it correctly. The cost
is that a future outbound-document capability -- redacting a filing to send to a
third party, for instance -- would not find a shipped primitive waiting, and
would need to reopen the question. That is an acceptable trade while the tool
has no detection stage, and a genuine cost if the product later wants that
capability.

If the residual-identity gate is later given its own minimal document writer,
the sanitiser's last consumers disappear and outright deletion becomes correct.
This record does not pre-authorise that; it names the condition so the next
reader can recognise it rather than rediscover it.

The related record `2026-04-21-real-pdf-fixture-corpus-adr` remains accepted
while the middle layer of its three-layer corpus was withdrawn by the same
purge. That drift is out of this record's scope and needs its own
reconciliation; it is named here so it is not mistaken for something this
decision resolved.
