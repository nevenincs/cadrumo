---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2797cd44eb68b45e131727d7dd159cd444df81488f8c7f50b64cb1cd52b33e54'
step_id: 'S15'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-liabilities-sanciones with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-08-07-aeat-liabilities-sanciones-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The BLOCKED on the same specimen: populate the guard real allowed_path_prefixes from the captured consulta path, verified by the guard test refusing every known payment and aplazamiento path observed in the specimen and ## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# BLOCKED on the same specimen: populate the guard real allowed_path_prefixes from the captured consulta path, verified by the guard test refusing every known payment and aplazamiento path observed in the specimen

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`

## Description

- Ran an authenticated Cl@ve Móvil discovery session against the live sede and
  established the debts consulta by navigation, not by inference: it is served
  at the `deudas_consulta` path now declared in `external_constants.toml`, and
  the landing matched the request with no redirect.
- Declared `deudas_consulta` and `deudas_pagar_todas` as sede paths in
  `external_constants.toml` and on the `AeatSedePaths` model, so no AEAT route
  literal lives in a feature module.
- Replaced the empty `_DEUDAS_READ_PATH_PREFIXES` tuple with the observed
  consulta ENDPOINT.
- Added `allowed_read_post_paths` to the read policy, scoped to the consulta
  alone, because the listing exists only behind the NIF form's submission.
- Rebuilt `_SEDE_HOST` on the unnumbered sede origin instead of a numbered host.
- Declared the observed consulta and payment routes as fixtures in the central
  AEAT literal module, keeping the invented shape canaries as negative cases.
- Rewrote the guard test around the populated allow-list: an admission case, the
  shared-application refusal, every observed payment route, session-independence
  across the numbered pool, and a proof of which policy field carries it.

## Outcome

Delivered as specified, and the specimen established more than the row asked
for.

**The entry is the consulta ENDPOINT, never its application prefix.** AEAT
serves *pagar todas mis deudas* from the SAME application as the consulta; only
the endpoint segment separates a read of what is owed from the flow that pays
it. The obvious allow-list shape — the shared application prefix — would have
admitted the payment launcher into the guard built to keep it out. That is now
the module's most valuable regression, and it fails loudly if anyone
"simplifies" the tuple.

**The consulta is a two-step surface.** The endpoint renders a NIF form and the
listing exists only behind its submission, so the read genuinely needs a POST.
That is a query, not a mutation, and it is admitted only for an
`authenticated_read_surface` at an explicitly named path — the same mechanism
the IVA compensation wallet reader already uses. The allowance is pinned to the
consulta and asserted as an exact equality, so a second entry cannot arrive
quietly.

**The numbered host is a per-session variable.** The capture landed on one
numbered host; the module previously named that number in `allowed_hosts` while
its own comment said pinning a number would refuse a legitimate dispatch. It now
builds on the unnumbered origin. The parametrised test alone does not prove
this, because the apex suffix admits every numbered host either way, so a
second test removes the suffix and shows a sibling number refused — identifying
the field that actually carries the load-balancer case.

Gate: the named guard test passes, 29 cases. The step introduced no AEAT route
literal offender; the two hits an ad-hoc scan reported are docstrings, which the
real gate excludes.

## Notes

**Not committed as one atomic Step commit, and not by choice.** A peer merge was
in flight in the shared worktree while this work sat uncommitted. The five
edited files were swept into peer commits: the adapter and its test landed
together under a message describing the unnumbered-host fix, and the two
constants files plus the central literal fixtures were absorbed into the merge
commit itself. Every piece is present and green at HEAD and nothing was lost,
but the one-Step-one-commit discipline was broken by the sweep and the history
records this step across several commits rather than one.

**Sibling rows stay open on absent data, not absent access.** The authenticated
session reached the consulta and the query was accepted; this taxpayer simply
has no outstanding deudas. That was established rather than assumed by driving
an invalid NIF, which produced AEAT's retrieval error while the valid query
re-rendered the form byte-identically apart from the clock. So the zero-state is
real and now observed. What remains unobserved is a populated listing: no row
DOM, no `situacion` label vocabulary, no importe or periodo formatting. The rows
needing those are recorded as blocked-on-data carry-forward rather than
satisfied with an invented parser.

**Also observed, and owed to whoever writes the walker:** the surface is served
as ISO-8859-15, not UTF-8. Decoding it as UTF-8 raises outright and decoding it
as Latin-1 would silently mangle the euro sign, which is the column the listing
exists to report. A retrieval failure surfaces as an error line naming the NIF
in the avisos region.

A broader run showed unrelated failures in the declarations adapter tests and
one route-literal gate. Both are peer surface — the declarations files were in
the merge's own conflict set, and none of the route-literal offenders is in a
file this step touched.
