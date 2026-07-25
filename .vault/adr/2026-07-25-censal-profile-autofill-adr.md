---
tags:
  - "#adr"
  - "#censal-profile-autofill"
date: '2026-07-25'
related:
  - "[[2026-07-25-censal-profile-autofill-research]]"
supersedes:
  - '2026-07-11-censo-operator-manual-enrolment-adr'
modified: '2026-07-25'
---
# `censal-profile-autofill` adr: `profile-borne auth credentials and a read-only censal autofill` | (**status:** `accepted`)

> **D3 UNBLOCKED — the 404 finding it was blocked on is stale.**
> This note previously blocked D3, on the grounds that
> `2026-07-11-censo-operator-manual-enrolment-adr` recorded a 2026-07-10
> live finding that the launcher `/wlpl/BUGC-JDIT/MdcAcceso` returns HTTP
> 404 and that AEAT exposed no read-only censal projection. That block was
> correct on the evidence then available and is now withdrawn: the
> operator confirms on 2026-07-25 that the launcher renders, as an HTML
> form carrying their NIF, name and censal information. AEAT evidently
> restored or re-pathed it in the intervening fortnight. The prior ADR's
> own revival condition - "a genuine AEAT consulta-only 'datos censales'
> endpoint would justify a new ADR to restore an automated read" - is
> therefore met, and this record is that ADR.
>
> Two corrections to D3 as written survive the unblocking:
>
> First, the S06 proof was wrong independently of the endpoint question.
> It forbids the token `MOD036`, but the filing tool is
> `BU36-ASIS/M036/index.zul` and the write sibling is
> `BUGC-JDIT/ModifDomiDual` - neither contains that token, so the gate
> would have passed while the reader sat next to a write surface. The
> reader MUST fail closed at runtime on any `BU36-*`, `.zul` or
> `ModifDomiDual` landing, with the static string check kept only as the
> weaker of two walls.
>
> Second, the consulta page carries buttons and AEAT's own help material
> titles the area "Consulta y modificación", so a modification path is
> reachable from the page the reader lands on. Reading the rendered DOM is
> a read; driving a control on it is not. The reader navigates and parses,
> and never submits, fills or follows a mutating control.

## Problem Statement

The profile TUI's reason to exist is that an operator should not retype
what AEAT already holds. Neither half of that is in place: the profile
schema carries nowhere to store the credentials an authentication mode
needs, and the codebase's censal pull reads the declarations register, a
surface that carries no censal data at all and returns nothing for every
taxpayer. This record decides where authentication credentials live, what
surface the censal read uses, how a pulled fact reaches the profile, and
what happens to the register-based pull already in the tree.

## Considerations

- The register-based censal derivation is not merely unfinished, it is
  categorically wrong: Modelo 036 is a censal communication, not a
  periodic return, so it never appears in a register of returns (research).
- The consulta view sits in an area titled "Consulta y modificación", and
  the 036 filing tool is one link away; this adjacency is exactly why
  `2026-07-11-censo-operator-manual-enrolment-adr` retired the previous
  scrape, and it binds any replacement.
- `aeat-safety-legal-gates` bars live submission absolutely; a read whose
  page also offers a write is the hazard class that rule exists for.
- `sensitive-financial-data-secure-storage-only`: a número de soporte is a
  credential input and may persist only in the encrypted store.
- `local-filed-observations-are-non-official-evidence` and the existing
  cotejo contract already fix the evidence tier and the write path for
  censal facts; `apply_cotejo` is the single apply authority and emits one
  `CENSO_APPLIED` per commit.
- `_assert_active_profile_identity_matches_provider` already fails closed
  on an identity mismatch, so profile and provider identity are coupled
  whether or not the profile stores its half.
- `no-dormant-source-resolvers` and `no-legacy-compatibility`: capacity
  with no live caller, and a surface that reads nothing, are both deletions
  rather than deferrals.

## Considered options

**A. Keep the register pull and add the censal reader beside it.** Rejected:
the register pull answers a question the register cannot answer, so it
would remain a permanent source of "no censal filing found" noise and a
second, wrong authority on the same fact.

**B. Read censal state by driving the 036 filing tool's own form.** Rejected
outright: that is the write surface, and reaching current state by opening
the tool that mutates it is the precise hazard the earlier retirement ADR
records.

**C. Credentials stay in the dotenv, TUI reads them.** Rejected: a second
profile on the same machine cannot carry different credentials, an
operator setting up through the TUI cannot supply them at all, and a
credential in a plaintext dotenv contradicts the secure-storage rule.

**D (chosen). Profile-borne credentials plus a read-only consulta reader.**
The profile carries an `auth` section; a new sede reader is pinned to the
consulta view; pulled facts commit through the existing cotejo authority.

## Constraints

- The reader MUST be incapable of reaching a write action, and that
  incapacity MUST be proven by a test, not asserted in a docstring.
- Pulled censal facts MUST carry a provenance token naming their surface
  and MUST land at the non-official evidence tier.
- A pull MUST NOT silently overwrite a value the operator declared.
- Credentials MUST persist only in the encrypted profile store.

## Implementation

**D1 - The profile carries an `auth` section.** `auth.provider`
(`certificate` | `clave_movil` | `clave_permanente`), `auth.dni_nie` and
`auth.numero_soporte`, all at `identity` sensitivity so they persist
encrypted. `dni_nie` is recorded separately from `identity.tax_id`
because the person authenticating is not always the taxpayer the profile
describes. Requirement is conditional on the mode: a Cl@ve provider needs
both Cl@ve fields, the certificate provider needs neither.

