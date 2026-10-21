---
name: cadrumo-pyme-sociedad
description: >-
  Sequence the obligations of a legal entity (sociedad) subject to Impuesto sobre
  Sociedades: quarterly IVA, IS pagos fraccionados and the annual IS return, read from
  the overview calendar rather than assumed. Use when the taxpayer profile declares
  `entity_type` legal_entity and you need to know what to prepare next.
applies_when:
  profile_facts:
    - fact: entity_type
      match: equals
      values: [legal_entity]
---

# Sociedad (pyme)

Gating predicate: the active `TaxpayerProfile` declares `entity_type` is
`legal_entity` (Ley 27/2014 LIS) - a contribuyente del Impuesto sobre Sociedades,
distinct from the natural-person IRPF route the `cadrumo-autonomo-*` skills own and
from the `attribution_entity` route (régimen de atribución de rentas, LIRPF
Title X Section 2), which is out of scope here. `legal_entity_form` (SL, SA,
cooperativa, etc.) selects the applicable IS rate schedule but does not change which
modelos apply. This skill is thin: it sequences the obligations Cadrumo derives and
points each filing to the per-modelo skill that owns it.

## Preconditions

- The entity is onboarded (`cadrumo-alta-contribuyente` has run) and
  `aeat app overview status` (operation `overview.status`, or the tool `status`)
  reports an active profile.
- The profile declares `entity_type` legal_entity and, where relevant,
  `legal_entity_form`. If undeclared, load `cadrumo-alta-contribuyente` to declare it.

## Procedure

Each overview command below is a local read of the profile and the bundled registry;
it never contacts the tax authority. Through the tool server, `search` for the
operation, `describe` it, run it with `execute` and read the outcome with `result`.
Say what you are about to read before you run it.

1. Derive the applicable obligations - never assume a sociedad's obligation set from
   memory. Read the deadline window with
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` (operation
   `overview.calendar`) and what is next due with `aeat app overview agenda`
   (`overview.agenda`). Read any `coverage_advised` entry as an open question to put
   to the taxpayer.
2. Confirm each candidate modelo's applicability explicitly with
   `aeat app overview explain <MODELO> --year <YEAR>` (`overview.explain`): modelo 200
   for the annual IS return, 202 for the IS pago fraccionado, 303 for periodic IVA.
   Read `applicable`, `verdict`, `rationale` and `profile_facts` rather than assuming
   from the entity type alone - `enrollment.large_company`, INCN volume and
   micro-empresa thresholds all change which schedule applies.
3. List the modelos the registry models: tool `authority` with `query` `modelos`, or
   `aeat app modelo list` (a local read).
4. Sequence the itinerary:
   - Keep the ledger current before any calculation: load `cadrumo-llevar-libro`, then
     `cadrumo-clasificar`.
   - Quarterly IVA, when the calendar surfaces it: load `cadrumo-preparar-modelo-303`.
   - IS pagos fraccionados (Modelo 202), when the calendar surfaces it: load
     `cadrumo-preparar-modelo-202`.
   - The annual IS return (Modelo 200), when the calendar surfaces it, typically after
     the year's pagos fraccionados: load `cadrumo-preparar-modelo-200`. A positive
     resultado contable that resolves to a zero base or cuota with no declared
     reduction is suspect (see the honest-declaration rule); do not treat a clean
     verify with zero findings on positive input as sufficient without confirming with
     the taxpayer.
   - Any other modelo the calendar surfaces (informativas, censo): read
     `aeat app modelo describe <MODELO> --year <YEAR> --period <PERIOD>` (tool
     `authority`, `query` `describe`) and load the matching `cadrumo-preparar-modelo-*`
     skill when one exists. If none exists, say so to the taxpayer rather than
     improvising a procedure.
5. After the taxpayer has filed in the AEAT portal, load `cadrumo-reconciliar` for
   that filing.

## Success assertions

- Every obligation acted on was read from `overview.calendar`, `overview.agenda` or
  `overview.explain`, never assumed from this skill's prose.
- A `coverage_advised` entry is surfaced to the taxpayer, not silently dropped.
- No casilla value is computed here; every number is quoted from the output of the
  per-modelo skill's tools.

## Finish

Each filing follows its own skill through verify, export (only with the person's
go-ahead), the taxpayer's own filing, and reconciliation. This skill is done once every
calendar-surfaced obligation for the period has been routed to its skill.
