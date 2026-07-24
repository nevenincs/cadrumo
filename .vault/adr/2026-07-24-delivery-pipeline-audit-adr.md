---
tags:
  - '#adr'
  - '#delivery-pipeline-audit'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - "[[2026-07-24-delivery-pipeline-audit-audit]]"
---

# `delivery-pipeline-audit` adr: `delivery pipeline dead-weight rulings` | (**status:** `accepted`)

## Problem Statement

The delivery-pipeline audit (cited by stem `2026-07-24-delivery-pipeline-audit-audit`)
closed its fix wave with four deferred decisions and three robustness follow-ups. The
operator mandate is a clean, conformant, compatible, robust delivery infrastructure
with zero deprecated or dead weight: every retained surface needs a charter, every
duplicated fact needs a single authority, and every deferred hardening needs a decided
mechanism. This record rules on all seven items in one operator-approved architecture
session so an implementer can execute without re-deriving.

## Considerations

- `publish-release.yml` is the sole publication authority per the accepted
  distribution-installation-readiness decision (stem
  `2026-07-15-distribution-installation-readiness-adr`); its Gate 3 publishes all
  three distributions to PyPI via OIDC Trusted Publishing behind the `release`
  environment and `CADRUMO_PUBLISH_ENABLED`.
- `pypi-upload.yml` was operator-ordered as a fast-follow to the v0.2.1 direct
  promotion (2026-07-21) and was hardened, not retired, in the audit fix wave. It is
  the only route that can deliver the still-owed v0.2.1 PyPI leg without re-running
  the whole readiness train, which the audit shows is currently blocked (pre-campaign
  oracle captures refuse re-emission; the Scoop lane is structurally blocked).
- PyPI Trusted Publishing registrations bind to a workflow filename plus environment.
  `pypi-upload.yml` uses per-package environments (`pypi`, `pypi-data-manuals`,
  `pypi-data-official`); `publish-release.yml` Gate 3 uses `release` and its header
  instructs the operator to register Trusted Publishing per package. The two routes
  therefore need distinct operator-side registrations; deleting the fast-follow before
  Gate 3's registrations are proven live would strand the PyPI route.
- The no-legacy discipline mandates deleting superseded surfaces and forbids "just in
  case" retention without a charter; it equally forbids deleting the only working
  route to an owed obligation.
- `dev/packaging/sync_aeat_record_design_corpus.py` is registry-corpus acquisition
  tooling; its sole consumer is
  `src/cadrumo/_data/corpus/tests/test_record_design_support.py`. Its packaging
  filing is an accident of history. `dev/packaging/extract_manual_corpus_text.py` is
  the same class of corpus tooling with a wider consumer set (justfile recipes,
  registry sidecar-freshness gates, prod comments).
- The three PyPI distributions ship as one exact-version pinned cohort: `cadrumo`
  declares both data companions as mandatory runtime dependencies. Root pyproject
  declares `Development Status :: 4 - Beta`; both companions declare `3 - Alpha`.
- Product identity is centrally owned by `src/cadrumo/core/product_identity.py`
  (`PRODUCT_IDENTITY`), per the cadrumo-product-authority-names rule and the accepted
  product-rename decision (stem `2026-07-13-product-rename-adr`). The plugin and
  marketplace manifests already derive their author/owner as
  `f"{PRODUCT_IDENTITY.display_name} tax assistant project"` in
  `src/cadrumo/agent/_workspace.py`, while `packaging/mcpb/manifest.json` carries the
  hand literal `"Cadrumo project (neve.md)"`.
- The root pyproject `authors` field names "Gergely Wootsch" — a PEP 621 legal-person
  fact (the copyright holder under the Apache-2.0 licence), a different referent from
  the product identity.
- The constrained-install closure fix (audit finding unpinned-user-install-closure)
  ships `dev/packaging/uv_constraints.py` lock exports into the Scoop constraints
  file and the MCPB `[tool.uv] constraint-dependencies` block, but no lane yet
  observes the installed result; the MCPB first-launch bootstrap in
  `packaging/mcpb/build.py` runs whatever `uv` the user's machine resolves, with no
  version floor for the constraint-dependencies mechanism.
- The real-client secret scan in `dev/packaging/emit_real_client_evidence.py` walks
  string values only (`_iter_strings` skips dict keys), so a secret-shaped or
  email-bearing key ships unscanned.

## Considered options

1. **D1 retire `pypi-upload.yml` now.** Rejected: strands the owed v0.2.1 PyPI leg
   and possibly the only live Trusted Publishing registrations while the readiness
   train is blocked.
2. **D1 keep `pypi-upload.yml` with a standing charter.** Rejected: a permanent
   second publication authority contradicts the sole-authority ruling; "hardened"
   does not convert duplicate authority into a charter.
3. **D1 retire-after-arming with a tracked trigger.** Chosen: a narrow written
   charter now, deletion bound to the first successful Gate 3 PyPI publication.
