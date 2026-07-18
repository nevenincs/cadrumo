---
name: cadrumo-cese-actividad
description: >-
  Life-situation itinerary for ceasing an economic activity: record the
  end date on the profile, treat the censo baja (Modelo 036) as the
  taxpayer's own AEAT-portal act, record the resulting censo facts on
  the profile by hand, and
  close out the tail obligations the ceased activity still owes — the
  final quarter's filings and the following year's annual summaries. Use
  when the taxpayer is ceasing (or has ceased) an activity — the
  profile's activity end date is being set or was set recently. Never
  assumes the tail obligation set; derives it from the overview surface.
applies_when:
  profile_facts:
    - fact: activity_end_date
      match: present
  temporal_trigger: activity_end
---

# Cese de actividad (ceasing an activity)

Gating situation: the taxpayer is winding an activity down. The defining
truth of a cese — and the thing most taxpayers get wrong — is that the
obligations do NOT end on the cease date: the final quarter still files,
and the next year's annual summaries and declaraciones still cover the
activity's last year. This itinerary records the end honestly, records
the censo baja's facts on the profile, and keeps the obligation tail visible until it is
actually empty. The same censo honesty rule as the alta applies: the
application does not prepare or file the Modelo 036 baja censal — the
taxpayer files it in the AEAT portal or through their gestor.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active
  profile) and the ceasing activity's facts are on the profile.
- The cease date is factual (the activity genuinely ended or has a firm
  end date), and the final period's records are or will be available —
  the last quarter still needs a complete ledger.

## Procedure

1. Record the end date on the profile: `aeat config profile edit` with
   the activity end date. The obligation derivation reads it; a missing
   end date keeps future obligations deriving as if the activity
   continued.
2. The censo baja itself: tell the taxpayer plainly that the Modelo 036
   baja censal is filed in the AEAT portal (or by their gestor). This
   application records and derives; it does not file the baja.
3. After the baja is filed, record the official censo state by hand:
   read the filed Modelo 036 baja with the taxpayer and enter the
   resulting facts through `aeat config profile edit`. AEAT publishes no
   read-only censo view this application could fetch, so the profile
   mirrors AEAT only as faithfully as the taxpayer's own copy; the
   calendar keeps its `censo.enrolment_unverified` disclosure because
   the facts are operator-declared, not AEAT-verified.
4. Derive the tail: `aeat app overview agenda` for what is still due, and
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>`
   across the final quarter AND the following year's annual windows.
   Relay each remaining obligation and deadline verbatim, and say
   explicitly which ones survive the cease date — the final quarter's
   self-assessments and the next year's resúmenes and declaraciones are
   the usual survivors. Confirm doubtful cases with
   `aeat app overview explain <MODELO> --year <YEAR>`.
5. Close the books for the final period: hand off to `cadrumo-llevar-libro` and
   `cadrumo-clasificar` for the last quarter's records, then drive each surviving
   obligation through its owning per-modelo skill in deadline order,
   exactly as a `cadrumo-cierre-trimestre` would — the last quarter is a quarter
   close with a shorter future.
6. The following year, when the annual windows open, `cadrumo-resumen-anual` owns
   the activity's final annual season; leave the taxpayer with that
   expectation stated in plain language and a note of which annual forms
   the calendar already projects.

## Success assertions

- The profile carries the end date before any tail obligation was
  discussed.
- The censo baja was described as the taxpayer's own AEAT-portal act; no
  narration implied this application filed it.
- The obligation tail was read from `aeat app overview agenda` /
  `calendar` / `explain`, never assumed — and the survivors past the
  cease date were named explicitly to the taxpayer.
- The final quarter's ledger was clean before its filings were prepared.

## Hand off

The final quarter's filings follow their per-modelo skills;
`cadrumo-resumen-anual` owns the final annual season. This itinerary closes when
the tail is enumerated, the final quarter is routed, and the taxpayer
knows what still arrives next year.