**D1a - The Cl@ve second factor is a contraste whose form follows the
document, and it is required only on the route that reads it.** D1's "a
Cl@ve provider needs both fields" was wrong as written and is corrected
here on evidence. The contraste is read only by the non-QR fallback, and
it is the número de soporte for a NIE but the **validity date** for a
DNI; Cl@ve Permanente's second half is a password, not a contraste at
all. Requiring both fields unconditionally would refuse the default QR
flow and Permanente outright, breaking flows that work today, which D2
forbids. So: every Cl@ve mode requires `auth.dni_nie`; the contraste is
required exactly when the non-QR route is selected, and is satisfied by
either the soporte or the DNI validity date. The schema therefore needs a
second contraste field for DNI holders, who have no home for their half
today. Cl@ve Permanente's password stays out of the profile record and in
the secret store, beside the certificate passphrase — a password is not a
profile fact.

**D1b - `dni_nie` is stored apart from `identity.tax_id` because it is a
credential, not because the two may differ.** D1's original rationale
said the authenticating person is not always the taxpayer the profile
describes. That case is unreachable and must stay so: the pre-existing
fail-closed guard refuses whenever the Cl@ve identity differs from
`identity.tax_id`, and the login driver refuses third-party
representation outright ("Do not provide represented-third-party data
through this driver"). The product does not support acting as a
representative, deliberately. The guard is NOT relaxed - keeping a
fail-closed safety gate closed needs no justification, opening one does,
and there is no current use case. The field stays separate because a
credential input and a taxpayer identifier are different things that
happen to carry equal values today, and conflating them would hide the
day they diverge.

**D2 - Authentication resolves credentials from the active profile,
falling back to settings.** The profile is the authority when it carries
them; the existing settings remain a fallback so nothing that works today
breaks. A Cl@ve mode with either field missing refuses at the setup
surface, naming what is absent, rather than at the first pull.

**D7 - The user-profile schema is a CONTRACT, and the code is brought to
it.** Three instances now show it read as an authority and honoured as
prose: `UserProfileFact.source` is a length-constrained `str` so the
schema's declared provenance enum binds nothing; the entire `auth`
section is absent from the compiled profile-key catalogue, so a
schema-declared `date` type is enforced nowhere and a malformed value is
refused opaquely by AEAT rather than by the profile that declared it; and
a fact path absent from the schema was written with no complaint. The
audit `2026-07-25-censal-profile-autofill-tooling-honesty-audit` records
these as one critical finding.

The alternative - declaring the schema documentation and dropping its
closed sets - is rejected. The schema is the one authority every other
surface already reads against: registry bindings select on its paths, the
manager renders its sections, validation quotes it to operators. Making
it advisory would demote the only thing holding those surfaces in
agreement, to avoid enforcing what they all already assume.

So: `UserProfileFact.source` validates against the schema's declared
provenance set; every schema-declared section is enrolled in the compiled
key catalogue; and a gate asserts that parity, because the `auth` gap was
found by someone trying a value by hand rather than by any check.

Two existing breaches are reconciled rather than grandfathered. The
shipped censal-artefact path stamps `censo_artefact_g313`, which the
declared set does not contain - the token is real and in use, so the
declared set gains it rather than the code losing it. And the `auth`
section is enrolled. Neither is new work; both are the schema being made
true about code that already ships.

**D3 - A new read-only censal reader lives in the sede adapter.** It
navigates to the consulta view only, through the same authenticated
session and access-gate path every other live read uses. It exposes no
method that submits a form, and its module carries no reference to the
`MOD036` filing path. A gate asserts both: the reader's surface offers no
write, and the filing path appears nowhere in it.

**D4 - Pulled facts commit through `apply_cotejo`.** They carry a
provenance token naming the censal consulta surface, adopt only where the
record is blank, and report every disagreement instead of overwriting it.
The operator resolves disagreements themselves; the pull never decides
between AEAT's answer and theirs.

**D5 - The register-based censal pull is deleted.**
`application/live/_censo_036_pull.py` and its manager action are removed
rather than left beside the new reader. The registry causa-casilla
mapping and `classify_from_causa_casillas` are retained only if the new
reader consumes them; otherwise they go too.

**D6 - The TUI setup surface collects the auth section before offering a
pull.** The manager's authentication action is mode-aware, shows the
fields the chosen mode needs, and the censal pull is unavailable until
the mode's requirements are satisfied.

## Rationale

Option D is the only one that puts each fact where its authority is: the
credential on the encrypted profile that uses it, the censal state at the
surface AEAT publishes it on, and the adoption decision with the operator
who can adjudicate it. The write-adjacency that killed the previous
attempt is met by pinning and proving rather than by avoidance, because
avoidance is what left the TUI asking operators to retype data the
authority already has.

## Consequences

The register-based pull disappears, so any caller of it must move. A
profile created before this record has no `auth` section and falls back
to settings, which is the pre-existing behaviour. The censal reader is
new attack surface against a live authority: it earns its place only with
the no-write proof, and without that proof it must not ship.

Deleting the register-based pull surfaced a typed-boundary hole that is
independent of this record and outlives it. The pull wrote a fact at
`censo.filed_on`, a path the user-profile schema does not declare, and
stamped it `censo_filed_036`, a token absent from the schema's declared
provenance enum (`manual_cli`, `setup_wizard`, `modelo_036_import`,
`aeat_censo_read`, `registry_inference`). Both values passed every gate.
`UserProfileFact.source` is a length-constrained `str` rather than that
enum, so the declared value set is documentation at the boundary and not
a constraint; and nothing cross-checks a fact's `path` against the
schema's declared field set either. Neither escape was loud, and only
the surface's total absence of output kept them from reaching a profile.
Closing this is a follow-up in its own right: it applies to every writer
of a profile fact, whatever becomes of D3.
