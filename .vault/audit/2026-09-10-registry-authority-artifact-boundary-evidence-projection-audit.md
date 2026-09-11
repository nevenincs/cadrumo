---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:a451d5e6935e4f546700d5d72d7d9e833110ce82872ace1217a3007cb267a653'
related: []
---



# `registry-authority-artifact-boundary` audit: `evidence projection`

## Scope

The signed legal-evidence projection and IVA adoption were audited for a complete artifact-only authority boundary.

## Findings

### evidence-projection | high | Published authority still exposes raw corpus through source root

Provenance and revision inspection dereference `authority.source_root`, and citation, review, filing, and XML consumers use that path. The IVA evidence projection alone does not establish artifact-only runtime behavior.

### evidence-projection | high | Runtime test preserves the forbidden raw-corpus behavior

An existing runtime test mutates a corpus reference and asserts provenance obtained through `legal_corpus_provenance`. It contradicts the artifact-only decision and must be replaced by a projection query or explicit refusal.

### evidence-projection | high | Staged IVA test is pre-empted by global authority setup

The global runtime fixture reads the absent real artifact before the staged-resource seam is installed. The staged artifact test needs isolated fixture composition before it is evidence.

## Recommendations

- Extend the signed artifact with provenance, inspection, and required export-layout projections, then migrate consumers.
- Replace the raw-corpus runtime test with projection behavior.
- Install staged artifact resources before authority fixture construction.
