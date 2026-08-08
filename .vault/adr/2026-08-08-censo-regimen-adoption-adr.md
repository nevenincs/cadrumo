---
tags:
  - '#adr'
  - '#censo-regimen-adoption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:678b1185f47ada6508b16626fea8749533a188cb1b07a67440ef70dbaa5ecb6a'
related:
  - '[[2026-08-08-censo-regimen-adoption-reference]]'
  - '[[2026-07-23-profile-setup-flow-adr]]'
  - '[[2026-06-05-live-censo-calendar-reconciliation-adr]]'
  - '[[2026-06-13-first-filer-attestation-adr]]'
---

# `censo-regimen-adoption` adr: `The cotejo defers the regimen axis and records unadopted obligation evidence` | (**status:** `accepted`)

## Problem Statement

The Certificado de Situación Censal (procedure G313) is parsed into a typed
record carrying six certified fields. Two of them — `situacion_tributaria` and
`obligaciones_periodicas` — speak to the taxpayer's obligation surface. Neither
becomes a profile fact, and, contrary to the domain module's own docstring
describing them as "display-only certificate evidence", neither is rendered
anywhere either: they are parsed and then dropped on the floor with no consumer
in the tree.

Meanwhile a régimen axis DOES exist on the profile schema —
`taxpayer_type.ley_49_2002_special_regime_option_declared`, `…_option_date`,
`…_renunciation_declared`, `…_renunciation_date`, anchored to modelo 036
casillas 651-654 — populated by the setup wizard from the operator's own typed
answers and consumed by deadline derivation in `domain/deadlines/_profiles.py`.

So the question is put sharply: AEAT's authoritative censal statement is
discarded while a hand-typed answer drives the filing calendar. Two decisions
are needed. Does the cotejo adopt the régimen axis from the certificate? And
what happens when AEAT and the operator disagree on a fact that drives
deadlines?

## Considerations

- The régimen's legal meaning IS groundable. Ley 49/2002 art. 14.1, bundled at
  `ley-49-2002-art-14.html`, establishes the opt-in as an exercised *opción*
  binding the entity indefinitely until renounced, both "en la forma que
  reglamentariamente se establezca" — the censal declaration. The régimen is
  genuinely a censal fact and AEAT genuinely holds the authoritative record of
  it. The grounding gap is not here.
- The grounding gap is the certificate's vocabulary. AEAT's "¿Qué certifica?"
  enumeration for G313 lists six certified fields and none of them is a
  régimen field. The two candidate carriers are typed `tuple[str, ...]` —
  free-form prose lines — and the domain record deliberately leaves the PDF
  layout extraction unpinned until a real issued-certificate specimen exists.
  The inbound adapter refuses every document today.
- The only vocabulary for those two fields anywhere in the tree is synthetic
  fixture prose invented by a test author ("Alta en el censo de empresarios",
  "303 trimestral"). It is not evidence of what AEAT prints.
- The cotejo already excludes `condicion_residencia` and `representantes_nif`
  for exactly this reason: mapping certificate prose onto a typed profile enum
  needs the specimen's exact vocabulary, and auto-mapping conflates axes.
- A divergence primitive already exists and is mature: `CensoDivergence`, the
  indexed `censo.divergencia.{n}.*` fact namespace, whole-namespace replacement
  on re-cotejo, and a standing WARNING `Notice` on every profile read. The
  divergence-to-operator rendering path is live and reaches the
  `config.profile.show` envelope; this record cites it rather than re-solving
  it.
- Prior rulings already govern the disagreement question. The
  `live-censo-calendar-reconciliation` record rules that the calendar resolves
  each obligation from live censo-backed facts when present, falls back to
  profile facts otherwise, and refuses rather than silently defaulting, stamping
  the source on every emitted obligation. The `profile-setup-flow` record
  establishes the cotejo compare-select shape. Neither needs restating or
  duplicating here.

## Considered options

- **Adopt the régimen axis by parsing `situacion_tributaria` prose.** Rejected.
  It requires inventing the mapping from an unknown Spanish phrase to a typed
  boolean, on a filing-grade axis that drives the deadline calendar. No BOE
  text, no AEAT publication and no bundled corpus file states how — or whether —
  the certificate prints the Ley 49/2002 régimen. This is precisely the "guess
  the tax semantics" failure the grounding rule forbids.
- **Adopt the régimen axis behind a heuristic keyword match with an advisory.**
  Rejected, and worse than the above. A keyword match that silently fails to
  fire looks identical to a certificate that does not mention the régimen, so
  the operator gets a confident-looking green cotejo over an unexercised
  matcher. Fabricated coverage on a deadline-driving axis.
