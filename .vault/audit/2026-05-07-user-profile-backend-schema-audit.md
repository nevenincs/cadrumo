---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/audit/ location)
# Feature tag (replace user-profile-backend-schema with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#audit'
  - '#user-profile-backend-schema'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-07'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-07-user-profile-backend-schema-exec]]"
  - "[[2026-05-07-user-profile-backend-schema-plan]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `user-profile-backend-schema` audit: `Wave 1 Schema Foundation Review`

## Scope

Wave 1 schema foundation slice:

- `registry/aeat/user_profile/schema.toml`
- `src/aeat/domain/user_profile/__init__.py`
- `src/aeat/domain/user_profile/_errors.py`
- `src/aeat/domain/user_profile/_loader.py`
- `src/aeat/domain/user_profile/_schema.py`
- `src/aeat/domain/user_profile/_values.py`
- `src/aeat/domain/user_profile/test_schema.py`
- `src/aeat/domain/user_profile/test_values.py`

The audit checked strict Pydantic enrollment, TOML schema loading, shared
worktree safety, focused test coverage, deterministic profile snapshot hashing,
tombstone lifecycle semantics, and lint compliance for the owned slice.

## Findings

USER-PROFILE-SCHEMA-001 | LOW | Ruff line-length violation in schema path constraint

`src/aeat/domain/user_profile/_schema.py` had one `E501` line-length violation
in the `_FieldPath` `StringConstraints` declaration. This was fixed by wrapping
the constraint arguments across multiple lines.

USER-PROFILE-SCHEMA-002 | INFO | No material safety or architecture issues found

The slice is isolated to new user-profile schema paths and owned vault
execution/audit records. It does not touch existing live profile consumers,
secure storage topology, CLI command registration, or unrelated dirty files.
The schema models use strict, frozen, extra-forbid Pydantic configuration and
the loader freezes TOML arrays before Python-mode validation.

USER-PROFILE-SCHEMA-003 | LOW | Ruff issues in value-model increment

The Wave 2 value-model increment initially had sorted-export, modern type
alias, quoted annotation, and line-length issues. These were fixed in
`src/aeat/domain/user_profile/__init__.py` and
`src/aeat/domain/user_profile/_values.py`.

USER-PROFILE-SCHEMA-004 | INFO | Value-model lifecycle checks passed

The strict value models enforce frozen records, tombstone requirements, valid
effective windows, snapshot rejection for tombstoned profiles, and canonical
snapshot hashes that are stable when fact order changes.

## Recommendations

Proceed to secure DB repository wiring only after keeping `ruff check` and
focused user-profile package tests passing. Later waves still need secure DB
value persistence, application lifecycle functions, model/revision preflight,
registry selector validation, and CLI facade integration.
