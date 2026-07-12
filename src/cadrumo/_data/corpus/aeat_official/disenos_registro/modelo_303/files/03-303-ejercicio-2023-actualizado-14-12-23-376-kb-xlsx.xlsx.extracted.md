# DP30300

 | Agencia Tributaria
Modelo 303
versión 1.09 |  | Diseño de registro
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "303"
3 | 6 | 1 | An | Discriminante |  | "0"
4 | 7 | 4 | An | Ejercicio de devengo (EEEE) |  | Nota 2
5 | 11 | 2 | An | Período. (PP) |  | "01"..."12" o "1T"…"4T"
6 | 13 | 5 | An | Tipo y cierre |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Tipo+> |  | "</T3030AAAAPP0000>"
Total |  | Variable
Nota 1
A cumplimentar por las entidades desarrolladoras (EEDD):
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota2:
EEEE indica las cuatro cifras del ejercicio en curso
Nota 3
El número máximo de ocurrencias de la página 2 del modelo es 6 para las actividades del régimen agrícolas, ganaderas y forestales; y 6 para las actividades
del régimen simplificado (excepto agrícolas, ganaderas y forestales). Por lo que el número máximo de páginas 2 será 3.
Nota 4
Este Diseño de Registro deber ser utilizado para las presentaciones de todos los periodos de 2023 y ejercicios posteriores.

# DP30301

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num | Modelo. | Obligatorio | Constante "303"
3 | 6 | 5 | Num | Página. | Obligatorio | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 1 | A | Tipo Declaración | Obligatorio PI | Nota 1
7 | 14 | 9 | An | Identificación (1) - NIF | Obligatorio
8 | 23 | 80 | An | Identificación (1) - Apellidos y nombre o Razón social | Obligatorio
9 | 103 | 4 | Num | Devengo (2) - Ejercicio | Obligatorio
10 | 107 | 2 | An | Devengo (2) - Período | Obligatorio | "01",..., "12" o "1T" … "4T"
11 | 109 | 1 | Num | Identificación (1) - Tributación exclusivamente foral. Sujeto pasivo que tributa exclusivamente a una Administración tributaria Foral con IVA a la importación liquidado por la Aduana pendiente de ingreso |  | "1" SI,                                                          "2" NO.                                                    Nota 5
12 | 110 | 1 | Num | Identificación (1) - Sujeto pasivo inscrito en el Registro de devolución mensual (art. 30 RIVA) |  | "1" SI, "2" NO. Nota 5
13 | 111 | 1 | Num | Identificación (1) - Sujeto pasivo que tributa exclusivamente en régimen simplificado |  | "1" SI (sólo RS),
 "2" NO (RG + RS),