- **Leave both fields discarded until a specimen arrives.** Rejected. It keeps
  the actual defect — AEAT's statement is silently dropped — and it is
  independent of the specimen. The certificate's verbatim prose can be
  preserved without interpreting one word of it.
- **Mint a new "unreconciled certificate evidence" record type.** Rejected as
  duplicate authority. The existing divergence row already means exactly
  "certificate evidence the operator did not adopt", already replaces its
  namespace on re-cotejo, and already carries a standing warning.
- **Defer adoption on grounding, and record the unadopted obligation fields as
  divergence rows.** Chosen.

## Constraints

- Reopening this decision depends on an artefact nobody in this repository
  controls: a real issued G313 specimen. Until one exists, the whole cotejo
  family is unreachable live and every test drives it synthetically.
- The `domain/censo/_certificado.py` module is under concurrent edit by another
  campaign at the time of this record. The implementation is therefore layered
  into the application package rather than extending the domain projection
  function, which is the correct layer for it anyway: the domain record states
  what the certificate says, the application decides what the cotejo does with
  it.
- The standing divergence `Notice` prose describes the rows as "profile
  field(s)". Widening the divergence axis to include certificate-side axes with
  no profile counterpart makes that wording narrower than the fact set it
  summarises.

## Implementation

The cotejo does not adopt the Ley 49/2002 régimen axis. Certificate values for
that axis are not projected to profile facts and the operator's wizard answers
continue to drive deadline derivation unchanged.

A new application-layer projection, `censo_unadopted_evidence`, reads the
certificate record and returns one `CensoDivergence` per certified line of the
two obligation-bearing fields, at the certificate-side axes
`censo.certificado.situacion_tributaria.{i}` and
`censo.certificado.obligaciones_periodicas.{i}`. One row per line rather than
one row per field, so no separator has to be invented and the certificate's
prose survives byte-for-byte: the `artefact_value` is that line verbatim, never
parsed, classified or mapped. `source` stays the non-official artefact
provenance token, so nothing this produces can ever read as an AEAT-verified
fact.

Those rows flow through the existing `apply_cotejo` write path alongside any
operator-deferred axes, so they inherit the atomic single-event commit, the
whole-namespace replace on re-cotejo, and the standing warning that rides every
profile read until the operator resolves them. No new write path, no new event
type, no new notice channel.

The divergence axis is redefined — in the type's own contract — as the axis of
the diverging *evidence*: a profile schema path where the certificate axis has a
profile counterpart, and a `censo.certificado.*` path where it does not. The
standing notice prose is widened across all four locale catalogues from "profile
field(s)" to "profile or certificate field(s)".

## Rationale

The knockout is the grounding rule. On a surface that determines which modelos a
taxpayer must file and when, an unverifiable mapping is not a lesser version of a
verified one — it is a worse outcome than the status quo, because it wears the
authority of the certificate while being invented. A deferral that names its
reopening trigger costs the operator nothing they have today; a wrong adoption
costs them a missed or spurious filing obligation.

But the disagreement half of the question does not depend on the specimen, and
answering it is where the real gain is. "AEAT's statement is discarded" was
literally true — two parsed fields with zero consumers. Preserving them verbatim
as unadopted evidence requires interpreting nothing, and it converts a silent
drop into a standing operator-visible warning through machinery that already
exists and is already proven.

The disagreement policy itself is not minted here. The operator's answer stands
as the profile fact; the certificate's value persists beside it as unadopted
evidence; a WARNING notice rides every profile read until it is resolved; and
the calendar continues to stamp the source of each obligation per the
`live-censo-calendar-reconciliation` ruling. Neither side silently overwrites the
other, which is the property that matters on a deadlines-driving axis.

## Consequences

- AEAT's certified obligation statement stops being silently discarded. An
  operator whose certificate says something the profile does not now sees a
  standing warning instead of nothing.
- The régimen axis remains operator-attested. A taxpayer who mistyped their Ley
  49/2002 status still gets a wrong calendar, and this record does not fix that.
  It is the honest state: the application cannot currently verify that axis
  against AEAT at all.
- **Open gap, precisely stated.** When a real G313 specimen is obtained, the
  `situacion_tributaria` block's vocabulary must be read against it and this
  record revisited to decide whether the régimen — and the periodic-obligation
  list — can be adopted as typed facts. That work is blocked on the specimen, not
  on engineering effort, and this record is the reopening trigger.
- **Open gap, second.** The divergence rows surface on the profile read envelope
  only. An obligation-bearing divergence arguably also belongs on the calendar
  surface, where its consequence is felt. That is a genuinely separate decision
  about the calendar's notice surface, and is deliberately not ruled here.
- The widened divergence axis means a divergence row is no longer guaranteed to
  name a writable profile path. Any future consumer that resolves the axis as a
  schema path must tolerate the `censo.certificado.*` namespace.
