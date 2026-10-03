# Snapshot and reading guide

[Technical overview](README.md) · [Detailed article index](articles/README.md)

## Audience and structure

This collection serves readers investigating Cadrumo's internals. Application instructions and tax-filing workflows belong to the separate user documentation.

- **Architecture:** the main body of the technical landing page explains the system's organization and boundaries.
- **Cross-cutting assessments:** four additional pages cover capabilities, knowledge and provenance, security, and implementation quality.
- **Topics:** 18 full overview reports explain subsystems. Each has one corresponding synthesis brief, retained in an expandable summary. Short landing-page descriptions help readers choose a topic.
- **Detailed articles:** 206 source-analysis reports provide the underlying mechanisms, observations, and coverage. Each topic draws on multiple articles. Article pages link back to their assigned topic; inline references retain additional cross-topic connections.

The original analysis called the overview and assessment collection **Stage 1** and the detailed collection **Stage 2**. The 18 synthesis briefs summarize the Stage 1 topic reports one-to-one. They do not summarize individual Stage 2 articles.

## What the snapshot establishes

The analysis recorded repository HEAD as `3df7c143cc67663fadeacedb38a113df5aaac07e`, but inspected the on-disk source snapshot, including its existing omissions. That identifier is context, not a claim that the analyzed tree was identical to a clean checkout.

The snapshot contained 8,355 files, including 3,025 Python files. Its original test tree and root build configuration were absent. Missing material in this snapshot must not be interpreted as missing from the project.

Reviewers read each assigned implementation file or line range in full. They inventoried the large reference-data collections completely and reviewed bounded, representative content samples. Coverage appendices retain those distinctions and the sampled material.

The analysis did not execute the application or its tests, verify live behavior at Spain's tax agency (AEAT), or independently validate current tax law. An implemented path, a conditionally available operation, a refused operation, and an unverified outcome remain distinct findings. Bundled schemas and source counts do not establish complete calculation or export support.

## Reading the evidence

Begin with a topic or cross-cutting assessment when investigating behavior across modules. Detailed articles describe bounded assignments; a local observation or unresolved question may depend on controls elsewhere. Follow the documentation references before drawing a system-wide conclusion.

Source identifiers remain as plain text. They locate the evidence in the analyzed snapshot conceptually; they are not links or promises about current file locations. Direct code links and line-number anchors have been removed. Links within this collection connect documentation pages and retained analysis metadata.

The original report prose, findings, qualifications, tables, diagrams, and coverage appendices are preserved. Presentation changes are limited to headings, navigation, placement of summaries, and citation formatting. The architecture report forms the landing page's body. No source-code reinspection or new runtime verification was performed for this presentation.

## Provenance

- [Document manifest](manifest.json): original report paths and hashes, destination pages, and preserved-body hashes.
- [Original snapshot and analysis record](evidence/run.json): recorded scope, assignments, and validation results.
- [Registry inventory](evidence/registry-structure.json): structural observations from the analyzed registry.
- [Terminology sampling record](evidence/terminology-sample-bound.json): the bounded terminology review.
- [Cross-module review questions](evidence/review-questions.md): original review leads, distinct from the synthesized conclusions.

This is a standalone Markdown collection, readable directly on GitHub. It is outside the user documentation's source directory and build navigation. No user-documentation compilation or site deployment is required to read it.
