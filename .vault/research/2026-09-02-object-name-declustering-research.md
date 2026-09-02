---
tags:
  - '#research'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:b260d3858d860463a24f192775eb6e573e1216216b3451afd89615451923b65a'
related:
  - "[[2026-09-02-object-name-audit-implementation-review-audit]]"
  - "[[2026-07-01-import-centralization-adr]]"
---
# `object-name-declustering` research: `safe declustering architecture`

The repository needs a repeatable way to turn object-name findings into small, reviewable rename operations without allowing one rename to pull unrelated modules into its diff. Evidence favors a manifest-driven planner over path-only grouping or a single similarity hash: use a typed operation-to-file graph to discover atomic batches, path and architecture metadata to assign ownership, separate hashes to identify findings and refuse stale inputs, and a disposable copy of the current dirty tree as the required execution rehearsal. Existing repository analyzers should supply the evidence; an ADR must decide the manifest contract and execution engine.

The requested completion condition is the stricter raw-zero result from
`audit-object-names`, not merely zero unadjudicated qualified-name conflicts. That
choice intentionally goes beyond the older collision policy and makes globally
repeated module stems and reviewed `distinct_by_design` symbols rename obligations.

## Findings

### Atomic batches are connected components of operations and touched surfaces, not directory clusters

Path proximity is useful for ownership and test selection, but it does not capture cross-layer imports, dynamic targets, generated references, or shared consumer files. Build a bipartite graph whose left nodes are proposed rename operations and right nodes are files or generated surfaces; add a hard edge whenever an operation must touch that surface. Connected components expose operations that cannot safely execute independently because they share a file. Annotate and deliberately cut components at ownership, architectural, and generator-authority boundaries.

A plain import graph remains useful for inbound reach, strongly connected components, and ordering, but weak components around shared hubs will be too large to serve as batches. Direct importer count, affected-file count, dynamic references, generated surfaces, and boundary crossings are more reviewable risk signals than PageRank. Grimp exposes import relations and NetworkX supplies component and condensation algorithms. https://grimp.readthedocs.io/en/stable/readme.html and https://networkx.org/documentation/stable/reference/algorithms/component.html

### Two hash families are needed; neither hash establishes semantic equivalence

Give a finding a stable identifier by hashing a canonical tuple of schema version, finding kind, object kind, old name, and sorted qualified sites. Separately record SHA-256 over every input file's bytes plus the canonical baseline inventory. The first survives unrelated line movement; the second refuses execution after concurrent edits. A naming-blind `ast.dump(..., include_attributes=False)` fingerprint can support duplicate review and before/after body-equivalence checks, but normalization can merge contextually distinct code. Raw and AST hashes are guards and evidence, not clustering authority. https://docs.python.org/3/library/ast.html

The need for byte preconditions was demonstrated during this research: the live tree changed from 61,497 to 61,594 declarations while the enforced total remained 781, and advisory findings changed from 1,522 to 1,526. A durable plan cannot rely on line numbers or an old whole-tree count alone.

### The reviewed manifest is the authority between discovery and execution

Each operation should state an operation ID, finding ID, old qualified locator and path, proposed target and path, disposition (`lexical-singular`, `rename-distinct`, `merge-authority`, or `keep-distinct`), owner, rationale, source byte hashes, advisory AST fingerprint, expected reference classes, exact moves, changed-path allowlist, generator commands, focused gates, and lifecycle status. Planning must reject duplicate or already-claimed targets, stale hashes, ambiguous ownership, unresolved dynamic references, and any merge without a substitutability decision.

The manifest should be authored intent, using the bidirectional and no-stale-row discipline in `dev/quality/name_collision_dispositions.toml:1`; inventories and rehearsal receipts remain generated evidence. Current object-name JSON lacks full declarations, stable IDs, import reach, ownership, and hashes (`dev/audit/object_names.py:336`).

### Existing repository analyzers compose into the planner but none is the whole solution

`dev/audit/object_names.py:277` owns exact collision and lexical-singularity findings. `dev/audit/semantic_duplication.py:1` treats fingerprints as candidates and provides enum, literal, call, derivation, field, import, and package overlap evidence. `dev/audit/duplication.py` wraps jscpd for token clones. `dev/quality/import_hygiene_scan.py:2189` detects dangling imports and later families inspect dynamic strings, shims, wrappers, and multi-sourced symbols. These should feed typed evidence edges and postconditions, not be reimplemented in a parallel scanner.

jscpd emits token-clone JSON and SARIF, so it is useful for copy/paste evidence but not architectural ownership or semantic equivalence. https://github.com/kucherenko/jscpd/blob/master/apps/jscpd/README.md

### Rope is an experiment, LibCST is a controlled fallback, and neither replaces the manifest