"3" NO (sólo RG).                                    Nota 5
14 | 112 | 1 | Num | Identificación (1) - Autoliquidación conjunta |  | "1" SI, "2" NO. Nota 5
15 | 113 | 1 | Num | Identificación (1) - Sujeto pasivo acogido al régimen especial del criterio de Caja (art. 163 undecies LIVA) |  | "1" SI, "2" NO. Nota 5
16 | 114 | 1 | Num | Identificación (1) - Sujeto pasivo destinatario de operaciones acogidas al régimen especial del criterio de caja |  | "1" SI, "2" NO. Nota 5
17 | 115 | 1 | Num | Identificación (1) - Opción por la aplicación de la prorrata especial (art. 103.Dos.1º LIVA) |  | Nota 6. Nota 5
18 | 116 | 1 | Num | Identificación (1) - Revocación de la opción por la aplicación de la prorrata especial |  | Nota 6. Nota 5
19 | 117 | 1 | Num | Identificación (1) - Sujeto pasivo declarado en concurso de acreedores en el presente período de liquidación |  | "1" SI, "2" NO. Nota 5
20 | 118 | 8 | An | Identificación (1) - Fecha en que se dictó el auto de declaración de concurso |  | DDMMYYYY
21 | 126 | 1 | An | Identificación (1) - Tipo de autoliquidación si se ha dictado auto de declaración de concurso en este período |  | "1" SI Preconcursal, 
"2" SI Postconcursal                             blanco NO.                                              Nota 5
22 | 127 | 1 | Num | Identificación (1) - Sujeto pasivo acogido voluntariamente al SII |  | "1" SI,                                                          "2" NO.                                                    Nota 5
23 | 128 | 1 | Num | Identificación (1) - Sujeto pasivo exonerado de la Declaración-resumen anual del IVA, modelo 390 |  | Nota 4. Nota 5
24 | 129 | 1 | Num | Identificación (1) - Sujeto pasivo con volumen anual de operaciones distinto de cero (art. 121 LIVA) |  | Nota 3. Nota 5
25 | 130 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [150] |  | 15 enteros y 2 decimales
26 | 147 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [151] |  | Constante "00000"
27 | 152 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [152] |  | 15 enteros y 2 decimales
28 | 169 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [01] |  | 15 enteros y 2 decimales
29 | 186 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [02] |  | Constante "00400". Nota 7
30 | 191 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [03] |  | 15 enteros y 2 decimales
31 | 208 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [153] |  | 15 enteros y 2 decimales
32 | 225 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [154] |  | Constante "00500". Nota 7
33 | 230 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [155] |  | 15 enteros y 2 decimales
34 | 247 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [04] |  | 15 enteros y 2 decimales
35 | 264 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [05] |  | Constante "01000". Nota 7
36 | 269 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [06] |  | 15 enteros y 2 decimales
37 | 286 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [07] |  | 15 enteros y 2 decimales
38 | 303 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [08] |  | Constante "02100". Nota 7
39 | 308 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [09] |  | 15 enteros y 2 decimales
40 | 325 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Adquisiciones intracomunitarias de bienes y servicios - Base imponible  [10] |  | 15 enteros y 2 decimales
41 | 342 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Adquisiciones intracomunitarias de bienes y servicios - Cuota [11] |  | 15 enteros y 2 decimales
42 | 359 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Otras operaciones con inversión del sujeto pasivo (excepto. adq. intracom) - Base imponible  [12] |  | 15 enteros y 2 decimales
43 | 376 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Otras operaciones con inversión del sujeto pasivo (excepto. adq. intracom) - Cuota [13] |  | 15 enteros y 2 decimales
44 | 393 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificación bases y cuotas- Base imponible  [14] |  | 15 enteros y 2 decimales
45 | 410 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificación bases y cuotas - Cuota [15] |  | 15 enteros y 2 decimales
46 | 427 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Base imponible [156] |  | 15 enteros y 2 decimales
47 | 444 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [157] |  | Constante "00175". Nota 7
48 | 449 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [158] |  | 15 enteros y 2 decimales
49 | 466 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Base imponible [16] |  | 15 enteros y 2 decimales
50 | 483 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [17] |  | "00000", "00050", "00062"
51 | 488 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [18] |  | 15 enteros y 2 decimales
52 | 505 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Base imponible [19] |  | 15 enteros y 2 decimales
53 | 522 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [20] |  | Constante "00140". Nota 7
54 | 527 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [21] |  | 15 enteros y 2 decimales
55 | 544 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Base imponible [22] |  | 15 enteros y 2 decimales
56 | 561 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [23] |  | Constante "00520". Nota 7
57 | 566 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [24] |  | 15 enteros y 2 decimales
58 | 583 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificaciones bases y cuotas del recargo de equivalencia - Base imponible [25] |  | 15 enteros y 2 decimales
59 | 600 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificaciones bases y cuotas del recargo de equivalencia - Cuota [26] |  | 15 enteros y 2 decimales
60 | 617 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Total cuota devengada ( [152] + [03] + [155] + [06] + [09] + [11] + [13] + [15] + [158] + [18] + [21] + [24] + [26] ) [27] |  | 15 enteros y 2 decimales
61 | 634 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores corrientes - Base [28] |  | 15 enteros y 2 decimales
62 | 651 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores corrientes - Cuota [29] |  | 15 enteros y 2 decimales
63 | 668 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores con bienes de inversión - Base [30] |  | 15 enteros y 2 decimales
64 | 685 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores con bienes de inversión - Cuota [31] |  | 15 enteros y 2 decimales
65 | 702 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en las importaciones de bienes corrientes - Base [32] |  | 15 enteros y 2 decimales
66 | 719 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en las importaciones de bienes corrientes - Cuota [33] |  | 15 enteros y 2 decimales
67 | 736 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en las importaciones de bienes de inversión - Base [34] |  | 15 enteros y 2 decimales
68 | 753 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en las importaciones de bienes de inversión - Cuota [35] |  | 15 enteros y 2 decimales
69 | 770 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - En adquisiciones intracomunitarias de bienes y servicios corrientes - Base [36] |  | 15 enteros y 2 decimales
70 | 787 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - En adquisiciones intracomunitarias de bienes y servicios corrientes - Cuota [37] |  | 15 enteros y 2 decimales
71 | 804 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - En adquisiciones intracomunitarias de bienes de inversión - Base [38] |  | 15 enteros y 2 decimales
72 | 821 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - En adquisiciones intracomunitarias de bienes de inversión - Cuota [39] |  | 15 enteros y 2 decimales
73 | 838 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Rectificación de deducciones - Base [40] |  | 15 enteros y 2 decimales
74 | 855 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Rectificación de deducciones - Cuota [41] |  | 15 enteros y 2 decimales
75 | 872 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Compensaciones Régimen Especial A.G. y P. - Cuota [42] |  | 15 enteros y 2 decimales
76 | 889 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Regularización inversiones - Cuota [43] |  | 15 enteros y 2 decimales
77 | 906 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Regularización por aplicación del porcentaje definitivo de prorrata - Cuota [44] |  | 15 enteros y 2 decimales
78 | 923 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Total a deducir ( [29] + [31] + [33] + [35] + [37] + [39] + [41] + [42] + [43] + [44] ) - Cuota [45] |  | 15 enteros y 2 decimales
79 | 940 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Resultado régimen general ( [27] - [45] ) - Cuota [46] |  | 15 enteros y 2 decimales
80 | 957 | 600 | An | Reservado para la AEAT
81 | 1557 | 13 | An | Reservado para la AEAT - Sello electrónico reservado para la AEAT
82 | 1570 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T30301000>"
TOTAL |  | 1581 | POSICIONES
Nota 1:
 | PI: El tipo de declaración puede ser: C (solicitud de compensación) D (devolución) G (cuenta corriente tributaria-ingreso) I (ingreso) N (sin actividad/resultado cero) V (cuenta corriente tributaria -devolución)
 | U (domiciliacion del ingreso en CCC) X (Devolución por transferencia al extranjero)
Nota 2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 3:
Valor | Descripción
0 | Para todos los periodos distintos del último (12 y 4T), y en el último periodo (12 y 4T) para aquellos que No estén exonerados
1 | SI
2 | NO
Nota 4:
Valor | Descripción
0 | Para todos los periodos distintos del último (12 y 4T)
1 | SI
2 | NO
Nota 5 - Tributación exclusivamente a una Administración Foral
Todos los campos referenciados con la Nota 5, en el caso de de tributación exclusivamente a una Administración Foral, se cumplimentarán con el valor "2" NO
Salvo los siguientes campos, que en este caso, tomarán los valores que se indican:
- | Sujeto pasivo que tributa exclusivamente a una Administración tributaria Foral con IVA a la importación liquidado por la Aduana pendiente de ingreso >> "1" SI
- | Identificación (1) - Tributa exclusivamente en Régimen Simplificado (RS) >> "3" NO (sólo RG).
- | Identificación (1) - Auto de declaración de concurso dictado en el período >> blanco NO
- | Identificación (1) - Opción por la aplicación de la prorrata especial (art. 103.Dos.1º LIVA) >> "2" blanco
- | Identificación (1) - Revocación de la opción por la aplicación de la prorrata especial >> "2" blanco
Nota 6:
Valor | Descripción
1 | SI para el último periodo (12 y 4T)
2 | Blanco para periodos distintos del último (12 y 4T), y NO para el último periodo (12 y 4T)
Nota 7 - Tributación exclusivamente a una Administración Foral
Todos los campos referenciados con la Nota 7, en el caso de de tributación exclusivamente a una Administración Foral, se podrán cumplimentarán con el valor "00000"