4. **D2 leave the corpus sync script in `dev/packaging/`.** Rejected: packaging is
   the delivery surface; corpus acquisition is registry-data maintenance, and the
   misfiling already misled one audit lane.
5. **D2 move to `dev/registry/`.** Rejected: `dev/registry/` owns modelo-authoring
   tooling (matrix, newmodelo), not corpus byte acquisition.
6. **D2 create `dev/corpus/` as the canonical corpus-tooling home.** Chosen.
7. **D3 downgrade the root to Alpha.** Rejected: the root's Beta claim postdates the
   promotion machinery and matches the released posture.
8. **D3 align all three to the root's `4 - Beta`.** Chosen: one cohort, one posture.
9. **D4 keep the hand-authored MCPB author literal.** Rejected: hand literals drift
   from the identity authority — the drift is already observable.
10. **D4 derive shipped-manifest author identity from `PRODUCT_IDENTITY`.** Chosen,
    with the pyproject `authors` legal-person fact explicitly preserved as a distinct
    referent.

## Constraints

- Gate 3's PyPI leg cannot be proven until the operator completes the Trusted
  Publishing registrations and the readiness train unblocks (oracle re-runs, Scoop
  container-mode window); the D1 retirement trigger is therefore operator-paced and
  must be tracked, not scheduled.
- Any relocation must follow the atomic-relocation discipline: one explicit-path
  commit carrying the canonical-site move, every consumer, and a clean
  `pytest --collect-only -q`, with a `relocation:<symbol>` commit subject.
- The MCPB manifest is a committed template validated by `load_manifest`; author
  derivation must therefore be enforced both at stamp time and by the `--check`
  drift gate, or the committed literal silently survives.
- The minimum-uv floor for `[tool.uv] constraint-dependencies` must be taken from
  the uv changelog at implementation time, not guessed; the floor is a declared
  constant, not prose.

## Implementation

**D1 — `pypi-upload.yml`: retire-after-arming with a tracked trigger.** The workflow
survives under a narrow written charter, stated in its header comment: it exists
solely to deliver Python distributions of already-published `v*` releases whose
promotion predates an armed Gate 3 PyPI leg (concretely the owed v0.2.1
fast-follow), and it is deleted — workflow file, its conformance test, and its three
PyPI Trusted Publishing registrations — upon the first successful
`publish-release.yml` Gate 3 PyPI publication. The trigger is tracked as a GitHub
issue titled to name the deletion, referencing this record; the charter comment in
the workflow names the same issue. No new capability may be added to the workflow in
the interim. Until deletion it stays behind `CADRUMO_PUBLISH_ENABLED` exactly as
hardened.

**D2 — `dev/corpus/` is the canonical home for corpus acquisition and extraction
tooling.** `dev/packaging/sync_aeat_record_design_corpus.py` relocates to
`dev/corpus/sync_aeat_record_design_corpus.py` in one atomic explicit-path commit
(`relocation:sync_aeat_record_design_corpus`): the module move, the new package
`__init__.py`, the consumer import in
`src/cadrumo/_data/corpus/tests/test_record_design_support.py`, and any self-naming
strings inside the module, with `uv run --no-sync pytest --collect-only -q` observed
clean immediately before the commit. `dev/packaging/extract_manual_corpus_text.py`
is enrolled under the same home as a follow-up second atomic relocation commit
(`relocation:extract_manual_corpus_text`) sweeping its wider consumer set: the two
justfile recipes, the sidecar-freshness tests under `src/cadrumo/_data/corpus/tests/`
and `src/cadrumo/domain/calculations/registry/tests/`, the self-referencing
instructive strings, and the path comments in `_validate_evidence.py` and
`pyproject.toml`. After each move, `python -m dev.docs.apidocs scaffold --check` is
not implicated (dev/ modules are unstubbed) but the collect-only gate is mandatory.

**D3 — one cohort, one development-status posture: `Development Status :: 4 - Beta`
on all three distributions.** The two companion pyprojects
(`packaging/cadrumo_data_manuals/pyproject.toml`,
`packaging/cadrumo_data_official/pyproject.toml`) change `3 - Alpha` to `4 - Beta`.
A conformance test in `dev/packaging/tests/` reads the three pyprojects and asserts
the `Development Status` classifier is identical across them, so the next posture
change is a one-fact edit plus gate, never a silent fork. Future posture promotions
edit the root and let the gate force the companions in the same commit.

