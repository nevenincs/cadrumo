---
tags:
  - '#adr'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-25-censal-profile-autofill-research]]"
---

# `censal-profile-autofill` adr: `profile-borne auth credentials and a read-only censal autofill` | (**status:** `accepted`)

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

**D2 - Authentication resolves credentials from the active profile,
falling back to settings.** The profile is the authority when it carries
them; the existing settings remain a fallback so nothing that works today
breaks. A Cl@ve mode with either field missing refuses at the setup
surface, naming what is absent, rather than at the first pull.

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
