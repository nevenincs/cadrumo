"""Drift-detection guards for Modelo 100 across all 6 supported ejercicios.

Each test compares the formula / binding / parameter inventory across
revisions and surfaces gaps where a 2025 chain element was not backported
or where a prior-year revision diverged silently. The tests do not require
strict 1-to-1 parity (year-specific casillas legitimately drop some
elements) but catch:

  - top-level chain casillas (cuota chain, base imponible/liquidable,
    income aggregators) missing from any year
  - external references (binding, parameter, relation) declared but
    unreferenced
  - external references referenced but undeclared
  - revisions with formulas but no calculation application_link
"""

from __future__ import annotations

import ast
from functools import cache

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.directory_scan import scan_directory
from .....tests import REPO_ROOT
from ..runtime_graph import expression_binding_refs, expression_parameter_refs, expression_relation_refs
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_TOP_LEVEL_CHAIN_TARGETS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(casilla_id, surface="_TOP_LEVEL_CHAIN_TARGETS")
    for casilla_id in (
        # Mínimo personal y familiar
        "0519",
        "0520",
        "0521",
        "0522",
        "0523",
        "0524",
        # Base imponible / liquidable
        "0432",
        "0435",
        "0460",
        "0500",
        "0510",
        # Cuota íntegra
        "0532",
        "0533",
        "0545",
        "0546",
        # Cuota líquida + incrementada
        "0570",
        "0571",
        "0585",
        "0586",
    )
)

_SUPPORTED_REVISIONS: tuple[str, ...] = ("2020", "2021", "2022", "2023", "2024", "2025")


def _modelo_100():
    return _committed_modelo("100")


def test_top_level_cuota_chain_targets_present_in_every_supported_revision() -> None:
    """Every supported ejercicio carries the top-level cuota-chain formula targets."""
    modelo, _ = _modelo_100()
    gaps: dict[str, list[CasillaId]] = {}
    for revision_id in _SUPPORTED_REVISIONS:
        revision = modelo.revisions.get(revision_id)
        if revision is None:
            gaps[revision_id] = sorted(_TOP_LEVEL_CHAIN_TARGETS)
            continue
        targets = {f.target_casilla_id for f in revision.formulas}
        missing = _TOP_LEVEL_CHAIN_TARGETS - targets
        if missing:
            gaps[revision_id] = sorted(missing)
    assert not gaps, f"top-level cuota chain incomplete in revisions {gaps}"


def test_every_revision_with_formulas_exposes_a_calculation_application_link() -> None:
    """Per the registry validator's contract, formula-bearing revisions need a calculation link."""
    modelo, _ = _modelo_100()
    offenders: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        if not revision.formulas:
            continue
        surfaces = {link.surface for link in revision.application_links}
        if "calculation" not in surfaces:
            offenders.append(revision_id)
    assert not offenders, f"revisions with formulas but no calculation application_link: {offenders}"


def test_every_supported_revision_carries_a_filing_application_link() -> None:
    """Every supported ejercicio is filing-grade and needs a filing application_link."""
    modelo, _ = _modelo_100()
    offenders: list[str] = []
    for revision_id in _SUPPORTED_REVISIONS:
        revision = modelo.revisions.get(revision_id)
        if revision is None:
            continue
        surfaces = {link.surface for link in revision.application_links}
        if "filing" not in surfaces:
            offenders.append(revision_id)
    assert not offenders, f"supported revisions missing filing application_link: {offenders}"


