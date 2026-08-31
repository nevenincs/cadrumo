"""Closed value set for the legal relationship linking a descendant to the filer.

LIRPF draws the descendant line twice, with different scopes, and the two clauses
do not coincide:

* **Art. 58.1** assimilates to descendants those "vinculadas al contribuyente por
  razón de tutela y acogimiento", and — as a third category, "fuera de los casos
  anteriores" — "a quienes tengan atribuida por resolución judicial su guarda y
  custodia". The tranche amounts therefore reach a tutela guardian, every
  acogimiento carer, and a judicial guarda y custodia holder alike.
* **Art. 58.2** grants the under-three increase, age-independently, "en los
  supuestos de adopción o acogimiento, **tanto preadoptivo como permanente**".
  Tutela is absent from that sentence, and the acogimiento it names is qualified.

The consequence is a boundary no single flag can carry: a **temporal** acogimiento
carer is assimilated for the tranches (58.1) and excluded from the supplement
(58.2). Collapsing the two acogimiento shapes onto one member would leave that
carer no honest value to record, so they would select the entitling one and take
a supplement the statute withholds — an over-grant produced by the axis that
exists to correct an under-grant. The two are therefore separate members, and
:attr:`DescendantRelacion.ACOGIMIENTO_TEMPORAL` is deliberately non-entitling
rather than merely unused.

:attr:`DescendantRelacion.DESCENDIENTE` is the default, so the ABSENCE of a
declared relación means an ordinary descendant — the overwhelming case, which
would otherwise force every filer to answer a question that concerns a minority.

Tutela is one member. The 2021 reform (Ley 8/2021) replaced tutela over minors
with the *representación legal* / *curatela* successors, but no LIRPF provision
distinguishes them from tutela for this purpose, so splitting the member would
encode a difference the statute does not draw.

Which members open the Art. 58.2 window is declared once, as
:data:`ART_58_2_ENTITLING_RELACIONES`, rather than restated at each predicate:
the whole point of the axis is that the entitling set is narrower than the
assimilated set, and two hand-maintained copies of that judgement is how the
narrower one drifts back to the wider.

See Also:
    :class:`~domain.contribuyente.DescendantInfo`
        Carries this axis as its ``relacion`` field alongside the two named
        entry-event dates the Art. 58.2 window anchors on.
"""

from __future__ import annotations

from enum import StrEnum


class DescendantRelacion(StrEnum):
    """The legal relationship linking one descendant to the contribuyente.

    The value byte-equals the stored fact token, so a member compares, hashes,
    and JSON-serialises identically to its string.

    Attributes:
        DESCENDIENTE: An ordinary descendant — biological or otherwise
            established filiation. The default: an absent relación fact means
            this. Takes the Art. 58.1 tranches; reaches the Art. 58.2 increase
            only through the ordinary age-under-three limb, never through the
            age-independent entry-event limb.
        ADOPTADO: An adopted descendant (Art. 58.2 "adopción"). Entitling: the
            window anchors on the Registro Civil inscription, or on the
            resolución judicial o administrativa where inscription is not
            required.
        ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE: An acogimiento placement of the
            two shapes Art. 58.2 names explicitly. Entitling, anchored on the
            first entitling acogimiento resolución.
        ACOGIMIENTO_TEMPORAL: A temporal acogimiento placement. Assimilated by
            Art. 58.1 — the tranches apply — but ABSENT from Art. 58.2's
            "tanto preadoptivo como permanente", so the increase does not.
            This member exists precisely to give that carer a truthful value.
        TUTELA: Tutela, and its post-2021 legal-representation successors.
            Assimilated by Art. 58.1 for the tranches; omitted from Art. 58.2,
            so it never opens the entry-event window.
        GUARDA_Y_CUSTODIA_JUDICIAL: A minor whose guarda y custodia is held by
            the contribuyente through a resolución judicial, outside tutela and
            outside every acogimiento shape. Art. 58.1 assimilates it
            positively and as a THIRD category — "o, fuera de los casos
            anteriores, a quienes tengan atribuida por resolución judicial su
            guarda y custodia" — so the tranches apply. It is absent from
            Art. 58.2, so the entry-event window never opens, and Art. 81.1
            excludes it BY NAME, so the deducción por maternidad never reaches
            it.
    """

    DESCENDIENTE = "descendiente"
    ADOPTADO = "adoptado"
    ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE = "acogimiento_preadoptivo_o_permanente"
    ACOGIMIENTO_TEMPORAL = "acogimiento_temporal"
    TUTELA = "tutela"
    GUARDA_Y_CUSTODIA_JUDICIAL = "guarda_y_custodia_judicial"