# DP30302

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | Obligatorio | Constante "303"
3 | 6 | 5 | Num |  | Página. | Obligatorio | Constante "02000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria) |  | Nota 1
6 | 13 | 2 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Código
7 | 15 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Volumen de ingresos |  | 15 enteros y 2 decimales
8 | 32 | 6 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Índice de cuota |  | 1 entero y 5 decimales
9 | 38 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Cuota devengada |  | 15 enteros y 2 decimales
10 | 55 | 5 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 1T/2T/3T - Porcentaje ingreso a cuenta |  | 3 enteros y 2 decimales
11 | 60 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 1T/2T/3T - Ingreso a cuenta [A] |  | 15 enteros y 2 decimales
12 | 77 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 4T - Cuota soportada operaciones corrientes |  | 15 enteros y 2 decimales
13 | 94 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 4T
 - Cuota anual derivada del regimen simplificado [B] |  | 15 enteros y 2 decimales
14 | 111 | 2 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Código
15 | 113 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Volumen de ingresos |  | 15 enteros y 2 decimales
16 | 130 | 6 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Índice de cuota |  | 1 entero y 5 decimales
17 | 136 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Cuota devengada |  | 15 enteros y 2 decimales
18 | 153 | 5 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 1T/2T/3T - Porcentaje ingreso a cuenta |  | 3 enteros y 2 decimales
19 | 158 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 1T/2T/3T - Ingreso a cuenta [A] |  | 15 enteros y 2 decimales
20 | 175 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 4T - Cuota soportada operaciones corrientes |  | 15 enteros y 2 decimales
21 | 192 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 4T
 - Cuota anual derivada del regimen simplificado [B] |  | 15 enteros y 2 decimales
22 | 209 | 4 | An | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Epigrafe IAE
23 | 213 | 1 | An | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Epigrafe IAE
 - Indicador auxiliar de actividad en el caso de epígrafes 691.9 y 722 |  | blanco, "1" o "2"  (Nota 3)
24 | 214 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 1 - Nº Unidades |  | 8 enteros y 2 decimales
25 | 224 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 1 - Importe |  | 15 enteros y 2 decimales
26 | 241 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 2 - Nº Unidades |  | 8 enteros y 2 decimales
27 | 251 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 2 - Importe |  | 15 enteros y 2 decimales
28 | 268 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 3 - Nº Unidades |  | 8 enteros y 2 decimales
29 | 278 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 3 - Importe |  | 15 enteros y 2 decimales
30 | 295 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 4 - Nº Unidades |  | 8 enteros y 2 decimales
31 | 305 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 4 - Importe |  | 15 enteros y 2 decimales
32 | 322 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 5 - Nº Unidades |  | 8 enteros y 2 decimales
33 | 332 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 5 - Importe |  | 15 enteros y 2 decimales
34 | 349 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 6 - Nº Unidades |  | 8 enteros y 2 decimales
35 | 359 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 6 - Importe |  | 15 enteros y 2 decimales
36 | 376 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 7 - Nº Unidades |  | 8 enteros y 2 decimales
37 | 386 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 7 - Importe |  | 15 enteros y 2 decimales
38 | 403 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Cuota devengada operaciones corrientes [C] |  | 15 enteros y 2 decimales
39 | 420 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Reducciones [D] |  | 15 enteros y 2 decimales
40 | 437 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 1T/2T/3T - Indice corrector activ. de temporada [Z] |  | 1 entero y 2 decimales
41 | 440 | 5 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 1T/2T/3T - Porcentaje ingreso a cuenta [E] |  | 3 enteros y 2 decimales
42 | 445 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 1T/2T/3T - Ingreso a cuenta ( ([C] - [D] ) x [E]) [F] |  | 15 enteros y 2 decimales
43 | 462 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Cuotas soportadas operaciones corrientes [G] |  | 15 enteros y 2 decimales
44 | 479 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Índice corrector de actividades de temporada [H] |  | 1 entero y 2 decimales
45 | 482 | 17 | N | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - RESULTADO (( [C] - [D] - [G] ) x [H]) [I] |  | 15 enteros y 2 decimales
46 | 499 | 5 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Porcentaje cuota mínima [J] |  | 3 enteros y 2 decimales
47 | 504 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Devolución cuotas soportadas otros países [K] |  | 15 enteros y 2 decimales
48 | 521 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Cuota mínima [L] |  | 15 enteros y 2 decimales
49 | 538 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Cuota anual derivada RS [M] |  | 15 enteros y 2 decimales
50 | 555 | 4 | An | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Epigrafe IAE
51 | 559 | 1 | An | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Epigrafe IAE
 - Indicador auxiliar de actividad en el caso de epígrafes 691.9 y 722 |  | blanco, "1" o "2"  (Nota 3)
