# Capital-goods register and bucket deletion assessment

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-040` · **Topic:** [Authentication and storage management](../topics/authentication-and-storage-management.md)

<!-- preserved:article -->
## Scope

This chunk covers 9 application modules (1,435 lines; 12,214 measured o200k_base proxy tokens) across bienes_inversion and bucket_maintenance. All assigned lines were read over three bounded pages. Static inspection only; I did not modify the source, perform a register write, or test a profile deletion.

## Capital-goods register capabilities

Operators can list and declare profile-scoped capital goods. The register service is deliberately a thin façade over an injected bucket-bound repository: it adds an already-validated record or returns the current register. The package does not calculate annual regularización or definitive prorrata. Elsewhere the register may feed a governed Modelo 303/390 calculation once definitive prorrata facts exist, or produce a non-blocking advisory while those facts are missing. Register boundary and scope (`src/cadrumo/application/bienes_inversion/service.py`) Repository capability (`src/cadrumo/application/bienes_inversion/ports.py`)

Declaration commands pair disposal year and regime; neither half alone is accepted. Kind and regime values are validated against the calculation registry before a domain record is built. The registered operation accepts an exact profile UUID, bounded text/year fields and public decimals, then resolves the vocabulary again, builds the domain record, and classifies known pre-write failures into a small typed refusal. The repository add happens in an irreversible section with effect UNKNOWN before the write; duplicate-identifier persistence errors become a stable refusal, while successful persistence stores the canonical updated register and reports an updated effect. Operator declaration command (`src/cadrumo/application/bienes_inversion/declare_command.py`) Operation request and result shapes (`src/cadrumo/application/bienes_inversion/registered_operation.py`) Validation and commit path (`src/cadrumo/application/bienes_inversion/registered_operation.py`)

The result projector checks operation ID, profile subject, result arm and receipt fields. For a list, it releases all records only against a successful no-effect receipt. For a declaration, it additionally confirms the reported record occurs unchanged in the private updated-register snapshot and that the count matches. The list/declaration access resolver delegates to ledger read access for the exact profile; declaration adds COMMIT, and the declared operation permits all operation frontends. Receipt-correlated projection (`src/cadrumo/application/bienes_inversion/registered_operation.py`) Profile access and commit policy (`src/cadrumo/application/bienes_inversion/registered_operation.py`)

One scoped contract question: the standalone declaration command uses NonNegativeInt for acquisition/disposal years, while the registered request uses 1..2099 bounds. The domain record may enforce the full range in either route; verify that the direct service path and all frontends converge on the same domain validation before treating this as a defect. Standalone command fields (`src/cadrumo/application/bienes_inversion/declare_command.py`) Registered request bounds (`src/cadrumo/application/bienes_inversion/registered_operation.py`)

## Bucket maintenance and retention knowledge

The current bucket-maintenance service is read-only. It can acquire target locks and produce a deletion pre-assessment, but does not delete, archive, restore, rename, import/export bundles, or reset profiles. Those lifecycle operations were moved to the profile-capsule lifecycle; full deletion is currently consumed by the durable all-profile configuration-reset flow, not exposed as a single-bucket maintenance verb. Current package scope (`src/cadrumo/application/bucket_maintenance/__init__.py`) Read-only service boundary (`src/cadrumo/application/bucket_maintenance/service.py`)

The assessment checks that the resolved bucket root is a real directory and not a symlink/junction before reading or inventorying it. It projects the label from the profile scan, computes a fingerprint over committed capsule contents (digest, file count and bytes), and obtains filing-retention status through FilingRetentionAuthority. An absent bucket returns an explicit exists=false assessment. A missing label projection, linked root, unreadable capsule inventory, absent retention snapshot or invalid/unreadable snapshot refuses with typed precondition evidence instead of treating missing data as proof that deletion is safe. Setup state remains unset because it is encrypted in the capsule and this preflight intentionally does not unlock it. Path validation (`src/cadrumo/application/bucket_maintenance/_deletion_paths.py`) Assessment assembly (`src/cadrumo/application/bucket_maintenance/service.py`) Fingerprinting (`src/cadrumo/application/bucket_maintenance/service.py`) Retention snapshot refusal behavior (`src/cadrumo/application/bucket_maintenance/service.py`)

Retention knowledge here is not computed from the encrypted filing catalogue at assessment time. The code documents that the filing owner writes a plaintext retention snapshot when profile creation or filing persistence has an open session; this service reads and authenticates that snapshot. It distinguishes a recorded empty filing set from an absent snapshot, because absence means the filing owner may never have recorded the answer. Invalid or unreadable data is also a refusal. The cited statutory retention rationale is product context, not independently verified legal advice or current-law validation. Assessment’s locked-profile data boundary (`src/cadrumo/application/bucket_maintenance/service.py`) Snapshot authority call (`src/cadrumo/application/bucket_maintenance/service.py`)

Target locks are acquired in stable unique bucket-ID order and released by the ExitStack. Missing buckets are skipped for this lock-only primitive; linked roots refuse. The deletion assessment itself performs no mutation and does not acquire those target locks in this module, so the fingerprint is an observation for a later deletion protocol rather than a lock-held reservation. Cross-module synthesis should confirm that the deletion workflow rechecks this fingerprint while holding the target lock before changing capsule contents. Stable target lock acquisition (`src/cadrumo/application/bucket_maintenance/service.py`) Read-only assessment contract (`src/cadrumo/application/bucket_maintenance/contracts.py`)

## Security and implementation assessment

Visible strengths are explicit profile-scoped repository injection, governed-fact authority validation, worker-thread execution and cancellation completion for the register operation; strict typed projection; path-link refusal before manifest reads; and fail-closed retention/inventory handling. The maintenance contract’s existing/absent arms are mutually exclusive, preventing an absent result from carrying stale profile metadata. The code keeps destructive lifecycle work in its dedicated capsule owner. Governed register executor (`src/cadrumo/application/bienes_inversion/registered_operation.py`) Assessment result shape (`src/cadrumo/application/bucket_maintenance/contracts.py`)

No confirmed local defect is established. Follow up on year-range parity and confirm the later delete caller locks and rechecks the assessment fingerprint. Adapter guarantees for atomic duplicate rejection, symlink resolution on each supported platform, inventory completeness and snapshot authentication were not tested here. No test evidence is included in the assigned modules.

## Complete assigned-file coverage

- bienes_inversion/__init__.py (35 lines) (`src/cadrumo/application/bienes_inversion/__init__.py`)
- bienes_inversion/declare_command.py (184 lines) (`src/cadrumo/application/bienes_inversion/declare_command.py`)
- bienes_inversion/ports.py (39 lines) (`src/cadrumo/application/bienes_inversion/ports.py`)
- bienes_inversion/registered_operation.py (669 lines) (`src/cadrumo/application/bienes_inversion/registered_operation.py`)
- bienes_inversion/service.py (61 lines) (`src/cadrumo/application/bienes_inversion/service.py`)
- bucket_maintenance/__init__.py (42 lines) (`src/cadrumo/application/bucket_maintenance/__init__.py`)
- bucket_maintenance/_deletion_paths.py (44 lines) (`src/cadrumo/application/bucket_maintenance/_deletion_paths.py`)
- bucket_maintenance/contracts.py (58 lines) (`src/cadrumo/application/bucket_maintenance/contracts.py`)
- bucket_maintenance/service.py (303 lines) (`src/cadrumo/application/bucket_maintenance/service.py`)
<!-- /preserved:article -->
