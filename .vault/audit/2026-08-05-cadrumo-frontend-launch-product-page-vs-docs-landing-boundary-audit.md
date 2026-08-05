---
tags:
  - '#audit'
  - '#cadrumo-frontend-launch'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:967afc717688d62f0674b29149a99b403b179ccd2866b6e01e635c3920d282c6'
related:
  - "[[2026-07-12-cadrumo-frontend-launch-audit]]"
---

# `cadrumo-frontend-launch` audit: `product page vs documentation landing boundary reconciliation`

## Scope

The operator flagged a suspected repository-boundary violation, in these terms:
the landing page belongs to a separate repository; the documentation page is not
the front end; there is a product page (the front end) and a comprehensive
documentation landing, and what this project delivers is the latter, not the
overall project page.

This audit treats that as a claim to verify rather than a premise to act on. It
covers the `frontend/` tree at the repository root, the two publishers
`dev/deploy/frontend_static_site.py` and `dev/deploy/docs_static_site.py`, their
justfile recipes, the deploy test surface, and the external repository inventory
on the publishing account. Analysis only: nothing was deleted, moved, or
published.

Not examined: the live S3 bucket and CloudFront distribution state (no AWS
session was opened, so every destination claim below is read from source
expressions, not from the deployed objects); the rendered page as served at the
canonical domain; the `infra/docs-static-site.yaml` CloudFormation template
beyond its role as the single stack both publishers target; and the contents of
`frontend/dist/` and `frontend/node_modules/`, which are gitignored build
output.

## Findings

### artefact-identity | high | `frontend/` is the product page, and it is correctly named

The tree is the product page in the operator's own vocabulary, not a
documentation landing under a misleading name. The evidence is the copy itself.
The working copy at `frontend/copy/cadrumo-landing-copy.md` opens with the hero
"A LOCAL TAX ENGINE FOR PEOPLE AND AGENTS", then "Calculate with rules. Work
with an agent. The engine calculates. The LLM helps you operate and understand."
It continues through a "How it works" section naming the CLI engine, the MCP
surface, and scoped agents; a "Claude plugin" section; a "Benefits" section
("Repeat each calculation", "Stay in control", "Understand the process"); and a
disclaimer stating the product is independent, does not represent a public
authority, does not file declarations, and does not provide advice. The document
title in `frontend/index.html` is "Cadrumo - Tax calculation engine, assisted by
agents", and its description calls the product "an AEAT-compatible Spanish tax
calculation toolset for you and AI agents".

None of that is documentation. It is positioning, capability framing, and legal
disclaimer: product-page content by every ordinary reading.

The relationship to the documentation is the decisive structural signal. The
page does not contain the docs; it *points at* them. `frontend/src/App.tsx`
declares `const docsBaseUrl = 'https://cadrumo.neve.md/docs'` and renders a
dedicated call-to-action section keyed `docs-cta` whose links route outward to
that base. The product page fronts the documentation as a separate destination,
which is exactly the two-artefact split the operator described, already built.

The repository's own documentation uses the same vocabulary independently:
`docs/index.md` sends the reader to the site root under the link text "product
page". The docs already call the root the product page and themselves the
documentation. Both artefacts already agree with the operator's distinction.

### cross-repo-contention | high | No second repository publishes to the shared root; the contention hazard is not real

This was the highest-priority hazard and it does not exist. The account carries
exactly one repository that could plausibly own a landing page,
`nevenincs/aeat-marketing`, private and last pushed 2026-07-21. It has a single
commit, subject "init: aeat-marketing with cadrumo as 'aeat' submodule pinned to
current main tip"; a reported size of 0; a top level of exactly `.gitmodules`,
`README.md`, and `aeat`; and no `.github/workflows` directory at all (the API
returns 404 for that path). There is no build step, no deploy job, and no
credential surface. It cannot publish anything.

What it actually is, is a consumer of this repository. Its `.gitmodules` reads
`url = https://github.com/nevenincs/cadrumo.git`, and its README states the
arrangement in terms that settle the ownership question outright: "The product
source is never copied into this repository" and "The marketing site frontend
lives inside the submodule at `aeat/frontend/`. Serve it from there; this
repository carries no stale product-source copy."

