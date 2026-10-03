# Wizard contracts and validation

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-108` · **Topic:** [Operations, profiles and workflows](../topics/operations-profiles-and-workflows.md)

<!-- preserved:article -->
## Scope and method

This chunk covers nine wizard application modules, totaling 2,231 lines, 94,157 bytes, and 20,539 measured `o200k_base` proxy tokens. I read all four bounded pages and their assigned file ranges. Analysis is static; no runtime or legal verification was performed.

## Wizard contract and validation

The wizard descriptor is a strict, frozen model of flows, sections, questions, choices, widget types, defaults, and visibility. Conditions support one equality or checkbox-membership clause; a visibility descriptor is a disjunction. Construction checks that question IDs are unique, every translatable belongs to the flow's locale-key prefix, and each visibility reference points to an earlier question. Those checks make the catalogue a constrained application contract rather than presentation-only metadata. models.py (`src/cadrumo/application/wizard/models.py`) models.py (`src/cadrumo/application/wizard/models.py`) models.py (`src/cadrumo/application/wizard/models.py`) models.py (`src/cadrumo/application/wizard/models.py`) models.py (`src/cadrumo/application/wizard/models.py`) models.py (`src/cadrumo/application/wizard/models.py`)

Per-widget validators canonicalize text, booleans, choices, checkboxes, paths, and integers. They preserve blank optional confirms as an undeclared value rather than a false answer; choice and checkbox tokens must come from the declared set. Taxpayer and spouse IDs use the shared identity validator, and the Spanish postcode field has a dedicated validator. Errors use a finite reason vocabulary, localized prompt labels, and a redacted structured context. The translated message is rendered from the original answer context to give the operator a concrete refusal, while the attached context passes through the redactor. widgets.py (`src/cadrumo/application/wizard/widgets.py`) widgets.py (`src/cadrumo/application/wizard/widgets.py`) widgets.py (`src/cadrumo/application/wizard/widgets.py`) widgets.py (`src/cadrumo/application/wizard/widgets.py`) widgets.py (`src/cadrumo/application/wizard/widgets.py`) widgets.py (`src/cadrumo/application/wizard/widgets.py`) widgets.py (`src/cadrumo/application/wizard/widgets.py`)

One taxpayer-construction flow validator reruns the canonical `projection_for_taxpayer` constructor over staged top-level answers. It maps recognized construction failures to stable localized checks and field names, omitting the raw Pydantic/deadline message from verdicts. A separate section-exit validator checks that a joint non-married/monoparental family declaration includes qualifying children. Its declared model has only the minor-children proxy and explicitly does not represent adult incapacitated children, a known limit on this setup surface rather than an implicit broader rule. flow_validators.py (`src/cadrumo/application/wizard/flow_validators.py`) flow_validators.py (`src/cadrumo/application/wizard/flow_validators.py`) flow_validators.py (`src/cadrumo/application/wizard/flow_validators.py`) setup_legal_validators.py (`src/cadrumo/application/wizard/setup_legal_validators.py`) setup_legal_validators.py (`src/cadrumo/application/wizard/setup_legal_validators.py`)

## Persistence and profile status

The persistence adapter maps typed answers to canonical path/value strings and reverses that mapping through the question descriptors. Optional blank confirms stay blank and therefore remain undeclared; an explicit false round-trips as a declared negative. Patch projection validates only supplied fields, preserves omitted facts, and retains explicit blank optional answers as clear operations. `apply_profile_patch` reopens the current session-bound record, compares revision and content digest, reruns patch validation on that current record, and commits through the shared fact-write door with an expected-record baseline. A complete profile must retain the filing baseline after a patch. persistence.py (`src/cadrumo/application/wizard/persistence.py`) persistence.py (`src/cadrumo/application/wizard/persistence.py`) persistence.py (`src/cadrumo/application/wizard/persistence.py`) persistence.py (`src/cadrumo/application/wizard/persistence.py`) patch_edit.py (`src/cadrumo/application/wizard/patch_edit.py`) patch_edit.py (`src/cadrumo/application/wizard/patch_edit.py`) patch_edit.py (`src/cadrumo/application/wizard/patch_edit.py`) patch_edit.py (`src/cadrumo/application/wizard/patch_edit.py`)

Descendant persistence inverts the repeating-group answers into canonical profile facts and reconstructs existing facts back into page-keyed answers. It reads only the count's indexed instances and preserves absent optional facts on both legs. Before constructing domain values, it filters invalid or relationship-incompatible civil-registry/foster dates rather than allowing a raw model error; the comments expect flow review to block those states. Combined with the validator gap recorded in STAGE-2-107, stale incompatible event answers may be silently dropped at projection when the review path does not issue the promised verdict. That is a conditional cross-module risk; verify whether the flow engine removes hidden answers before review and exercise relation-change/resume cases. persistence.py (`src/cadrumo/application/wizard/persistence.py`) persistence.py (`src/cadrumo/application/wizard/persistence.py`) persistence.py (`src/cadrumo/application/wizard/persistence.py`) persistence.py (`src/cadrumo/application/wizard/persistence.py`) persistence.py (`src/cadrumo/application/wizard/persistence.py`) persistence.py (`src/cadrumo/application/wizard/persistence.py`)

`build_wizard_status` combines schema/profile-key validation with IVA-enrolment completeness only when the taxpayer facts require IVA. It gets provider/auth readiness from the canonical no-live-backend state projection and avoids echoing an unknown provider as valid. It offers a typed next action only when the profile exists, required identity and enrollment data are present, and a known provider can be offered for login; otherwise it does not invent a continuation. The `TaxpayerProfile` bridge requires the enclosing operation's schema, refuses absent active profile or tax ID, and uses the canonical taxpayer projection. `ProfileWizardStatus` is a closed machine-readable result vocabulary, including `unchanged` for no-op patches. status.py (`src/cadrumo/application/wizard/status.py`) status.py (`src/cadrumo/application/wizard/status.py`) status.py (`src/cadrumo/application/wizard/status.py`) status.py (`src/cadrumo/application/wizard/status.py`) results.py (`src/cadrumo/application/wizard/results.py`) results.py (`src/cadrumo/application/wizard/results.py`)

## Assessment and follow-up

The principal strengths are declarative validation of flow shape, shared validators for user-entered IDs and booleans, parity between answer projection and persistence, preservation of tri-state answers, revision/digest concurrency checks, and strict typed output/status models. A review point for CLI integration is the IVA regime flag: command construction configures its `click.Choice` as case-insensitive, while `validate_select` compares supplied text exactly to choice values. Confirm whether Click returns the canonical choice token before patch projection; if it returns the user's casing, an input accepted by the parser can be rejected by the shared widget validator. This is a conditional compatibility question, not a confirmed runtime failure from static reading alone.

Synthesis should also trace the flow engine's treatment of hidden resumed answers, the create/status CLI consumers, the auth readiness authority, and exact write paths. No tests or execution results appear in this chunk. Legal descriptions here are application rationale, not independently verified advice.

## Complete assigned-file coverage

- errors.py (`src/cadrumo/application/wizard/errors.py`)
- flow_validators.py (`src/cadrumo/application/wizard/flow_validators.py`)
- models.py (`src/cadrumo/application/wizard/models.py`)
- patch_edit.py (`src/cadrumo/application/wizard/patch_edit.py`)
- persistence.py (`src/cadrumo/application/wizard/persistence.py`)
- results.py (`src/cadrumo/application/wizard/results.py`)
- setup_legal_validators.py (`src/cadrumo/application/wizard/setup_legal_validators.py`)
- status.py (`src/cadrumo/application/wizard/status.py`)
- widgets.py (`src/cadrumo/application/wizard/widgets.py`)
<!-- /preserved:article -->
