---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d5bf38333374cfd29f648ea7524a1982e9c0c53a59125669fa608b7395855755'
step_id: 'S17'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
  - '[[2026-08-04-minimo-descendientes-eligibility-deferred-descendant-axes-adr]]'
---

# Assimilate an economically dependent descendant where the filer declares no anualidades at all, sweeping the existing incompatibility injector in the same change, BLOCKED on per-child attribution of anualidades

## Scope

- `src/cadrumo/application/modelo/_profile_binding.py`

## Description

- Add `dependencia_economica` to the descendant record as a tri-state, defaulting to
  unset, and add `anualidades_alimentos_euros` to the family profile.
- Widen the Art. 58.1 household limb from cohabitation to cohabitation OR assimilated
  dependency, behind a keyword-only flag defaulting to the withholding answer.
- Add the profile-level availability gate, the assimilated-index and suppressed-index
  disclosure predicates, and thread the flag through every profile eligibility call.
- Add the fact paths, the `DEPENDENCIA` flag key, the gated tri-state wizard page, the
  CLI payload field and list column, and the profile schema declarations.
- Land four new locale keys and both flag-help strings across all four catalogues
  through the locales CLI.
- Add the two-directional calculate-path advisory and wire it into the coordinator.
- Sweep the art. 64/75 separate-escala injector: read the filer's anualidades, pass the
  assimilation flag explicitly, and record why the two halves cannot collide.

## Outcome

The household the authority names in terms now receives the allowance. Art. 58.1
conditions the mínimo on cohabitation and this engine read that as necessary; the
authority makes it sufficient but not necessary, granting the mínimo to a progenitor
without custody, not even shared, who pays no judicial anualidades and still contributes
to the descendant's upkeep. That filer previously had two options, both wrong: receive
nothing, or misstate cohabitation. Keeping `convive_con_contribuyente` factual and
adding a separate field is what removes that choice.

The axis is tri-state rather than boolean and that is load-bearing. Unset never
assimilates, an explicit no is a distinct recorded answer, and only an explicit yes
grants. A defaulting two-state field would have made the assimilation reachable through
the only input available, which is the same shape the entry-date coherence rules guard
against on the relación axis.

The anualidades carve-out is applied at filer level, which is the staged boundary rather
than the law. The statute carves out per child; this profile cannot attribute a payment
to one, so a positive declared figure suppresses the assimilation for every descendant.
That under-grants a filer paying for one child while supporting another outside any court
order, and the calculate path says so rather than leaving it silent. A declared zero
means none are paid and does not suppress, because treating an answer as a suppressing
declaration would withdraw the allowance from exactly the filer the authority names.

The incompatibility's other half was swept in the same change rather than left. The art.
64/75 separate-escala flag asserts the payer holds no mínimo; the assimilation asserts a
non-cohabiting supporter does. They cannot collide today because that régimen exists only
for a filer who pays anualidades, for whom the assimilation is already suppressed - and
that reasoning is recorded at the call site, which passes the flag explicitly rather than
relying on its default, together with a note that it expires when per-child attribution
lands.

Both test lanes were run and the second deliberately: 2716 unit tests and 96
integration-marked tests across the contribuyente, wizard, modelo and CLI surfaces, plus
a token grep for stragglers. ruff and the API stub check are clean.

## Notes

Four mutations were run against a green baseline and each turns the suite red: collapsing
unset onto an affirmative, never suppressing on declared anualidades, suppressing on a
declared zero, and flipping the predicate's default from withhold to grant. The last one
matters most - the keyword defaults to `False` so that forgetting it withholds rather than
grants, and that default is what lets the anualidades injector pass `False` explicitly and
be correct rather than lucky.

The disclosure predicates apply the non-income conditions only, not the registry ceilings,
because the calculate-path advisory that consumes them cannot resolve those ceilings. The
narrowing is safe in this direction: a descendant excluded by a ceiling contributes
nothing either way, so the worst case is one redundant disclosure rather than a missing
one. Stated here because the asymmetry is deliberate and would otherwise read as an
oversight.

The advisory's anualidades read treats an unreadable stored figure as UNDECLARED, which
leaves the assimilation available. That is the opposite of this module's usual
fail-closed default and is deliberate: the alternative reads a corrupt value as a large
payment and silently withdraws an allowance the authority grants, whereas leaving it
available still requires a second affirmative act per descendant and every grant is
disclosed.

`anualidades_alimentos_euros` draws a `pyrefly` diagnostic for `Field(ge=0)` on a
`Decimal | None`. It is the same known false positive already carried by three
pre-existing fields in the same module and follows their established pattern rather than
introducing a new one.

DISCLOSED: the lead's brief numbered this item `S16` and the guardería spend model `S17`,
which is the reverse of the plan. The work was done by subject in the order requested and
recorded against the plan's own ids; nothing was checked on the wrong Step.

Out of scope and still blocked, unchanged: per-child attribution of anualidades. Until it
exists the suppression stays total, and the Step that would close it is the one that must
revisit the art. 64/75 injector alongside.
