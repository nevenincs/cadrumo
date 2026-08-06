---
tags:
  - '#adr'
  - '#m184-socio-attribution-handoff'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:cd3dd2bbc5f210e4b376e89ba74b118b6a1fb4841170640eba298a8fdb8580e6'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - '[[2026-07-10-m184-socio-attribution-handoff-research]]'
---

# `m184-socio-attribution-handoff` adr: `M184 attributed-base handoff to socio M100 via typed profile facts` | (**status:** `accepted`)

## Problem Statement

Cross-domain-continuity step `W09.P41.S324` (persona R9-MANUEL-B): a sociedad
civil / comunidad de bienes profile files Modelo 184 with per-socio attributed
bases (LIRPF arts. 86-90 regimen de atribucion de rentas), but a member socio's
personal Modelo 100 in the same workspace receives none of it - the socio
re-enters the attributed share by hand with no typed home, no provenance, and
no guard against forgetting it entirely. The step left the design open between
(A) an auto-resolving cross-profile `attribution_received` binding source and
(B) a documented manual workflow with explicit CLI prompts. This ADR decides.

## Considerations

- **Profiles are bucket-isolated.** Every calculation source resolver reads the
  ACTIVE bucket only: the profile-binding resolver loads the bucket's
  `UserProfileRecord`; the M184 `AtribucionMemberSourceResolver` reads
  `attribution_entity_socios.N.*` facts from the active attribution-entity
  profile; the M353<-M322 `per_grupo_member` fan-in enumerates observations in
  the SAME repository. No production calculation path reads across buckets
  today; sensitive data lives per-bucket in encrypted secure storage.
- **A cross-bucket read is a new security/provenance axis.** Option A requires
  loading a NON-active bucket's encrypted store during the socio's calculate,
  a linkage declaration, staleness re-confirmation against the SC's revision
  lifecycle (the carried-observations discipline), and non-official-evidence
  semantics (a locally-filed M184 is `app_filing` evidence). None of that
  machinery exists; it would be the first cross-bucket data flow in the
  application.
- **The typed-fact machinery already exists on both sides.** The SC side
  models socios as repeatable profile facts (`attribution_entity_socios.N.nif`
  / `name` / `share_pct` / `base_imponible_assigned`, step S323); the M100 side
  resolves `source = "profile"` bindings through the established
  profile-binding channel, and M100 revisions already carry a regimen de
  atribucion casilla surface (the atribucion income/retencion sections
  inventoried by the schema-hardening audit).
- **Silent under-declaration is the real hazard.** A socio who forgets the
  attributed share files an M100 that under-declares with zero findings -
  exactly the class the `no-silent-under-declaration` rule exists to surface.
  Any decision must make the omission loud, whether or not the value flows
  automatically.
- **The M184 verify/file output already computes the per-socio rows** (typed
  `Modelo184MemberRow` detail rows), so the handoff VALUES exist at the moment
  the SC operator finishes - the gap is transport and the socio-side home.

## Considered options

- **A: cross-profile `attribution_received` binding source (auto-flow).** A new
  `BindingSourceKind` whose resolver opens the linked SC bucket, reads its
  filed M184 revision, matches the socio NIF, and materialises the share into
  the M100 engine. Pro: zero re-entry; single source of truth. Con: first
  cross-bucket read (new security surface over encrypted stores); needs a
  linkage-declaration model, revision staleness stamping, and non-official
  evidence semantics; large blast radius for one persona flow. Rejected FOR
  NOW - not buildable as an executable step without its own security ADR, and
  the value delta over B-typed is re-entry of a handful of Decimals once per
  year.
- **B-bare: documentation-only manual workflow.** Document "copy the value
  from the SC's M184 output into `--binding` at calculate time". Pro: zero
  code. Con: per-calculation re-entry, no typed home, no provenance, and the
  forgotten-share case stays silent. Rejected - fails the
  no-silent-under-declaration bar.
- **B-typed (CHOSEN): manual handoff through typed socio-profile facts +
  existing profile bindings + M184 handoff output + omission advisory.** The
  socio's OWN profile gains a repeatable `attribution_received` fact group
  (entity NIF, entity name, share pct, attributed base, filing year); the M100
  atribucion casillas bind `source = "profile"` through the existing resolver;
  the M184 verify/file CLI emits explicit per-socio handoff lines (the values
  plus the exact socio-side command); an M100 advisory fires when the profile
  declares attribution facts for the filing year but the atribucion casillas
  resolve empty (and, mirror case, prompts profile capture when the profile is
  a declared SC member with no facts). Pro: one-time entry per year onto the
  profile (not per calculation), full provenance via the profile-binding
  channel, loud omission, zero new security surface, all four mechanisms are
  established patterns. Con: the value is still typed twice in the workspace
  (SC profile, socio profile); a transcription typo is possible - mitigated by
  the advisory carrying the expected value context in the M184 handoff output.
  Accepted.
