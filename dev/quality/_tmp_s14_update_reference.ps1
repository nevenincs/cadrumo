$ErrorActionPreference = 'Stop'

$path = '.vault/reference/2026-09-04-clitui-ledger-reference.md'
$blob = (git hash-object $path).Trim()
$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = 'git'
$startInfo.ArgumentList.Add('show')
$startInfo.ArgumentList.Add("HEAD:$path")
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
$process = [System.Diagnostics.Process]::Start($startInfo)
$raw = $process.StandardOutput.ReadToEnd()
$errorOutput = $process.StandardError.ReadToEnd()
$process.WaitForExit()
if ($process.ExitCode -ne 0) {
    throw "git show failed: $errorOutput"
}
$body = [regex]::Replace($raw, '\A---\n.*?\n---\n', '', [System.Text.RegularExpressions.RegexOptions]::Singleline)

$oldOpening = 'This document is the authoritative human-readable publication surface for the `LedgerCapabilityMatrixV1` campaign contract in `dev/quality/clitui_ledger_capability_matrix.py`. The exact union contains 760 raw observations, 769 observation-to-row selections, and 693 semantic rows. Singular ownership and the active campaign hold are recorded, every TUI-applicable row carries the hold, and the exhaustive row review binds all eight applicability and proof decisions plus every open disposition. The canonical 693-row **pre-acceptance candidate** is now deterministic and digest-bound, but it is not an accepted campaign matrix: two fresh independent rulings, an `ACCEPT` attestation, its external acceptance-record anchor, and G0 closure are all still absent.'
$newOpening = 'This document is the authoritative human-readable publication surface for the `LedgerCapabilityMatrixV1` campaign contract in `dev/quality/clitui_ledger_capability_matrix.py`. The exact union contains 760 raw observations, 769 observation-to-row selections, and 693 semantic rows. Singular ownership and the active campaign hold are recorded, every TUI-applicable row carries the hold, and the exhaustive row review binds all eight applicability and proof decisions plus every open disposition. Two independent engineering rulings accepted the same frozen 693-row candidate, the accepted attestation and exact G0 gate receipt are digest-bound, and the separately observed acceptance-record anchor closes G0. G1 through G4 remain locked, and the Ledger TUI implementation hold remains active.'
$body = $body.Replace($oldOpening, $newOpening)
$body = $body.Replace('| Publication revision | `s14-remediation-candidate-2` |', '| Publication revision | `s14-g0-accepted-1` |')
$body = $body.Replace('| Candidate revision | Final scoped commit is the review subject; its source and matrix digests below are the only candidate identity claims |', '| Frozen candidate revision | commit `f9580577ffcb1d730c6459c73ff209e3ea3412bc`; tree `4db16a09813d8f41702b8779881f3996e9f8de39` |')
$matrixRows = '| Candidate matrix digest / pre-receipt review basis | `sha256:c4a210bbd5410a3b6f7630262277b0cfc780d278815cc7a58da66dccd265c30a` / `sha256:a8cd7cb17aea3d508459423c708b596d8931c76660fee6abf987c2c6fe21d7bd` |' + "`n" + '| Accepted matrix digest | `sha256:6f4dcc03bbf6c8780affefb35546aaa47c3f883e83e6150ff5bb30aed6151f50` |'
$body = $body.Replace('| Matrix digest / pre-receipt review basis | `sha256:c4a210bbd5410a3b6f7630262277b0cfc780d278815cc7a58da66dccd265c30a` / `sha256:a8cd7cb17aea3d508459423c708b596d8931c76660fee6abf987c2c6fe21d7bd` |', $matrixRows)
$body = $body.Replace('| Acceptance attestation | No accepted attestation: candidate carries the deterministic `independent-review-pending` / `REJECT` state only |', '| Acceptance attestation | `attestation.ledger.g0`; `primary-independent-review`; `ACCEPT`; digest `sha256:d0b8630c9e137efb3e308ed7f185623745ee4f15c573f9cbd154264ee33e34d7` |')
$body = $body.Replace('| Acceptance-record anchor / G0 | Absent / **OPEN**; neither is minted by candidate preparation |', '| Acceptance-record anchor / G0 | current external subject `sha256:0c3807c8c53259c97b4bd4ac923c3de5f216684910d9f0674f5ee526ffb9f64a` / **CLOSED** |')
$body = $body.Replace('The row review issues a provisional reviewed union without upgrading any operational claim. G0 remains open pending S14 independent digest-bound acceptance; S13 now relocks G0 through G4 for every reviewed-union, census, row, evidence, receipt, or anchor currentness defect.', 'The accepted reviewed union does not upgrade any operational claim or erase these open gaps. G0 is closed by the S14 digest-bound independent acceptance record; the S13 currentness contract relocks G0 through G4 for every reviewed-union, census, row, evidence, receipt, or anchor defect.')
$body = $body.Replace('| G0 denominator and ownership freeze | **OPEN** | Current source observations, singular ownership, serialized semantic union, row-level TUI hold, and exhaustive 693-row review are complete; reopening enforcement is active, but digest-bound independent `ACCEPT` remains outstanding |', '| G0 denominator and ownership freeze | **CLOSED** | Two independent `ACCEPT` rulings bind the same frozen 693-row candidate; the exact G0 receipt and current external acceptance-record anchor pass live evaluation |')
$body = $body.Replace('| G1 semantic authority recovery | **LOCKED by G0** |', '| G1 semantic authority recovery | **OPEN** |')
$body = $body.Replace('| G2 backend product completeness | **LOCKED by G0/G1** |', '| G2 backend product completeness | **LOCKED by G1** |')
$body = $body.Replace('| G3 CLI clean break and completeness | **LOCKED by G0-G2** |', '| G3 CLI clean break and completeness | **LOCKED by G1-G2** |')
$body = $body.Replace('| G4 TUI admission and parity | **HELD and LOCKED by G0-G3** |', '| G4 TUI admission and parity | **HELD and LOCKED by G1-G3** |')
$body = $body.Replace('S04 establishes only the complete CLI stream and current observations: G0 remains open until every other mandatory stream is collected, row applicability and semantic homes are adjudicated, the TUI hold is recorded, and independent review accepts a digest-bound union denominator.', 'S04 established only the complete CLI stream and current observations; it did not close G0 by itself. S14 now closes G0 only after every mandatory stream, row decision, hold, and digest-bound independent acceptance requirement is satisfied.')
$body = $body.Replace('Reopening enforcement is active; independent acceptance remains outstanding; G0 remains open.', 'Reopening enforcement remains active; the current external acceptance record closes G0, while the row-level TUI hold remains active through G3.')

