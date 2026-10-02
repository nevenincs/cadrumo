# Authoring commands

Run from the repository root in PowerShell. Bind `$modelo`, `$revision`, `$validFrom`, `$filingYear`, `$period` and, when needed, `$sourceRef` to the subject established with the user and official evidence. These are task coordinates, not new registry support-range settings. Use a fresh work directory for each converter/assessor invocation. Commands below mutate only where explicitly stated.

## Orient and capture evidence

```powershell
uv run --no-sync python -m dev.registry.newmodelo checklist
uv run --no-sync python -m dev.registry.newmodelo scaffold --help
uv run --no-sync python -m dev.registry.newmodelo new-edition --help
uv run --no-sync python -m dev.registry.edition_delta_migration --help
uv run --no-sync python -m dev.registry.pipeline --help
```

The checklist is a hydrated-coverage aid, not a full-copy template. Scaffolds require explicit applicability coordinates. Storage baselines select reusable payload independently of legal predecessor continuity, and only independent validation establishes registry validity or minimality.

For enrolled record-design corpus integrity:

```powershell
uv run --no-sync python -m dev.corpus.sync_aeat_record_design_corpus
uv run --no-sync python -m dev.corpus.sync_aeat_record_design_corpus --live-check
```

The second command uses the network and reports changed/missing official artifacts; neither replaces official release discovery. `--pull` is a corpus-wide mutation with no modelo filter: do not use it as a targeted downloader. Inspect its declared coverage before an explicitly scoped corpus refresh. For a newly discovered artifact, capture it using the existing corpus format and update its per-modelo evidence manifest and canonical source declaration; there is no generic one-modelo enrollment switch in this command. Inspect `dev/registry/compiler/corpus_catalogue.py` and a same-format enrolled artifact for the required identity fields and storage path. Never fabricate a download CLI or hash.

After an authorized per-modelo manifest edit, recompute the corpus census if applicable:

```powershell
uv run --no-sync python -m dev.corpus.sync_aeat_record_design_corpus --regenerate-aggregate
```

For changed PDF/manual or HTML/workbook source families respectively, regenerate their owned sidecars and check freshness:

```powershell
just generate-corpus-text
just check-corpus-text
just generate-corpus-sidecars
just check-corpus-sidecars
```

These generators can touch multiple enrolled sources. Review their scope and preserve unrelated concurrent changes; run only the relevant source-family generators.

## Create declarations

For a genuinely new modelo only, after confirming its directory does not already contain real declarations:

```powershell
just registry-modelo-scaffold $modelo $revision $validFrom $filingYear $period
```

Replace the remaining manifest/revision placeholders with grounded declarations at `src/cadrumo/_data/registry/aeat/modelos/<modelo>/`. For an existing modelo, use the preserving route:

```powershell
just registry-modelo-new-edition $modelo $revision $validFrom $filingYear $period
```

It writes only `revisions/<revision>/revision.toml`, preserves the existing manifest and declarations, and proposes storage baselines without inventing legal continuity. Author only required delta fragments. An isolated scaffold remains structural authoring assistance, not enrollment or publication proof.

Resolve legal/source IDs through the canonical compiler catalogues. Find the owning declaration for a known source ID with targeted `rg`, then enroll the new evidence alongside its actual owner rather than guessing a top-level catalogue filename.

For each required shared locale value, bind `$locale`, `$key` and `$text` and use:

```powershell
uv run --no-sync python -m dev.locales set $locale $key $text
```

Use derived keys from the canonical localization helpers and existing locales. Record review provenance truthfully through the existing stamp command when a review is actually completed:

```powershell
uv run --no-sync python -m dev.registry.conformance stamp --help
```

Do not stamp operator review on behalf of an operator or use a passing compiler as review evidence.

## Inspect current authoring source without publication

This uses the canonical bundled **source paths**, not the published bundle. It prints findings and returns failure if publication validation is not satisfied; structural input errors may raise before findings are returned.

```powershell
@'
from dev.registry.compiler.authority import AuthoritySourceSet, inspect_authoring_candidate
s = AuthoritySourceSet.bundled()
r = inspect_authoring_candidate(s.registry_root, s.source_evidence_root, profile_schema_path=s.profile_schema_path)
print("registry_fingerprint", r.registry_fingerprint)
print("source_evidence_fingerprint", r.source_evidence_fingerprint)
for finding in r.findings:
    print(finding)
raise SystemExit(0 if r.publication_valid else 1)
'@ | uv run --no-sync python -
```

Use explicit captured root paths instead of `AuthoritySourceSet.bundled()` when inspecting an isolated candidate. Do not mix a candidate registry with unrelated or stale evidence roots.

## Normalize and actually apply the modelo delta

Set the canonical roots and create a unique, not-yet-existing converter path:

```powershell
$registryRoot = Join-Path (Get-Location) 'src/cadrumo/_data/registry/aeat'
$sourceRoot = Join-Path (Get-Location) 'src/cadrumo/_data'
$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ('registry-authoring-' + [guid]::NewGuid().ToString('N'))
uv run --no-sync python -m dev.registry.edition_delta_migration --registry-root $registryRoot --modelo $modelo --work-dir $workDir
```

