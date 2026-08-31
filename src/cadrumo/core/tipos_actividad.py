"""Closed value set for the AEAT Modelo 036 tipo de actividad.

Modelo 036 declares the taxpayer's economic activity under a two-letter-plus-two-digit
code, and the diseño de registro names the field only as ``Tabla`` without enumerating
it. AEAT publishes the enumeration in the *instrucciones* instead, bundled under
``_data/corpus/aeat_official/instructions/modelo_036/`` with its ``PROVENANCE.md``.
This enum is the single typed home for that closed set, declared in ``core`` per the
core-authority discipline: closed axes live in ``core/``, hydrate at boundaries, and
are asserted as members in tests.

The table has two halves, and the split is load-bearing rather than cosmetic. The
``A`` series covers activities that ARE part of the hecho imponible of the Impuesto
sobre Actividades Económicas; the ``B`` series covers activities that are NOT. The
consequence is stated by AEAT in the same instructions: the epígrafe/sección IAE field
is filled *solo para las actividades comprendidas dentro de los códigos de actividad
A01, A02, A03, A04 y A05*, so a ``B``-series filer never carries an IAE epígrafe and
the epígrafe cannot serve as a discriminator for exactly the agrarian activities that
would most need one.

What this axis is FOR: separating income by activity so a return that splits its
casillas by activity type can route each row to the right one. The worked case is
Modelo 131, where casilla 01 carries the estimación-objetiva volume and casilla 08 the
agrarian one; without an activity axis the same rows would feed both and double-count.
It is also the selector for the RIRPF art. 95 retención partitions, whose
code-to-partition correspondence is registry data in
``registry/aeat/legal/irpf-retencion-actividades.toml`` under the
``rirpf-art-95:selector-m036-*`` parameters — never a mapping inlined here.

The correspondence does not cover art. 95 completely, and the gap is declared rather
than hidden: art. 95.4.1.º fixes 1 % for *engorde de porcino y avicultura*
specifically, while this table's finest livestock grain is
:attr:`TipoActividad.B02_GANADERA` with :attr:`TipoActividad.A02_GANADERIA_INDEPENDIENTE`
beside it. Neither isolates porcino or avicultura. The registry carries that partition
with an empty code set so a consumer meets the gap where it looks for the mapping.

See Also:
    :mod:`~domain.transactions._tipo_actividad_partitions`
        Reads the registry selectors and resolves a code to its art. 95 partition.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "IAE_SUBJECT_TIPOS_ACTIVIDAD",
    "NON_IAE_SUBJECT_TIPOS_ACTIVIDAD",
    "TipoActividad",
]


class TipoActividad(StrEnum):
    """One Modelo 036 tipo-de-actividad code.

    The value byte-equals the stored token, so a member compares, hashes, and
    JSON-serialises identically to its string.

    Attributes:
        A01_ARRENDADORES_BIENES_INMUEBLES: Arrendadores de bienes inmuebles.
        A02_GANADERIA_INDEPENDIENTE: Ganadería independiente. Subject to IAE, yet
            art. 95.4 counts it among the actividades agrícolas o ganaderas
            expressly (*Se entenderán incluidas ... a) La ganadería independiente*),
            so it partitions with the ``B`` livestock code rather than against it.
        A03_RESTO_EMPRESARIALES: Resto de actividades empresariales.
        A04_ARTISTICAS_Y_DEPORTIVAS: Artísticas y deportivas — Sección Tercera of the
            IAE tarifas, which art. 95.2.a) counts as rendimientos de actividades
            profesionales alongside Sección Segunda.
        A05_PROFESIONALES: Profesionales — Sección Segunda of the IAE tarifas.
        B01_AGRICOLA: Agrícola.
        B02_GANADERA: Ganadera.
        B03_FORESTAL: Forestal.
        B04_PRODUCCION_DE_MEJILLON: Producción de mejillón.
        B05_PESQUERA: Pesquera.
    """

    A01_ARRENDADORES_BIENES_INMUEBLES = "A01"
    A02_GANADERIA_INDEPENDIENTE = "A02"
    A03_RESTO_EMPRESARIALES = "A03"
    A04_ARTISTICAS_Y_DEPORTIVAS = "A04"
    A05_PROFESIONALES = "A05"
    B01_AGRICOLA = "B01"
    B02_GANADERA = "B02"
    B03_FORESTAL = "B03"
    B04_PRODUCCION_DE_MEJILLON = "B04"
    B05_PESQUERA = "B05"


IAE_SUBJECT_TIPOS_ACTIVIDAD: Final[frozenset[TipoActividad]] = frozenset(
    tipo for tipo in TipoActividad if tipo.value.startswith("A")
)
"""Codes AEAT lists under activities forming part of the IAE hecho imponible.

Derived from the code prefix rather than hand-listed, so a future ``A06`` joins by
construction. These are the only codes for which the M036 epígrafe/sección IAE field
is filled.
"""

NON_IAE_SUBJECT_TIPOS_ACTIVIDAD: Final[frozenset[TipoActividad]] = frozenset(
    tipo for tipo in TipoActividad if tipo.value.startswith("B")
)
"""Codes AEAT lists under activities outside the IAE hecho imponible.

Complement of :data:`IAE_SUBJECT_TIPOS_ACTIVIDAD` by construction. A filer here
carries no IAE epígrafe, which is why an epígrafe-based discriminator cannot reach
the agrarian activities.
"""
