"""Core cross-cutting infrastructure shared by every Cadrumo layer.

The core layer is the innermost package in the hexagonal architecture. It
exports typed primitives, configuration-adjacent helpers, parsing utilities,
and layer-neutral policies that domain, application, adapter, and entrypoint
modules can import without depending outward.

The public facade groups stable surfaces. Immutable modelling primitives
include :data:`STRICT_FROZEN_CONFIG`, :class:`CasillaId`, :class:`Modelo`,
:class:`Period`, :class:`StandardPeriodCode`, ``PeriodKind``,
:class:`TaxDomain`, :class:`RefundElection`, :class:`ResultDisposition`,
:class:`RevisionReviewStatus` with its derived
:data:`REVIEWED_REVISION_REVIEW_STATUSES` companion set,
:class:`RegistryAuthorityGrade` with its fail-closed
:data:`UNDECLARED_REGISTRY_AUTHORITY_GRADE` floor, and
the lazily resolved :class:`BindingSourceKind` registry-source taxonomy.
Obligation-coverage mappings expose :data:`OUT_OF_SCOPE_OBLIGATIONS` and
:data:`UNMODELED_OBLIGATIONS`, the codified AEAT modelo sets the overview
coverage report reads to distinguish product-scope exclusions from
registry gaps. :func:`pid_is_alive` is the shared
cross-platform PID-liveness probe consumed by every crash-recoverable
lockfile (bucket lockfile, auth-acquisition lock), and :func:`unlink_lockfile`
is the matching shared removal primitive those same locks use to survive the
Windows sharing violation a waiter's open handle causes. TOML and option utilities expose
:func:`read_toml`, :func:`parse_toml_text`, :func:`freeze_toml`,
:class:`OptionalExtra`, and :func:`require_optional_extra`. Directory
listing goes through :func:`~cadrumo.core.directory_scan.scan_directory` (sorted
and materialised) and :func:`~cadrumo.core.directory_scan.iter_directory` (lazy,
for early-exit callers), narrowed by
:class:`~cadrumo.core.directory_scan.DirectoryEntryKind` — the one ``os.scandir`` walk every layer shares
instead of reaching for ``Path.glob``. Filing-result
helpers expose the codified :class:`ResultDisposition` mapping and its
casilla/refund predicates. Service and operator-adjacent primitives include
:class:`ServiceCapability`, :class:`LedgerSortField`,
:class:`LedgerSortOrder`, :data:`IBAN_SHAPE_RE`, and :func:`iban_mod_97`. The
closed :class:`GoogleCredentialSourceKind` taxonomy governs which mechanism
:mod:`adapters.outbound.google` uses to obtain Google API credentials.

``BindingSourceKind`` is resolved through ``__getattr__`` so callers can
import the public core facade without eagerly paying for registry taxonomy.

Major subpackages remain the specialised homes for broader contracts:
:mod:`core.config` owns :class:`core.config.Settings` and storage route
classification, :mod:`core.errors` owns the error taxonomy and registry,
:mod:`core.money` and :mod:`core.decimal` own Decimal primitives,
:mod:`core.time` owns clocks, :mod:`core.identity` owns NIF/NIE/bucket/profile
identifiers, :mod:`core.access_gate` owns live-read and write-refusal gating,
:mod:`core.redaction` owns safe output, and :mod:`core.classification` owns
sensitivity policy.

See Also:
    :class:`Period`: Canonical filing year plus registry period-code value used
        across registry, deadline, and workflow boundaries.
    :func:`read_toml`: Shared committed-TOML loader with caller-owned error
        wrapping.
    :class:`ResultDisposition`: Codified fichero result-disposition
        code set grounded in bundled AEAT diseños.
    :class:`BindingSourceKind`: Canonical registry binding-source taxonomy
        resolved lazily from :mod:`core.aggregation`.
    :class:`ConceptLifecycle`: Terminology Handbook concept lifecycle, shared
        by the shipped terminology search and the unshipped authoring tooling.
    :class:`ExternalOracleCorpus`: Bundled AEAT-authoritative oracle corpus that
        supplies an expected casilla value for independent reconciliation.
    :class:`ExportLayoutFormat`: Wire shape a registry export layout declares,
        closing the value set every export consumer used to re-spell.
    :class:`ExportExemptionReason`: Why a manifest casilla files no slot on the
        official record, so exemption from the completeness gate is declared
        data rather than an unexplained absence.
    :class:`DeclaracionIdioma`: Languages AEAT's declaration ``Aux/Idioma``
        element accepts, which are not the application's own output languages.
    :class:`CasillaValueKind`: How an observed casilla value is meant to be read,
        so a reader asks what a value IS instead of attempting a conversion.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