def test_no_orphan_formula_feeding_bindings_in_any_revision() -> None:
    """Every formula-feeding binding declared in a revision must be referenced.

    Profile-source bindings expose taxpayer data to the application layer
    (declaration filling, observation capture) and are not expected to be
    consumed by formulas; they are excluded from the orphan check.
    Manual_input and previous_filing bindings are formula-feeding and must
    be referenced by at least one formula, relation, or casilla binding.
    """
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        formula_feeding = {b.id for b in revision.bindings if b.source in ("manual_input", "previous_filing")}
        referenced: set[str] = set()
        for formula in revision.formulas:
            referenced.update(expression_binding_refs(formula.expression))
        for relation in revision.relations:
            target_binding = getattr(relation, "target_binding", None)
            if target_binding:
                referenced.add(target_binding)
        for casilla in revision.casillas:
            if casilla.binding:
                referenced.add(casilla.binding)
            referenced.update(casilla.alternate_bindings)
        orphans = formula_feeding - referenced
        for orphan in sorted(orphans):
            offences.append(f"{revision_id}: orphan formula-feeding binding {orphan!r}")
    assert not offences, "orphan formula-feeding bindings detected:\n  " + "\n  ".join(offences)


def test_no_orphan_parameters_in_any_revision() -> None:
    """Every parameter declared in a revision must be referenced.

    A parameter counts as referenced when it is consumed either by a
    formula expression tree (``{ parameter = "..." }`` arg) or by an
    in-tree ``read_parameter("100", revision, parameter_id, ...)`` call
    in :mod:`cadrumo.domain.*` Python source. The latter is the
    out-of-formula consumption pattern used by the rental tier resolver
    and any future cross-module readers.

    A small allow-list (:data:`_PRE_STAGED_PARAMETERS`) covers
    parameters whose data is authoritative on disk (IRPF state-scale
    brackets) but whose consuming formula has not yet landed. Removing
    a parameter from that list is the gate that future formula work
    must clear when it begins to consume the data.
    """
    modelo, _ = _modelo_100()
    cross_module_refs = _read_parameter_refs_for_modelo("100")
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared = {p.id for p in revision.parameters}
        referenced: set[str] = set()
        for formula in revision.formulas:
            referenced.update(expression_parameter_refs(formula.expression))
        referenced |= cross_module_refs
        referenced |= _PRE_STAGED_PARAMETERS
        orphans = declared - referenced
        for orphan in sorted(orphans):
            offences.append(f"{revision_id}: orphan parameter {orphan!r}")
    assert not offences, "orphan parameters detected:\n  " + "\n  ".join(offences)