- **Future path:** option A remains open as a follow-on feature; B-typed's
  fact group is exactly the slot an auto-resolver would populate, so A would
  supersede only the transport (CLI transcription -> cross-bucket read), not
  the schema. A requires its own ADR covering cross-bucket access, staleness,
  and evidence semantics before any step is authored.

## Constraints

- **Registry-grounded casilla targets.** The exact M100 atribucion casilla ids
  MUST be read from the loaded snapshot of the target M100 revision (never
  from `ls` or memory, per the fragmented-registry discipline); the binding
  grounding cites LIRPF arts. 86-90 already present in the legal catalogue
  (the M184 bindings cite `ley-35-2006:art-87` / `art-89`).
- **Profile schema is registry-authored.** The fact group lands in the central
  profile schema TOML and rides the loader, mirroring the S323
  `attribution_entity_socios` shape; no inline Python schema literals.
- **No cross-bucket read anywhere in this slice.** The resolver side is the
  UNCHANGED profile-binding resolver over the active bucket.
- **Locale discipline.** Operator-facing prose routes through `tr()` and the
  locale CLI across en/es/ca/hu. RESOLVED under the cross-cutting
  attribution-locale follow-up (task #204): the S413 M184-side handoff Notice
  message and the S414 M100 omission-advisory message / next_action (both
  triggers) now route through `tr()` keys authored across en/es/ca/hu via the
  locale CLI (`cli.app.modelo.work.m184_socio_handoff_message`,
  `application.modelo.findings.attribution_received_unfolded[_next_action]`,
  `application.modelo.findings.attribution_received_uncaptured[_next_action]`),
  matching the `_dt12_advisory` / `_art20_advisory` tr()-routed precedent. The
  handoff Notice `suggestion` stays a code-built machine command so the exact
  `--binding 1577=<importe>` fold-in token is stable across every output
  language. The S411 schema-capture half needs no locale keys: the
  `attribution_received` fact group is captured through the generic
  schema-driven profile edit path via its inline schema `description` prose,
  exactly as its sibling `attribution_entity_socios` group is (neither carries
  wizard prompts nor locale keys), so no redundant capture prompts were added.

## Implementation

Four small surfaces, each an established pattern:

1. **Socio-profile fact group.** Repeatable `attribution_received.N.*` facts
   (entity_nif, entity_name, share_pct, base_imponible_attributed,
   filing_year) in the central profile schema, captured by wizard/edit
   prompts.
2. **M100 profile bindings.** `source = "profile"` bindings on the M100
   revisions mapping the fact group onto the regimen-de-atribucion casillas
   the loaded snapshot declares, with arts. 86-89 legal_refs and full
   provenance parity.
3. **M184 handoff output.** The M184 verify/file path already holds typed
   `Modelo184MemberRow` rows; emit per-socio info Notices carrying the
   attributed values and the exact profile-capture command for the socio side.
4. **Omission advisory.** M100 verification advisory (non-blocking) when
   attribution facts exist for the filing year but resolve to no casilla
   value, and when an SC-membership signal exists with no captured facts -
   the no-silent-under-declaration guard for this flow.

## Rationale

B-typed is the only option that is simultaneously executable now (every
mechanism exists), honest about its own limits (the captured-but-unfolded case
surfaces loudly via the S414 advisory; the fully-forgotten socio-bucket case is
a bounded, disclosed gap - see Consequences), and non-expanding on the security
model (no cross-bucket reads). Option A's genuine
advantage - eliminating one manual transcription per year - does not justify
opening the first cross-bucket data flow without a dedicated security ADR; and
because B-typed lands the typed home and the advisory, A later reduces to a
transport upgrade rather than a redesign.

## Consequences

- **Gain:** the socio's M100 gains a typed, provenance-carrying home for the
  attributed base; re-entry drops from per-calculation to once per filing
  year; the CAPTURED-but-unfolded case (the socio recorded the
  `attribution_received` facts but did not fold the value into their M100)
  becomes a visible S414 advisory instead of a silent zero.
- **Uncovered (bounded, disclosed):** the FULLY-forgotten case - a socio who
  never captures the `attribution_received` facts AND never enters the
  atribucion casilla - still verifies with zero findings on their own bucket.
  The S414 advisory fires only when facts are PRESENT and the casilla resolves
  empty; with no facts on the socio bucket there is nothing to compare against,
  and (per the Considerations) no production path reads across buckets to
  discover the omission. The loud channel for this case is the S413 M184-side
  handoff Notice (emitted on the ENTITY operator's verify/file, instructing them
  to relay each socio's attributed value); full socio-bucket coverage of the
  fully-forgotten case awaits cross-bucket auto-flow (Option A) or a 2024
  relation-symmetry follow-up. This is the exact hazard the Considerations name,
  accepted here as bounded because Option A is deferred behind its own security
  ADR.
- **Cost (accepted):** the attributed value exists twice in the workspace and
  is transcribed by the operator; a typo is caught only if the operator reads
  the handoff Notice values.
- **Bounded:** cross-bucket auto-resolution (option A) is explicitly deferred
  behind its own future ADR; this decision neither builds nor forecloses it.
- **Ownership:** executable steps land in the cross-domain-continuity plan
  replacing `W09.P41.S324`.

## Code-surface footprint

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml` (fact group)
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/` and
  `revisions/2025/bindings/` (profile bindings onto atribucion casillas)
- `src/cadrumo/application/modelo/_profile_binding.py` (fact projection, if the
  repeating-group shape needs a selector extension)
- `src/cadrumo/application/modelo/_verification_actions.py` /
  `_verification_predicates.py` (omission advisory)
- `src/cadrumo/entrypoints/cli/_modelo.py` + `_modelo_rendering.py` (M184 handoff
  Notices)
- `src/cadrumo/application/wizard/` + `src/cadrumo/locales/` (capture prompts,
  locale keys)

## Addendum (2026-07-09): casilla-1577 binding reconciliation

Implementation execution (CDC step S412) surfaced a collision this ADR's
Option B-typed did not reckon with. Grounded findings, loaded from the
authority snapshot of the target M100 revisions:

- The canonical M100 régimen-de-atribución income casilla for an attributed
  actividad-económica base is **1577** ("Rendimiento neto de actividad
  económica atribuido por entidades en régimen de atribución de rentas").
- **2025** M100 already binds casilla 1577 via
  `renta-2025-modelo-184-atribucion-actividades-economicas`,
  `source = "relation_prefill"` (selector `source_modelo = "184"`,
  `source_casilla_id = "tipo2.renta-atribuible-importe"`, `op = "sum"`),
  landed by commit `be47886cd1` ("relation canonical for cross-modelo
  fold-in"). **2024** M100 leaves 1577 unbound (`input_kind = informational`).
- A casilla holds exactly one binding, and the `calculation-source-canonical-
  mechanism` rule states verbatim "cross-MODELO fold-ins are relations" and
  "never model one fold-in two ways at once". The M184→M100 attributed income
  IS a cross-modelo fold-in.

Therefore the Implementation §2 proposal — a `source = "profile"` binding onto
the atribución casilla — is **rejected**: on 2025 it double-binds the
relation-canonical casilla 1577, and on 2024 it would model the same
cross-modelo fold-in a second way. The relation is the intra-bucket transport
(a socio who files both the entity's M184 and their own M100 in one
workspace); this ADR's concern is the CROSS-bucket transport (SC bucket ≠
socio bucket), which the relation cannot serve because a relation reads only
the active bucket.

### Why this amendment is required either way

Note a `source = "profile"` binding onto casilla 1577 is not merely a
double-binding hazard: even restricted to 2024 (where 1577 is unbound), it
would model a CROSS-MODELO fold-in (M184 → M100 attributed income) through a
PROFILE fact — a NEW aggregation surface that no row of the
`calculation-source-canonical-mechanism` taxonomy covers (the taxonomy routes
cross-modelo fold-ins through relations, and relations cannot cross buckets).
That rule requires a new aggregation surface to "enroll under an existing row
OR amend the ADR before shipping". So the choice below is an ADR-level
amendment regardless of which resolution is picked; this addendum is that
amendment, recording which resolution and why.

### Decision — options weighed

Casilla 1577 is a cross-modelo fold-in and stays relation-canonical wherever a
relation exists. The open question is how the CROSS-bucket value (SC bucket ≠
socio bucket, which a relation cannot serve) reaches the socio's M100.

- **(a) No profile binding either year; cross-bucket served manually —
  RECOMMENDED.** The socio's typed `attribution_received` facts (S411) are the
  provenance-carrying home and transcription source. The M184 handoff Notice
  (S413) emits the per-socio value plus the exact profile-capture command; the
  M100 omission advisory (S414) fires — non-blocking, LOUD — when
  `attribution_received` facts exist for the filing year but the atribución
  casilla resolves empty. The cross-bucket value enters M100 via a documented
  manual `--binding` override on 1577, BOTH years. Rule-symmetric (1577 stays
  relation-canonical where a relation exists; cross-bucket manual both years),
  no new aggregation surface, consistent with this ADR's own deferral of
  cross-bucket auto-flow (Option A) behind a future security ADR.
- **(b) 2024 `source = "profile"` binding + 2025 stays relation.** Pragmatic —
  ships cross-bucket auto-flow for 2024 (no manual transcription that year).
  Honest cost: **asymmetric** — 2024 cross-bucket auto-flows via the profile
  fact while 2025 cross-bucket stays manual, a distinction that is purely an
  artifact of the relation campaign having covered only 2025, not a principled
  legal or design difference. It also introduces the new profile-based
  cross-modelo aggregation surface named above (and needs the
  `_profile_binding.py` repeatable-group sum injector), which the
  canonical-mechanism taxonomy disfavours.
- **(option 3) Extend the relation to 2024 for full symmetry.** Author a 2024
  M100 `relation_prefill` binding on 1577 mirroring 2025, so the relation
  covers both years and cross-bucket is manual both years — the symmetric twin
  of (a) that additionally closes the 2024 same-bucket gap. Attractive, but the
  2024 relation binding is a registry change owned by the relation-canonical
  campaign's scope (and presupposes the same-bucket M184), so it belongs to a
  follow-up rather than this cross-bucket-handoff slice. Recorded as the future
  symmetry improvement; (a) does not foreclose it.

**Recommendation: (a).** It is rule-symmetric, minimal-blast, introduces no new
aggregation surface, and matches this ADR's deferral of auto-flow. (b)'s only
gain (2024 auto-flow) is bought with a principled-looking-but-accidental
asymmetry and a disfavoured new surface; option 3 is the right way to gain
symmetry later, as a relation-campaign follow-up.

### Re-scoped S412 (under recommendation (a))

The original S412 ("`source = "profile"` binding onto the atribución casilla")
is **superseded**. The net slice is: S411 (typed facts) + S413 (handoff Notice
carrying value + capture command) + S414 (omission advisory) + documented
manual `--binding` override = a complete, rule-clean cross-bucket handoff with
casilla 1577 left relation-canonical. The plan-step text for S412 records this
decision; the profile-binding registry edit that S412 originally scoped is not
authored. This addendum is **proposed** and gated: no S412/S414 code lands
until the coordinator ratifies the chosen option.

### Grounding

Arts. 86-89 LIRPF (régimen de atribución de rentas) verified against the
bundled consolidated corpus (`ley-35-2006.html` anchors `#a86`-`#a89`:
art. 86 "Régimen de atribución de rentas", art. 87 "Entidades…", art. 88
"Calificación de la renta atribuida", art. 89 "Cálculo de la renta atribuible
y pagos a cuenta") and present in the legal catalogue. No regulated value is
fabricated. Companion rules: `calculation-source-canonical-mechanism`,
`relation-slot-bindings-declare-relation-source`,
`composition-service-no-parallel-write-path`, `no-silent-under-declaration`.

**Persistent grounding of the folded value (why arts 86-89 ride the Notice,
not the observation).** When the socio folds the attributed base into M100
casilla 1577 via the manual `--binding`, the persisted observation carries
1577's OWN registry `legal_refs` — the actividades-económicas chapter (LIRPF
arts. 27-32) — because 1577 is genuinely an actividad-económica income box
("Rendimiento neto de actividad económica atribuido por entidades en régimen
de atribución de rentas"), and art. 88 ("Calificación de la renta atribuida")
says the attributed income KEEPS its original actividad-económica
qualification. So the actividades grounding is the CORRECT persistent home for
the folded value (per `casilla-grounding-corrects-actividades-default-by-section`:
where the box genuinely IS actividades, the actividades chapter is correct and
preserved). Arts. 86-89 are the attribution MECHANISM, surfaced as context on
the transient S413 handoff Notice; they are intentionally not duplicated onto
the folded observation. This is an accepted design, not a dropped-provenance
defect.

### Review follow-ups (2026-07-09 honesty review)

The campaign-close honesty review
(`2026-07-09-m184-socio-attribution-handoff-audit`) returned PASS and surfaced
bounded follow-ups, actioned as honest disclosures rather than new code: the
Consequences now state the fully-forgotten socio-bucket case is an uncovered,
bounded gap (S413 Notice is its loud channel; Option A / relation-symmetry the
closure); the Locale-discipline constraint records the S413/S414 message
localisation as deferred to the cross-cutting attribution-locale follow-up; and
the S411/S413/S414 plan-step texts were corrected to match the shipped scope
and coverage. Finding F2 (operator-surfaces-not-localized) is now closed by
task #204: the handoff Notice message and both omission-advisory message /
next_action strings route through `tr()` keys across en/es/ca/hu, and the
S411 schema-capture half was confirmed already covered by the generic
schema-driven profile edit path (no locale keys needed, consistent with the
sibling `attribution_entity_socios` group).