52 | 560 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 1 - Nº Unidades |  | 8 enteros y 2 decimales
53 | 570 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 1 - Importe |  | 15 enteros y 2 decimales
54 | 587 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 2 - Nº Unidades |  | 8 enteros y 2 decimales
55 | 597 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 2 - Importe |  | 15 enteros y 2 decimales
56 | 614 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 3 - Nº Unidades |  | 8 enteros y 2 decimales
57 | 624 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 3 - Importe |  | 15 enteros y 2 decimales
58 | 641 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 4 - Nº Unidades |  | 8 enteros y 2 decimales
59 | 651 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 4 - Importe |  | 15 enteros y 2 decimales
60 | 668 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 5 - Nº Unidades |  | 8 enteros y 2 decimales
61 | 678 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 5 - Importe |  | 15 enteros y 2 decimales
62 | 695 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 6 - Nº Unidades |  | 8 enteros y 2 decimales
63 | 705 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 6 - Importe |  | 15 enteros y 2 decimales
64 | 722 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 7 - Nº Unidades |  | 8 enteros y 2 decimales
65 | 732 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 7 - Importe |  | 15 enteros y 2 decimales
66 | 749 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Cuota devengada operaciones corrientes [C] |  | 15 enteros y 2 decimales
67 | 766 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Reducciones [D] |  | 15 enteros y 2 decimales
68 | 783 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 1T/2T/3T - Indice corrector activ. de temporada [Z] |  | 1 entero y 2 decimales
69 | 786 | 5 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 1T/2T/3T - Porcentaje ingreso a cuenta [E] |  | 3 enteros y 2 decimales
70 | 791 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 1T/2T/3T - Ingreso a cuenta ( ([C] - [D] ) x [E]) [F] |  | 15 enteros y 2 decimales
71 | 808 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Cuotas soportadas operaciones corrientes [G] |  | 15 enteros y 2 decimales
72 | 825 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Índice corrector de actividades de temporada [H] |  | 1 entero y 2 decimales
73 | 828 | 17 | N | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - RESULTADO (( [C] - [D] - [G] ) x [H]) [I] |  | 15 enteros y 2 decimales
74 | 845 | 5 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Porcentaje cuota mínima [J] |  | 3 enteros y 2 decimales
75 | 850 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Devolución cuotas soportadas otros países [K] |  | 15 enteros y 2 decimales
76 | 867 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Cuota mínima [L] |  | 15 enteros y 2 decimales
77 | 884 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Cuota anual derivada RS [M] |  | 15 enteros y 2 decimales
78 | 901 | 17 | Num |  | Liquidación (3) - RS - (B) Actividades en RS - 1T/2T/3T
 - Suma de ingresos a cuenta del conjunto de actividades (A1 + A2 + A3 + … + F1 + F2 + F3 + ...) [47] |  | 15 enteros y 2 decimales