#: Parameters that are declared in the registry with authoritative tax
#: data (e.g. IRPF state-level progressive bracket tables, Ley 19/1994
#: RIC caps, Ley 19/1994 ZEC reduced rate, LIRPF arts. 86-89 attribution
#: pass-through, RD-Ley estimación objetiva indices) but whose consuming
#: formula has not yet been wired into the registry. Removing an entry
#: from this set is the gate that the corresponding formula work must
#: clear before this allow-list shrinks. The data is preserved on disk
#: so future formula work can land without re-entering authoritative
#: bracket values.
#:
#: Each entry below carries a one-line rationale and a pointer at the
#: tracking task that will land the consuming formula:
#:
#: * RIC trio (Ley 19/1994 art-27) — three legal-authority parameters
#:   (reduction rate cap 80 %, materialization window 3 years, holding
#:   period 5 years) cited by the 26 RIC casillas in the
#:   ``reserva_inversiones_canarias_res`` section, but the aggregation
#:   formula that applies the cap to the dotación total has not landed.
#:   See task #46 (Wire orphan RIC parameters).
#: * ZEC reduced rate (Ley 19/1994 art-43+) — Canarias special economic
#:   zone reduced corporate-tax rate cited by ZEC-eligible casillas;
#:   IRPF integration formula pending alongside the MM-7 Canarias work
#:   slice referenced by the Ley 19/1994 corpus commit.
#: * Estimación objetiva reducción general rate + corrector pequeña
#:   dimensión (Orden HFP estimación objetiva annual orders) —
#:   parameters consumed by the EO computation outside the registry
#:   evaluator. The values are authoritative for the EO module but the
#:   in-registry formula path is deferred until EO is brought under the
#:   formula evaluator.
#: * Atribución de rentas pass-through 100 % (LIRPF arts. 86-89) —
#:   parameter encodes the legal 100 % pass-through rate but the
#:   modelo-184 cross-modelo binding already returns the full attributed
#:   amount at casilla 1577 (``input_kind = "bound"``). The parameter
#:   exists for legal citation; turning it into a real consumer requires
#:   converting 1577 to ``input_kind = "computed"`` with an
#:   ``op = "percent"`` formula, which is a schema-level change tracked
#:   by task #47.
#: * 2024 mínimos personales y familiares (LIRPF arts. 57-61) —
#:   legally sourced state/autonomic minimo parameters were staged for
#:   the 2024 renta revision, but the formulas currently consume the
#:   base contributor minimo only. These entries must be removed as the
#:   remaining age, descendant, and ascendant minimo formulas land in
#:   the 2024 cuota chain.
_PRE_STAGED_PARAMETERS: frozenset[str] = frozenset(
    {
        # Art. 81.2 guardería annual cap. Authored ahead of its consumer on
        # purpose: the figure previously existed only as an inline literal
        # inside the 0613 formula, which the application layer cannot read,
        # and the per-child proration is computed there. This entry goes when
        # the injector that resolves it lands.
        "renta-2024-guarderia-incremento-cap-anual",
        "renta-2024-minimo-ascendientes-mayor-65-2024",
        "renta-2024-minimo-ascendientes-mayor-75-2024",
        "renta-2024-minimo-contribuyente-edad-65-74-2024",
        "renta-2024-minimo-contribuyente-edad-75-2024",
        "renta-2024-minimo-descendientes-cuarto-y-siguientes-2024",
        "renta-2024-minimo-descendientes-fallecimiento-2024",
        "renta-2024-minimo-descendientes-menor-tres-anos-2024",
        "renta-2024-minimo-descendientes-primer-hijo-2024",
        "renta-2024-minimo-descendientes-segundo-hijo-2024",
        "renta-2024-minimo-descendientes-tercer-hijo-2024",
        "renta-2025-ric-reduccion-rate-maximo",
        "renta-2025-ric-materializacion-plazo-anos",
        "renta-2025-ric-mantenimiento-plazo-anos",
        "renta-2025-zec-tipo-gravamen-reducido",
        "renta-2025-estimacion-objetiva-reduccion-general-rate",
        "renta-2025-estimacion-objetiva-indice-corrector-empresas-pequena-dimension-rate",
        "renta-2025-atribucion-rentas-rate-pass-through",
        # Mínimo personal y familiar 2020-2025 (LIRPF arts. 57-61) — the
        # authoritative per-year mínimo brackets (contribuyente, ascendientes,
        # descendientes, discapacidad) are staged on disk so the multi-year
        # renta mínimo formula can land without re-entering legal figures. The
        # consuming formula path is not yet wired into the registry evaluator;
        # this allow-list shrinks as each year's mínimo aggregation lands.
        #
        # The ``minimo-descendientes-*`` entries are listed here for a narrower
        # reason than the rest, and the distinction matters to whoever tries to
        # shrink this list: they ARE consumed, by the Art. 58/61 aggregate the
        # application layer injects, but this gate only scans
        # ``cadrumo.domain.*`` for ``read_parameter`` calls and only registry
        # formulas for ``{ parameter = "..." }`` args, so an application-layer
        # consumer is invisible to it. Deleting one of these entries reds the
        # gate even though the parameter is live. That is a gate-reach gap, not
        # staged data; the ``fallecimiento`` entries (Art. 61 norma 4ª's
        # death-in-period flat figure) are listed on the same footing as the
        # birth-order tranches they sit beside.
        "renta-2020-minimo-ascendientes-mayor-65-2020",
        "renta-2020-minimo-ascendientes-mayor-75-2020",
        "renta-2020-minimo-contribuyente-base-2020",
        "renta-2020-minimo-contribuyente-edad-65-74-2020",
        "renta-2020-minimo-contribuyente-edad-75-2020",
        "renta-2020-minimo-descendientes-cuarto-y-siguientes-2020",
        "renta-2020-minimo-descendientes-fallecimiento-2020",
        "renta-2020-minimo-descendientes-menor-tres-anos-2020",
        "renta-2020-minimo-descendientes-primer-hijo-2020",
        "renta-2020-minimo-descendientes-segundo-hijo-2020",
        "renta-2020-minimo-descendientes-tercer-hijo-2020",
        "renta-2020-minimo-discapacidad-gastos-asistencia-2020",
        "renta-2020-minimo-discapacidad-grado-33-2020",
        "renta-2020-minimo-discapacidad-grado-65-2020",
        "renta-2021-minimo-ascendientes-mayor-65-2021",
        "renta-2021-minimo-ascendientes-mayor-75-2021",
        "renta-2021-minimo-contribuyente-base-2021",
        "renta-2021-minimo-contribuyente-edad-65-74-2021",
        "renta-2021-minimo-contribuyente-edad-75-2021",
        "renta-2021-minimo-descendientes-cuarto-y-siguientes-2021",
        "renta-2021-minimo-descendientes-fallecimiento-2021",
        "renta-2021-minimo-descendientes-menor-tres-anos-2021",
        "renta-2021-minimo-descendientes-primer-hijo-2021",
        "renta-2021-minimo-descendientes-segundo-hijo-2021",
        "renta-2021-minimo-descendientes-tercer-hijo-2021",
        "renta-2021-minimo-discapacidad-gastos-asistencia-2021",
        "renta-2021-minimo-discapacidad-grado-33-2021",
        "renta-2021-minimo-discapacidad-grado-65-2021",
        "renta-2022-minimo-ascendientes-mayor-65-2022",
        "renta-2022-minimo-ascendientes-mayor-75-2022",
        "renta-2022-minimo-contribuyente-base-2022",
        "renta-2022-minimo-contribuyente-edad-65-74-2022",
        "renta-2022-minimo-contribuyente-edad-75-2022",
        "renta-2022-minimo-descendientes-cuarto-y-siguientes-2022",
        "renta-2022-minimo-descendientes-fallecimiento-2022",
        "renta-2022-minimo-descendientes-menor-tres-anos-2022",
        "renta-2022-minimo-descendientes-primer-hijo-2022",
        "renta-2022-minimo-descendientes-segundo-hijo-2022",
        "renta-2022-minimo-descendientes-tercer-hijo-2022",
        "renta-2022-minimo-discapacidad-gastos-asistencia-2022",
        "renta-2022-minimo-discapacidad-grado-33-2022",
        "renta-2022-minimo-discapacidad-grado-65-2022",
        "renta-2023-minimo-ascendientes-mayor-65-2023",
        "renta-2023-minimo-ascendientes-mayor-75-2023",
        "renta-2023-minimo-contribuyente-base-2023",
        "renta-2023-minimo-contribuyente-edad-65-74-2023",
        "renta-2023-minimo-contribuyente-edad-75-2023",
        "renta-2023-minimo-descendientes-cuarto-y-siguientes-2023",
        "renta-2023-minimo-descendientes-fallecimiento-2023",
        "renta-2023-minimo-descendientes-menor-tres-anos-2023",
        "renta-2023-minimo-descendientes-primer-hijo-2023",
        "renta-2023-minimo-descendientes-segundo-hijo-2023",
        "renta-2023-minimo-descendientes-tercer-hijo-2023",
        "renta-2023-minimo-discapacidad-gastos-asistencia-2023",
        "renta-2023-minimo-discapacidad-grado-33-2023",
        "renta-2023-minimo-discapacidad-grado-65-2023",
        "renta-2024-minimo-discapacidad-gastos-asistencia-2024",
        "renta-2024-minimo-discapacidad-grado-33-2024",
        "renta-2024-minimo-discapacidad-grado-65-2024",
        "renta-2025-minimo-ascendientes-mayor-65-2025",
        "renta-2025-minimo-ascendientes-mayor-75-2025",
        "renta-2025-minimo-descendientes-cuarto-y-siguientes-2025",
        "renta-2025-minimo-descendientes-fallecimiento-2025",
        "renta-2025-minimo-descendientes-menor-tres-anos-2025",
        "renta-2025-minimo-descendientes-primer-hijo-2025",
        "renta-2025-minimo-descendientes-segundo-hijo-2025",
        "renta-2025-minimo-descendientes-tercer-hijo-2025",
        "renta-2025-minimo-discapacidad-gastos-asistencia-2025",
        "renta-2025-minimo-discapacidad-grado-33-2025",
        "renta-2025-minimo-discapacidad-grado-65-2025",
        # Comunidad de Madrid mínimo por descendientes autonómico (#593,
        # Decreto Legislativo 1/2010 art. 2). Consumed by the SAME
        # out-of-formula pattern as the estatal mínimo-por-descendientes
        # parameters above: the application-layer injector
        # ``_minimo_descendientes_parameter`` / ``_resolved_minimo_descendientes_
        # tranches`` (``src/cadrumo/application/modelo/profile_binding.py``) reads
        # these by manually iterating ``snapshot.revision.parameters`` rather
        # than calling ``read_parameter(...)``, and lives under
        # ``src/cadrumo/application/`` rather than ``src/cadrumo/domain/`` — outside
        # both branches this gate's AST scan can see. Verified consumed by
        # ``test_minimo_descendientes_engine.py``'s Madrid-tranche tests.
        "renta-2020-minimo-descendientes-madrid-tercer-hijo-2020",
        "renta-2020-minimo-descendientes-madrid-cuarto-y-siguientes-2020",
        "renta-2021-minimo-descendientes-madrid-tercer-hijo-2021",
        "renta-2021-minimo-descendientes-madrid-cuarto-y-siguientes-2021",
        "renta-2022-minimo-descendientes-madrid-primer-hijo-2022",
        "renta-2022-minimo-descendientes-madrid-segundo-hijo-2022",
        "renta-2022-minimo-descendientes-madrid-tercer-hijo-2022",
        "renta-2022-minimo-descendientes-madrid-cuarto-y-siguientes-2022",
        "renta-2022-minimo-descendientes-madrid-menor-tres-anos-2022",
        "renta-2023-minimo-descendientes-madrid-primer-hijo-2023",
        "renta-2023-minimo-descendientes-madrid-segundo-hijo-2023",
        "renta-2023-minimo-descendientes-madrid-tercer-hijo-2023",
        "renta-2023-minimo-descendientes-madrid-cuarto-y-siguientes-2023",
        "renta-2023-minimo-descendientes-madrid-menor-tres-anos-2023",
        "renta-2024-minimo-descendientes-madrid-primer-hijo-2024",
        "renta-2024-minimo-descendientes-madrid-segundo-hijo-2024",
        "renta-2024-minimo-descendientes-madrid-tercer-hijo-2024",
        "renta-2024-minimo-descendientes-madrid-cuarto-y-siguientes-2024",
        "renta-2024-minimo-descendientes-madrid-menor-tres-anos-2024",
        "renta-2025-minimo-descendientes-madrid-primer-hijo-2025",
        "renta-2025-minimo-descendientes-madrid-segundo-hijo-2025",
        "renta-2025-minimo-descendientes-madrid-tercer-hijo-2025",
        "renta-2025-minimo-descendientes-madrid-cuarto-y-siguientes-2025",
        "renta-2025-minimo-descendientes-madrid-menor-tres-anos-2025",
        # Art. 58.1 rentas ceiling and Art. 61 norma 2ª own-return exclusion
        # (LIRPF). Unlike every other entry in this set these are ELIGIBILITY
        # THRESHOLDS rather than amounts: they gate whether a descendant
        # generates the mínimo at all, so no formula multiplies them and none
        # ever will.
        #
        # CONSUMED, not pending. Resolved by the SAME out-of-formula pattern as
        # the Madrid tranches above: ``_resolved_minimo_descendientes_thresholds``
        # (``src/cadrumo/application/modelo/profile_binding.py``) reads them by
        # iterating ``snapshot.revision.parameters`` rather than calling
        # ``read_parameter(...)``, and lives under ``src/cadrumo/application/``
        # rather than ``src/cadrumo/domain/`` — outside both branches this
        # gate's AST scan can see. They feed
        # :meth:`DescendantInfo.is_eligible_ordinary` as caller-supplied
        # ``MinimoDescendientesThresholds``, which is what keeps the two legal
        # figures out of Python. Verified consumed by
        # ``test_minimo_descendientes_eligibility.py``.
        "renta-2020-minimo-descendientes-rentas-anuales-limite-2020",
        "renta-2021-minimo-descendientes-rentas-anuales-limite-2021",
        "renta-2022-minimo-descendientes-rentas-anuales-limite-2022",
        "renta-2023-minimo-descendientes-rentas-anuales-limite-2023",
        "renta-2024-minimo-descendientes-rentas-anuales-limite-2024",
        "renta-2025-minimo-descendientes-rentas-anuales-limite-2025",
        "renta-2020-minimo-descendientes-declaracion-propia-rentas-limite-2020",
        "renta-2021-minimo-descendientes-declaracion-propia-rentas-limite-2021",
        "renta-2022-minimo-descendientes-declaracion-propia-rentas-limite-2022",
        "renta-2023-minimo-descendientes-declaracion-propia-rentas-limite-2023",
        "renta-2024-minimo-descendientes-declaracion-propia-rentas-limite-2024",
        "renta-2025-minimo-descendientes-declaracion-propia-rentas-limite-2025",
    },
)


