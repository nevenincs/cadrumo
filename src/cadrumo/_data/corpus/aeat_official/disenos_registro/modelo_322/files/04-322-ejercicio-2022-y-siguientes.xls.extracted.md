# DR32200

 | Agencia Tributaria
Modelo 322
vers. 1.1 |  | Diseño de registro
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "322"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) |  | "01"..."12"
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T3220+Ejercicio+periodo+0000> |  | "</T3220AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# DR32201

 | Agencia Tributaria
Modelo 322 |  | Diseño de registro. Castellano
 |  | Impuesto sobre el Valor Añadido. Grupo de entidades. Modelo individual. Autoliquidación mensual
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 11 | An | Etiqueta inicio página |  | <T32201000>
2 | 12 | 1 | An | Reservado página complementaria |  | Blanco o C
3 | 13 | 1 | An | Tipo Declaración |  | blanco
4 | 14 | 9 | An | Identificación. Sujeto pasivo. N.I.F. | obligatorio
5 | 23 | 60 | An | Identificación. Sujeto pasivo. Razón o denominación social
6 | 83 | 20 | An | Reservado AEAT
7 | 103 | 4 | Num | Identificación. Ejercicio
8 | 107 | 2 | An | Identificación. Periodo
9 | 109 | 10 | An | Identificación. Nº Grupo
10 | 119 | 1 | An | Identificación. Dominante / Dependiente |  | Dominante=D ,Dependiente=P o blanco
11 | 120 | 9 | An | Identificación. NIF de la entidad dominante
12 | 129 | 1 | Num | Identificación. Tipo régimen especial aplicable: Art. 163 sexies.Cinco LIVA. |  | Si=1, No=2. Nota 3
13 | 130 | 1 | Num | Identificación. ¿Está inscrito en el Registro de devolución mensual (Art. 30 RIVA)?. |  | Si=1, No=2. Nota 3
14 | 131 | 1 | Num | Identificación. ¿Es destinatario de operaciones a las que se aplique el régimen especial del criterio de caja?. |  | Si=1, No=2. Nota 3
15 | 132 | 1 | Num | Identificación. Aplicación de la prorrata especial (art. 103.Dos.1ºLIVA)  - Opción por la aplicación / Revocación de la opción |  | 1 - Opción , 2 - Renovación o 0 - blanco. Nota 3
16 | 133 | 17 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Base imponible [01] |  | 15 enteros + 2 decimales
17 | 150 | 5 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Tipo % [02] |  | 3 enteros + 2 decimales
18 | 155 | 17 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Cuota [03] |  | 15 enteros + 2 decimales
19 | 172 | 17 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Base imponible [04] |  | 15 enteros + 2 decimales
20 | 189 | 5 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Tipo % [05] |  | 3 enteros + 2 decimales
21 | 194 | 17 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Cuota [06] |  | 15 enteros + 2 decimales
22 | 211 | 17 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Base imponible [07] |  | 15 enteros + 2 decimales
23 | 228 | 5 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Tipo % [08] |  | 3 enteros + 2 decimales
24 | 233 | 17 | Num | Liquidación. IVA DEVENGADO. Operaciones intragrupo. Cuota [09] |  | 15 enteros + 2 decimales
25 | 250 | 17 | N | Liquidación. IVA DEVENGADO. Modificación bases y cuotas de operaciones intragrupo [10] |  | 15 enteros + 2 decimales
26 | 267 | 17 | N | Liquidación. IVA DEVENGADO. Modificación bases y cuotas de operaciones intragrupo  [11] |  | 15 enteros + 2 decimales
27 | 284 | 17 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general [12] |  | 15 enteros + 2 decimales
28 | 301 | 5 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general. Tipo % [13] |  | 3 enteros + 2 decimales
29 | 306 | 17 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general. Cuota [14] |  | 15 enteros + 2 decimales
30 | 323 | 17 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general [15] |  | 15 enteros + 2 decimales
31 | 340 | 5 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general.  Tipo % [16] |  | 3 enteros + 2 decimales
32 | 345 | 17 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general. Cuota [17] |  | 15 enteros + 2 decimales
33 | 362 | 17 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general [18] |  | 15 enteros + 2 decimales
34 | 379 | 5 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general.  Tipo % [19] |  | 3 enteros + 2 decimales
35 | 384 | 17 | Num | Liquidación. IVA DEVENGADO.  Resto de operaciones en régimen general. Cuota [20] |  | 15 enteros + 2 decimales
36 | 401 | 17 | Num | Liquidación. IVA DEVENGADO. Adquisiciones intracomunitarias de bienes y servicios. Base imponible  [21] |  | 15 enteros + 2 decimales
37 | 418 | 17 | Num | Liquidación. IVA DEVENGADO. Adquisiciones intracomunitarias de bienes y servicios. Cuota [22] |  | 15 enteros + 2 decimales
38 | 435 | 17 | Num | Liquidación. IVA DEVENGADO. Otras operaciones con inversión del sujeto pasivo (excepto adq. intracom.) [23] |  | 15 enteros + 2 decimales
39 | 452 | 17 | Num | Liquidación. IVA DEVENGADO. Otras operaciones con inversión del sujeto pasivo (excepto adq. intracom.). Cuota [24] |  | 15 enteros + 2 decimales
40 | 469 | 17 | N | Liquidación. IVA DEVENGADO. Modificación bases y cuotas en régimen general. Base imponible  [25] |  | 15 enteros + 2 decimales
41 | 486 | 17 | N | Liquidación. IVA DEVENGADO. Modificación bases y cuotas en régimen general. Cuota [26] |  | 15 enteros + 2 decimales
42 | 503 | 17 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.  Base imponible  [27] |  | 15 enteros + 2 decimales
43 | 520 | 5 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.   Tipo % [28] |  | 3 enteros + 2 decimales
44 | 525 | 17 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.  Cuota [29] |  | 15 enteros + 2 decimales
45 | 542 | 17 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.  Base imponible  [30] |  | 15 enteros + 2 decimales
46 | 559 | 5 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.   Tipo % [31] |  | 3 enteros + 2 decimales
47 | 564 | 17 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.  Cuota [32] |  | 15 enteros + 2 decimales
48 | 581 | 17 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.   Base imponible  [33] |  | 15 enteros + 2 decimales
49 | 598 | 5 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.   Tipo % [34] |  | 3 enteros + 2 decimales
50 | 603 | 17 | Num | Liquidación. IVA DEVENGADO. Recargo de Equivalencia.   Cuota [35] |  | 15 enteros + 2 decimales
51 | 620 | 17 | N | Liquidación. IVA DEVENGADO. Modificación bases y cuotas del recargo de equivalencia.   Base imponible  [36] |  | 15 enteros + 2 decimales
52 | 637 | 17 | N | Liquidación. IVA DEVENGADO. Modificación bases y cuotas del recargo de equivalencia.  Cuota  [37] |  | 15 enteros + 2 decimales
53 | 654 | 34 | An | Reservado para la Administración
54 | 688 | 17 | N | Total cuota devengada ([03]+[06]+[09]+[11]+[14]+[17]+[20]+[22]+[24]+[26]+[29]+[32]+[35]+[37]). [38] |  | 15 enteros + 2 decimales
55 | 705 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en operaciones intragrupo corrientes.  Base imponible  [39] |  | 15 enteros + 2 decimales
56 | 722 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en operaciones intragrupo corrientes.  Cuota  [40] |  | 15 enteros + 2 decimales
57 | 739 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en operaciones intragrupo con bienes de inversión. Base imponible [41] |  | 15 enteros + 2 decimales
58 | 756 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en operaciones intragrupo con bienes de inversión. Cuota [42] |  | 15 enteros + 2 decimales
59 | 773 | 17 | N | Liquidación. IVA DEDUCIBLE. Rectificación de deducciones por operaciones intragrupo. Base imponible [43] |  | 15 enteros + 2 decimales
60 | 790 | 17 | N | Liquidación. IVA DEDUCIBLE. Rectificación de deducciones por operaciones intragrupo. Cuota [44] |  | 15 enteros + 2 decimales
61 | 807 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en otras operaciones interiores corrientes. Base imponible [45] |  | 15 enteros + 2 decimales
62 | 824 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en otras operaciones interiores corrientes. Cuota [46] |  | 15 enteros + 2 decimales
63 | 841 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en otras operaciones interiores con bienes de inversión. Base imponible [47] |  | 15 enteros + 2 decimales
64 | 858 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en otras operaciones interiores con bienes de inversión. Cuota [48] |  | 15 enteros + 2 decimales
65 | 875 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en las importaciones de bienes corrientes. Base imponible [49] |  | 15 enteros + 2 decimales
66 | 892 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en las importaciones de bienes corrientes. Cuota [50] |  | 15 enteros + 2 decimales
67 | 909 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en las importaciones de bienes de inversión. Base imponible [51] |  | 15 enteros + 2 decimales
68 | 926 | 17 | Num | Liquidación. IVA DEDUCIBLE. Por cuotas soportadas en las importaciones de bienes de inversión. Cuota [52] |  | 15 enteros + 2 decimales
69 | 943 | 17 | Num | Liquidación. IVA DEDUCIBLE. En adquisiciones intracomunitarias de bienes y servicios corrientes. Base imponible [53] |  | 15 enteros + 2 decimales
70 | 960 | 17 | Num | Liquidación. IVA DEDUCIBLE. En adquisiciones intracomunitarias de bienes y servicios corrientes. Cuota[54] |  | 15 enteros + 2 decimales
71 | 977 | 17 | Num | Liquidación. IVA DEDUCIBLE. En adquisiciones intracomunitarias de bienes de inversión. Base imponible [55] |  | 15 enteros + 2 decimales
72 | 994 | 17 | Num | Liquidación. IVA DEDUCIBLE. En adquisiciones intracomunitarias de bienes de inversión. Cuota [56] |  | 15 enteros + 2 decimales
73 | 1011 | 17 | N | Liquidación. IVA DEDUCIBLE. Rectificación de deducciones en resto de operaciones (no intragrupo). Base imponible [57] |  | 15 enteros + 2 decimales
74 | 1028 | 17 | N | Liquidación. IVA DEDUCIBLE. Rectificación de deducciones en resto de operaciones (no intragrupo). Cuota [58] |  | 15 enteros + 2 decimales
75 | 1045 | 17 | N | Liquidación. IVA DEDUCIBLE.Compensación régimen especial A.G. y P. Cuota [59] |  | 15 enteros + 2 decimales
76 | 1062 | 17 | N | Liquidación. IVA DEDUCIBLE. Regularización bienes de inversión. Cuota [60] |  | 15 enteros + 2 decimales
77 | 1079 | 17 | N | Liquidación. IVA DEDUCIBLE. Regularización por aplicación del porcentaje definitivo de prorrata. Cuota [61] |  | 15 enteros + 2 decimales
78 | 1096 | 17 | N | Total a deducir ([40]+[42]+[44]+[46]+[48]+[50]+[52]+[54]+[56]+[58]+[59]+[60]+[61])  [62] |  | 15 enteros + 2 decimales
79 | 1113 | 1 | Num | Identificación. ¿Existe volumen de operaciones (art. 121 LIVA)? |  | Si=1, No=2. Nota 3
80 | 1114 | 1 | An | Sujeto pasivo que tributa exclusivamente a una Administración tributaria Foral con IVA a la importación liquidado
por la Aduana pendiente de ingreso |  | X o blanco. Nota 2 y Nota 3
81 | 1115 | 1 | An | Identificación. ¿Está exonerado de la Declaración-resumen anual del IVA, modelo 390? |  | Si=1, No=2.
82 | 1116 | 360 | An | Reservado para la Administración. |  | En blanco
83 | 1476 | 13 | An | Reservado para la Administración. Sello electronico |  | En blanco
84 | 1489 | 12 | An | Identificador de fin de registro. | obligatorio | Constante "</T32201000>"
TOTAL |  | 1500 | Posiciones
Nota 1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota2: Esta nueva marca no será aplicable para el periodo 01 del ejercicio 2018
Nota 3: Tributación exclusivamente a una Administración Foral
En el caso de de Tributación exclusivamente a una Administración Foral, los siguientes campos se rellenarán con el valor indicado:
Sujeto pasivo que tributa exclusivamente a una Administración tributaria Foral con IVA a la importación liquidado por la Aduana pendiente de ingreso = X "SÍ"
Identificación. Tipo régimen especial aplicable: Art. 163 sexies.Cinco LIVA.  = 2 (NO)
Identificación. ¿Está inscrito en el Registro de devolución mensual (Art. 30 RIVA)? = 2 (NO)
Identificación. ¿Es destinatario de operaciones a las que se aplique el régimen especial del criterio de caja?. = 2 (NO)
Identificación. Aplicación de la prorrata especial (art. 103.Dos.1ºLIVA)  - Opción por la aplicación / Revocación de la opción = 0 (blanco)
Identificación. ¿Existe volumen de operaciones (art. 121 LIVA)? = 2 (NO)

