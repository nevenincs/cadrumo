---
tags:
  - '#audit'
  - '#registry-legal-grounding-windows'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:cfd348c79bd22fa59d16019a1cb5fcbe47d295b5cae27220bddeacbf17b9ac35'
related: []
---

# `registry-legal-grounding-windows` audit: the last families are grounded, and the sweep's real scope

## The families are sound

The parameter families left unswept by this campaign were checked by comparing
each encoded value numerically against every number stated in its cited
provision's bundled corpus. All clean:

| family | where | result |
|---|---|---|
| IVA rates and the RDL 4/2024 transitional companions | `modelos/303` (15 numeric) | all stated |
| patrimonio tariffs | `modelos/714` (15 numeric) | all stated |
| módulos coefficients | `modelos/131` (20 numeric) | all stated |
| IRNR rates | `modelos/210` (8 numeric) | all stated |
| retención percentages | `legal/irpf-retencion-actividades`, `-administradores` | 10 stated, 0 missing |
| recargo de equivalencia | `legal/iva-recargo-equivalencia`, `iva/recargo-rates.toml` | all stated |
| estimación objetiva exclusions | `legal/irpf-estimacion-objetiva` | all stated |

Nine apparent misses in the retención file are non-numeric selector values
(`"A04,A05"`), correctly skipped rather than absent.

Spanish rows in `iva/rates.toml` verify against their `legal_refs`. The 56
other-member-state rows carry no `legal_refs` and are NOT ungrounded: they cite
`source_refs` to two declared EU sources (`eu-eprs-iva-rates-2025-07-01`,
`eu-your-europe-iva-rates-2026-07-13`, both defined in `legal/iva-rates.toml`).
That is the correct channel — a Spanish BOE provision does not establish another
member state's VAT rate. Checking only `legal_refs` reported them as unverified;
that was the probe's error, not the registry's.

## The correction that matters: my sweep covered two subtrees of ten

Every grounding claim this campaign has made — "structural clean across all 458
numeric parameters", "335 every-number-stated" — was produced by probes that walk
`registry/aeat/modelos/**` and `registry/aeat/legal/**` **only**.

`registry/aeat/` also contains `iva/`, `categories/`, `treaties/`, `calendars/`,
`apoderamientos/`, `authorization.d/`, `m303_orden_anual/`, `territories` and
`topics/`. None was ever scanned. The IVA rate tables — among the most-consumed
values in the product — were invisible to the sweep until this pass went looking
for them by name.

They also use a different shape: `[[rates]]` rows keyed on `pct`, not
`[parameters]` tables keyed on `value`. A probe keyed to one shape cannot see the
other, so the omission was silent in both directions.

So the earlier counts are accurate for what they measured and must not be read as
registry-wide. Anyone citing them should say "of the modelo and legal subtrees".

## A residual the file declares about itself

`iva/rates.toml` documents, in its own comments, that it does not date-bound the
zero rate and that nothing downstream does so either. It explains the trade-off:
the flat `kind = "zero"` axis cannot express LIVA art. 91.Cuatro's donativos-only
zero rate, and the IVA domain does not model `donativo` at all, so the case is
unreachable today. Recorded as the author's declared residual, not a finding.

## Next

Sweep the eight unscanned subtrees for regulatory values, starting with
`categories/` and `treaties/` (treaty withholding caps are rate-shaped and
liability-bearing). A shape-agnostic probe is needed: collect any row carrying a
percentage or money field, whatever the table is called.

## Follow-up: the unscanned subtrees are grounded

The eight subtrees named above were swept with a shape-agnostic probe — any row
carrying a rate, percentage or money field, whatever the table is called.

Only three hold regulatory magnitudes at all:

| subtree | numeric rows | grounding |
|---|---|---|
| `treaties/` | 16 | 16 carry `legal_refs` |
| `iva/` | 68 | 12 `legal_refs` (Spanish), 56 `source_refs` (EU tables) |
| `categories/` | 5 | parent-block `citations`, see below |

`calendars/`, `apoderamientos/`, `authorization.d/`, `m303_orden_anual/`,
`territories` and `topics/` yielded no rows matching the numeric field set.

The five `categories/profiles.toml` rows first read as declaring neither channel.
They are grounded: the `[profiles.proportionality]` block carries a `citations`
list — `ley-35-2006:art-30` (LIRPF art. 30.2.1.ª) plus the Manual práctico Renta
and the AEAT help page. The probe looked for `legal_refs` / `source_refs` on the
ROW; the citation sits on the parent block. Checking the wrong scope, not a gap.