def test_every_relation_references_an_existing_target_binding() -> None:
    """Each relation's target_binding must be a binding declared in the same revision."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared_bindings = {b.id for b in revision.bindings}
        for relation in revision.relations:
            target_binding = getattr(relation, "target_binding", None)
            if target_binding and target_binding not in declared_bindings:
                offences.append(
                    f"{revision_id}: relation {relation.id!r} target_binding {target_binding!r} not declared",
                )
    assert not offences, "relations with undeclared target_bindings:\n  " + "\n  ".join(offences)


def test_relation_target_bindings_are_consumed_or_relation_is_formula_operand() -> None:
    """Relation targets must either feed a casilla binding or be used directly by a formula."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        formula_relation_refs: set[str] = set()
        for formula in revision.formulas:
            formula_relation_refs.update(expression_relation_refs(formula.expression))

        consumed_bindings: set[str] = set()
        for casilla in revision.casillas:
            if casilla.binding:
                consumed_bindings.add(casilla.binding)
            consumed_bindings.update(casilla.alternate_bindings)

        for relation in revision.relations:
            target_binding = getattr(relation, "target_binding", None)
            if not target_binding:
                continue
            if target_binding not in consumed_bindings and relation.id not in formula_relation_refs:
                offences.append(
                    f"{revision_id}: relation {relation.id!r} targets unused binding {target_binding!r}",
                )
    assert not offences, "relations with unused target_bindings:\n  " + "\n  ".join(offences)