79 | 918 | 17 | N |  | Liquidación (3) - RS - (A+B) Actividades en RS - 4T 
- Suma de cuotas derivadas RS del conjunto de actividades ( B1 + B2 + ... + M1 + M2 + ... ) [48] |  | 15 enteros y 2 decimales
80 | 935 | 17 | Num |  | Liquidación (3) - RS - (A+B) Actividades en RS - 4T 
- Suma de ingresos a cuenta realizados en el ejercicio [49] |  | 15 enteros y 2 decimales
81 | 952 | 17 | N |  | Liquidación (3) - RS - (A+B) Actividades en RS - 4T - Resultado ( [48] - [49] ) [50] |  | 15 enteros y 2 decimales
82 | 969 | 17 | N |  | Liquidación (3) - RS - Cuotas devengadas - Adquisiciones intracomunitarias de bienes [51] |  | 15 enteros y 2 decimales
83 | 986 | 17 | N |  | Liquidación (3) - RS - Cuotas devengadas - Entregas de activos fijos [52] |  | 15 enteros y 2 decimales
84 | 1003 | 17 | N |  | Liquidación (3) - RS - Cuotas devengadas - IVA devengado por inversión del sujeto pasivo [53] |  | 15 enteros y 2 decimales
85 | 1020 | 17 | N |  | Liquidación (3) - RS - Cuotas devengadas - Total cuota resultante
Si 1T, 2T, 3T: ( [47] + [51] + [52] + [53] ) [54]
Si 4T: ( [50] + [51] + [52] + [53] ) [54] |  | 15 enteros y 2 decimales
86 | 1037 | 17 | N |  | Liquidación (3) - RS - IVA deducible - Adquisición o importación de activos fijos [55] |  | 15 enteros y 2 decimales
87 | 1054 | 17 | N |  | Liquidación (3) - RS - IVA deducible - Regularización bienes de inversión [56] |  | 15 enteros y 2 decimales
88 | 1071 | 17 | N |  | Liquidación (3) - RS - IVA deducible - Total IVA deducible ( [55] + [56] ) [57] |  | 15 enteros y 2 decimales
89 | 1088 | 17 | N |  | Liquidación (3) - RS - Resultado RS ( [54] - [57] ) [58] |  | 15 enteros y 2 decimales
90 | 1105 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - ACTIVIDAD DE TEMPORADA: nº de días en los que se ejerció la actividad en el año anterior - 1T/2T/3T |  | 3 enteros
91 | 1108 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Número de días de ejercicio de la actividad en el trimestre - 1T/2T/3T |  | 2 enteros
92 | 1110 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Nº de empleados a uno de enero del ejercicio (o en la fecha de inicio de la actividad) - 1T/2T/3T |  | 3 enteros
93 | 1113 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Actividad de temporada. Número de días de ejercicio - 4T |  | 3 enteros
94 | 1116 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Nº máximo de asalariados que han trabajado simultáneamente durante el ejercicio - 4T |  | 3 enteros
95 | 1119 | 1 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Si en el ejercicio realiza la actividad en LORCA, seleccione lo que proceda |  | Nota 5
96 | 1120 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Cuotas soportadas - 4T |  | 15 enteros y 2 decimales
97 | 1137 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Compensaciones satisfechas a sujetos pasivos en R.E.A.G.P. - 4T |  | 15 enteros y 2 decimales
98 | 1154 | 7 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Personal Empleado - Personal Asalariado - Horas anuales - Mayores de 19 años |  | 7 enteros
99 | 1161 | 7 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Personal Empleado - Personal Asalariado - Horas anuales - Menores de 19 años y trabajadores con contratos de aprendizaje o formación que no sean discapacitados |  | 7 enteros
100 | 1168 | 7 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Personal Empleado - Personal Asalariado - Horas anuales - Discapacitados con grado de minusvalía igual o superior al 33 por 100 |  | 7 enteros
101 | 1175 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Personal Empleado - Personal Asalariado - Horas anuales - Horas anuales fijadas en el convenio colectivo vigente |  | 4 enteros
102 | 1179 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: titular |  | 4 enteros
103 | 1183 | 1 | An | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Personal Empleado - Personal No Asalariado - El titular es discapacitado en grado igual o superior al 33 por 100. |  | X o blanco
104 | 1184 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: cónyuge |  | 4 enteros
105 | 1188 | 7 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: hijos menores de 18 años |  | 7 enteros
106 | 1195 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Capacidad |  | 2 enteros
107 | 1197 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Mesas |  | 4 enteros
108 | 1201 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Días - 4T |  | 3 enteros
109 | 1204 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Capacidad |  | 2 enteros
110 | 1206 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Mesas |  | 4 enteros
111 | 1210 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Días - 4T |  | 3 enteros
112 | 1213 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Capacidad |  | 2 enteros
113 | 1215 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Mesas |  | 4 enteros
114 | 1219 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Días - 4T |  | 3 enteros
115 | 1222 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Capacidad |  | 2 enteros
116 | 1224 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Mesas |  | 4 enteros
117 | 1228 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Mesas - Días - 4T |  | 3 enteros
118 | 1231 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - ACTIVIDAD DE TEMPORADA: nº de días en los que se ejerció la actividad en el año anterior - 1T/2T/3T |  | 3 enteros
119 | 1234 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Número de días de ejercicio de la actividad en el trimestre - 1T/2T/3T |  | 2 enteros
120 | 1236 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Nº de empleados a uno de enero del ejercicio actual (o en la fecha de inicio de la actividad) - 1T/2T/3T |  | 3 enteros
121 | 1239 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Actividad de temporada. Número de días de ejercicio - 4T |  | 3 enteros
122 | 1242 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Nº máximo de asalariados que han trabajado simultáneamente durante el ejercicio - 4T |  | 3 enteros
123 | 1245 | 1 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Si en el ejercicio realiza la actividad en LORCA, seleccione lo que proceda |  | Nota 5
124 | 1246 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Cuotas soportadas - 4T |  | 15 enteros y 2 decimales
125 | 1263 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Compensaciones satisfechas a sujetos pasivos en R.E.A.G.P. - 4T |  | 15 enteros y 2 decimales
126 | 1280 | 7 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Personal Empleado - Personal Asalariado - Horas anuales - Mayores de 19 años |  | 7 enteros
127 | 1287 | 7 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Personal Empleado - Personal Asalariado - Horas anuales - Menores de 19 años y trabajadores con contratos de aprendizaje o formación que no sean discapacitados |  | 7 enteros
128 | 1294 | 7 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Personal Empleado - Personal Asalariado - Horas anuales - Discapacitados con grado de minusvalía igual o superior al 33 por 100 |  | 7 enteros
129 | 1301 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Personal Empleado - Personal Asalariado - Horas anuales - Horas anuales fijadas en el convenio colectivo vigente |  | 4 enteros
130 | 1305 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: titular |  | 4 enteros
131 | 1309 | 1 | An | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Personal Empleado - Personal No Asalariado - El titular es discapacitado en grado igual o superior al 33 por 100. |  | X o blanco
132 | 1310 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: cónyuge |  | 4 enteros
133 | 1314 | 7 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: hijos menores de 18 años |  | 7 enteros
134 | 1321 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Capacidad |  | 2 enteros
135 | 1323 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Mesas |  | 4 enteros
136 | 1327 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Días - 4T |  | 3 enteros
137 | 1330 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Capacidad |  | 2 enteros
138 | 1332 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Mesas |  | 4 enteros
139 | 1336 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Días - 4T |  | 3 enteros
140 | 1339 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Capacidad |  | 2 enteros
141 | 1341 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Mesas |  | 4 enteros
142 | 1345 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Días - 4T |  | 3 enteros
143 | 1348 | 2 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Capacidad |  | 2 enteros
144 | 1350 | 4 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Mesas |  | 4 enteros
145 | 1354 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Mesas - Días - 4T |  | 3 enteros
146 | 1357 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Cuotas soportadas - 4T |  | 15 enteros y 2 decimales
147 | 1374 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Compensaciones satisfechas a sujetos pasivos en R.E.A.G.P. - 4T |  | 15 enteros y 2 decimales
148 | 1391 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Cuotas soportadas - 4T |  | 15 enteros y 2 decimales
149 | 1408 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Compensaciones satisfechas a sujetos pasivos en R.E.A.G.P. - 4T |  | 15 enteros y 2 decimales
150 | 1425 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo Superficie de horno - Días - 4T |  | 3 enteros
151 | 1428 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo Superficie de horno - Días - 4T |  | 3 enteros
152 | 1431 | 264 | An |  | Reservado para la AEAT
153 | 1695 | 12 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T30302000>"
TOTAL |  | 1706 | POSICIONES
Nota 1:
El campo indicador de página complementaria se cumplimentará cuando en el fichero van más de una página del mismo tipo.
La C de la columna Comp indica los campos que pueden tener contenido en las páginas complementarias
Nota 2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 3:
La cumplimentación de estos campos deberá realizarse de la siguiente forma:
 | blanco | Cuando el epígrafe de la actividad correspondiente sea distinto de 691.9 o 722 (o no esté cumplimentada esa actividad).
Epígrafe I.A.E.: 691.9
 | 1 | Actividad: Reparación de calzado.
 | 2 | Actividad: Reparación de otros bienes de consumo n.c.o.p. (excepto reparación de calzado, restauración de obras de arte, muebles, antigüedades e instrumentos musicales).
Epígrafe I.A.E.: 722
 | 1 | Actividad: Transporte de mercancías por carretera, excepto residuos.
 | 2 | Actividad: Transporte de residuos por carretera.
Nota 4:
En el caso de un sujeto pasivo de IVA para el que no aplique el régimen simplificado, esta página 2 no debe incluirse en el diseño de registro.
Nota 5:
Si en el ejercicio realiza la actividad en LORCA, seleccione lo que proceda
Valor | Descripción
0 | Blanco
1 | Actividad realizada exclusivamente en Lorca
2 | Actividad realizada en Lorca y en otros municipios
Nota abreviaturas:
RS - Régimen Simplificado
exc. - excepto
inc. - incluido
a, g y f - agrícolas, ganaderas y forestales

