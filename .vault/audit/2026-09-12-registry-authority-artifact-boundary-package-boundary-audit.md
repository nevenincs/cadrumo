---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:92e9602426c1b02a5c62ccf467b3eff3119862645b785ca7269dd35e371279a6'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# `registry-authority-artifact-boundary` audit: `package boundary`

## Scope

This review covers the `W03.P04.S05` distribution boundary: Hatch selection for
the wheel and source distribution, exclusion of mutable registry authoring
inputs, retention of the published digest-verified authority artifact, and the
executable gates that rebuild and inspect both distribution paths. The review
also tests whether the archive policy can detect future package-root widening
independently of the mutable build declaration.

## Findings

### package-allowlist-gate | high | The archive allowlist follows the declaration it is meant to constrain

`test_distributions_ship_only_the_product_package` derives the accepted wheel roots from `wheel.packages` and the accepted source-distribution roots from `sdist.only-include`. A packaging change can therefore add a non-product package or source root and expand the test oracle in the same edit, while any added path below the already accepted `src` root is accepted without even changing that root set. The real wheel and source-distribution builds are clean today, and the dedicated registry assertions independently reject the known `registry/aeat` tree, but this generic gate does not enforce its stated closed runtime-product boundary or demonstrate detector teeth against policy widening. Keep backend-conformance checks separate from an independent fixed policy allowlist, and prove a representative extra package or source subtree is rejected.

### artifact-integrity-terminology | medium | Distribution diagnostics claim cryptographic authenticity that is not provided

The wheel and source-distribution assertions describe the published authority as "signed", and the wheel configuration says its evidence projection is "authenticated". The accepted contract deliberately rejected repository-held signing and provides a schema-versioned integrity digest, which detects inconsistent bytes but does not establish signer authenticity. These messages therefore overstate the security property operators and reviewers can infer from a successful build. Describe the asset as the published digest-verified authority artifact and reserve signing or authentication terminology for a future contract with a distinct trust boundary.

### sdist-rebuild-proof | medium | The source-distribution assertion never builds the downstream wheel it claims to protect

`test_sdist_keeps_only_published_registry_payload` stops after inspecting members of the source archive. It proves that the published authority is present and the authored registry tree is absent, but it does not prove that the new deny-by-default source selection retained every input Hatch needs to build a wheel from that archive or that the rebuilt wheel preserves the same authority-only boundary. A reviewer reconstruction from the current source distribution succeeds, so this is a release-gate coverage defect rather than evidence of a presently broken archive; make the test build from its produced source distribution and assert the published artifact, authored-tree absence, and required runtime payload on that resulting wheel.

### sdist-rebuild-proof-reaudit | medium | Closed by the real source-distribution-to-wheel gate

The source-distribution fixture now feeds the produced archive back to `uv build --wheel`, and the resulting wheel is checked for the digest-verified authority artifact, absence of the authored registry tree, required data roots, and required functional members. The complete package-boundary file passes with nine tests, including that real rebuild, so the original source-distribution reconstruction finding is closed.

### package-allowlist-gate-reaudit | high | Partially remediated; prefixed wheel roots still bypass the fixed allowlist

The policy oracle is now independent of `pyproject.toml`, and the new detector proves an unrelated package root is rejected. The wheel root normalizer still partitions every top-level name at the first hyphen, however, so `_unexpected_wheel_members` accepts `cadrumo-rogue/payload.txt` as though it belonged to `cadrumo`; a live synthetic call returns an empty offender list. Restrict the version normalization to the generated `cadrumo-*.dist-info` metadata directory and compare every other top-level member exactly before closing the original high finding.

### artifact-integrity-terminology-reaudit | medium | Closed by digest-accurate package language

The reviewed build comment, test descriptions, and failure diagnostics now consistently describe the authority as `digest-verified`; the package-boundary surfaces no longer claim that the unsigned artifact is signed or authenticated. This closes the original terminology finding and aligns the distribution contract with the accepted integrity-only design.

### package-allowlist-gate-final-reaudit | high | Closed by exact non-metadata root handling

The wheel normalizer now strips the version only when the archive root ends in `.dist-info`; every other root is compared whole against the fixed product-package allowlist. The detector-teeth test now includes `cadrumo-rogue/payload.txt` alongside unrelated wheel and source roots, and the focused detector passes. Together with the earlier nine-test direct-wheel, source-distribution, and rebuilt-wheel run, this closes the original allowlist finding and its partial re-audit. No high or critical package-boundary finding remains.

### package-allowlist-gate-dist-info-reaudit | high | Arbitrary metadata roots still bypass the fixed wheel allowlist

The non-metadata prefix bypass is closed and the focused detector plus real-distribution tests pass with two tests. The remaining branch still strips every root ending in `.dist-info` at its first hyphen without verifying the distribution identity or version, so `_unexpected_wheel_members` accepts `cadrumo-rogue.dist-info/payload.txt` and a stale `cadrumo-9.9.9.dist-info/METADATA` tree as current-product metadata. Match the one canonical metadata root for the built distribution and add that adversarial detector before treating the fixed archive policy as closed; the original high finding therefore remains unresolved.

### package-allowlist-gate-exact-metadata-final | high | Closed by exact current-version metadata policy and adversarial proof

The wheel root helper now returns the exact top-level name, and the fixed allowlist admits only `cadrumo`, `cadrumo_harness`, and the `cadrumo-{project.version}.dist-info` directory. Detector cases reject a non-metadata prefix, a rogue metadata root, and a stale-version metadata root; live probes return each path as an offender. The complete direct-wheel, source-distribution, and source-distribution-built-wheel suite passes with nine tests, and Ruff, formatting, and diff checks are clean. This closes the original high finding and every later refinement; no unresolved high or critical package-boundary finding remains.

## Recommendations

Keep the fixed product-root policy independent from Hatch declarations and
retain the explicit rogue-package, rogue-metadata, and stale-version detector
cases that close `package-allowlist-gate`. Continue describing the authority as
digest-verified, not signed or authenticated, as established by
`artifact-integrity-terminology`. Preserve the real source-distribution-to-wheel
rebuild gate and its required-payload and authored-source isolation assertions,
which close `sdist-rebuild-proof`. No follow-on ADR is required because the
remediation implements the accepted artifact-boundary decision without changing
its trust model.