def test_every_formula_binding_reference_resolves_to_a_declared_binding() -> None:
    """Formulas that reference a binding via {binding = "..."} must point at a declared binding."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared_bindings = {b.id for b in revision.bindings}
        for formula in revision.formulas:
            referenced: set[str] = set()
            referenced.update(expression_binding_refs(formula.expression))
            unresolved = referenced - declared_bindings
            for ref in sorted(unresolved):
                offences.append(f"{revision_id}: formula {formula.id!r} references undeclared binding {ref!r}")
    assert not offences, "formulas referencing undeclared bindings:\n  " + "\n  ".join(offences)


def test_every_formula_parameter_reference_resolves_to_a_declared_parameter() -> None:
    """Formulas that reference a parameter via {parameter = "..."} must point at a declared parameter."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared = {p.id for p in revision.parameters}
        for formula in revision.formulas:
            referenced: set[str] = set()
            referenced.update(expression_parameter_refs(formula.expression))
            unresolved = referenced - declared
            for ref in sorted(unresolved):
                offences.append(f"{revision_id}: formula {formula.id!r} references undeclared parameter {ref!r}")
    assert not offences, "formulas referencing undeclared parameters:\n  " + "\n  ".join(offences)


@cache
def _read_parameter_refs_for_modelo(modelo_id: str) -> frozenset[str]:
    """Return every parameter id consumed via ``read_parameter`` for ``modelo_id``.

    The orphan-detection test treats a parameter as referenced when
    either (a) a formula expression tree consumes it via
    ``{ parameter = "..." }`` or (b) Python source under
    ``src/cadrumo/domain/`` calls
    ``read_parameter(modelo_id, <revision>, <parameter_id>, ...)``.
    Branch (b) covers the rental tier resolver and any other
    cross-module reader that drives the registry's parameter index
    outside the formula evaluator.

    The scan walks the AST of every ``.py`` file under
    ``src/cadrumo/domain/`` and harvests:

    - constant string literals passed as the third positional argument
      to a ``read_parameter`` call whose first positional argument is
      ``modelo_id`` (or any other constant; constants are filtered to
      the requested modelo at the call site below);
    - f-strings whose template substitutes the literal ``period_year``
      placeholder. The four-digit year supported by the registry is
      iterated (2020-2030) and each substitution is added to the set,
      so the test can identify references to year-keyed parameter ids
      (e.g. ``f"renta-{period_year}-rental-prior-rent-rebaja-threshold"``).

    Calls whose arguments are not statically analysable (dynamic
    parameter ids built from variables) are ignored — those would have
    to register the orphan via the formula tree to satisfy the gate.
    """
    refs: set[str] = set()
    domain_root = REPO_ROOT / "src" / "cadrumo" / "domain"
    for path in scan_directory(domain_root, pattern="*.py", recursive=True):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, OSError):
            continue
        for param_arg in _iter_read_parameter_arg_nodes(tree, modelo_id=modelo_id):
            refs.update(_expand_parameter_id_node(param_arg))
    return frozenset(refs)


