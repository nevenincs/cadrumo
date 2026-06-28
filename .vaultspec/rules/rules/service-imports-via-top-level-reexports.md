---
name: service-imports-via-top-level-reexports
---

# Service imports via top-level re-exports

## Rule

A new application-layer service MUST consume cross-package primitives through
the consumed package's top-level ``__all__`` re-export, never through an
internal submodule import (the ``_foo`` module that owns the implementation is
private to its package). Promote the symbol to ``__all__`` as a precondition;
the service-side import line is then the package-top-level form.

## Why

The BucketMaintenanceService composition pattern landing on 2026-06-03 surfaced
the consequence of letting one consumer dot into a package's internals: every
later consumer reads the precedent as permission to do the same. The fix is
mechanical (add the symbol to ``__all__`` + the lazy ``__getattr__`` block) but
re-binding the call sites later is invasive. Better to insist at authoring
time that a new service consume symbols through the package boundary.

Concretely, the precondition Step for the bucket-maintenance composition
promoted ``rename_profile``, ``delete_profile_with_lifecycle_span``,
``remove_profile_bucket_directory``, ``serialize_profile_bundle``,
``deserialize_profile_bundle``, ``SUPPORTED_BUNDLE_SCHEMA_VERSIONS``, and
``UserProfilePortableExport`` to top-level surfaces before the service
consumed them. Operator-direct directive recorded 2026-06-03 in the same
session: "single authoritative source that is imported only from top level
re-exports not from internal submodules".

## How

- **Good:** a new ``aeat.application.bucket_maintenance`` service imports
  ``rename_profile`` from ``aeat.application.user_profile`` (the package
  ``__all__`` re-export). The precondition Step promoted the symbol to that
  surface before the service file was authored.
- **Good:** a regression-gate test pins the public surface
  (``test_bundle_reexports.py``) so a future refactor cannot retract the
  re-export and force the service to import from internals again.
- **Bad:** a service file imports ``from ....application.user_profile._orchestration
  import rename_profile`` (dotting into the private submodule). The next agent
  who needs the same symbol reads the precedent and does the same; gradually
  the package boundary is eroded.

## Source

Operator directive recorded 2026-06-03 during the BucketMaintenanceService
composition-pattern landing on the ``chore/eliminate-shims`` branch. Backing
ADR: ``2026-06-03-cli-workflow-redesign-adr``. Backing research:
``2026-06-03-cli-workflow-redesign-research``. Backing exec record:
``2026-06-03-cli-workflow-redesign-exec``.