$acceptance = @'
#### G0 independent acceptance record

Both engineering rulings independently observed the same frozen candidate commit and tree. The labels below are durable review roles only; no agent identity or team topology is recorded. Both rulings carry the observed date `2026-09-05`. Because no event time was supplied, the typed attestation and external subject use the explicit date-normalized value `2026-09-05T00:00:00+02:00`; it denotes date granularity, not a claimed review time.

| Receipt | Ruling | Bound evidence | Receipt digest |
| --- | --- | --- | --- |
| `primary-independent-review` | `ACCEPT`; zero blockers | Exact 693-row identity equality; hostile one-row/full-union refusal; lossless gap cohorts `AUTHORITY=112`, `REGISTRY=546`, `PRODUCT=689`, `ARTIFACT=39`, `REACHABILITY=679`, `COMPOSITION=638`, `PROVENANCE=562`, `PROOF=693`; annotations `CLI_OWNED=112`, `COMPONENT_ONLY=679`, `INSTALLED=1` with `ledger.workspace.read` sole installed row; source-coordinate detector; focused 11 plus mutation, static, and Vault checks | Supplied ruling-envelope digest `sha256:e862e5183d3755932386d65f991bab2a0b508952d1648b6e49d915e803263ca1` |
| `second-independent-review` | `ACCEPT`; zero blockers | Source, union, review, row-attestation, denominator, candidate-matrix, pre-receipt-basis, and pending-attestation digests below; `760` observations, `769` selections, `693` unique identities; hostile mutation refusal; lossless cohorts; `ledger.workspace.read` sole installed row; 297 matrix tests plus static, compile, and Vault checks | Locally computed canonical-envelope digest `sha256:1d6090de2b908208e6c3cd1934ca18e64a12eeb8d0982ab67abea79854631d17` |

The second reviewer supplied no envelope digest. Its receipt digest is therefore explicitly local derivation, computed by the contract's `_canonical_digest` serializer over this complete payload; it is not represented as reviewer-supplied:

```json
{"blockers":[],"candidate_commit":"f9580577ffcb1d730c6459c73ff209e3ea3412bc","candidate_matrix_digest":"sha256:c4a210bbd5410a3b6f7630262277b0cfc780d278815cc7a58da66dccd265c30a","candidate_tree":"4db16a09813d8f41702b8779881f3996e9f8de39","denominator_digest":"sha256:48c2c800faa2c9932811678fc16c8caff2cae89bcdaf81512e7ae7aa29d5d140","denominator_revision":"row-review-v1","observations":{"identities":693,"raw":760,"selections":769},"pending_attestation_digest":"sha256:01eee26b8be50f485801e15271361cc1bcd76de562cc8aa4c2e7066f6fc75d7","pre_receipt_basis_digest":"sha256:a8cd7cb17aea3d508459423c708b596d8931c76660fee6abf987c2c6fe21d7bd","receipt_id":"receipt.ledger.independent_review.second","reviewer":"second-independent-review","row_attestation_digest":"sha256:fc15a433ad145832934cbe894d3d0b875d27e9a54ed1a70ae271c16ff81aedf7","row_review_digest":"sha256:4e42e5e04ccfd7a8654e629933698e141033b0767d0f94ec5433619400203ff8","ruling":"accept","ruling_date":"2026-09-05","schema_version":1,"source_digest":"sha256:18e201e66d73b883ad015aff966a8255febeffbac7b04e923d278d2b02adce58","union_digest":"sha256:8a158b5cc4c8e6c3035dc272999af61ac6cb080af8c208eccc8d28e4105a7575","union_review_basis_digest":"sha256:f1fb6a15d1d93188ae50abc0ff76f6846723e71450f01173d76ea03be946212a","verification":{"matrix_tests_passed":297,"static_checks":"pass","vault_checks":"pass"}}
```

The accepted typed state binds the unchanged pre-receipt basis to `attestation.ledger.g0`, the exact one-element receipt identity set, and the external acceptance record:

| Acceptance field | Bound value |
| --- | --- |
| Attestation / digest | `attestation.ledger.g0` / `sha256:d0b8630c9e137efb3e308ed7f185623745ee4f15c573f9cbd154264ee33e34d7` |
| Reviewer / ruling | `primary-independent-review` / `ACCEPT` |
| Receipt-set digest | `sha256:c8db11ec579df4b3b0632d3fbc12d872c6d626523c32b317cb8bc7fdc3574eb4` |
| G0 receipt | `receipt.ledger.g0_denominator_and_ownership_freeze`; closure basis `sha256:dc2a1aa901e96941fdad4dbd4dbb1e770412681433203927f51d7361e068d815`; attestation digest `sha256:d0b8630c9e137efb3e308ed7f185623745ee4f15c573f9cbd154264ee33e34d7` |
| Accepted matrix digest | `sha256:6f4dcc03bbf6c8780affefb35546aaa47c3f883e83e6150ff5bb30aed6151f50` |
| External subject | `subject.ledger.acceptance_record.g0`; revision `g0-acceptance-2026-09-05`; locator `reference://clitui-ledger/g0-acceptance-record`; digest `sha256:0c3807c8c53259c97b4bd4ac923c3de5f216684910d9f0674f5ee526ffb9f64a` |
| External coordinate | `evidence.acceptance_record.g0_independent_review`; `review` / `independent_engineering_review`; all eight axes |

Live evaluation against the exact 693-row union, current census and source subject, and the exact external subject/anchor returns G0 `closed=true` with zero blockers. Omitting the anchor returns `closed=false`; changing the independently observed subject revision returns `closed=false` as stale. No G1, G2, G3, or G4 receipt is present. The active global and row-level TUI hold remains unchanged until accepted G3 closure.

'@
$marker = '#### Mandatory source-stream landscape'
if (-not $body.Contains($marker)) {
    throw "reference insertion marker is missing"
}
$body = $body.Replace($marker, $acceptance + "`n" + $marker)
$body = $body.TrimEnd("`r", "`n")

if ($body -eq ([regex]::Replace($raw, '\A---\n.*?\n---\n', '', [System.Text.RegularExpressions.RegexOptions]::Singleline))) {
    throw "reference body was not changed"
}

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$body | vaultspec-core vault edit 2026-09-04-clitui-ledger-reference --body-stdin --expected-blob-hash $blob