# DP30303

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num | Modelo. | Obligatorio | Constante "303"
3 | 6 | 5 | Num | Página. | Obligatorio | Constante "03000"
4 | 11 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 17 | N | Información adicional - Entregas intracomunitarias de bienes y servicios [59] |  | 15 enteros y 2 decimales
6 | 29 | 17 | N | Información adicional - Exportaciones y operaciones asimiladas [60] |  | 15 enteros y 2 decimales
7 | 46 | 17 | N | Información adicional - Operaciones no sujetas por reglas de localización (excepto las incluidas en la casilla 123) [120] |  | 15 enteros y 2 decimales
8 | 63 | 17 | N | Información adicional - Operaciones sujetas con inversión del sujeto pasivo [122] |  | 15 enteros y 2 decimales
9 | 80 | 17 | N | Información adicional - Operaciones no sujetas por reglas de localización acogidas a los regímenes especiales de ventanilla única [123] |  | 15 enteros y 2 decimales
10 | 97 | 17 | N | Información adicional - Operaciones sujetas y acogidas a los regímenes especiales de ventanilla única [124] |  | 15 enteros y 2 decimales
11 | 114 | 17 | N | Información adicional - Importes de las entregas de bienes y prestaciones de servicios a las que habiéndoles sido aplicado el régimen especial del criterio de caja hubieran resultado devengadas conforme a la regla general de devengo contenida en el art. 75 LIVA - Base Imponible [62] |  | 15 enteros y 2 decimales
12 | 131 | 17 | N | Información adicional - Importes de las entregas de bienes y prestaciones de servicios a las que habiéndoles sido aplicado el régimen especial del criterio de caja hubieran resultado devengadas conforme a la regla general de devengo contenida en el art. 75 LIVA - Cuota [63] |  | 15 enteros y 2 decimales
13 | 148 | 17 | N | Información adicional - Importes de las adquisiciones de bienes y servicios a las que sea de aplicación o afecte el régimen
especial del criterio de caja - Base Imponible [74] |  | 15 enteros y 2 decimales
14 | 165 | 17 | N | Información adicional - Importes de las adquisiciones de bienes y servicios a las que sea de aplicación o afecte el régimen
especial del criterio de caja - Cuota [75] |  | 15 enteros y 2 decimales
15 | 182 | 17 | N | Resultado - Regularización cuotas art. 80.cinco.5ª LIVA  [76] |  | 15 enteros y 2 decimales
16 | 199 | 17 | N | Resultado - Suma de resultados ( [46] + [58] + [76] ) [64] |  | 15 enteros y 2 decimales
17 | 216 | 5 | Num | Resultado - % Atribuible a la Administración del Estado [65] |  | 3 enteros y 2 decimales
18 | 221 | 17 | N | Resultado - Atribuible a la Administración del Estado [66] |  | 15 enteros y 2 decimales
19 | 238 | 17 | Num | Resultado - IVA a la importación liquidado por la Aduana pendiente de ingreso  [77] |  | 15 enteros y 2 decimales
20 | 255 | 17 | Num | Resultado - Cuotas a compensar pendientes de periodos anteriores [110] |  | 15 enteros y 2 decimales
21 | 272 | 17 | Num | Resultado - Cuotas a compensar de periodos anteriores aplicadas en este periodo [78] |  | 15 enteros y 2 decimales
22 | 289 | 17 | Num | Resultado - Cuotas a compensar de periodos previos pendientes para periodos posteriores ([110] - [78]) [87] |  | 15 enteros y 2 decimales
23 | 306 | 17 | N | Resultado - Exclusivamente para sujetos pasivos que tributan conjuntamente a la Administración del Estado y a las Haciendas Forales Resultado de la regularización anual [68] |  | 15 enteros y 2 decimales
24 | 323 | 17 | N | Resultado - Resultado de la autoliquidación ( [66] + [77] - [78] + [68] ) [69] |  | 15 enteros y 2 decimales
25 | 340 | 17 | Num | Resultado - Resultados a ingresar de anteriores autoliquidaciones o liquidaciones administrativas
correspondientes al ejercicio y período objeto de la autoliquidación [70] |  | 15 enteros y 2 decimales
26 | 357 | 17 | Num | Resultado - Devoluciones acordadas por la Agencia Tributaria como consecuencia de la tramitación de
anteriores autoliquidaciones correspondientes al ejercicio y período objeto de la autoliquidación [109] |  | 15 enteros y 2 decimales
27 | 374 | 17 | N | Resultado - Resultado ( [69] - [70] + [109] ) [71] |  | 15 enteros y 2 decimales
28 | 391 | 1 | An | Declaración Sin actividad |  | X o blanco
29 | 392 | 1 | An | Declaración complementaria |  | X o blanco
30 | 393 | 13 | An | Número justificante declaración anterior
31 | 406 | 35 | An | Reservado para la AEAT
32 | 441 | 86 | An | Reservado para la AEAT
33 | 527 | 479 | An | Reservado para la AEAT
34 | 1006 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T30303000>"
TOTAL |  | 1017 | POSICIONES
Nota 1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
6. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.