# DR32202

 | Agencia Tributaria
Modelo 322 |  | Diseño de registro. Castellano
 |  | Impuesto sobre el Valor Añadido. Grupo de entidades. Modelo individual. Autoliquidación mensual
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 11 | An | Inicio del identificador de modelo | obligatorio | Constante "<T32202000>"
2 | 12 | 1 | A | Indicador de página complementaria | obligatorio | blanco
3 | 13 | 17 | N | Regularización cuotas art. 80.Cinco.5ª LIVA [76] |  | 15 enteros + 2 decimales
4 | 30 | 17 | N | Liquidación (continuación). Diferencia ([38] - [62]) . [63] |  | 15 enteros + 2 decimales
5 | 47 | 5 | An | Reservado para la Agencia Tributaria
6 | 52 | 17 | N | Liquidación (continuación). Atribuible a la Administración del Estado. [65] |  | 15 enteros + 2 decimales
7 | 69 | 17 | Num | IVA a la importación liquidado por la Aduana pendiente de ingreso [77] |  | 15 enteros + 2 decimales
8 | 86 | 17 | Num | Liquidación (continuación). Cuotas a compensar de períodos anteriores a la incorporación al grupo. [66] |  | 15 enteros + 2 decimales
9 | 103 | 17 | N | Liquidación (continuación). Exclusivamente para sujetos pasivos que tributan conjuntamente a la Administración del Estado y a las Haciendas
Forales. Resultado de la regularización anual. [67] |  | 15 enteros + 2 decimales
10 | 120 | 17 | N | Liquidación (continuación). Resultado ([65] - [66] + [67]) [68] |  | 15 enteros + 2 decimales
11 | 137 | 17 | N | Liquidación (continuación).A deducir (exclusivamente en caso de autoliquidación complementaria):
Resultado de las autoliquidaciones anteriores presentadas por el mismo concepto, ejercicio y periodo. [69] |  | 15 enteros + 2 decimales
12 | 154 | 17 | N | Resultado de la autoliquidación ([68] - [69]) [70] |  | 15 enteros + 2 decimales
13 | 171 | 17 | N | Información adicional. Entregas intracomunitarias de bienes y servicios [71] |  | 15 enteros + 2 decimales
14 | 188 | 17 | N | Información adicional. Exportaciones y operaciones asimiladas. [72] |  | 15 enteros + 2 decimales
15 | 205 | 17 | N | Información adicional. Operaciones no sujetas o con inversión del sujeto pasivo que originan el derecho a deducción  [73]
(hasta 30 de junio, resto a 0) |  | 15 enteros + 2 decimales
16 | 222 | 17 | N | Información adicional. Exclusivamente para aquellos sujetos pasivos que sean destinatarios de operaciones afectadas por el régimen del criterio de caja:  Importe de las adquisiciones de bienes y servicios a las que sea
de aplicación o afecte el régimen especial del criterio de caja.  Base imponible [74] |  | 15 enteros + 2 decimales
17 | 239 | 17 | N | Información adicional. Exclusivamente para aquellos sujetos pasivos que sean destinatarios de operaciones afectadas por el régimen del criterio de caja:  Importe de las adquisiciones de bienes y servicios a las que sea
de aplicación o afecte el régimen especial del criterio de caja.  Cuota soportada. [75] |  | 15 enteros + 2 decimales
18 | 256 | 1 | An | Autoliquidación complementaria. Autoliquidación complementaria |  | X o blanco
19 | 257 | 13 | An | Autoliquidación complementaria. Número de justificante de la autoliquidación anterior
20 | 270 | 1 | An | Sin actividad. Sin actividad |  | X o blanco
21 | 271 | 5 | Num | Liquidación (continuación). Atribuible a la Administración del Estado (%) . [64] |  | 3 enteros y 2 decimales
22 | 276 | 17 | N | Operaciones no sujetas por reglas de localización (excepto las incluidas en la casilla 123). [120] |  | 15 enteros + 2 decimales
23 | 293 | 17 | An | Reservado para la Agencia Tributaria
24 | 310 | 17 | N | Operaciones sujetas con inversión del sujeto pasivo [122] |  | 15 enteros + 2 decimales
25 | 327 | 17 | N | Operaciones no sujetas por reglas de localización acogidas a los regímenes especiales de ventanilla única [123] |  | 15 enteros + 2 decimales
26 | 344 | 17 | N | Operaciones sujetas y acogidas a los regímenes especiales de ventanilla única [124] |  | 15 enteros + 2 decimales
27 | 361 | 1628 | An | Reservado para la Agencia Tributaria | En blanco
28 | 1989 | 12 | An | Identificador de fin de registro. | obligatorio | Constante "</T32202000>"
TOTAL |  | 2000 | Posiciones