Rope 1.14.0 supports symbol and module rename, import updates, and change-set preview. It is the closest purpose-built Python refactoring engine found. Its published compatibility lists Python through 3.12 while Cadrumo requires Python 3.13, so it must pass isolated detector-teeth probes and operate only in rehearsal. Its string/comment and "rename when unsure" modes are too broad. https://rope.readthedocs.io/en/latest/library.html, https://rope.readthedocs.io/en/latest/overview.html, and https://pypi.org/project/rope/

LibCST provides formatting-preserving codemods, scope and qualified-name metadata, multi-pass transforms, and unified diffs. It fits repository-specific transformations Rope cannot prove, but does not discover configs, arbitrary dynamic strings, or generator ownership. Use sequential execution on Windows unless parallel support is proven. https://libcst.readthedocs.io/en/latest/codemods.html and https://libcst.readthedocs.io/en/latest/metadata.html

ast-grep and Semgrep offer structured rewrites, but pattern matches are not symbol resolution. Keep them for narrow syntax migrations or residue screens. https://ast-grep.github.io/guide/rewrite-code

### Rehearsal receipts make the safety net mechanically enforceable

The lifecycle should be `inventory` -> `plan` -> `rehearse` -> `apply` -> `verify`. Planning performs no writes and renders the graph, risks, and rejected operations. Rehearsal copies the current dirty tree, including untracked work but excluding `.git` and caches, into a verified system-temporary directory; it applies the exact manifest, compares actual paths with the allowlist, and runs object-name delta, residue, parsing/import, boundary, focused-test, type, lint, generator, and duplication non-regression checks.

The receipt binds manifest digest, baseline and file digests, tool versions, changed-path digest, finding delta, and gate outcomes. Live apply refuses unless preconditions still match, then replays the same operations and gates. No cleanup, shim, alias, facade, or fallback is permitted. This implements `2026-07-01-import-centralization-adr` and `2026-09-02-object-name-audit-implementation-review-audit`.

### Semantic consolidation should remain a related but separate lane

Exact-name collision is not proof of interchangeability, and different names can hide overlapping behavior. Lexical declustering should consume semantic fingerprints as review evidence and run semantic/jscpd checks as non-regression gates, but it should not automatically merge modules. A merge requires constraint-superset and canonical-owner adjudication. The ADR should decide whether `merge-authority` is prohibited from lexical batches or routed to a separately approved semantic-consolidation plan; evidence favors separation.

### Raw-zero global uniqueness is intentionally stricter than existing policy

The current scanner groups by bare name across `src` and `dev`
(`dev/audit/object_names.py:282`). Existing policy instead permits cross-layer
restatement and records `extract_pages_text`, `review_view`, and
`active_profile_label` as `distinct_by_design`
(`dev/quality/name_collision_dispositions.toml:12-14,93-139`). The accepted import
decision requires exact defining-module imports but does not require repository-global
leaf-stem uniqueness (`.vault/adr/2026-07-01-import-centralization-adr.md:23-31`). The
operator's raw-zero objective therefore cannot be achieved by preserving those older
allowances or reclassifying findings; the ADR must explicitly authorize semantic
renames even where qualified imports are already unambiguous.

The 2026-09-02 live census measured 781 enforced findings: 189 duplicate-name groups
and 592 plural-name candidates. Of the duplicate groups, 69 are module-only and 54 mix
functions with modules. Plural findings comprise 429 modules, 158 classes, and five
functions. One `errors` cluster spans 68 modules, `conftest` spans 34, and `models`
spans 22. A declaration can participate in both a duplicate and plural finding, so the
finding total is not an operation count; the manifest must derive connected rename
components from qualified sites before scheduling work.

## Sources

- `dev/audit/object_names.py:277`
- `dev/audit/object_names.py:336`
- `dev/audit/semantic_duplication.py:1`
- `dev/audit/semantic_duplication.py:253`
- `dev/audit/semantic_duplication.py:374`
- `dev/audit/semantic_duplication.py:408`
- `dev/quality/import_hygiene_scan.py:2189`
- `dev/quality/name_collision_dispositions.toml:1`
- `dev/quality/name_collision_dispositions.toml:12-14`
- `dev/quality/name_collision_dispositions.toml:93-139`
- `dev/quality/namespace_retirement_sweep.py:1`
- `pyproject.toml:353`
- `uv.lock:1998`
- `.vault/adr/2026-07-01-import-centralization-adr.md:23-31`
- https://rope.readthedocs.io/en/latest/library.html
- https://rope.readthedocs.io/en/latest/overview.html
- https://pypi.org/project/rope/
- https://libcst.readthedocs.io/en/latest/codemods.html
- https://libcst.readthedocs.io/en/latest/metadata.html
- https://grimp.readthedocs.io/en/stable/readme.html
- https://networkx.org/documentation/stable/reference/algorithms/component.html
- https://github.com/kucherenko/jscpd/blob/master/apps/jscpd/README.md
- https://ast-grep.github.io/guide/rewrite-code
- https://docs.python.org/3/library/ast.html