The separate repository therefore does not own the landing page. It deliberately
declines to own it, points a submodule at this repository, and instructs the
reader to serve the page from here. `frontend/` in this repository is the
canonical source, and the marketing repository is a downstream workspace wrapper
pinned to it. Two repositories publishing to one bucket root, each unaware of the
other, is a genuine and serious failure mode in the abstract; it is not this
repository's situation.

### deploy-boundary | medium | The docs-versus-landing guard is real code in both directions, not merely an asserted comment

The comment in `dev/deploy/frontend_static_site.py` claiming the landing sync
must never touch the documentation prefix was checked against the mechanism, in
line with the recurring defect where prose asserts a property the code lacks.
Here the code backs the prose, and it does so on both sides.

The landing publisher declares `_PROTECTED_PREFIX_EXCLUDES = ("docs/*",)` and
threads it into every sync pass. `_sync_site` computes `destination =
f"s3://{bucket}/"`, builds `protected` from that tuple as `--exclude` pairs, and
passes it into both passes: pass one for mutable page documents (additionally
excluding `assets/*`) and pass two for content-hashed assets. Neither pass can
reach `docs/`. A second, independent check lives in `_sync_pass`, which on a dry
run raises `SystemExit("Root sync dry run would mutate protected docs/* objects.")`
when the destination's `docs/` prefix appears in the command output. That is
belt-and-braces: a filter plus an observation of what the filter actually did.

The reverse direction is protected by construction rather than by exclusion. The
docs publisher's `_sync_site` sets `destination = f"s3://{bucket}/docs/"` — a
scoped destination that cannot reach the root regardless of filters, with the
docstring "Synchronise only the generated documentation prefix." The two
publishers write to disjoint prefixes of one bucket, one by scoping and one by
exclusion, and the exclusion side is additionally asserted at dry-run time.

The `2026-07-12` close-honesty review recorded that this publisher had zero
tests while writing to the shared bucket with `--delete`. That finding is closed:
`dev/deploy/tests/test_frontend_static_site.py` now exists and includes
`test_docs_prefix_is_always_excluded_from_the_root_sync`, which asserts `"docs/*"
in _PROTECTED_PREFIX_EXCLUDES`. The test pins the constant rather than exercising
a sync, so it would catch the constant being emptied but not a call site that
forgot to thread `protected` through; that is a narrower guarantee than the
mechanism deserves, but the mechanism itself is sound.

### premise-reconciliation | medium | The operator's premise is half-true, and the true half is a labelling conflation, not a boundary violation

Taken clause by clause against the evidence: "there is a product page, which I
call the front end" holds, and it is `frontend/`. "The documentation page is not
the front end" holds, and the separation is already implemented as two artefacts,
two publishers, and two prefixes. "The landing page is a separate repository"
does not hold in the sense that matters — a separate marketing repository exists,
but the landing page is not in it, and that repository's own README says so. "The
comprehensive documentation landing is what this project delivers, not the
overall project page" is the one clause the shipped system contradicts: this
repository delivers both, by design and with guards.

The operator's instinct that something is conflated is nonetheless correct; it
is simply not conflated where the premise located it. The conflation is in the
labelling and the code structure, not in the destinations or the ownership.
First, `justfile` groups the landing recipe under documentation: the recipe
`frontend-deploy` carries `[group('docs')]`, filing the product-page publish
under the docs menu alongside `docs-deploy` and `docs-stack-deploy`. Second, and
more substantively, `dev/deploy/frontend_static_site.py` imports thirteen private
underscore-prefixed symbols from `dev.deploy.docs_static_site` — among them
`_aws_base_command`, `_stack_target`, `_run`, `_repo_root`, `_published_body`,
and `_verify_distribution_alias` — plus the shared constants. The product-page
publisher is thereby implemented as a client of the documentation publisher's
internals. The artefacts are properly separated at the destination; the code that
publishes them is not separated at all, and the menu says they are the same
category of thing.

That is what an observer reading the justfile or the import block would perceive
as a boundary violation, and the perception is fair even though the deployed
result is correct.

### removal-blast-radius | high | Removing `frontend/` would break the consuming repository and delete the only source of the published root

