"""Capital-goods IVA deduction-regularización register and annual/disposal computes.

Models the LIVA arts. 107-110 regularización de deducciones por bienes de
inversión: a durable, cross-year :class:`BienesInversionIvaRegister`, one
:class:`BienInversionIvaRecord` per capital good, the pure art-109
:class:`RegularizacionAnualResult` computed for each supplied definitive prorrata
percentage, and the pure art-110 :class:`RegularizacionTransmisionResult` computed
for a good disposed of during its regularisation window.

The register is a taxpayer-fact store (owned goods, acquisition year, cuota
soportada, initial definitive prorrata percentage), sibling to
:mod:`domain.iva_compensation`; the regulatory constants it consumes (the
4/9-year windows, the over-10-point gate, and the /5, /10 divisors) live in the
central authoring surface :mod:`core.external_constants`, grounded verbatim
in the bundled consolidated LIVA corpus.

Register-wide projection returns :class:`RegistroRegularizacionResult` for the
ordinary annual art-109 path: each art-108-eligible in-window good (not yet
disposed of) is either computed into the proposed Modelo 303 casilla 43 / Modelo
390 regularización value when the current-year definitive prorrata fact is
available, or reported as pending that separate input. A good recorded as
disposed of in the projected year routes instead through
:func:`compute_registro_transmisiones`, which folds the art-110 single ("única")
regularización for every remaining window year into the same casilla-43 total;
art-110 carries no pending state — the disposal regime and acquisition-year facts
are already on the record, so every disposed good is always computed. This domain
module does not read the secure-object store or derive prorrata; application and
persistence layers supply those facts.

See Also:
    :mod:`application.bienes_inversion`
        Profile-scoped service that declares and lists the persisted register.
    :mod:`adapters.persistence.profile.bienes_inversion`
        FINANCIAL secure-object repository that stores the register singleton.
    :mod:`application.calculations`
        Source resolver and advisory projection surfaces for the
        ``bienes_inversion_regularizacion`` calculation source.
    :mod:`domain.iva`
        Legal prorrata substrate that supplies the separate definitive
        percentage input; usage ratios are not a substitute.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
