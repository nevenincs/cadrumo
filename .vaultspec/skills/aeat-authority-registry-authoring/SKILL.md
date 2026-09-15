---
name: aeat-authority-registry-authoring
description: >-
  Author and enroll a new AEAT modelo or revision in the union/delta registry,
  discover the latest official release and filing frame, validate minimal live
  declarations, and publish the requested authority or export targets. Use for
  registry release authoring, not private taxpayer filing or harness development.
---

# AEAT authority registry authoring

Deliver the requested registry change on disk, not merely a report or scratch candidate. Follow `aeat-registry-authority-flow` for source, projection, continuity and publication boundaries. Read [the command workflow](references/authoring-commands.md) before executing the selected route. Do not modify the development harness as a side effect of using this skill.

### Workflow routing

- Discovery-only: establish the official release and compare it with current source; do not scaffold, apply or publish.
- Unchanged projected edition: prove selection and unchanged payload; skip scaffolding and conversion. Check publication currency only if runtime delivery was requested.
- New or changed declarations: author, inspect, test and assess; apply normalization only when it produces an accepted change.
- Runtime delivery: finish any required generated targets, then publish authority from the final source and verify adoption. Do not publish an intermediate generation merely to make development tooling usable.

The only specialist skill required by this workflow is [aeat-continuidad-grounding](../aeat-continuidad-grounding/SKILL.md), and only when continuity identities, evolutions, structural successions or lineage claims need adjudication. Read it fully when that condition applies. Ordinary evidence capture, delta authoring and publication do not require a separate planning, research, review or skill-writing skill. `aeat-registry-authority-flow` is a governing rule, not another skill or pipeline to execute.

## 1. Establish the subject and end state

Ask only for information not already supplied or discoverable:

- **Which modelo?** Preserve its three-digit identifier, including leading zeroes. If none is given, ask; do not choose a tax obligation for the user.
- **Which frame?** Tax year/ejercicio, filing period, effective date or within-year branch, and material taxpayer/territorial conditions. Distinguish the tax year from the year in which the return is submitted.
- **Exact release or latest official release?** If the user names a modelo and asks for latest/current, autonomously research the official release and its applicability. Do not ask them to supply facts the official sources establish.
- **What completion boundary?** Source-only enrollment, or enrollment plus authority publication and any applicable generated export target. Respect an already explicit instruction to finish publication; do not ask again at each routine step. Discovery alone does not authorize live edits or publication.

For autonomous discovery, browse AEAT's Sede procedure page, current and historical form/record-design downloads, instructions, and official taxpayer calendar; corroborate approving/amending provisions in BOE. Record URLs, retrieval date, source publication/update date, applicable ejercicio and period, and exact evidence locations. Latest web modification, latest published document and latest effective revision are different facts. Filing deadlines do not prove a document release date. Report an unpublished or unannounced release as such; do not invent AEAT's future publication schedule or a new edition.

Compare official evidence with the current **authored** source through the compiler, not just the currently published bundle. Preserve source/tool receipts and coordinate one writer for the affected files. A missing published authority does not prevent authoring.

## 2. Decide whether anything must be authored

The effective edition is the typed union of its selected storage baseline, genuine additions and field patches, minus explicit removals, with declared ordering, defaults and scope applied. It is not a concatenation of repeated full editions.

| Situation | Authoring action |
|---|---|
| New modelo with no usable baseline | Author its manifest and one grounded baseline containing the required payload. |
| Existing modelo; requested year is a gap with no evidenced divergence | Resolve nearest eligible authored data through canonical temporal projection; author no duplicate edition. |
| New release changes values, members, applicability or revision-local claims | Author only those divergences and the metadata required to locate and interpret them. |
| Same payload, new evidence/review scope only | Record the genuine evidence/scope change without copying payload. |
| Split, merge, repurposing or uncertain identity | Use `aeat-continuidad-grounding`; storage reuse is not a continuity adjudication. |

Projection works backward, forward and across gaps within the single registry-owned support envelope. Respect period and coexistence branches: the baseline is not necessarily the lexically latest directory. Keep authored-source and requested-frame identities distinct. Do not add consumer-specific year bounds, claim a projected year was reviewed, or promote filing capability from storage reuse.

