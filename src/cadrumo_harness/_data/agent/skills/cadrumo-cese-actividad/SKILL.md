---
name: cadrumo-cese-actividad
description: >-
  Walk a taxpayer through ceasing an economic activity: record the end date on the
  profile, explain that the censo baja (Modelo 036) is the person's own act in the
  AEAT portal, record that it was filed, and list the obligations that still
  survive the cease date. Use when the taxpayer is ceasing or has ceased an
  activity and the profile's activity end date is being set.
applies_when:
  profile_facts:
    - fact: activity_end_date
      match: present
  temporal_trigger: activity_end
---

# Cese de actividad (ceasing an activity)

Gating situation: the taxpayer is winding an activity down. The thing most
taxpayers get wrong is that obligations do not end on the cease date: the final
quarter still files, and the next year's annual summaries and declaraciones still
cover the activity's last year. Record the end honestly, record the censo baja, and
keep the obligation tail visible until it is empty. As with the alta, Cadrumo does
not prepare or file the Modelo 036 baja censal; the taxpayer files it in the AEAT
portal or through their gestor.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports a profile) and the
  ceasing activity's facts are on the profile.
- The cease date is factual (the activity ended or has a firm end date), and the
  final period's records are or will be available - the last quarter still needs a
  complete ledger.

## Procedure

1. Record the end date on the profile. The obligation calendar reads it; without it,
   future obligations keep deriving as if the activity continued. Tell the person
   the date you will write. `aeat config profile edit` has no flag for it; the tool
   server's operation `user-profile.field-mutation` replaces one profile field by
   path, and the path is `censo.activity_end_date` (find the operation with
   `search`, read its schema with `describe`, and take the profile revision and
   digest it asks for from `user-profile.view`). If the operation refuses the path,
   report exactly what came back and do not go on as if the date were recorded.
2. The censo baja itself: tell the taxpayer plainly that the Modelo 036 baja censal
   is filed in the AEAT portal (or by their gestor); Cadrumo does not file it.
3. After the person has filed the baja, ask for the date they filed it (and the sede
   acuse identifier if they have one) and record it with
   `aeat app modelo m036 baja --declared-on <YYYY-MM-DD> [--sede-justificante <ID>]`
   (operation `modelo.036.record`). It stores the person's own statement locally and
   sends nothing to AEAT. Never invent the date. If it refuses because no alta is
   recorded, report that and ask whether the person has the earlier alta's date; do
   not make one up. If the person also has AEAT's censal data or a Certificado de
   Situación Censal PDF in the workspace, `aeat config profile censo pull` and
   `aeat config profile censo import --file <PDF>` preview what AEAT holds (add
   `--apply` only after the person has seen the preview and agrees). Censo facts the
   person enters themselves stay their declarations, so the calendar keeps its
   `censo.enrolment_unverified` advisory for them; relay it.
4. Derive the tail. Both commands read local state and contact nobody:
   `aeat app overview agenda` (operation `overview.agenda`) for what is still due,
   and `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>`
   (operation `overview.calendar`) across the final quarter and the following year's
   annual windows. Relay each remaining obligation and deadline exactly as returned,
   and say which ones survive the cease date - the final quarter's self-assessments
   and the next year's resúmenes and declaraciones are the usual survivors. Confirm
   doubtful cases with `aeat app overview explain <MODELO> --year <YEAR>`.
5. Close the final period's books: load `cadrumo-llevar-libro` and
   `cadrumo-clasificar` for the last quarter's records, then take each surviving
   obligation through its modelo skill in deadline order, as `cadrumo-cierre-trimestre`
   does - the last quarter is a quarter close with a shorter future.
6. The following year, when the annual windows open, `cadrumo-resumen-anual` covers
   the activity's final annual season. Leave the taxpayer with that expectation in
   plain language and a note of which annual forms the calendar already projects.

## Success assertions

- The profile carried the end date before any tail obligation was discussed, or the
  person was told it could not be recorded.
- The censo baja was described as the taxpayer's own act in the AEAT portal; nothing
  said implied Cadrumo filed it.
- The obligation tail was read from `overview agenda`, `calendar` and `explain`, not
  assumed, and the obligations that survive the cease date were named to the
  taxpayer.
- The final quarter's ledger was clean before its filings were prepared.

## Next

The final quarter's filings follow their modelo skills, and `cadrumo-resumen-anual`
covers the final annual season. This skill is done when the tail is listed, the final
quarter is under way, and the taxpayer knows what still arrives next year.
