---
tags:
  - '#exec'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-16-protected-browser-certificate-auth-plan]]"
---

# Run repository-wide quality Vault documentation packaging and CI-equivalent gates and resolve the formal audit

## Scope

- `.vault/audit/2026-07-16-protected-browser-certificate-auth-audit.md`
- `repository`

## Description

- Run the repository-wide quality, Vault, documentation, and CI-equivalent gates against the final architecture.
- Distinguish owner-surface failures from concurrent peer-campaign churn and report peer-owned signatures to their owners rather than patching their files.
- Repair the unowned repository-wide breakage the run exposed, and record what remains out of reach.
- Resolve the formal audit by writing a disposition for every finding still lacking one, then add a fresh-context honesty review of the whole campaign.

## Outcome

The certificate-auth surface is clean on every gate that reaches it. Product-tree pytest collection is error-free at 13,508 tests. The focused outbound auth and browser suites pass 208 tests with no skips, no xfails, and no synthetic browser implementations. Repository-wide lint passes, the outbound AEAT adapter tree is fully formatted, the registry verifies across all 73 modelos, the non-fixing full Vault check exits clean, and the test-framework ratchets for markers, skip/xfail, mock, monkeypatch, broad raises, bare except, and tautology drift all hold.

Two unowned repository-wide defects surfaced during the run and were repaired. The ruff 0.16.0 lock bump had reddened the style gate with six new violations across four developer tools and two source modules, which had been failing the per-push CI static job for every campaign. The quiet gate runner decoded subprocess output with the console codepage, so it raised on the first UTF-8 byte a tool emitted and reported a fabricated failure with no drift list; both its decode and encode sides are fixed, and the format gate now reports its real verdict.

One environment defect was found and cleared: a core dependency added the previous day was missing from the shared environment, so the entire modelo command group had silently degraded to the unavailable-command placeholder and the documentation gate could not build the CLI reference. The subtree recovered its 23 subcommands once the locked version was installed.

The import, type, generated-reference, and source-hygiene gates remain red on signatures owned entirely by two live peer campaigns. Those were reported to their owners. This Step therefore closes on the narrower, honest claim recorded in the audit rather than the plan's unqualified repository-wide green sentence.

## Notes

Fresh semantic and exact sweeps confirm the hard cut holds: no handshake, backend selector, context marker, or configurable verification target exists in source, and semantic search surfaces none of them. The vault decision search for certificate-authentication authority returns exactly the protected-browser record and the three auth decisions reconciled against it, so the active corpus is non-contradictory.

Four findings that the implementation Steps had closed in code carried no written disposition; each was re-verified against the source at this commit and now has one. The audit also gained a fresh-context honesty review covering the gate-run boundary, the two gates out of this feature's reach, the environment defect, a surviving duck-typed close that is a fail-closed assertion rather than a compatibility path, the live oracle's deliberate default-suite absence, and one unreproducible ratchet error traced to concurrent peer file churn.

The external live oracle remains the separate AEAT acceptance proof and is unchanged. No submission path exists or was added; the feature builds, validates, verifies, and exports only.
