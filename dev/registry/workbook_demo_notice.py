"""Fictional scenario disclosures for demonstration workbooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workbook_demo_cases import DemoCase

DEMO_NOTICE = (
    "EJEMPLO FICTICIO. Generado desde las declaraciones actuales del registro para probar el diseño. "
    "No contiene datos de un contribuyente ni constituye una declaración presentada. "
    "Las entradas de la rama de cálculo demostrada se fijan explícitamente a cero salvo los importes indicados; "
    "las demás entradas permanecen sin dato. Las páginas y secciones conservan su estado de revisión."
)


def _notice_base(case: DemoCase) -> str:
    notice = DEMO_NOTICE + (
        " Los resultados por actividad del modelo 131 son datos introducidos; todavía no se calculan "
        "automáticamente a partir del rendimiento y el porcentaje."
        if case.modelo == "131"
        else ""
    )
    if case.modelo == "303":
        notice += (
            " Las bases y cuotas son entradas ficticias del ejemplo; los totales y el resultado usan las fórmulas "
            "del modelo. Los datos de identificación y, cuando corresponde, actividad anual proceden "
            "de hechos guardados del ejemplo "
            "y no se recalculan al editar las cifras. Este documento no está listo para presentar."
        )
    if case.modelo == "390" and case.revision in {"2024", "2025"}:
        notice += (
            " Ejemplo ficticio de actividades con regímenes de deducción diferenciados: "
            "las nueve cuotas de cada grupo se han fijado en 100, 200 y 300 euros respectivamente. "
            "Las sumas de deducciones se calculan con las fórmulas del registro. "
            "Las bases, la identificación, la liquidación anual y las demás secciones siguen sin datos; "
            "este documento no está listo para presentar."
        )
    elif case.modelo == "390":
        notice += (
            " Resumen anual ficticio: bases de ventas de 48.000 euros, IVA devengado de 10.080 euros "
            "y cuotas deducibles de 3.360 euros. Las bases y cuotas son datos introducidos; "
            "las cuotas por tipo no se recalculan al cambiar la base. Los totales usan las fórmulas "
            "del modelo. El detalle de las deducciones, la identificación y otras secciones siguen "
            "pendientes; este documento no está listo para presentar."
        )
    if case.modelo == "136":
        notice += (
            " La cuantía exenta es un dato introducido para este ejemplo de titular único; "
            "no se calcula automáticamente el reparto de la exención. El importe ingresado se declara "
            "por separado y no prueba que se haya efectuado un pago."
        )
    if case.modelo == "309":
        notice += (
            " La base, el tipo y las cuotas por fila son datos introducidos; las cuotas no se recalculan "
            "al cambiar la base o el tipo. Los totales 22 y 24 sí se calculan con las fórmulas del modelo. "
            "El importe mostrado en Ingreso es el resultado a ingresar y no acredita un pago. "
            "Los datos sin completar siguen pendientes; este ejemplo no está listo para presentar."
        )
    if case.modelo == "322":
        notice += (
            " Las bases, tipos y cuotas por operación son entradas del ejemplo; las cuotas por fila no se "
            "recalculan al cambiar la base o el tipo. Los totales y el resultado sí usan las fórmulas del modelo. "
            "Los 150 euros de pago a cuenta son un dato ficticio, no un pago acreditado. "
            "Sin actividad se deja sin marcar porque este ejemplo tiene operaciones; "
            "un resultado cero no prueba ausencia de actividad. "
            "Los códigos y datos pendientes no se han completado: este ejemplo no está listo para presentar."
        )
    if case.modelo == "122":
        notice += (
            " La deducción, el abono anticipado y el resultado de 300 euros son datos introducidos. "
            "El resultado no se recalcula automáticamente al modificar los importes de las deducciones. "
            "Este ejemplo utiliza el diseño de 2018; la presentación histórica de 2017 está pendiente."
        )
    return notice


def _notice_part_1(case: DemoCase, notice: str) -> str:
    if case.modelo == "145":
        notice = (
            "EJEMPLO FICTICIO. Comunicación al pagador, no declaración presentada a la AEAT. Este borrador conserva "
            "los campos del diseño de 2012; no reproduce íntegramente el formulario vigente. "
            "No calcula retenciones. Las firmas y el acuse de recibo están sin completar. "
            "Los datos no facilitados permanecen sin dato; no se sustituyen por cero."
        )
    if case.modelo == "232":
        notice = (
            "EJEMPLO FICTICIO. Declaración informativa de operaciones vinculadas. "
            "Los importes sin IVA de 250.000 euros de ingreso y 175.000 euros de pago son datos introducidos "
            "de dos entidades jurídicas inventadas. Se muestran por separado, sin compensarlos; "
            "este modelo no calcula una cuota tributaria. Las demás operaciones, códigos y datos de "
            "identificación permanecen sin dato. Las fechas corresponden al período anual seleccionado; "
            "este ejemplo no representa un ejercicio fiscal distinto del año natural. Las explicaciones "
            "de los códigos todavía no están completas. No constituye una declaración presentada."
        )
    if case.modelo == "180":
        notice = (
            "EJEMPLO FICTICIO. Resumen anual de arrendamientos con dos perceptores inventados. "
            "El detalle guardado muestra bases de 12.000 y 6.000 euros y retenciones de 2.280 y 1.140 euros. "
            "Las casillas 02 y 03 copian los totales anuales de origen: 18.000 y 3.420 euros. "
            "El detalle es de consulta; editar los totales de origen no modifica ni vuelve a sumar sus registros. "
            "No constituye una declaración presentada. Los datos no aportados permanecen sin dato."
        )
    if case.modelo == "181":
        notice = (
            "EJEMPLO FICTICIO PARA EL EJERCICIO 2025. Hoja resumen y una operación de préstamo inventada. "
            "Las casillas 01 a 05 siguen la hoja resumen oficial; el detalle adapta el diseño electrónico de 2022. "
            "Los totales y los importes del préstamo son datos declarados independientes: no se recalculan entre sí. "
            "Los datos no aportados permanecen sin dato. "
            "La firma y la repetición de varias operaciones están pendientes. "
            "El nuevo diseño aplicable desde el ejercicio 2026 no está representado en este ejemplo. "
            "No constituye una declaración presentada."
        )
    if case.modelo == "185":
        notice = (
            "EJEMPLO FICTICIO DE MARZO DE 2026. Una afiliada inventada, con datos del mes declarado, "
            "febrero y enero. Ejemplo de información de la Seguridad Social: no corresponde a una mutualidad. "
            "A significa alta; G, régimen general; jornada 1, completa; pluriactividad N, un solo régimen. "
            "Los días 31, 28 y 15 y el total de un registro son datos declarados, no resultados calculados. "
            "La afiliación 000000000001 es ficticia. Los datos no aportados permanecen sin dato. "
            "El documento adapta el diseño electrónico oficial; no es una declaración presentada. "
            "La repetición de varios afiliados y la ocultación de campos no aplicables están pendientes."
        )
    if case.modelo == "188":
        notice = (
            "EJEMPLO FICTICIO. Una perceptora de rendimientos dinerarios de un seguro. "
            "Rendimiento y base de 1.000 euros, tipo declarado del 19 % y retención de 190 euros. "
            "Todos son importes declarados independientes: todavía no se recalculan entre sí. "
            "El resumen también contiene valores declarados, no una suma automática del detalle. "
            "La provincia 08 es Barcelona y la modalidad 1 corresponde a rendimientos dinerarios. "
            "La identidad del declarante es ficticia e introducida manualmente; no procede de un perfil real. "
            "El teléfono, los justificantes y las circunstancias no aportadas quedan sin dato. "
            "La repetición de perceptores y los controles entre campos están pendientes. "
            "No constituye una declaración presentada."
        )
    if case.modelo == "156":
        notice = (
            "EJEMPLO FICTICIO. Dos afiliados y doce meses de cotización por persona. "
            "S indica que cotizó al menos un día; N indica que no cotizó. "
            "Cada situación y cada cuota son datos independientes del ejemplo. "
            "El número de afiliados se obtiene de los dos registros del ejemplo. "
            "No se calcula una deducción ni un resultado fiscal. Los datos no aportados quedan sin dato. "
            "El domicilio es ficticio. La fecha y los datos de quien firma quedan sin dato; el espacio de firma "
            "está reservado para el papel y no acredita una firma electrónica. "
            "El detalle muestra los datos guardados de cada afiliado; sus cuotas no se recalculan.  "
            "No constituye una declaración presentada."
        )
    return notice


def _notice_part_2(case: DemoCase, notice: str) -> str:
    if case.modelo == "194":
        notice = (
            "EJEMPLO FICTICIO. Cinco operaciones de una misma perceptora. "
            "Dos bases positivas suman 125 euros; tres bases negativas o cero suman 50 euros en valor absoluto. "
            "Las retenciones declaradas suman 23,75 euros. El resumen y el detalle se generan a partir "
            "de las mismas operaciones. Las bases y el tipo del 19 % son supuestos del ejemplo, "
            "no una determinación fiscal. El detalle guardado es de consulta; sus celdas no recalculan el resumen. "
            "Los datos no aportados quedan sin dato. Firma y controles entre campos pendientes. "
            "No constituye una declaración presentada."
        )
    if case.modelo == "193":
        source_notice = (
            "Los totales proceden de los importes anuales del modelo 123. "
            if case.revision == "2024"
            else "Los totales proceden de los importes agregados de los perceptores. "
        )
        notice = (
            "EJEMPLO FICTICIO. Dos perceptores con bases declaradas de 1.000 y 2.000 euros, "
            "retenciones de 190 y 380 euros y un gasto de custodia de 25 euros. "
            + source_notice
            + "El tipo del 19 % y las bases son supuestos del ejemplo, no una determinación fiscal. "
            "El detalle guardado es de consulta: editar los totales de origen "
            "no modifica ni vuelve a sumar sus registros. "
            "Los gastos y las retenciones ingresadas del resumen son importes declarados independientes. "
            "Los datos no aportados quedan sin dato. La empresa y sus perceptores son ficticios. "
            "La firma y los controles entre campos siguen pendientes. No constituye una declaración presentada."
        )
    if case.modelo == "190":
        source_notice = (
            "El resumen usa los totales anuales de origen del modelo 111: 42.000 y 4.200 euros. "
            if case.revision == "2025-y-siguientes"
            else "El resumen suma los importes agregados por concepto del detalle: 42.000 y 4.200 euros. "
        )
        notice = (
            "EJEMPLO FICTICIO. Dos perceptores de rendimientos del trabajo, clave A. "
            "Importes declarados de 24.000 y 18.000 euros, con retenciones de 2.400 y 1.800 euros. "
            + source_notice
            + "Se supone que no hay otras percepciones anuales. El detalle guardado es de consulta: "
            "editar los totales de origen no modifica ni vuelve a sumar sus registros. "
            "Las circunstancias personales no aportadas permanecen sin dato. "
            "La empresa declarante y su NIF son ficticios y distintos de la identidad del presentador. "
            "La firma y los controles entre campos siguen pendientes. "
            "Desde 2025 se adapta el diseño electrónico, sin la numeración de la antigua hoja impresa. "
            "No constituye una declaración presentada."
        )
    if case.modelo == "349":
        notice = (
            "EJEMPLO FICTICIO. Dos facturas de 7.000 y 5.000 euros del mismo operador se agrupan "
            "en una operación de 12.000 euros; otro operador aporta 4.500 euros. "
            "El resumen muestra dos operadores y 16.500 euros. Una rectificación del tercer trimestre "
            "sustituye 1.000 euros por 900 euros: la casilla 04 recoge 900 euros, no la diferencia de −100. "
            "El resumen y el detalle proceden de las mismas facturas ficticias procesadas por la aplicación. "
            "Las claves E y S identifican entregas de bienes y prestaciones de servicios, respectivamente. "
            "El detalle guardado es de consulta: editar una celda de la hoja no vuelve a agregar las facturas. "
            "Los datos no aportados permanecen sin dato. No constituye una declaración presentada."
        )
    if case.modelo == "189":
        notice = (
            "EJEMPLO FICTICIO. Una entidad depositaria y una titular inventadas. "
            "Diez valores, nominal unitario de 100 euros y valoración declarada de 1.500 euros. "
            "El nominal no es el valor de mercado: esta hoja no calcula la valoración multiplicándolo. "
            "Las claves A corresponden al mercado secundario oficial español y a acciones o participaciones. "
            "La participación declarada es del 100 %. El total y el detalle son datos independientes; "
            "todavía no se agregan automáticamente. La identificación del valor, el contacto y los "
            "justificantes no aportados quedan sin dato. La repetición de titulares, la firma y los "
            "controles entre campos están pendientes. No constituye una declaración presentada."
        )
    if case.modelo == "184":
        notice = (
            "EJEMPLO FICTICIO. Entidad en atribución de rentas con dos miembros inventados. "
            "Los ingresos de 10.000 euros, gastos de 4.000 euros y renta atribuible de 6.000 euros "
            "son datos introducidos. "
            "El registro no define fórmulas para recalcularlos. Las participaciones del 60 % y 40 % y los importes "
            "atribuidos de 3.600 y 2.400 euros pertenecen al detalle guardado: "
            "no cambian al editar la renta de la entidad. "
            "La clave D identifica actividades económicas; la subclave 01 de la entidad "
            "indica rentas obtenidas en España "
            "y la subclave 01 de los miembros indica estimación directa normal. "
            "Este ejemplo contiene una sola renta de la entidad. "
            "Los campos de otras clases de renta permanecen sin dato. "
            "No constituye una declaración presentada."
        )
    return notice


def _notice_part_3(case: DemoCase, notice: str) -> str:
    if case.modelo in {"202", "222"}:
        rate_count = "cuatro" if case.revision == "2025-y-siguientes" else "dos"
        notice += (
            f" Los {rate_count} porcentajes son ficticios para comprobar las filas de la tabla; "
            "no determinan el tipo que corresponde a una empresa. "
        )
        if case.modelo == "222" and case.revision != "2025-y-siguientes":
            notice += (
                "La base total de la casilla 19 y la segunda base de la casilla 23 se calculan desde las entradas. "
            )
        elif case.modelo == "222":
            notice += "La base total de la casilla 19 se calcula desde las entradas. "
        else:
            notice += "La base total de la casilla 19 es un dato introducido. "
        notice += (
            "Este borrador cubre las casillas de la parte 1; "
            "las opciones de régimen y los desgloses de la parte 2 siguen pendientes. "
        )
        if case.modelo == "202":
            notice += (
                "Los datos de identificación permanecen sin dato: la aplicación todavía no admite "
                "un perfil de presentación completo para este modelo."
            )
        else:
            notice += "Este ejemplo no aporta un perfil del grupo fiscal; sus datos de identificación siguen sin dato."
    return notice


def demonstration_notice(case: DemoCase) -> str:
    """Describe the assumptions and remaining unknowns of a fictional case."""
    notice = _notice_base(case)
    notice = _notice_part_1(case, notice)
    notice = _notice_part_2(case, notice)
    return _notice_part_3(case, notice)