def _iter_read_parameter_arg_nodes(tree: ast.AST, *, modelo_id: str) -> tuple[ast.expr, ...]:
    """Yield the parameter-id AST node from every ``read_parameter(modelo_id, ...)`` call.

    A call qualifies when (a) its callee resolves to the name
    ``read_parameter`` (direct call or attribute access), (b) it has
    at least three positional arguments, and (c) its first positional
    is a constant matching the requested ``modelo_id``. Callers that
    fail any of these gates are dropped before parameter-id expansion.
    """
    matches: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _read_parameter_matches(node, modelo_id=modelo_id):
            matches.append(node.args[2])
    return tuple(matches)


def _read_parameter_matches(node: ast.Call, *, modelo_id: str) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        func_name = func.id
    elif isinstance(func, ast.Attribute):
        func_name = func.attr
    else:
        return False
    if func_name != "read_parameter" or len(node.args) < 3:
        return False
    return _modelo_arg_code(node.args[0]) == modelo_id


def _modelo_arg_code(node: ast.expr) -> str | None:
    """Return the three-digit modelo code a ``read_parameter`` first arg denotes.

    Recognises the bare literal (``"100"``) and the canonical
    :class:`cadrumo.core.Modelo` enum references that replaced it during the
    modelo-enum-hardening sweep: the member ``Modelo.M100`` and its
    ``Modelo.M100.value`` form. Any other expression yields ``None`` (the
    call is treated as not statically analysable for this modelo).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # Unwrap a trailing ``.value`` (``Modelo.M100.value`` -> ``Modelo.M100``).
    if isinstance(node, ast.Attribute) and node.attr == "value":
        node = node.value
    # ``Modelo.M100`` -> Attribute(value=Name("Modelo"), attr="M100").
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Modelo"
        and node.attr.startswith("M")
        and node.attr[1:].isdigit()
    ):
        return node.attr[1:]
    return None


def _expand_parameter_id_node(node: ast.expr) -> tuple[str, ...]:
    """Resolve a parameter-id AST node into the set of ids it could match.

    Constant strings expand to themselves. F-strings expand into the
    Cartesian product of every formatted placeholder against a small
    static substitution table — see :data:`_FSTRING_PLACEHOLDER_VALUES`.
    Placeholders not in the table render as ``"{}"`` so the resulting
    template no longer matches any registered parameter id; that path
    cleanly drops out of the cross-module reference set instead of
    silently widening it.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if not isinstance(node, ast.JoinedStr):
        return ()
    static_segments, placeholder_names = _split_joined_str(node)
    if not placeholder_names:
        return ("".join(s for s in static_segments if s != _SEG_GAP),)
    placeholder_value_sets = tuple(_FSTRING_PLACEHOLDER_VALUES.get(name, ()) for name in placeholder_names)
    if any(not values for values in placeholder_value_sets):
        return ()
    from itertools import product as _product

    return tuple(_render_segments(static_segments, combo) for combo in _product(*placeholder_value_sets))


