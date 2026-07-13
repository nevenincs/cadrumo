# DP30300

 | Agencia Tributaria
Modelo 303
versión 1.04 |  | Diseño de registro
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
16 | *** | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
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
Este Diseño de Registro deber ser utilizado para las presentaciones de todos los periodos de 2018 y ejercicios posteriores.

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
8 | 23 | 60 | An | Identificación (1) - Apellidos o Razón Social | Obligatorio
9 | 83 | 20 | A | Identificación (1) - Nombre | Obligatorio P.F.
10 | 103 | 4 | Num | Devengo (2) - Ejercicio | Obligatorio
11 | 107 | 2 | An | Devengo (2) - Período | Obligatorio | "01",..., "12" o "1T" … "4T"
12 | 109 | 1 | Num | Identificación (1) - Inscrito en el Registro de devolución mensual (Art. 30 RIVA) |  | "1" SI, "2" NO. Nota 5
13 | 110 | 1 | Num | Identificación (1) - Tributa exclusivamente en Régimen Simplificado (RS) |  | "1" SI (sólo RS),
 "2" NO (RG + RS),
"3" NO (sólo RG).                                    Nota 5
14 | 111 | 1 | Num | Identificación (1) - Autoliquidación conjunta |  | "1" SI, "2" NO. Nota 5
15 | 112 | 1 | Num | Identificación (1) - Declarado en concurso de acreedores en el presente período de liquidación |  | "1" SI, "2" NO. Nota 5
16 | 113 | 8 | An | Identificación (1) - Fecha en que se dictó el auto de declaración de concurso
17 | 121 | 1 | An | Identificación (1) - Auto de declaración de concurso dictado en el período |  | "1" SI Preconcursal, 
"2" SI Postconcursal                             blanco NO.                                              Nota 5
18 | 122 | 1 | Num | Identificación (1) - Opción por el régimen especial de criterio de Caja |  | "1" SI, "2" NO. Nota 5
19 | 123 | 1 | Num | Identificación (1) - Destinatario de las operaciones a las que se aplique el régimen especial del criterio de Caja |  | "1" SI, "2" NO. Nota 5
20 | 124 | 1 | Num | Identificación (1) - Opción por la aplicación de la prorrata especial |  | "1" SI, "2" NO. Nota 5
21 | 125 | 1 | Num | Identificación (1) - Revocación de la opción por la aplicación de la prorrata especial |  | "1" SI, "2" NO. Nota 5
22 | 126 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [01] |  | 15 enteros y 2 decimales
23 | 143 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [02] |  | 3 enteros y 2 decimales
24 | 148 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [03] |  | 15 enteros y 2 decimales
25 | 165 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [04] |  | 15 enteros y 2 decimales
26 | 182 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [05] |  | 3 enteros y 2 decimales
27 | 187 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [06] |  | 15 enteros y 2 decimales
28 | 204 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [07] |  | 15 enteros y 2 decimales
29 | 221 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [08] |  | 3 enteros y 2 decimales
30 | 226 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [09] |  | 15 enteros y 2 decimales
31 | 243 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Adquisiciones intracomunitarias de bienes y servicios - Base imponible  [10] |  | 15 enteros y 2 decimales
32 | 260 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Adquisiciones intracomunitarias de bienes y servicios - Cuota [11] |  | 15 enteros y 2 decimales
33 | 277 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Otras operaciones con inversión del sujeto pasivo (excepto. adq. intracom) - Base imponible  [12] |  | 15 enteros y 2 decimales
34 | 294 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Otras operaciones con inversión del sujeto pasivo (excepto. adq. intracom) - Cuota [13] |  | 15 enteros y 2 decimales
35 | 311 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificación bases y cuotas- Base imponible  [14] |  | 15 enteros y 2 decimales
36 | 328 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificación bases y cuotas - Cuota [15] |  | 15 enteros y 2 decimales
37 | 345 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia- Base imponible [16] |  | 15 enteros y 2 decimales
38 | 362 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [17] |  | 3 enteros y 2 decimales
39 | 367 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [18] |  | 15 enteros y 2 decimales
40 | 384 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Base imponible [19] |  | 15 enteros y 2 decimales
41 | 401 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [20] |  | 3 enteros y 2 decimales
42 | 406 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [21] |  | 15 enteros y 2 decimales
43 | 423 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Base imponible [22] |  | 15 enteros y 2 decimales
44 | 440 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [23] |  | 3 enteros y 2 decimales
45 | 445 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [24] |  | 15 enteros y 2 decimales
46 | 462 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificaciones bases y cuotas del recargo de equivalencia - Base imponible [25] |  | 15 enteros y 2 decimales
47 | 479 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificaciones bases y cuotas del recargo de equivalencia - Cuota [26] |  | 15 enteros y 2 decimales
48 | 496 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Total cuota devengada ( [03] + [06] + [09] + [11] + [13] + [15] + [18] + [21] + [24] + [26]) [27] |  | 15 enteros y 2 decimales
49 | 513 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores corrientes - Base [28] |  | 15 enteros y 2 decimales
50 | 530 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores corrientes - Cuota [29] |  | 15 enteros y 2 decimales
51 | 547 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores con bienes de inversión - Base [30] |  | 15 enteros y 2 decimales
52 | 564 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores con bienes de inversión - Cuota [31] |  | 15 enteros y 2 decimales
53 | 581 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en las importaciones de bienes corrientes - Base [32] |  | 15 enteros y 2 decimales
54 | 598 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en las importaciones de bienes corrientes - Cuota [33] |  | 15 enteros y 2 decimales
55 | 615 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en las importaciones de bienes de inversión - Base [34] |  | 15 enteros y 2 decimales
56 | 632 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en las importaciones de bienes de inversión - Cuota [35] |  | 15 enteros y 2 decimales
57 | 649 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - En adquisiciones intracomunitarias de bienes y servicios corrientes - Base [36] |  | 15 enteros y 2 decimales
58 | 666 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - En adquisiciones intracomunitarias de bienes y servicios corrientes - Cuota [37] |  | 15 enteros y 2 decimales
59 | 683 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - En adquisiciones intracomunitarias de bienes de inversión - Base [38] |  | 15 enteros y 2 decimales
60 | 700 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - En adquisiciones intracomunitarias de bienes de inversión - Cuota [39] |  | 15 enteros y 2 decimales
61 | 717 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Rectificación de deducciones - Base [40] |  | 15 enteros y 2 decimales
62 | 734 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Rectificación de deducciones - Cuota [41] |  | 15 enteros y 2 decimales
63 | 751 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Compensaciones Régimen Especial A.G. y P. - Cuota [42] |  | 15 enteros y 2 decimales
64 | 768 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Regularización inversiones - Cuota [43] |  | 15 enteros y 2 decimales
65 | 785 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Regularización por aplicación del porcentaje definitivo de prorrata - Cuota [44] |  | 15 enteros y 2 decimales
66 | 802 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Total a deducir ( [29] + [31] + [33] + [35] + [37] + [39] + [41] + [42] + [43] + [44] ) - Cuota [45] |  | 15 enteros y 2 decimales
67 | 819 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Resultado régimen general ( [27] - [45] ) - Cuota [46] |  | 15 enteros y 2 decimales
68 | 836 | 1 | Num | Identificación (1) - ¿Existe volumen de operaciones (art. 121 LIVA)? |  | Nota 3
69 | 837 | 1 | Num | Sujeto pasivo que tributa exclusivamente a una Administración tributaria Foral con IVA a la importación liquidado por la Aduana pendiente de ingreso |  | "0" Para el mes de enero (01),                  "1" SI,                                                          "2" NO.                                                    Nota 5
70 | 838 | 1 | Num | ¿Ha llevado voluntariamente los Libros registro del IVA a través de la Sede electrónica de la AEAT durante el ejercicio? |  | "0" Para el mes de enero (01),                  "1" SI,                                                          "2" NO.                                                    Nota 5
71 | 839 | 1 | Num | Identificación (1) - ¿Está exonerado de la Declaración-resumen anual del IVA, modelo 390? |  | Nota 4
72 | 840 | 578 | An | Reservado para la AEAT
73 | 1418 | 13 | An | Reservado para la AEAT - Sello electrónico reservado para la AEAT
74 | 1431 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T30301000>"
TOTAL |  | 1442 | POSICIONES
Nota 1:
 | PI :El tipo de declaración puede ser: C (solicitud de compensación) D (devolución) G (cuenta corriente tributaria-ingreso) I (ingreso) N (sin actividad/resultado cero) V (cuenta corriente tributaria -devolución)
 | U (domiciliacion del ingreso en CCC)
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
Salvo los siguientes campos, que en este caso, tomatrán los valores que se indican:
- | Sujeto pasivo que tributa exclusivamente a una Administración tributaria Foral con IVA a la importación liquidado por la Aduana pendiente de ingreso >> "1" SI
- | Identificación (1) - Tributa exclusivamente en Régimen Simplificado (RS) >> "3" NO (sólo RG).
- | Identificación (1) - Auto de declaración de concurso dictado en el período >> blanco NO

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
8 | 32 | 6 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Indice de cuota |  | 1 entero y 5 decimales
9 | 38 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Cuota devengada |  | 15 enteros y 2 decimales
10 | 55 | 5 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 1T/2T/3T - Porcentaje trimestral |  | 3 enteros y 2 decimales
11 | 60 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 1T/2T/3T - Ingreso a cuenta [A] |  | 15 enteros y 2 decimales
12 | 77 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 4T - Cuota soportada |  | 15 enteros y 2 decimales
13 | 94 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 4T
 - Cuota anual derivada del regimen simplificado [B] |  | 15 enteros y 2 decimales