Read the emitted report and candidate diff. The canonical owner handles casillas plus family/scalar continuation; do not invoke removed modelo-specific converters or standalone compact/lift tools.

If the converter reports no changes and the live declarations already pass minimality, skip `--apply`. Otherwise, after the source change's evidence/tests and normalization proof are accepted, apply through the converter using a fresh directory. This recomputes against current live inputs rather than installing a stale candidate blindly:

```powershell
$applyDir = Join-Path ([System.IO.Path]::GetTempPath()) ('registry-authoring-apply-' + [guid]::NewGuid().ToString('N'))
uv run --no-sync python -m dev.registry.edition_delta_migration --registry-root $registryRoot --modelo $modelo --work-dir $applyDir --apply
```

`--apply` installs source, not runtime authority. Retain its recovery receipt. Rerun the non-applying command with a fresh work directory against live source to prove no-op/idempotence. Then run independent full-inventory verification without authorizing changes to other modelos:

```powershell
$verifyDir = Join-Path ([System.IO.Path]::GetTempPath()) ('registry-authoring-verify-' + [guid]::NewGuid().ToString('N'))
uv run --no-sync python -m dev.registry.registry_collapse_verification --registry-root $registryRoot --source-root $sourceRoot --work-dir $verifyDir
```

Require complete assessment coverage, zero eligible duplicate payload and unresolved shapes for the changed source, and stable receipts. Report independent publication/indexed-parity failures separately; an aggregate nonzero exit is not automatically a source-equivalence failure.

Run the owning release tests, including new assertions for actual changed values, unchanged historical frames, gap projection and boundary/branch selection. When continuity changed, run the existing `aeat-continuidad-grounding` workflow and its commands. At minimum exercise the authoring/publication boundary tests:

```powershell
uv run --no-sync pytest -o addopts='' -n 0 -q dev/registry/tests/test_authoring_candidate_inspection.py dev/registry/tests/test_compile_path_never_reads_the_published_bundle.py
git diff --check
```

## Publish authority and applicable export targets

Use one publication owner. Finish applicable generated targets before the final authority publication so the active generation represents the final source. Skip the target subsection for revisions without a generated record-design target. Target preparation uses canonical source compilation, not the published runtime bundle; an absent runtime pointer is not by itself a prerequisite failure.

For a generated record-design target only, first author/enroll its mapping and reviewed render profile in the locations resolved by the current pipeline. Inspect a same-format target and `dev/registry/pipeline/cli.py` for enrollment; the pipeline does not infer semantic mappings from arbitrary PDF prose. Then:

```powershell
uv run --no-sync python -m dev.registry.pipeline check $modelo $revision $sourceRef $filingYear $period
just registry-publish-target $modelo $revision $sourceRef $filingYear $period
uv run --no-sync python -m dev.registry.pipeline target-current $modelo $revision $sourceRef $filingYear $period
```

For replacement of an existing reviewed target, bind `$expectedManifestSha256` to the exact reviewed lowercase SHA-256 and use:

```powershell
just registry-republish-target $modelo $revision $sourceRef $filingYear $period $expectedManifestSha256
```

The digest alone does not authorize changed records: record drift additionally requires the pipeline's source-pinned disposition with remedy `republish` and a reconsideration condition. A disposition declaring the shipped records correct instead requires fixing generator inputs. An expected drift refusal from `check` is not a reason to retry ordinary `publish-target` indefinitely; inspect the comparison and use only the matching supported replacement route.

For a never-published target, `_prepare` requires a reviewed bootstrap target matching modelo, revision, source reference and source hash. Follow the existing `generated_export_bootstrap_target` declaration owner; this is not a universal bypass for invalid source. The source must still compile. If no supported declaration can express the required target or compilation fails, report the exact missing contract rather than manufacture authority or relax capability to pass.

After target writes, rerun source inspection and independent minimality/currentness checks against the resulting live files. Once source, evidence and compiler writers have quiesced, publish the final authority:

```powershell
just registry-publish-authority
```

The result must be an accepted `src/cadrumo/_data/registry/authority/authority.current.json` referencing the content-addressed SQLite generation. Retain the publisher's identity/receipt and verify through the canonical runtime reader and checks below; pointer existence alone proves nothing. Do not edit these artifacts manually.

If captured inputs change during publication, the refusal invalidates that attempt. Identify the writer, wait for the affected inputs to stabilize, revalidate the changed dependencies and retry against a fresh receipt. Do not repeatedly rerun an unchanged failed attempt or remove lock sidecars. A publication failure does not undo or conceal already-installed source; report both states and retain recovery artifacts.

Final checks:

```powershell
just check-registry
uv run --no-sync pytest -o addopts='' -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py dev/packaging/tests/test_authority_runtime_boundary.py src/cadrumo/tests/test_wheel_bundles_corpus_and_registry.py
```

Check report components and actual test selection/results. Runtime/package acceptance must consume the final published generation. No-op source, validated candidate, published target and adopted runtime generation are separate outcomes; report each one relevant to the requested completion boundary.
