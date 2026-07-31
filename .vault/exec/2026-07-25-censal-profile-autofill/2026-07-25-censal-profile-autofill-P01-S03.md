---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:687b0cef6641f08810c87e61c86ea817f72eb63f72f1be93f2a51079ff80f01d'
step_id: 'S03'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Make the manager authentication action mode-aware over the profile fields, offering certificate selection only when a certificate is registered

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`

## Description

- Adopt the partial rewrite of `_run_certificate` found in the working tree and finish it.
- Split the action into a page builder, a refusal check, and a commit half, so each is reachable without a terminal.
- Offer the provider choice and both Cl@ve fields unconditionally, seeded from the `auth` section the profile already holds.
- Offer the certificate row only when a certificate source is registered, retiring the blanket refusal that stopped the action when none was.
- Name the absent credential in the Cl@ve refusal, using the label the field carried on the page.
- Write the auth facts through the plural `set_active_fields` door in one call, selecting the certificate before activating the provider.
- Translate the refusal in all four catalogues through the locales CLI, adding the missing-credential placeholder it had no way to carry.
- Type `_provider_label` as the provider enum rather than `object`.
- Add Pilot-driven coverage of the real page plus real-storage coverage of the commit half.

## Outcome

The authentication page is reachable for an operator who authenticates
with Cl@ve and has registered no certificate, which is the operator the
profile screen exists for. Their credentials persist in the encrypted
profile beside the data those credentials unlock, so a second profile on
the same machine can carry different ones and an operator setting up
through the screen can supply them at all.

Eighteen new cases pass. Four drive the real form application under
Textual's Pilot against the real page the action builds: that the page
opens with no certificate registered, that a registered certificate adds
a row opened on the active one, that the page opens on the values already
stored, and that committing hands back exactly the paths the commit half
reads. Five pin the refusal, including that it names only the credential
actually absent. Four render the refusal in every shipped catalogue and
prove each interpolates the missing name, which the two catalogues that
held their own key as their value could not have satisfied. Three drive
the commit half against a real encrypted profile bucket and prove the
facts land, the activated provider matches the recorded one, and a blank
credential clears its fact rather than storing an empty string.

`ruff format --check` and `ruff check` pass on both files. `ty check`
passes on both. The two owning suites pass whole and serially, 292 cases
across both lanes, with no held-serial warning.

## Notes

The step's own working-tree state was stale: a peer commit had removed
the censal-pull action from the same module, and the inherited copy still
carried it. Committing that copy would have resurrected the deleted
action and its cross-package private import. The file was rebuilt as the
committed version plus this step's own changes, so the deletion stands.

The four locale files were entangled with another agent's live,
uncommitted rewrite of an unrelated Cl@ve key. Their hunks were separated
out and only this step's were staged, through a patch reversed and
reapplied against the index; the working tree was never touched, and that
agent's edit remains uncommitted and intact.

Two claims made in this Step were later found false and are corrected in
`S13` rather than left standing here. The requirement that every Cl@ve
mode supply both halves was wrong: the ADR correction establishes that
the contraste is read only by the non-QR route and takes a different
form for a DNI than for a NIE, so demanding both refused the default QR
flow and Cl@ve Permanente outright. And the plural `set_active_fields`
door does not make the write atomic - it is a loop over the singular
door, persisting between iterations - so the account given here of what
that door buys was mistaken, and a test asserting the property was
removed.

Two findings belong to other owners and were not acted on. The locale
catalogues still carry four censal-pull keys that no source references
since the action was deleted, so the locale drift check reports them as
extra; whether the replacement reader reuses those strings is a later
step's call, and deleting four translated leaves in each of four
catalogues was not this step's to make. Separately, the repository-wide
import-hygiene gate is red at the committed tree for five test-only
private imports in files this step does not touch, all of them clean at
the committed revision and therefore red independently of this work.