14 | 111 | 2 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Código
15 | 113 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Volumen de ingresos |  | 15 enteros y 2 decimales
16 | 130 | 6 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Indices de cuota |  | 1 entero y 5 decimales
17 | 136 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Cuota devengada |  | 15 enteros y 2 decimales
18 | 153 | 5 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 1T/2T/3T - Porcentaje trimestral |  | 3 enteros y 2 decimales
19 | 158 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 1T/2T/3T - Ingreso a cuenta [A] |  | 15 enteros y 2 decimales
20 | 175 | 17 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 4T - Cuota soportada |  | 15 enteros y 2 decimales
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
90 | 1105 | 590 | An |  | Reservado para la AEAT
91 | 1695 | 12 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T30302000>"
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
 | blanco | Cuando el epígrafe de la actividad correspondiente sea distinto de 691.9 ó 722 (o no esté cumplimentada esa actividad).
Epígrafe I.A.E.: 691.9
 | 1 | Actividad: Reparación de calzado.
 | 2 | Actividad: Reparación de otros bienes de consumo n.c.o.p. (excepto reparación de calzado, restauración de obras de arte, muebles, antigüedades e instrumentos musicales).
Epígrafe I.A.E.: 722
 | 1 | Actividad: Transporte de mercancías por carretera, excepto residuos.
 | 2 | Actividad: Transporte de residuos por carretera.