# DP30304

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num | Modelo. | Obligatorio | Constante "303"
3 | 6 | 5 | Num | Página. | Obligatorio | Constante "04000"
4 | 11 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 3 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: B - Código de actividad - Principal
7 | 16 | 4 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Principal
8 | 20 | 3 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: B - Código de actividad - Otras - 1ª
9 | 23 | 4 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 1ª
10 | 27 | 3 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: B - Código de actividad - Otras - 2ª
11 | 30 | 4 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 2ª
12 | 34 | 3 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: B - Código de actividad - Otras - 3ª
13 | 37 | 4 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 3ª
14 | 41 | 3 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: B - Código de actividad - Otras - 4ª
15 | 44 | 4 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 4ª
16 | 48 | 3 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: B - Código de actividad - Otras - 5ª
17 | 51 | 4 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 5ª
18 | 55 | 1 | An | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA: 
D - Marque si ha efectuado operaciones por las que tenga obligación de presentar la declaración anual de operaciones 
con terceras personas. |  | X o blanco
19 | 56 | 5 | Num | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Información de la tributación por razón de territorio: Álava [89] |  | 3 enteros y 2 decimales
20 | 61 | 5 | Num | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Información de la tributación por razón de territorio: Guipuzcoa [90] |  | 3 enteros y 2 decimales
21 | 66 | 5 | Num | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Información de la tributación por razón de territorio: Vizcaya [91] |  | 3 enteros y 2 decimales
22 | 71 | 5 | Num | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Información de la tributación por razón de territorio: Navarra [92] |  | 3 enteros y 2 decimales
23 | 76 | 5 | Num | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Información de la tributación por razón de territorio: Territorio común [107] |  | 3 enteros y 2 decimales
24 | 81 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen general [80] |  | 15 enteros y 2 decimales
25 | 98 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen especial del criterio de caja conforme art. 75 LIVA [81] |  | 15 enteros y 2 decimales
26 | 115 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Entregas intracomunitarias de bienes y servicios [93] |  | 15 enteros y 2 decimales
27 | 132 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Exportaciones y otras operaciones exentas con derecho a deducción [94] |  | 15 enteros y 2 decimales
28 | 149 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones exentas sin derecho a deducción [83] |  | 15 enteros y 2 decimales
29 | 166 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones no sujetas por reglas de localización (excepto las incluidas en la casilla 126) [84] |  | 15 enteros y 2 decimales
30 | 183 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones sujetas con inversión del sujeto pasivo [125] |  | 15 enteros y 2 decimales
31 | 200 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones no sujetas por reglas de localización acogidas a los regímenes especiales de ventanilla única [126] |  | 15 enteros y 2 decimales
32 | 217 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - OSS. Operaciones sujetas y acogidas a los regímenes especiales de ventanilla única [127] |  | 15 enteros y 2 decimales
33 | 234 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones intragrupo valoradas conforme a lo dispuesto en los arts. 78 y 79 LIVA [128] |  | 15 enteros y 2 decimales
34 | 251 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen simplificado [86] |  | 15 enteros y 2 decimales
35 | 268 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen especial de la agricultura, ganadería y pesca [95] |  | 15 enteros y 2 decimales
36 | 285 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones realizadas por sujetos pasivos acogidos al régimen especial del recargo de equivalencia [96] |  | 15 enteros y 2 decimales
37 | 302 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en Régimen especial de bienes usados, objetos de arte, antigüedades y objetos de colección [97] |  | 15 enteros y 2 decimales
38 | 319 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen especial de Agencias de Viajes [98] |  | 15 enteros y 2 decimales
39 | 336 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Entregas de bienes inmuebles, operaciones financieras y relativas al oro de inversión no habituales [79] |  | 15 enteros y 2 decimales
40 | 353 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Entregas de bienes de inversión [99] |  | 15 enteros y 2 decimales
41 | 370 | 17 | N | Exclusivamente a cumplimentar en el último periodo por sujetos pasivos exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Total volumen de operaciones ([80]+[81]+[93]+[94]+[83]+[84]+[125]+[126]+[127]+[128]+[86]+[95]+[96]+[97]+[98]-[79]-[99]) [88] |  | 15 enteros y 2 decimales
42 | 387 | 600 | An | Reservado para la AEAT
43 | 987 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T30304000>"
TOTAL |  | 998 | POSICIONES
Nota 1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
6. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
Nota 2:
En el caso de no tener contenido, esta página 4 no debe incluirse en el diseño de registro.

