---
tags:
  - '#plan'
  - '#docs-static-deployment'
date: '2026-07-10'
modified: '2026-07-11'
tier: L2
related:
  - '[[2026-07-10-docs-static-deployment-adr]]'
  - '[[2026-07-10-docs-static-deployment-research]]'
---

# `docs-static-deployment` plan

Deploy Cadrumo docs through a private, human-gated path.

## Description

Create the static origin, deploy it locally, and route both URLs.

## Steps

### Phase `P01` - Provision the static origin

Create the private delivery stack.

- [x] `P01.S01` - Define the private S3 and CloudFront stack; `infra/docs-static-site.yaml`.
- [x] `P01.S02` - Declare stack deployment inputs; `infra/docs-static-site.parameters.example.json`.

### Phase `P02` - Build and publish the docs

Create the human-gated deployment path.

- [x] `P02.S03` - Build, validate, upload, and invalidate docs; `dev/deploy/docs_static_site.py`.
- [x] `P02.S04` - Expose local deployment commands; `justfile`.
- [x] `P02.S07` - Repair Pagefind deployment indexing; `dev/docs/pagefind_index.py, docs/conf.py, dev/deploy/docs_static_site.py`.

### Phase `P03` - Route and verify the public site

Document Cloudflare setup and endpoint checks.

- [x] `P03.S05` - Document DNS, redirect, and rollback actions; `docs/runbooks/RB-006-cadrumo-docs-delivery.md`.
- [x] `P03.S06` - Verify both public documentation URLs; `dev/deploy/docs_static_site.py`.

## Parallelization

Finish P01 before P02.

Finish P02 before P03.

## Verification

Build the full strict site.

Verify Pagefind, both URLs, and private S3 access.
