# Pag. 1

130 DISEÑO DE REGISTRO 28/02/2007
Agencia Tributaria
Modelo 130 Diseño de registro. Ejercicio 2007
vers. 1.0 IRPF - Actividades económicas en estimación directa - Pago fraccionado
Nº Posic. Lon Tipo Descripción Validación Contenido Uso
1 1 3 Num Modelo OBLIGATORIO Constante "130"
2 4 2 Num Página OBLIGATORIO Constante "01" MI
3 6 1 A Indicador de página complementaria En blanco MI
4 7 1 A Tipo Declaración OBLIGATORIO PI Ver nota
5 8 5 Num Código Administración OBLIGATORIO Incluido en el fichero ADMON.TXT MI
6 13 9 An Identificación (1) - NIF OBLIGATORIO Cualquier NIF válido P.F.
7 22 4 An Identificación (1) - Comienzo del primer apellido en personas físicas OBLIGATORIO PI PI
8 26 30 An Identificación (1) - Apellidos
9 56 15 A Identificación (1) - Nombre
10 71 4 Num Devengo (2) - Ejercicio OBLIGATORIO
11 75 2 An Devengo (2) - Período OBLIGATORIO "1T","2T","3T" ó "4T"
12 77 13 N Liquidación (3) - I. Activ. económicas estimac. Directa - Ingresos computables [01] 11 enteros y 2 decimales
13 90 13 N Liquidación (3) - I. Activ. económicas estimac. Directa - Gastos fiscalmente deducibles [02] 11 enteros y 2 decimales
14 103 13 N Liquidación (3) - I. Activ. económicas estimac. Directa - Rendimiento neto [03] 11 enteros y 2 decimales
15 116 13 N Liquidación (3) - I. Activ. económicas estimac. Directa - 20% de la casilla 03 [04] 11 enteros y 2 decimales
16 129 13 N Liquidación (3) - I. Activ. económicas estimac. Directa - A deducir - Pagos fraccionados [05] 11 enteros y 2 decimales
17 142 13 N Liquidación (3) - I. Activ. económicas estimac. Directa - A deducir - Retenciones e ingr. a cuenta [06] 11 enteros y 2 decimales
18 155 13 N Liquidación (3) - I. Activ. económicas estimac. Directa - Pago fraccionado [07] 11 enteros y 2 decimales
19 168 13 N Liquidación (3) - II. Activ. agrícola. estimac. directa - Volumen de ingresos [08] 11 enteros y 2 decimales
20 181 13 N Liquidación (3) - II. Activ. agrícola. estimac. directa - 2% de la casilla 08 [09] 11 enteros y 2 decimales
21 194 13 N Liquidación (3) - II. Activ. agrícola. estimac. directa - A deducir- Retenciones e ingr. a cuenta [10] 11 enteros y 2 decimales
22 207 13 N Liquidación (3) - II. Activ. agrícola estimac. directa - Pago fraccionado [11] 11 enteros y 2 decimales
23 220 13 N Liquidación (3) - III. Total liquidación - Suma de pagos fraccionados (12) 11 enteros y 2 decimales
24 233 13 N Liquidación (3) - III. Total liquidación - A deducir - Resultado de las anteriores declaraciones [13] 11 enteros y 2 decimales
25 246 13 N Liquidación (3) - III. Total liquidación - Resultado de la declaración [14] 11 enteros y 2 decimales
26 259 13 N Ingreso (4) - Importe del ingreso [I] 11 enteros y 2 decimales
"0" No consta, "1" Efectivo,
"2" Adeudo en cuenta, "3"
27 272 1 Num Ingreso (4) - Forma de pago Domiciliación
28 273 4 An Ingreso (4) - Código cuenta cliente - Entidad
29 277 4 An Ingreso (4) - Código cuenta cliente - Sucursal
30 281 2 An Ingreso (4) - Código cuenta cliente - DC
31 283 10 An Ingreso (4) - Código cuenta cliente - Número de cuenta
32 293 16 An Complementaria (6) - Código electrónico declaración anterior PI
33 309 13 An Declaración complementaria (6) - nº justificante declaración anterior
34 322 100 An Persona de Contacto OBLIGATORIO PI PI
35 422 9 An Teléfono OBLIGATORIO PI PI
36 431 350 An Observaciones PI
37 781 16 A Firma (7) - Localidad MI
38 797 2 An Firma (7) - Fecha: Día MI
39 799 10 A Firma (7) - Fecha: Mes MI
40 809 4 An Firma (7) - Fecha: Año MI
41 813 2 An Fin de Registro. Constante CRLF (Hexadecimal 0D0A, Decimal 1310) MI
Total: 814
Nota: El uso MI significa que sólo se tiene en cuenta en el módulo de impresión y el uso PI significa que sólo tiene utilidad en las presentaciones por Internet.
PI: El tipo de declaración puede ser: G (cuenta corriente tributaria-ingreso) I (ingreso) N(negativa) U (domiciliación del ingreso en CCC)
MI: En caso de declaración negativa consígnese "N". En el caso de declaración NO negativa, se considerará válido cualquier otro carácter alfanumérico.
Página 1 de 1