# DP30305

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | Obligatorio | Constante "303"
3 | 6 | 5 | Num |  | Página. | Obligatorio | Constante "05000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria) |  | Nota 1
6 | 13 | 3 | An | C | Prorratas - 1 - Código CNAE [500] |  | Incluido en fichero CNAE.TXT.
7 | 16 | 17 | N | C | Prorratas - 1 - Importe de operaciones [501] |  | 15 enteros 2 decimales
8 | 33 | 17 | N | C | Prorratas - 1 - Importe de operaciones con derecho a deducción [502] |  | 15 enteros 2 decimales
9 | 50 | 1 | An | C | Prorratas - 1 - Tipo de prorrata [503] |  | "G", "E" o blanco.
10 | 51 | 5 | Num | C | Prorratas - 1 - % de prorrata [504] |  | 3 enteros 2 decimales, menor o igual que 100.
11 | 56 | 3 | An | C | Prorratas - 2 - Código CNAE [505] |  | Incluido en fichero CNAE.TXT.
12 | 59 | 17 | N | C | Prorratas - 2 - Importe de operaciones [506] |  | 15 enteros 2 decimales
13 | 76 | 17 | N | C | Prorratas - 2 - Importe de operaciones con derecho a deducción [507] |  | 15 enteros 2 decimales
14 | 93 | 1 | An | C | Prorratas - 2 - Tipo de prorrata [508] |  | "G", "E" o blanco.
15 | 94 | 5 | Num | C | Prorratas - 2 - % de prorrata [509] |  | 3 enteros 2 decimales, menor o igual que 100.
16 | 99 | 3 | An | C | Prorratas - 3 - Código CNAE [510] |  | Incluido en fichero CNAE.TXT.
17 | 102 | 17 | N | C | Prorratas - 3 - Importe de operaciones [511] |  | 15 enteros 2 decimales
18 | 119 | 17 | N | C | Prorratas - 3 - Importe de operaciones con derecho a deducción [512] |  | 15 enteros 2 decimales
19 | 136 | 1 | An | C | Prorratas - 3 - Tipo de prorrata [513] |  | "G", "E" o blanco.
20 | 137 | 5 | Num | C | Prorratas - 3 - % de prorrata [514] |  | 3 enteros 2 decimales, menor o igual que 100.
21 | 142 | 3 | An | C | Prorratas - 4 - Código CNAE [515] |  | Incluido en fichero CNAE.TXT.
22 | 145 | 17 | N | C | Prorratas - 4 - Importe de operaciones [516] |  | 15 enteros 2 decimales
23 | 162 | 17 | N | C | Prorratas - 4 - Importe de operaciones con derecho a deducción [517] |  | 15 enteros 2 decimales
24 | 179 | 1 | An | C | Prorratas - 4 - Tipo de prorrata [518] |  | "G", "E" o blanco.
25 | 180 | 5 | Num | C | Prorratas - 4 - % de prorrata [519] |  | 3 enteros 2 decimales, menor o igual que 100.
26 | 185 | 3 | An | C | Prorratas - 5 - Código CNAE [520] |  | Incluido en fichero CNAE.TXT.
27 | 188 | 17 | N | C | Prorratas - 5 - Importe de operaciones [521] |  | 15 enteros 2 decimales
28 | 205 | 17 | N | C | Prorratas - 5 - Importe de operaciones con derecho a deducción [522] |  | 15 enteros 2 decimales
29 | 222 | 1 | An | C | Prorratas - 5 - Tipo de prorrata [523] |  | "G", "E" o blanco.
30 | 223 | 5 | Num | C | Prorratas - 5 - % de prorrata [524] |  | 3 enteros 2 decimales, menor o igual que 100.
31 | 228 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes y servicios corrientes - Base imponible [700] |  | 15 enteros 2 decimales
32 | 245 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes y servicios corrientes - Cuota deducible [701] |  | 15 enteros 2 decimales
33 | 262 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes inversión - Base imponible [702] |  | 15 enteros 2 decimales
34 | 279 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes inversión - Cuota deducible [703] |  | 15 enteros 2 decimales
35 | 296 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes corrientes - Base imponible [704] |  | 15 enteros 2 decimales
36 | 313 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes corrientes - Cuota deducible [705] |  | 15 enteros 2 decimales
37 | 330 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes inversión - Base imponible [706] |  | 15 enteros 2 decimales
38 | 347 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes inversión - Cuota deducible [707] |  | 15 enteros 2 decimales
39 | 364 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes corrientes y servicios - Base imponible [708] |  | 15 enteros 2 decimales
40 | 381 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes corrientes y servicios - Cuota deducible [709] |  | 15 enteros 2 decimales
41 | 398 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes inversión - Base imponible [710] |  | 15 enteros 2 decimales
42 | 415 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes inversión - Cuota deducible [711] |  | 15 enteros 2 decimales
43 | 432 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - Compensac. rég. especial agric./ganad./pesca - Base impon. [712] |  | 15 enteros 2 decimales
44 | 449 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 1 - Compensac. rég. especial agric./ganad./pesca - Cuota deduc. [713] |  | 15 enteros 2 decimales
45 | 466 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Rectificación de deducciones - Base impon.  [714] |  | 15 enteros 2 decimales
46 | 483 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Rectificación de deducciones - Cuota deduc. [715] |  | 15 enteros 2 decimales
47 | 500 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Regularización de bienes de inversión [716] |  | 15 enteros 2 decimales
48 | 517 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Suma de deducciones [717] |  | 15 enteros 2 decimales
49 | 534 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes y servicios corrientes - Base imponible [718] |  | 15 enteros 2 decimales
50 | 551 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes y servicios corrientes - Cuota deducible [719] |  | 15 enteros 2 decimales
51 | 568 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes inversión - Base imponible [720] |  | 15 enteros 2 decimales
52 | 585 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes inversión - Cuota deducible [721] |  | 15 enteros 2 decimales
53 | 602 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes corrientes - Base imponible [722] |  | 15 enteros 2 decimales
54 | 619 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes corrientes - Cuota deducible [723] |  | 15 enteros 2 decimales
55 | 636 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes inversión - Base imponible [724] |  | 15 enteros 2 decimales
56 | 653 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes inversión - Cuota deducible [725] |  | 15 enteros 2 decimales
57 | 670 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes corrientes y servicios - Base imponible [726] |  | 15 enteros 2 decimales
58 | 687 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes corrientes y servicios - Cuota deducible [727] |  | 15 enteros 2 decimales
59 | 704 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes inversión - Base imponible [728] |  | 15 enteros 2 decimales
60 | 721 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes inversión - Cuota deducible [729] |  | 15 enteros 2 decimales
61 | 738 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - Compensac. rég. especial agric./ganad./pesca - Base impon. [730] |  | 15 enteros 2 decimales
62 | 755 | 17 | Num | C | 13. Reg. Deducc. Diferenc.- 2 - Compensac. rég. especial agric./ganad./pesca - Cuota deduc. [731] |  | 15 enteros 2 decimales
63 | 772 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Rectificación de deducciones - Base impon.  [732] |  | 15 enteros 2 decimales
64 | 789 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Rectificación de deducciones - Cuota deduc. [733] |  | 15 enteros 2 decimales
65 | 806 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Regularización de bienes de inversión [734] |  | 15 enteros 2 decimales
66 | 823 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Suma de deducciones [735] |  | 15 enteros 2 decimales
67 | 840 | 672 | An |  | Reservado para la AEAT
68 | 1512 | 12 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T30305000>"
TOTAL |  | 1523 | POSICIONES
Nota 1:
El campo indicador de página complementaria se cumplimentará cuando en el fichero van más de una página del mismo tipo.
La C de la columna Comp indica los campos que pueden tener contenido en las páginas complementarias
Nota 2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
6. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
Nota 3:
En el caso de no tener contenido, esta página 5 no debe incluirse en el diseño de registro.

# DP303DID

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num | Modelo. | Obligatorio | Constante "303"
3 | 6 | 5 | An | Página. | Obligatorio | Constante "DID00"
4 | 11 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 11 | An | Devolución. SWIFT-BIC
6 | 23 | 34 | An | Domiciliación/Devolución - IBAN
7 | 57 | 70 | An | Devolución - Banco/Bank name
8 | 127 | 35 | An | Devolución - Dirección del Banco/ Bank address
9 | 162 | 30 | An | Devolución - Ciudad/City
10 | 192 | 2 | An | Devolución - Código País/Country code
11 | 194 | 1 | Num | Devolución - Marca SEPA |  | "0", "1", "2", "3" Nota 2
12 | 195 | 617 | An | Reservado para la AEAT
13 | 812 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T303DID00>"
TOTAL |  | 823 | POSICIONES
Nota 1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
6. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
Nota 2: Devolución marca SEPA
Valor | Descripción
0 | Vacía
1 | Cuenta España
2 | Unión Europea SEPA
3 | Resto Países