# Sentinel markers used to flatten JoinedStr values into a single segment
# stream. _SEG_GAP marks "a constant string slot ended here" so the
# renderer can skip it; _SEG_HOLE marks "consume the next placeholder
# value here." Real f-strings cannot contain raw NUL or SOH bytes.
_SEG_GAP = "\x00"
_SEG_HOLE = "\x01"
_UNKNOWN_PLACEHOLDER = "__unknown__"


def _split_joined_str(node: ast.JoinedStr) -> tuple[list[str], list[str]]:
    """Flatten a JoinedStr into (segments, placeholder-names).

    Each ``ast.Constant`` value contributes its literal text followed by
    a gap sentinel; each ``ast.FormattedValue`` contributes a hole
    sentinel and pushes its placeholder name. Unsupported formatted
    expressions (non-Name) push ``__unknown__`` so the caller can
    decide to drop the candidate.
    """
    static_segments: list[str] = []
    placeholder_names: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            static_segments.append(value.value)
            static_segments.append(_SEG_GAP)
            continue
        if isinstance(value, ast.FormattedValue):
            inner = value.value
            placeholder_names.append(inner.id if isinstance(inner, ast.Name) else _UNKNOWN_PLACEHOLDER)
        else:
            placeholder_names.append(_UNKNOWN_PLACEHOLDER)
        static_segments.append(_SEG_HOLE)
    return static_segments, placeholder_names


def _render_segments(static_segments: list[str], combo: tuple[str, ...]) -> str:
    """Render a flattened segment stream against one placeholder-value combo."""
    combo_iter = iter(combo)
    rendered: list[str] = []
    for segment in static_segments:
        if segment == _SEG_GAP:
            continue
        if segment == _SEG_HOLE:
            rendered.append(next(combo_iter))
        else:
            rendered.append(segment)
    return "".join(rendered)


#: Static substitution table for f-string placeholder names that the
#: orphan-detection scan can resolve. The entries cover the rental tier
#: resolver and any other consumer whose parameter id is built from a
#: small closed set of Python locals; new placeholder names that appear
#: in future ``read_parameter`` calls must be registered here.
_FSTRING_PLACEHOLDER_VALUES: dict[str, tuple[str, ...]] = {
    "period_year": tuple(str(year) for year in range(2020, 2031)),
    "tier_id": ("tier-50", "tier-60", "tier-70", "tier-90"),
}