**D4 — shipped-manifest author identity derives from `PRODUCT_IDENTITY`; the
pyproject legal author is a distinct preserved fact.** The single product
author-identity string is `f"{PRODUCT_IDENTITY.display_name} tax assistant project"`
("CADRUMO tax assistant project"), already used by the plugin and marketplace
manifests. `packaging/mcpb/manifest.json` corrects its committed `author.name` to
that value; `packaging/mcpb/build.py` enforces it twice — `stamped_manifest` stamps
`author.name` from the derived value, and `load_manifest` (the `--check` template
gate) refuses a committed template whose author diverges. The derived string is
promoted to one shared constant (natural home: alongside the existing
`_PLUGIN_AUTHOR_NAME` derivation, exposed through the owning package facade) so the
plugin, marketplace, and MCPB surfaces read one declaration.
`verify_distribution_identity.py` gains a product check asserting the MCPB
manifest's author equals the derived value. The root pyproject `authors` entry
"Gergely Wootsch" is ruled a distinct correct fact — the PEP 621 legal
author/copyright holder under Apache-2.0 — and stays; it is never rewritten to the
product identity, and the product identity is never written into `authors`.

**F1 — install-time constraint-effect assertion.** A shared helper
`dev/packaging/constraint_effect.py` exposes
`assert_installed_matches_constraints(python_exe, constraint_lines)`: it invokes the
installed environment's interpreter to enumerate installed distributions
(`importlib.metadata` via a `-c` one-liner, avoiding a pip dependency), parses the
name-version set, and asserts that every distribution named in the
`uv_constraints.py` lock export is installed at exactly the pinned version —
fail-closed with an enumerated name/expected/actual diff. The Scoop smoke lane
(`smoke_scoop.ps1` calling into the installed python) and the MCPB client-install
lane (`packaging/mcpb/tests/test_client_install.py` / `smoke_mcpb.py`) call it after
install and before the tax oracle, so the acquisition evidence rows can only mint on
a lock-exact closure. Unit tests feed a synthetic installed set with one drifted
version and assert the refusal names it.

**F2 — minimum-uv guard for the MCPB constraint-dependencies mechanism.** The
bootstrap template in `packaging/mcpb/build.py` gains a declared constant
`_MIN_UV_VERSION` set to the oldest uv release whose `uv sync` honours
`[tool.uv] constraint-dependencies` (verified against the uv changelog at
implementation time). `_provision()` runs `uv --version` before `uv sync`, parses
the version, and refuses first-launch provisioning below the floor with an
instructive upgrade message naming the floor and the reason (the pinned dependency
closure would silently not apply). The floor is also stated in the generated
bundle's `constraints.txt` header comment for transparency. A build test asserts the
generated bootstrap source carries the guard and that the constant parses as a
version triple.

**F3 — real-client secret scan covers dict keys.** `_iter_strings` in
`dev/packaging/emit_real_client_evidence.py` additionally yields every dict key
(keys in session JSON are strings), so `assert_session_carries_no_secret` applies
the token-length and email refusals to keys and values uniformly; its docstring
drops the values-only caveat. A test feeds a session whose only secret-shaped
content is a dict key (and another whose key contains an email) and asserts the
mint refuses both.

## Rationale

D1 resolves the tension between the no-dead-weight mandate and the owed obligation
by making retention conditional and observable: the charter names the one job, the
trigger is the exact event that proves the successor route live (a successful Gate 3
PyPI publication proves both the Trusted Publishing registrations and the
environment exist), and the tracked issue makes the deletion an inventory item
rather than a memory. D2 files tooling by what it maintains, not by which campaign
authored it — the corpus scripts maintain registry-grounded corpus bytes, and a
`dev/corpus/` home ends the recurring mis-classification the audit hit. D3 follows
from the cohort being one product: exact-version mandatory dependencies make the
companions' maturity claim inseparable from the root's, and the root's Beta is the
deliberate, current claim. D4 applies the existing identity-authority rule to the
one shipped manifest that predates it; the dual enforcement (stamp plus template
gate) is required because the manifest is committed, and the legal-author ruling
prevents the opposite failure of laundering a person into a product string. F1–F3
each convert an audit-noted honesty gap into a fail-closed gate at the exact
boundary the gap lives on: the installed closure, the first-launch resolver, and the
published evidence row.

## Consequences

- The PyPI route stays continuously available through the v0.2.1 fast-follow window,
  and the second authority has a guaranteed, evidenced end of life; until the
  trigger fires, two gated workflows coexist under one written charter.
- `dev/corpus/` becomes a real package; two atomic relocation commits touch a wide
  consumer set (justfile, registry gates) and must land under the relocation
  discipline or not at all.
- The companions' PyPI pages claim Beta; any future posture change is a single-fact
  edit guarded by a cross-pyproject conformance gate.
- Author identity gains a third derivation site and a template drift gate; the
  committed MCPB manifest can no longer silently diverge from `PRODUCT_IDENTITY`.
- Acquisition evidence rows become strictly harder to mint (lock-exact closure
  required), which is the point: an upstream release after cohort testing now fails
  the smoke lane instead of shipping an untested closure.
- First-launch MCPB users on an old uv get an instructive refusal instead of a
  silently unconstrained environment.
- The secret scan's residual key gap closes; the scan remains heuristic (length and
  email shaped), which is accepted for a hand-curated session summary.
