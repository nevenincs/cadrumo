---
name: cadrumo-inicio-actividad
description: >-
  Walk a taxpayer through starting an economic activity: record the start facts on
  the profile, explain that the censo alta (Modelo 036) is the person's own act in
  the AEAT portal, bring the resulting censo data into the profile, and read the
  first obligations from the overview. Use when the taxpayer is starting or has
  just started an activity and the profile's activity start date is being set.
applies_when:
  profile_facts:
    - fact: activity_start_date
      match: present
  temporal_trigger: activity_start
---

# Inicio de actividad (starting an activity)

Gating situation: the taxpayer is starting an economic activity - the moment their
obligations change shape. The order that keeps this honest: facts first (what
activity, from when, under which regime), censo second (the alta is the taxpayer's
own act before AEAT), derivation third (the overview works out which obligations now
exist). One rule governs the censo step: Cadrumo does not prepare or file the
Modelo 036 alta censal. The taxpayer files it in the AEAT portal or through their
gestor, and you say so plainly.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports a profile); for a
  brand-new taxpayer load `cadrumo-alta-contribuyente` first.
- The activity's defining facts are known: what the activity is, the intended start
  date, the IRPF estimation regime and the IVA regime it will operate under. Where
  the choice of regime is genuinely open, tell the person it has multi-year
  consequences and is theirs (with professional advice) to make; do not assume a
  default.

## Procedure

1. Record the start facts the person gave you. Say which you are about to write,
   then run `aeat config profile edit --quiet` with just those flags:
   `--activity`, `--activity-start-date`, `--irpf-income-categories`,
   `--irpf-estimation-regime` and `--iva-regime` (operation `user-profile.patch`).
   Do not add `--accept-defaults`. These facts are what the overview reads: an
   undeclared regime leaves the calendar incomplete, and the tools say so rather
   than guess.
2. The censo alta itself: tell the taxpayer plainly that the Modelo 036 alta censal
   is filed in the AEAT portal (or by their gestor) before the activity starts, and
   that Cadrumo only records and derives.
3. After the person has filed the alta, bring the censo into the profile. Each
   source covers only part of it, and the person chooses which to use.
   - AEAT's own censal data: tell the person you will contact AEAT (it needs the
     AEAT read access they configured; `aeat config auth status` shows it), run
     `aeat config profile censo pull` to preview, and apply the exact proposal with
     `aeat config profile censo pull --apply` only after they have seen it. It reads
     identity and domicile, and needs the tax ID already on the profile.
   - The Certificado de Situación Censal PDF (sede procedure G313) saved in the
     workspace: `aeat config profile censo import --file <PDF>` previews what it
     carries (domicile and activities with their IAE epígrafe); add `--apply` to
     record it once the person agrees. The profile marks it as taken from a
     document the person supplied, not as read from AEAT.
   - Everything neither covers (start date, regimes, IVA facts) is read with the
     person from their filed Modelo 036 and entered with
     `aeat config profile edit --quiet` as in step 1. `aeat config profile censo show`
     reads back what is stored. Facts entered this way are the person's declarations,
     so the calendar keeps its `censo.enrolment_unverified` advisory for them;
     relay it, and put any divergence from the filed 036 to the person.
   - Record that the alta was filed: ask for the date they filed it (and the sede
     acuse identifier if they have one), then run
     `aeat app modelo m036 alta --declared-on <YYYY-MM-DD> [--sede-justificante <ID>]`
     (operation `modelo.036.record`). It stores the person's own statement locally
     and sends nothing to AEAT. Never invent the date.
4. Derive the new obligations. Both commands read local state and contact nobody:
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` (operation
   `overview.calendar`) for the first filing horizon and
   `aeat app overview agenda` (operation `overview.agenda`) for what comes first.
   Confirm a doubtful obligation with
   `aeat app overview explain <MODELO> --year <YEAR>` (operation `overview.explain`).
   Relay the first deadlines exactly as returned - the first quarter of a new
   activity arrives faster than most taxpayers expect.
5. Send the steady state to the skill the recorded facts now select
   (`cadrumo-autonomo-estimacion-directa`, `cadrumo-autonomo-modulos` or
   `cadrumo-pyme-sociedad`, with `cadrumo-retenedor-empleador` or
   `cadrumo-intra-community-operator` on top as the facts declare), and start the
   bookkeeping habit now: load `cadrumo-llevar-libro` so the first quarter's records
   are complete from day one.

## Success assertions

- The profile carried the declared start facts before any obligation was discussed;
  nothing was derived from an undeclared profile.
- The censo alta was described as the taxpayer's own act in the AEAT portal; nothing
  said implied Cadrumo filed it.
- Post-alta censo facts came from AEAT's data, the person's certificate or the
  person's own copy of the filed 036, and any divergence was put to the person.
- The first obligations were read from `overview calendar`, `agenda` and `explain`,
  not recited from memory.

## Next

Steady-state work belongs to the skill the facts select. This skill is done when the
recorded censo facts agree with the filed 036, the first deadlines are known to the
taxpayer, and the bookkeeping has started.
