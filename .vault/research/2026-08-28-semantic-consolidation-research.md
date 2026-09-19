---
tags:
  - '#research'
  - '#semantic-consolidation'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:7d8e7cf4a942ce7bd32d17e03200ac2115dc9233776927e6f76bce49f965424d'
related: []
---

# `semantic-consolidation` research: locating duplication by meaning-reference

## Why the existing instruments do not find this

Two duplication instruments already ship and neither can see the class of defect this
campaign targets.

`dev/audit/duplication.py` drives jscpd, and its own docstring records the limit: jscpd
matches token sequences, so a concept implemented twice in different syntax is
invisible to it, and that is exactly the duplication this project's rules treat as a
blocker. Five ledger projections once shared one casilla fold differing only in an
accumulator loop versus a comprehension; that runner reported none of them and flagged
their shared import preambles instead.

`dev/audit/semantic.py` uses the RAG daemon, but for a different question: whether
domain concepts leak into adapters and entrypoints. It is a layering check, not a
duplication check.

Embedding search does not close the gap either, and the reason is worth stating because
it is counter-intuitive. Embeddings match VOCABULARY. Two implementations written by
different authors use different nouns, different helper names and different comments,
so they score as unrelated however identical their behaviour. The harder the
duplication, meaning the more independently the second copy was written, the worse
embedding recall gets. Semantic search is excellent at finding a concept you can
describe; it is close to useless at finding the SECOND implementation of a concept.

## The inversion this campaign rests on

Do not scan code asking whether it is duplicated. Enumerate the domain's concepts from
sources the code cannot paraphrase away, then ask of each: how many independent
implementations reference it? Two or more is a candidate.

This codebase suits that unusually well, because its concepts are already externalised
as data: closed enum members in `core/`, registry TOML source kinds and casilla ids,
legal-catalogue article ids, the CLI manifest verbs, locale keys. Each is a name for a
MEANING that survives every rewrite of the code around it. A module's fingerprint is
the set of those meanings it touches, and two modules with the same rare fingerprint
are implementing the same rule whatever they call it.

## The detectors

Implemented in `dev/audit/semantic_duplication.py` as one runner, following the
convention the jscpd runner set: one owner per measurement, no second command anywhere.
Detection is deterministic AST work with no model in the path, so the output is
reproducible and can later back a gate.

Closed enums are DISCOVERED from the tree rather than listed, because a hand-kept
inventory of enums is itself the restated list this runner exists to find.

- **enum_subset** reports modules naming the same multi-member subset of one closed
  enum. The subset is a fingerprint of the partition a module implements. Whole-enum
  references are excluded: naming every member is usually exhaustive dispatch.
- **scarce_literal** reports module pairs sharing two or more literals that occur at
  few sites. In a regulated domain a rule is a number, and a number cannot be
  paraphrased. Two shared scarce literals rather than one, because a single shared
  figure is often a genuine cross-reference while a pair is a shared rule.
- **call_fingerprint** reports functions whose multiset of callees, literals and
  comparison operators is identical. It is blind to the function name, its parameters
  and its locals, which are the axes a second author spells differently. This is the
  detector aimed at the accumulator-versus-comprehension case jscpd missed.
- **field_set** reports record types in different modules declaring an identical
  annotated field set. A record shape is a claim about what a thing IS; the same shape
  under two names is one concept modelled twice, and the copies drift independently.
- **import_overlap** reports module pairs depending on nearly the same first-party set
  with no import edge between them. Two implementations of one concept reach for the
  same collaborators, and the no-edge condition separates a duplicate from a layering.
- **package_overlap** covers the whole-module-lives-twice case, rolled up from function
  fingerprints rather than from names.

## Measured inventory, first run

Over 1941 production modules in `src/cadrumo`.

The largest single class is that **116 CLI payload models duplicate a non-CLI model**:
92 against `application/`, 17 against `domain/`, 5 against `adapters/`, restating at
least 715 annotated fields. `entrypoints/cli/_ledger_payloads.py` is substantially a
parallel copy of `application/ledger/models.py`, pairing `TransactionPayload` with
`LedgerTransactionPayload` and `LedgerExportRowPayload` with `LedgerExportRow`. No
accepted decision sanctions this. The nearest,
`2026-06-05-modelo-work-revision-cli-decomposition-adr`, rules that revision commands
are thin transports over modelo application facades, which points the other way.

**Eleven repository classes** declare the identical four-field configuration shape
`namespace, payload_type, schema_version, sensitivity`.

**Four modules carry an identical PEP 562 `__getattr__`** lazy re-export resolver, at
`adapters/persistence/storage/__init__.py:627`,
`adapters/persistence/storage/crypto/__init__.py:93`,
`adapters/persistence/storage/custody/__init__.py:351` and
`domain/modelos/__init__.py:351`, with two more of a second shape at
`application/filing/__init__.py:393` and `application/registry/__init__.py:317`. These
are duplication AND an independent rules breach: package namespaces must be inert, and
PEP 562 export maps are prohibited outright.

**`_code_is_uppercase_alnum`** is implemented twice with identical behaviour, at
`domain/auth/apoderamientos/_catalogue.py:40` and
`entrypoints/cli/_config_payloads.py:1160`.

Further confirmed pairs from the same run: `_render_strength` across two TUI screens,
`_rows_for` across the M200 and M296 projections, `list_snapshots` across
`borrador_100` and `justificante`, and three identical secure-persistence `__init__`
bodies under `adapters/persistence/profile/`.

Two clusters were closed before this runner existed, by hand, and are the worked
precedent for the method: the home-office family grouping restated in four modules with
two independent category-set functions, and the bucket-as-profile afectación lookup
restated at two sites.

## What the detectors deliberately do not do

Every detector emits CANDIDATES. A shared fingerprint is evidence that two sites mean
the same thing; it is not proof, and the substitutability rule applies before anything
is collapsed: the proposed canonical site's constraint shape must be a SUPERSET of the
other's. A class carrying a constraint the other lacks is not interchangeable with it.
Two sites partitioning the same enum for genuinely different rules are a legitimate
finding to leave standing, and a lower duplicate count bought by merging them is a
regression rather than progress.

The enum detector also produces a known noise shape. Seven clusters reference a subset
across more than six modules, and at that spread the reference is usually a shipped
idiom rather than a restated rule: `SchemaState` with `NOT_SUPPORTED` and `TARGET`
appears in twenty-six CLI command-spec modules because each spec declares its own
schema state. Those are held back from the first confirmation pass rather than deleted
from the output, because the cut-off is a heuristic and the runner should not silently
hide what it saw.