## 3. Enroll evidence and author the delta

Capture the actual official documents in the canonical public corpus and enroll their identities in the source catalogue with content receipts and applicability. Add the governing legal references and any calendar/schedule changes at their existing owners. Reuse existing evidence IDs only for the same source identity; a new release is not permission to silently replace older evidence needed by historical revisions.

For a new modelo, use the scaffold route in the command reference and replace every placeholder. For a new revision of an existing modelo, author the narrow revision manifest and required delta fragments directly; do not clone the previous revision directory or force the scaffold over its real manifest.

Use the current `ModeloRevision` schema in `src/cadrumo/domain/calculations/registry/schema.py` and the public keyed-family/delta types it imports as the declaration contract:

- `casilla_storage_baseline` and `family_storage_baseline` select storage ancestry. Do not invent legal `predecessor` continuity to obtain inheritance.
- `casilla_overrides` and `family_overrides` patch changed leaves; their selectors identify the actual inherited member. Author new members in their owning family fragments.
- `casilla_removals`/`family_removals`, positions and `cleared_families` encode real deletion, ordering and clearing. Omission inherits; it is not deletion. False, zero and empty values retain distinct typed meanings.
- Use the canonical nested mapping and sequence patch representations. Do not assume lists merge like dictionaries, replace whole lists for one changed member, or invent a `scalar_overrides` key. Let the generic converter normalize supported scalar/singleton shapes.
- Keep effective inherited source defaults and provenance intact. A new revision default must not reattribute unchanged inherited rows.
- `scoped_families`, lineage attestations, evolution records and family dispositions preserve assertion scope. They are not excuses for full family redeclaration or automatic claim carry-forward. Do not introduce `restated_families` to evade precise deltas.

Meet coverage on the **hydrated** edition: casillas, formula closure, bindings, constructs, application links, applicability, schedules, verification, completeness and relevant extraction/export definitions. Only physically author the additions and differences needed to achieve that coverage. An unneeded family needs an evidenced disposition where required, not an invented empty implementation.

Author presentation through `dev.locales`, not revision-local locale copies. Modelo membership comes from the registry manifest and published enumeration, not a Python list/enum edit. Existing typed capabilities and resolvers should suffice for data enrollment. If genuinely new behavior requires implementation, identify the narrow missing contract and obtain scope for that work; do not fabricate unsupported declarations.

For official record designs, author the semantic mapping and reviewed render-profile inputs consumed by the pipeline. Generate supported export targets; do not transcribe generated output. Ground widths, signs, decimals, reserved values and conditions explicitly. Hand-authored exceptional formats must follow the existing schema's exception contract, not an invented waiver.

## 4. Validate, normalize, and install

Follow the command reference for candidate inspection, generic modelo collapse, independent registry assessment and source application. Keep two proofs separate:

1. The release intentionally changes exactly the evidenced fields/claims, with tests for affected frames and preserved historical behavior.
2. The storage normalization changes no effective typed meaning and leaves no eligible duplicate payload, unresolved shapes or coverage gaps; a second conversion changes no files.

Inspect the complete report, not only the process exit code. Already-delta casillas do not mean remaining families are minimal. If the user requested implementation, finish the actual source installation and verify its live fingerprint; a staging path is not completion. Do not replace unrelated modelos during a single-modelo task.

## 5. Publish and verify the requested boundary

When publication is in scope, finish applicable named export targets against the canonical compiled candidate, then use the real authority publisher on stable final inputs and verify currency. The target pipeline compiles source; it does not require publishing an intermediate runtime generation. Recheck source minimality after target writes. If a target operation changes inputs after publication, republish authority only after those final inputs pass acceptance. Never hand-write the active pointer, treat a temporary SQLite file as publication, or remove retained lock sidecars.

Complete only when the requested boundary is proven. Report modelo/frame, official release evidence, authored versus projected status, changed live paths, baseline/delta counts, semantic change tests, minimality/idempotence, and separate source-installed/authority-published/runtime-package results. For an unchanged projected edition, report the resolved baseline and evidence for the no-new-payload decision. For a real blocker, name the failing invariant and exact affected scope; continue independent in-scope work, but do not bypass publication validation.