Mapped for completeness, and as the evidence against acting on the removal
reading. The tree is 64 tracked files (build output is gitignored via
`/frontend/node_modules/`, `/frontend/dist/`, `/frontend/build/`,
`/frontend/output/`, and `/frontend/*.tsbuildinfo`). Removal would touch, at
minimum: the `frontend/` tree itself including `index.html`, `src/`, the
self-hosted font set and `public/` artefacts, `copy/`, `package.json`,
`package-lock.json`, `vite.config.ts`, `tsconfig.json`, and
`THIRD_PARTY_NOTICES.md`; the 335-line publisher `dev/deploy/frontend_static_site.py`;
the `frontend-deploy` justfile recipe; `dev/deploy/tests/test_frontend_static_site.py`
in full, plus the frontend-touching portions of `test_published_delivery_content.py`
and `test_publish_authority.py`; the six gitignore entries; and the npm toolchain
dependency in the developer environment.

Three consequences make the removal net-negative as things stand. The published
root at the canonical domain has no other source in any repository on the
account, so removing the tree removes the only thing that can rebuild the live
product page. The marketing repository's submodule pin and its explicit
instruction to serve the frontend from `aeat/frontend/` would both dangle. And
the licence surface in `frontend/THIRD_PARTY_NOTICES.md` covers the self-hosted
fonts and bundled dependencies that the page ships; retiring it needs the page
retired first, not concurrently.

Publication is currently held behind two structural blockers, which raises the
bar on any change to a live publish path. A removal is the largest possible such
change and is not warranted by the evidence gathered here.

### drift-detectability | medium | Nothing would detect a second publisher appearing at the shared root

The guards are strong within this repository and absent across repositories. Both
publishers verify delivery after publishing — the landing publisher's
`_verify_published_landing_page` fetches the served root and requires it to
reference the hashed bundle names this build produced, which is a genuinely good
check that catches stale caches and blank pages. But it runs only when this
repository publishes. If another producer overwrote the root between two of this
repository's publishes, nothing here would notice; the next publish would simply
overwrite it back, and the two would alternate silently.

Today that is a hypothetical, because no second producer exists. It is worth
recording as the condition that must stay true, because the property protecting
the root is currently "no one else has a deploy path", which is a fact about the
world rather than a guarantee enforced anywhere.

## Recommendations

Do not remove `frontend/`. The premise that motivated the question does not
survive contact with the evidence: the tree is the product page, this repository
is its canonical and only source, and the separate marketing repository is a
downstream consumer that explicitly declines to carry a copy. Acting on the
removal reading would delete the only source of the live root and dangle the
consuming repository's submodule.

Fix the labelling conflation, which is the real and cheap finding. Move the
`frontend-deploy` recipe out of `[group('docs')]` into its own group naming the
product-page artefact, so the menu stops asserting that publishing the product
page is a documentation operation.

Address the structural coupling as a separate, larger piece of work. Thirteen
private symbols reaching from the product-page publisher into the documentation
publisher's internals is the code-level expression of the same conflation. The
durable fix is to promote the genuinely shared publishing primitives — the AWS
command construction, the stack target resolution, the process runner, the
published-body fetch, the distribution alias verification — into a neutral
publishing-support module that both publishers consume as peers, leaving each
publisher owning only its own artefact's logic. That is architecturally
significant enough to warrant its own decision record if pursued, and it should
not be attempted while publication is held.

Record the boundary as an explicit invariant rather than an accident. The
proposed rule, in the terms the evidence supports: this repository owns both the
product page and the documentation landing; the product page is built from
`frontend/` and published to the site root by the frontend publisher, the
documentation is built from `docs/` and published to the `docs/` prefix by the
docs publisher, and no other repository may publish to either destination. The
marketing repository consumes the product page by submodule and never copies or
republishes it.

Make future drift detectable rather than noticed by eye. The two mechanisms that
would do it are a publisher-identity marker written into the published root and
checked on the next publish, so a foreign overwrite surfaces as a loud refusal
rather than a silent alternation; and a test asserting that the landing
publisher's sync actually threads the protected excludes into every pass, rather
than only asserting that the constant contains `docs/*`. The first closes the
cross-repository gap that no guard currently covers. The second upgrades the
existing test from pinning a value to proving the mechanism uses it.