# DR32203

 | Agencia Tributaria
Modelo 322 |  | Diseño de registro. Castellano
 |  | Impuesto sobre el Valor Añadido. Grupo de entidades. Modelo individual. Autoliquidación mensual
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 11 | An | Inicio del identificador de modelo | obligatorio | Constante "<T32203000>"
2 | 12 | 1 | A | Indicador de página complementaria | obligatorio | blanco
3 | 13 | 3 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración B - Clave - Principal
4 | 16 | 4 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración C - Epígrafe IAE - Principal
5 | 20 | 3 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración B - Clave - Otras - 1ª
6 | 23 | 4 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración C - Epígrafe IAE - Otras - 1ª
7 | 27 | 3 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración B - Clave - Otras - 2ª
8 | 30 | 4 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración C - Epígrafe IAE - Otras - 2ª
9 | 34 | 3 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración B - Clave - Otras - 3ª
10 | 37 | 4 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración C - Epígrafe IAE - Otras - 3ª
11 | 41 | 3 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración B - Clave - Otras - 4ª
12 | 44 | 4 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración C - Epígrafe IAE - Otras - 4ª
13 | 48 | 3 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración B - Clave - Otras - 5ª
14 | 51 | 4 | An | Exclusivamente a cumplimentar en el último periodo de la Declaración C - Epígrafe IAE - Otras - 5ª
15 | 55 | 5 | Num | Información de la tributación por territorio (sólo para sujetos pasivos que tributan a varias Administraciones) - Álava [89] |  | 3 enteros y 2 decimales
16 | 60 | 5 | Num | Información de la tributación por territorio (sólo para sujetos pasivos que tributan a varias Administraciones)-Guipúcoa [90] |  | 3 enteros y 2 decimales
17 | 65 | 5 | Num | Información de la tributación por territorio (sólo para sujetos pasivos que tributan a varias Administraciones) -Vizcaya [91] |  | 3 enteros y 2 decimales
18 | 70 | 5 | Num | Información de la tributación por territorio (sólo para sujetos pasivos que tributan a varias Administraciones) -Navarra [92] |  | 3 enteros y 2 decimales
19 | 75 | 17 | N | Operaciones realizadas en el ejercicio. Operaciones en régimen general [80] |  | 15 enteros + 2 decimales
20 | 92 | 17 | N | Operaciones realizadas en el ejercicio. Operaciones a las que habiéndoles sido aplicado el régimen especial del criterio de caja hubieran resultado devengadas conforme a la regla general de devengo contenida en el art. 75 LIVA [81] |  | 15 enteros + 2 decimales
21 | 109 | 17 | N | Operaciones realizadas en el ejercicio. Entregas intracomunitarias de bienes y servicios [93] |  | 15 enteros + 2 decimales
22 | 126 | 17 | N | Operaciones realizadas en el ejercicio.. Exportaciones y otras operaciones exentas con derecho a deducción [94] |  | 15 enteros + 2 decimales
23 | 143 | 17 | N | Operaciones realizadas en el ejercicio. Operaciones exentas sin derecho a deducción [83] |  | 15 enteros + 2 decimales
24 | 160 | 17 | N | Operaciones no sujetas por reglas de localización (excepto las incluidas en la casilla 126) [84] |  | 15 enteros + 2 decimales
25 | 177 | 17 | An | Reservado para la Agencia Tributaria
26 | 194 | 17 | N | Operaciones realizadas en el ejercicio. Operaciones en régimen simplificado [86] |  | 15 enteros + 2 decimales
27 | 211 | 17 | N | Operaciones realizadas en el ejercicio. Operaciones en régimen especial de la agricultura, ganadería y pesca [95] |  | 15 enteros + 2 decimales
28 | 228 | 17 | N | Operaciones realizadas en el ejercicio.. Operaciones realizadas por sujetos pasivos acogidos al régimen especial del recargo de equivalencia [96] |  | 15 enteros + 2 decimales
29 | 245 | 17 | N | Operaciones realizadas en el ejercicio. Operaciones en Régimen especial de bienes usados, objetos de arte, antigüedades y objetos de colección [97] |  | 15 enteros + 2 decimales
30 | 262 | 17 | N | Operaciones realizadas en el ejercicio. Operaciones en régimen especial de Agencias de Viajes [98] |  | 15 enteros + 2 decimales
31 | 279 | 17 | N | Operaciones realizadas en el ejercicio. Entregas de bienes inmuebles y operaciones financieras no habituales [79] |  | 15 enteros + 2 decimales
32 | 296 | 17 | N | Operaciones realizadas en el ejercicio. Entregas de bienes de inversión [99] |  | 15 enteros + 2 decimales
33 | 313 | 17 | N | Operaciones realizadas en el ejercicio. Total volumen de operaciones (Art. 121 Ley IVA) (80 + 81 + 93 + 94 + 83 + 84 + 125 + 126 + 127 + 128 + 86 + 95 + 96 + 97 + 98 - 79 - 99) [88] |  | 15 enteros + 2 decimales
34 | 330 | 5 | Num | Información de la tributación por territorio (sólo para sujetos pasivos que tributan a varias Administraciones) -Territorio común [107] |  | 3 enteros y 2 decimales
35 | 335 | 17 | N | Operaciones sujetas con inversión del sujeto pasivo [125] |  | 15 enteros + 2 decimales
36 | 352 | 17 | N | Operaciones no sujetas por reglas de localización acogidas a los regímenes especiales de ventanilla única [126] |  | 15 enteros + 2 decimales
37 | 369 | 17 | N | Operaciones sujetas y acogidas a los regímenes especiales de ventanilla única [127] |  | 15 enteros + 2 decimales
38 | 386 | 17 | N | Operaciones intragrupo valoradas conforme a lo dispuesto en los arts. 78 y 79 LIVA [128] |  | 15 enteros + 2 decimales
39 | 403 | 1186 | An | Reservado para la Agencia Tributaria | En blanco
40 | 1589 | 12 | An | Identificador de fin de registro. | obligatorio | Constante "</T32203000>"
TOTAL |  | 1600 | Posiciones