ART_58_2_ENTITLING_RELACIONES: frozenset[DescendantRelacion] = frozenset(
    {
        DescendantRelacion.ADOPTADO,
        DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE,
    },
)
"""The relaciones whose entry event opens the Art. 58.2 age-independent window.

Derived from the statute's own enumeration — "adopción o acogimiento, tanto
preadoptivo como permanente" — and deliberately narrower than the Art. 58.1
assimilated set, which additionally reaches tutela and temporal acogimiento.
Every predicate testing the entry-event limb reads this set rather than
re-listing members, so the narrowing cannot be lost at one call site while
holding at another.

It doubles as the permission set for the acogimiento resolución date, and that
is one judgement rather than two reused by coincidence. The date field means the
first **entitling** resolución, so a temporal placement has no truthful value to
put in it — recording one would both misdescribe the placement and leave an
entitling anchor sitting on a record the statute excludes, which is exactly how
the excluded case becomes reachable through the only available field. An
adoptado record may carry one, because a fostered-then-adopted child's window
anchors on the earlier placement: Art. 58.2's three periods are a CAP measured
from the first entitling event, not a count restarted by the adoption.
"""


ART_81_1_MATERNIDAD_RELACIONES: frozenset[DescendantRelacion] = frozenset(
    {
        DescendantRelacion.DESCENDIENTE,
        DescendantRelacion.ADOPTADO,
        DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE,
        DescendantRelacion.TUTELA,
    },
)
"""The relaciones the Art. 81.1 deducción por maternidad reaches.

A THIRD set on this axis, and deliberately not merged with either of the other
two. Art. 58.1 assimilates the widest group, Art. 58.2 narrows to the entry-event
limb, and Art. 81.1 draws its own line again — three statutes, three populations.
Conflating any two of them is how a carer entitled under one statute silently
collects under another, which is exactly the defect this set closes: the deducción
gated only on the Art. 58.1 test, which assimilates temporal acogimiento, so a
temporal carer took a full twelve months the authority excludes outright.

The authority states the exclusion directly and it is byte-stable across every
manual vintage the registry serves, 2020 through 2025: the deducción "no resulta
aplicable en el caso de nietos y demás descendientes por consanguinidad distintos
de los hijos, ni cuando se trate de acogimientos familiares simples, de urgencia o
temporales, ni en los casos de menores respecto de los que se tenga la guarda y
custodia por resolución judicial".

Tutela is INCLUDED, and that is stated positively rather than inferred from the
exclusion list: "en el supuesto de tutela, el tutor tendrá derecho al importe de
la deducción que corresponda al tiempo que reste hasta que el tutelado alcance los
tres años de edad". The same passage names "tutela o acogimiento permanente o de
delegación de guarda para la convivencia preadoptiva" as the qualifying set, which
is why the preadoptivo-or-permanente member belongs here while the temporal one
does not.

Judicial guarda y custodia IS now expressible, and its exclusion here is by
name rather than by absence: the passage above bars the deducción "en los casos
de menores respecto de los que se tenga la guarda y custodia por resolución
judicial". It reaches this set the same way every other non-member does — by
not being added — but the omission is a reading of the statute, not a gap.

A recorded tension, unresolved, so that a later reader meets it as a known
question rather than as a discovery. Three sentences before that exclusion, the
same section's multi-filer allocation rule names the same population: "en el
supuesto de existencia de varios contribuyentes con derecho a la deducción por
maternidad respecto del mismo tutelado o acogido o menor bajo su guarda y
custodia para la convivencia preadoptiva o por resolución judicial, su importe
deberá repartirse entre ellos por partes iguales". Both sentences are
byte-stable across 2020-2025. The adopted reading is that the allocation rule
is conditional rather than a grant — it opens on contributors "con derecho a"
the deducción, and says how to divide an entitlement determined elsewhere,
which for this population the exclusion denies. That reading is supported by
the conditional wording but is NOT settled by it, because a drafter naming a
population in an allocation rule plausibly expected some of it to qualify. The
exclusion is the more specific statement and is the one implemented; the
conservative direction is the same either way, since a member outside this set
contributes zero months.

One exclusion the axis still cannot express, recorded rather than silently
approximated. A NIETO has no member, so a cohabiting grandchild under three is
Art. 58.1-eligible and Art. 81.1-excluded but currently takes the deducción — a
representability gap in the axis, not a gate that can be tightened here. It is
deliberately NOT modelled as a member: hijo, nieto and bisnieto are one
relationship type differing by generational DEGREE, and degree is a
differently-shaped fact from legal basis. Encoding it here would bolt a second
axis onto this one.
"""


__all__ = [
    "ART_58_2_ENTITLING_RELACIONES",
    "ART_81_1_MATERNIDAD_RELACIONES",
    "DescendantRelacion",
]