Those rows are the RETA cuota-máxima cap schedule, and their test module is worth
reading as a model. It states the direction in its own docstring: the registry
previously shipped a flat 15000 that "matches no ejercicio at all", every real
year is higher, so it "under-stated the allowance and cost the taxpayer
deduction" — and "nothing in this repository watches over-payment... A gate that
only watches under-declaration would never have found it." Its expected values are
declared as "the amounts AEAT prints in the Manual practico Renta for each
ejercicio... external authority, not values re-derived from the code under test."

That is both the reference shape for a non-tautological registry test and an
independent confirmation of this campaign's organising question, arrived at by
someone else.

So grounding across the registry is now swept, with the scope caveat above
retired: the modelo and legal subtrees by the numeric probe, and the remaining
three by this one.

## Swept clean: the undated-constant-for-an-annual-figure class

The RETA cuota-máxima cap (see above) is a confirmed instance of a distinct
defect shape, and it is worth knowing whether it had siblings:

> a single undated constant standing in for a figure the law re-fixes each
> ejercicio, where every real year is higher, so the constant under-states the
> relief and the taxpayer over-pays.

Swept: 317 single-scalar registry parameters, keeping those that carry no date
axis, no `valid_from`/`effective_from`, and no per-year rows, whose id or notes
name a concept Spanish law re-fixes annually (cuota, cotización, SMI, IPREM,
tope, módulo, escala, límite, umbral).

Twelve candidates surfaced and **all twelve are sound**. Each is a figure fixed
by article text rather than re-fixed annually, and each says so in its own note:
the RIRPF art. 95 retención percentages (7 %, 2 %, 1 %), the LIRPF art. 101.2
reduced administrator rate (19 %) and its 100.000 EUR INCN threshold, the
RDL 7/2024 DANA simplified-regime reduction (25 %, and its id carries the year),
plus several non-numeric Modelo 036 activity-code selectors the value filter
should not have admitted.

So the class has exactly one known instance, already repaired with a dated
schedule. Recorded so it is not re-swept.

**Residual, stated:** this probe reads the REGISTRY only. The same shape in a
Python constant — a regulatory magnitude inlined in a feature module — is not
covered here. `aeat-registry-authority-flow` forbids that placement and an AST
gate enforces the modelo-identifier case, but the annual-figure case has not been
checked from the Python side.

## The Python side of the same class, and what its gate actually covers

Last section left a residual: the same undated-constant shape in a Python
constant rather than a registry row. Taking it up.

The repository already owns a fold for this —
`core/tests/test_external_constants_centralisation_part{1,2}.py` — so it was run
rather than reimplemented. 48 passed, 1 failed (see below).

**Its coverage is narrower than its name suggests.** It pins exactly four Decimal
constants by name: `M347_THRESHOLD_EUR` (3005.06), `ART_7P_EXEMPTION_CAP_EUR`
(60100), `MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR` (1500) and
`WORK_INCOME_GENERAL_DECLARATION_LIMIT_EUR` (22000). Its AST scan catches those
four literals being *re-introduced* outside the canonical module. It does not
scan for a NEW regulatory magnitude inlined somewhere it should not be.

So "regulatory constants are centralised" is enforced as a whitelist of four, not
as a property. Worth knowing before citing the gate as broad protection.

### The declaration-threshold family is sound, and correctly dated

The two obligation-to-declare thresholds are the ones a reform law does move, so
they were checked against the bundled consolidated LIRPF art. 96:

| constant | value | corpus |
|---|---|---|
| general work-income ceiling | 22.000 | "con el límite de 22.000 euros anuales" |
| reduced ceiling, multiple pagadores, 2024-2026 | 15.876 | "será de 15.876 euros" |
| secondary-pagador trigger | 1.500 | "1.500 euros anuales" |

All three present verbatim. The module had already applied the discipline this
class is about: the year-varying ceiling is a dated map
(14.000 for 2019-2022, 15.000 for 2023 per Ley 31/2022, 15.876 for 2024-2026 per
RD-Ley 4/2024), while the two stable figures are flat AND annotated
"year-stable" in their own comments.

Direction, for the record: a declaration ceiling set too HIGH tells a taxpayer
they need not file when they must — under-declaration. Too LOW over-obliges. The
figures are right, so neither applies.

### One unrelated red in that module, not mine

`test_test_suite_aeat_route_literals_are_centralized_or_declared` fails on a
hardcoded sede URL at
`application/live/tests/test_iva_remote_state_acquisition.py:83`. A test-suite
route literal, not a regulatory magnitude, in a package this campaign has not
touched.