# DR32204

 | Agencia Tributaria
Modelo 322 |  | Diseño de registro. Castellano
 |  | Impuesto sobre el Valor Añadido. Grupo de entidades. Modelo individual. Autoliquidación mensual
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 11 | An |  | Inicio del identificador de modelo | obligatorio | Constante "<T32204000>"
2 | 12 | 1 | A |  | Indicador de página complementaria | obligatorio | blanco
3 | 13 | 3 | An | C | Prorratas - 1 - Código CNAE [500] |  | Incluido en fichero CNAE.TXT.
4 | 16 | 17 | Num | C | Prorratas - 1 - Importe de operaciones [501] |  | 15 enteros 2 decimales
5 | 33 | 17 | Num | C | Prorratas - 1 - Importe de operaciones con derecho a deducción [502] |  | 15 enteros 2 decimales
6 | 50 | 1 | An | C | Prorratas - 1 - Tipo de prorrata [503] |  | "G", "E" o blanco.
7 | 51 | 5 | Num | C | Prorratas - 1 - % de prorrata [504] |  | 3 enteros 2 decimales, menor o igual que 100.
8 | 56 | 3 | An | C | Prorratas - 2 - Código CNAE [505] |  | Incluido en fichero CNAE.TXT.
9 | 59 | 17 | Num | C | Prorratas - 2 - Importe de operaciones [506] |  | 15 enteros 2 decimales
10 | 76 | 17 | Num | C | Prorratas - 2 - Importe de operaciones con derecho a deducción [507] |  | 15 enteros 2 decimales
11 | 93 | 1 | An | C | Prorratas - 2 - Tipo de prorrata [508] |  | "G", "E" o blanco.
12 | 94 | 5 | Num | C | Prorratas - 2 - % de prorrata [509] |  | 3 enteros 2 decimales, menor o igual que 100.
13 | 99 | 3 | An | C | Prorratas - 3 - Código CNAE [510] |  | Incluido en fichero CNAE.TXT.
14 | 102 | 17 | Num | C | Prorratas - 3 - Importe de operaciones [511] |  | 15 enteros 2 decimales
15 | 119 | 17 | Num | C | Prorratas - 3 - Importe de operaciones con derecho a deducción[512] |  | 15 enteros 2 decimales
16 | 136 | 1 | An | C | Prorratas - 3 - Tipo de prorrata [513] |  | "G", "E" o blanco.
17 | 137 | 5 | Num | C | Prorratas - 3 - % de prorrata [514] |  | 3 enteros 2 decimales, menor o igual que 100.
18 | 142 | 3 | An | C | Prorratas - 4 - Código CNAE[515] |  | Incluido en fichero CNAE.TXT.
19 | 145 | 17 | Num | C | Prorratas - 4 - Importe de operaciones[516] |  | 15 enteros 2 decimales
20 | 162 | 17 | Num | C | Prorratas - 4 - Importe de operaciones con derecho a deducción [517] |  | 15 enteros 2 decimales
21 | 179 | 1 | An | C | Prorratas - 4 - Tipo de prorrata[518] |  | "G", "E" o blanco.
22 | 180 | 5 | Num | C | Prorratas - 4 - % de prorrata [519] |  | 3 enteros 2 decimales, menor o igual que 100.
23 | 185 | 3 | An | C | Prorratas - 5 - Código CNAE [520] |  | Incluido en fichero CNAE.TXT.
24 | 188 | 17 | Num | C | Prorratas - 5 - Importe de operaciones[521] |  | 15 enteros 2 decimales
25 | 205 | 17 | Num | C | Prorratas - 5 - Importe de operaciones con derecho a deducción[522] |  | 15 enteros 2 decimales
26 | 222 | 1 | An | C | Prorratas - 5 - Tipo de prorrata [523] |  | "G", "E" o blanco.
27 | 223 | 5 | Num | C | Prorratas - 5 - % de prorrata [524] |  | 3 enteros 2 decimales, menor o igual que 100.
28 | 228 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en operaciones interiores. Bienes y servicios corrientes. Base imponible [700] |  | 15 enteros 2 decimales
29 | 245 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en operaciones interiores Bienes y servicios corrientes.Cuota deducible [701] |  | 15 enteros 2 decimales
30 | 262 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en operaciones interiores. Bienes de inversión. Base imponible [702] |  | 15 enteros 2 decimales
31 | 279 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en operaciones interiores. Bienes de inversión.Cuota deducible [703] |  | 15 enteros 2 decimales
32 | 296 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en importaciones. Bienes corrientes. Base imponible [704] |  | 15 enteros 2 decimales
33 | 313 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en importaciones. Bienes corrientes.Cuota deducible [705] |  | 15 enteros 2 decimales
34 | 330 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en importaciones Bienes de inversión. Base imponible [706] |  | 15 enteros 2 decimales
35 | 347 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en importaciones.  Bienes de inversión.Cuota deducible [707] |  | 15 enteros 2 decimales
36 | 364 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en adquisiciones intracomunitarias. Bienes y servicios corrientes. Base imponible [708] |  | 15 enteros 2 decimales
37 | 381 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en adquisiciones intracomunitarias. Bienes y servicios corrientes.Cuota deducible [709] |  | 15 enteros 2 decimales
38 | 398 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en adquisiciones intracomunitarias.  Bienes de inversión. Base imponible [710] |  | 15 enteros 2 decimales
39 | 415 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. IVA deducible en adquisiciones intracomunitarias. Bienes y servicios corrientes.Cuota deducible [711] |  | 15 enteros 2 decimales
40 | 432 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. Compensaciones en régimen especial de la agricultura, ganadería y pesca. Base imponible [712] |  | 15 enteros 2 decimales
41 | 449 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. Compensaciones en régimen especial de la agricultura, ganadería y pesca. Cuota deducible [713] |  | 15 enteros 2 decimales
42 | 466 | 17 | N | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. Rectificación de deducciones. Base imponible [714] |  | 15 enteros 2 decimales
43 | 483 | 17 | N | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. Rectificación de deducciones. Cuota deducible [715] |  | 15 enteros 2 decimales
44 | 500 | 17 | N | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. Regularización de bienes de inversión. Cuota deducible [716] |  | 15 enteros 2 decimales
45 | 517 | 17 | N | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 1. Suma de deducciones (701 + 703 + 705 + 707 + 709 + 711 + 713 + 715 + 716). Cuota deducible [717] |  | 15 enteros 2 decimales
46 | 534 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en operaciones interiores. Bienes y servicios corrientes. Base imponible [718] |  | 15 enteros 2 decimales
47 | 551 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2.. IVA deducible en operaciones interiores Bienes y servicios corrientes.Cuota deducible [719] |  | 15 enteros 2 decimales
48 | 568 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en operaciones interiores. Bienes de inversión. Base imponible [720] |  | 15 enteros 2 decimales
49 | 585 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en operaciones interiores. Bienes de inversión.Cuota deducible [721] |  | 15 enteros 2 decimales
50 | 602 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en importaciones. Bienes corrientes. Base imponible [722] |  | 15 enteros 2 decimales
51 | 619 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en importaciones. Bienes corrientes.Cuota deducible [723] |  | 15 enteros 2 decimales
52 | 636 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en importaciones Bienes de inversión. Base imponible [724] |  | 15 enteros 2 decimales
53 | 653 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en importaciones.  Bienes de inversión.Cuota deducible [725] |  | 15 enteros 2 decimales
54 | 670 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en adquisiciones intracomunitarias. Bienes y servicios corrientes. Base imponible [726] |  | 15 enteros 2 decimales
55 | 687 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en adquisiciones intracomunitarias. Bienes y servicios corrientes.Cuota deducible [727] |  | 15 enteros 2 decimales
56 | 704 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en adquisiciones intracomunitarias.  Bienes de inversión. Base imponible [728] |  | 15 enteros 2 decimales
57 | 721 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. IVA deducible en adquisiciones intracomunitarias. Bienes y servicios corrientes.Cuota deducible [729] |  | 15 enteros 2 decimales
58 | 738 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. Compensaciones en régimen especial de la agricultura, ganadería y pesca. Base imponible [730] |  | 15 enteros 2 decimales
59 | 755 | 17 | Num | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. Compensaciones en régimen especial de la agricultura, ganadería y pesca. Cuota deducible [731] |  | 15 enteros 2 decimales
60 | 772 | 17 | N | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. Rectificación de deducciones. Base imponible [732] |  | 15 enteros 2 decimales
61 | 789 | 17 | N | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. Rectificación de deducciones. Cuota deducible [733] |  | 15 enteros 2 decimales
62 | 806 | 17 | N | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. Regularización de bienes de inversión. Cuota deducible [734] |  | 15 enteros 2 decimales
63 | 823 | 17 | N | C | Actividades con regímenes de deducción diferenciados. IVA deducible: Grupo 2. Suma de deducciones (719 + 721 + 723 + 725 + 727 + 729 + 731 + 733 + 734). Cuota deducible [735] |  | 15 enteros 2 decimales
64 | 840 | 1149 | An |  | Reservado para la Agencia Tributaria | En blanco
65 | 1989 | 12 | An |  | Identificador de fin de registro. | obligatorio | Constante "</T32204000>"
TOTAL |  | 2000 | Posiciones