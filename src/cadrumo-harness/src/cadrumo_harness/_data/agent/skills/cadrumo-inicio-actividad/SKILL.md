---
name: cadrumo-inicio-actividad
description: >-
  Life-situation itinerary for starting an economic activity: record the
  start facts on the profile, treat the censo alta (Modelo 036) as the
  taxpayer's own AEAT-portal act, record the resulting censo facts on the
  profile by hand, and derive the first obligations the new activity
  creates.
  Use when the taxpayer is starting (or has just started) an activity —
  the profile's activity start date is being set or was set recently.
  Never invents the new obligation set; derives it from the overview
  surface after the censo facts land.
applies_when:
  profile_facts:
    - fact: activity_start_date
      match: present
  temporal_trigger: activity_start
---

# Inicio de actividad (starting an activity)

Gating situation: the taxpayer is starting an economic activity — the
moment their obligation universe changes shape. The sequence that keeps
this honest: facts first (what activity, from when, under which regime),
censo second (the alta is the taxpayer's own act before AEAT), derivation
third (the CLI computes which obligations now exist). One hard honesty
rule governs the censo step: the application does not prepare or file the
Modelo 036 alta censal — the taxpayer files it in the AEAT portal or
through their gestor, and this itinerary says so plainly instead of
pretending otherwise.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active
  profile) — run `cadrumo-alta-contribuyente` first for a brand-new user.
- The activity's defining facts are known: what the activity is, the
  intended start date, the IRPF estimation regime, and the IVA regime the
  activity will operate under (with professional advice where the choice
  is genuinely open — regime election is a decision with multi-year
  consequences, not a default to assume).

## Procedure

1. Record the start facts on the profile: `aeat config profile edit` with
   the activity start date, income category, estimation regime, and IVA
   regime the taxpayer chose. These facts are what the obligation
   derivation reads; an undeclared regime leaves the calendar incomplete
   and the CLI will say so rather than guess.
2. The censo alta itself: tell the taxpayer plainly that the Modelo 036
   alta censal is filed in the AEAT portal (or by their gestor), before
   the activity starts. This application records and derives; it does not
   file the alta.
3. After the alta is filed, record the official censo state by hand:
   read the filed Modelo 036 (or the AEAT portal) with the taxpayer and
   enter the resulting facts through `aeat config profile edit`. AEAT
   publishes no read-only censo view this application could fetch, so
   the profile mirrors AEAT only as faithfully as the taxpayer's own
   copy — divergences are questions for the taxpayer, and the calendar
   keeps its `censo.enrolment_unverified` disclosure because the facts
   are operator-declared, not AEAT-verified.
4. Derive the new obligation universe:
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>`
   for the first filing horizon and `aeat app overview agenda` for what
   comes first. Confirm any doubtful obligation with
   `aeat app overview explain <MODELO> --year <YEAR>`. Relay the first
   deadlines verbatim — the first quarter of a new activity arrives
   faster than most taxpayers expect.
5. Route the steady state to the WHO itinerary the recorded facts now
   select (`cadrumo-autonomo-estimacion-directa`, `cadrumo-autonomo-modulos`,
   `cadrumo-pyme-sociedad`, with `cadrumo-retenedor-empleador` or
   `cadrumo-intra-community-operator` overlays as the facts declare), and start
   the bookkeeping habit immediately: hand off to `cadrumo-llevar-libro` so the
   first quarter's records are complete from day one.

## Success assertions

- The profile carries the declared start facts before any obligation was
  discussed; nothing was derived from an undeclared profile.
- The censo alta was described as the taxpayer's own AEAT-portal act;
  no narration implied this application filed it.
- The post-alta censo facts were entered from the taxpayer's own filed
  036 copy, and any divergence was put to the taxpayer.
- The first obligations were read from `aeat app overview calendar` /
  `agenda` / `explain`, never recited from memory.

## Hand off

Steady-state operation belongs to the selected WHO itinerary. This
itinerary closes when the recorded censo facts agree with the filed 036, the first
deadlines are known to the taxpayer, and the bookkeeping loop is running.