Nota 4:
En el caso de un sujeto pasivo de IVA para el que no aplique el régimen simplificado, esta página 2 no debe incluirse en el diseño de registro.
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
7 | 46 | 17 | N | Información adicional - Operaciones no sujetas o con inversión del sujeto pasivo que originan el derecho a deducción [61] |  | 15 enteros y 2 decimales
8 | 63 | 17 | N | Información adicional - Exclusivamente para operaciones de entrega de bienes y prestaciones de servicios
a las que resulte de aplicación el régimen especial del criterio de Caja.
Importes devengados en período de liquidación según art. 75 LIVA. - Base Imponible [62] |  | 15 enteros y 2 decimales
9 | 80 | 17 | N | Información adicional - Exclusivamente para operaciones de entrega de bienes y prestaciones de servicios
a las que resulte de aplicación el régimen especial del criterio de Caja.
Importes devengados en período de liquidación según art. 75 LIVA. - Cuota [63] |  | 15 enteros y 2 decimales
10 | 97 | 17 | N | Información adicional - Exclusivamente para operaciones de entrega de bienes y prestaciones de servicios
a las que resulte de aplicación el régimen especial del criterio de Caja.
Cuotas de IVA soportados en operaciones que tributen por el régimen especial del criterio de caja
conforme a la regla general de devengo contenida en el artículo 75 LIVA. - Base Imponible [74] |  | 15 enteros y 2 decimales
11 | 114 | 17 | N | Información adicional - Exclusivamente para operaciones de entrega de bienes y prestaciones de servicios
a las que resulte de aplicación el régimen especial del criterio de Caja.
Cuotas totales de IVA soportados en operaciones que tributen por el régimen especial del criterio de caja
conforme a la regla general de devengo contenida en el artículo 75 de LIVA. - Cuota [75] |  | 15 enteros y 2 decimales
12 | 131 | 17 | N | Resultado - Regularización cuotas art. 80.cinco.5ª LIVA  [76] |  | 15 enteros y 2 decimales
13 | 148 | 17 | N | Resultado - Suma de resultados ( [46] + [58] + [76] ) [64] |  | 15 enteros y 2 decimales
14 | 165 | 5 | Num | Resultado - % Atribuible a la Administración del Estado [65] |  | 3 enteros y 2 decimales
14bis | 170 | 4 | Num | Reservado para la AEAT
15 | 174 | 17 | N | Resultado - Atribuible a la Administración del Estado [66] |  | 15 enteros y 2 decimales
16 | 191 | 17 | Num | Resultado - IVA a la importación liquidado por la Aduana pendiente de ingreso  [77] |  | 15 enteros y 2 decimales
17 | 208 | 17 | Num | Resultado - Cuotas a compensar de periodos anteriores [67] |  | 15 enteros y 2 decimales
18 | 225 | 17 | N | Resultado - Exclusivamente para sujetos pasivos que tributan conjuntamente a la Administración del Estado y a las Diputaciones Forales Resultado de la regularización anual [68] |  | 15 enteros y 2 decimales
19 | 242 | 17 | N | Resultado - Resultado ( [66] + [77] - [67] ± [68] ) [69] |  | 15 enteros y 2 decimales
20 | 259 | 17 | N | Resultado - A deducir [70] |  | 15 enteros y 2 decimales
21 | 276 | 17 | N | Resultado - Resultado de la liquidación ( [69] - [70] ) [71] |  | 15 enteros y 2 decimales
22 | 293 | 1 | An | Declaración complementaria |  | X o blanco
23 | 294 | 13 | An | Número justificante declaración anterior
24 | 307 | 1 | An | Declaración Sin actividad |  | X o blanco
25 | 308 | 11 | An | Devolución. SWIFT-BIC
26 | 319 | 34 | An | Domiciliación/Devolución - IBAN
27 | 353 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: B - Clave - Principal |  | Nota 1
28 | 354 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Principal |  | Nota 1
29 | 358 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: B - Clave - Otras - 1ª |  | Nota 1
30 | 359 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 1ª |  | Nota 1
31 | 363 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: B - Clave - Otras - 2ª |  | Nota 1
32 | 364 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 2ª |  | Nota 1
33 | 368 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: B - Clave - Otras - 3ª |  | Nota 1
34 | 369 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 3ª |  | Nota 1
35 | 373 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo
exonerados de la Declaración-resumen anual del IVA: B - Clave - Otras - 4ª |  | Nota 1
36 | 374 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 4ª |  | Nota 1
37 | 378 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: B - Clave - Otras - 5ª |  | Nota 1
38 | 379 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resumen anual del IVA: C - Epígrafe IAE - Otras - 5ª |  | Nota 1
39 | 383 | 1 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA: 
D - Marque si ha efectuado operaciones por las que tenga obligación de presentar la declaración anual de operaciones 
con terceras personas. |  | X o blanco
40 | 384 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen general [80] |  | 15 enteros y 2 decimales
41 | 401 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen especial del criterio de caja conforme art. 75 LIVA [81] |  | 15 enteros y 2 decimales
42 | 418 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Entregas intracomunitarias exentas [93] |  | 15 enteros y 2 decimales
43 | 435 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones exentas sin derecho a deducción [83] |  | 15 enteros y 2 decimales
44 | 452 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones no sujetas por reglas de localización o con inversión del sujeto pasivo [84] |  | 15 enteros y 2 decimales
45 | 469 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Entregas de bienes objeto de instalación o montaje en otros Estados miembros [85] |  | 15 enteros y 2 decimales
46 | 486 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen simplificado [86] |  | 15 enteros y 2 decimales
47 | 503 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Entregas de bienes inmuebles no habituales, operaciones financieras y relativas al oro de inversión no habituales [79] |  | 15 enteros y 2 decimales
48 | 520 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Total volumen de operaciones ([80]+[81]+[93]+[94]+[83]+[84]+[85]+[86]+[95]+[96]+[97]+[98]-[79]-[99]) [88] |  | 15 enteros y 2 decimales
49 | 537 | 1 | Num | Reservado para la AEAT
50 | 538 | 5 | Num | Información de la tributación por razón de territorio: Álava [89] |  | 3 enteros y 2 decimales
51 | 543 | 5 | Num | Información de la tributación por razón de territorio: Guipuzcoa [90] |  | 3 enteros y 2 decimales
52 | 548 | 5 | Num | Información de la tributación por razón de territorio: Vizcaya [91] |  | 3 enteros y 2 decimales
53 | 553 | 5 | Num | Información de la tributación por razón de territorio: Navarra [92] |  | 3 enteros y 2 decimales
54 | 558 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Exportaciones y otras operaciones exentas con derecho a deducción [94] |  | 15 enteros y 2 decimales
55 | 575 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen especial de la agricultura, ganadería y pesca [95] |  | 15 enteros y 2 decimales
56 | 592 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones realizadas por sujetos pasivos acogidos al régimen especial del recargo de equivalencia [96] |  | 15 enteros y 2 decimales
57 | 609 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en Régimen especial de bienes usados, objetos de arte, antigüedades y objetos de colección [97] |  | 15 enteros y 2 decimales
58 | 626 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen especial de Agencias de Viajes [98] |  | 15 enteros y 2 decimales
59 | 643 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resumen anual del IVA - Operaciones realizadas en el ejercicio - Entregas de bienes de inversión [99] |  | 15 enteros y 2 decimales
60 | 660 | 5 | Num | Información de la tributación por razón de territorio: Territorio común [107] |  | 3 enteros y 2 decimales
61 | 665 | 463 | An | Reservado para la AEAT
62 | 1128 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T30303000>"
TOTAL |  | 1139 | POSICIONES
Nota 1:
Las casillas B (Clave) y C (Epígrafe IAE) podrán tomar los siguientes valores para periodo 12 y para periodo 4T:
B | C
0 | Sin Epígrafe
1 | Epígrafes correspondientes a: Actividades empresariales sujetas al IAE
2 | Epígrafes correspondientes a: Actividades profesionales sujetas al IAE
2 | Epígrafes correspondientes a: Actividades artísticas sujetas al IAE
3 | Epígrafe 861.1 correspondiente a: Alquiler de viviendas
3 | Epígrafe 861.2 correspondiente a: Alquiler de locales industriales
3 | Epígrafe 862 correspondiente a: Alquiler de inmuebles rústicos
4 | Sin epígrafe, correspondiente a: Actividades agrícolas, ganaderas, forestales o pesqueras, no sujetas al IAE
5 | Sin epígrafe, correspondiente a: Sujetos pasivos sin actividad
6 | Sin epígrafe, correspondiente a: Otras actividades no sujetas al IAE
Nota 2:
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
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | Obligatorio | Constante "303"
3 | 6 | 5 | Num |  | Página. | Obligatorio | Constante "04000"
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
31 | 228 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes y servic. - Base imponible [700] |  | 15 enteros 2 decimales
32 | 245 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes y servic. - Cuota deducible [701] |  | 15 enteros 2 decimales
33 | 262 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes inversión - Base imponible [702] |  | 15 enteros 2 decimales
34 | 279 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes inversión - Cuota deducible [703] |  | 15 enteros 2 decimales
35 | 296 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes corrientes - Base imponible [704] |  | 15 enteros 2 decimales
36 | 313 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes corrientes - Cuota deducible [705] |  | 15 enteros 2 decimales
37 | 330 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes inversión - Base imponible [706] |  | 15 enteros 2 decimales
38 | 347 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes inversión - Cuota deducible [707] |  | 15 enteros 2 decimales
39 | 364 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes corrientes - Base imponible [708] |  | 15 enteros 2 decimales
40 | 381 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun.  - Bienes corrientes - Cuota deducible [709] |  | 15 enteros 2 decimales
41 | 398 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes inversión - Base imponible [710] |  | 15 enteros 2 decimales
42 | 415 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes inversión - Cuota deducible [711] |  | 15 enteros 2 decimales
43 | 432 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Compensac. rég. especial agric./ganad./pesca - Base impon. [712] |  | 15 enteros 2 decimales
44 | 449 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Compensac. rég. especial agric./ganad./pesca - Cuota deduc. [713] |  | 15 enteros 2 decimales
45 | 466 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Rectificación de deducciones - Base impon.  [714] |  | 15 enteros 2 decimales
46 | 483 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Rectificación de deducciones - Cuota deduc. [715] |  | 15 enteros 2 decimales
47 | 500 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Regularización de inversiones [716] |  | 15 enteros 2 decimales
48 | 517 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 1 - Suma de deducciones [717] |  | 15 enteros 2 decimales
49 | 534 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes y servic. - Base imponible [718] |  | 15 enteros 2 decimales
50 | 551 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes y servic. - Cuota deducible [719] |  | 15 enteros 2 decimales
51 | 568 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes inversión - Base imponible [720] |  | 15 enteros 2 decimales
52 | 585 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes inversión - Cuota deducible [721] |  | 15 enteros 2 decimales
53 | 602 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes corrientes - Base imponible [722] |  | 15 enteros 2 decimales
54 | 619 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes corrientes - Cuota deducible [723] |  | 15 enteros 2 decimales
55 | 636 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes inversión - Base imponible [724] |  | 15 enteros 2 decimales
56 | 653 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes inversión - Cuota deducible [725] |  | 15 enteros 2 decimales
57 | 670 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes corrientes - Base imponible [726] |  | 15 enteros 2 decimales
58 | 687 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun.  - Bienes corrientes - Cuota deducible [727] |  | 15 enteros 2 decimales
59 | 704 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes inversión - Base imponible [728] |  | 15 enteros 2 decimales
60 | 721 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes inversión - Cuota deducible [729] |  | 15 enteros 2 decimales
61 | 738 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Compensac. rég. especial agric./ganad./pesca - Base impon. [730] |  | 15 enteros 2 decimales
62 | 755 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Compensac. rég. especial agric./ganad./pesca - Cuota deduc. [731] |  | 15 enteros 2 decimales
63 | 772 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Rectificación de deducciones - Base impon.  [732] |  | 15 enteros 2 decimales
64 | 789 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Rectificación de deducciones - Cuota deduc. [733] |  | 15 enteros 2 decimales
65 | 806 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Regularización de inversiones [734] |  | 15 enteros 2 decimales
66 | 823 | 17 | N | C | 13. Reg. Deducc. Diferenc.- 2 - Suma de deducciones [735] |  | 15 enteros 2 decimales
67 | 840 | 672 | An |  | Reservado para la AEAT
68 | 1512 | 12 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T30304000>"
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
En el caso de no tener contenido, esta página 4 no debe incluirse en el diseño de registro.