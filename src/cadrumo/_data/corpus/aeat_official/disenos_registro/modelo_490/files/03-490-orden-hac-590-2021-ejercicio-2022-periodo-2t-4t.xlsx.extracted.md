# DR49000

 | Agencia Tributaria
Modelo 490 |  | Diseño de registro. Impuesto sobre Determinados Servicios Digitales.
version 2.3 |  | Autoliquidación.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | Constante "<T"
2 | 3 | 3 | An | Modelo. |  | Constante "490"
3 | 6 | 1 | An | Discriminante |  | Constante "0"
4 | 7 | 4 | An | Ejercicio de devengo (EEEE)
5 | 11 | 2 | An | Periodo |  | "1T", "2T", "3T" o "4T"
6 | 13 | 5 | An | Tipo y cierre |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | variable | An | Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Tipo+> |  | "</T4900EEEEPP0000>"
Total |  | Variable
Nota 1:
A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# DR49001

 | Agencia Tributaria
Modelo 490 |  | Diseño de registro.  Impuesto sobre Determinados Servicios Digitales.
 |  | Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Indicador de inicio de registro | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "490"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "01"
4 | 8 | 4 | An |  | Indicador de inicio de registro | Obligatorio | Constante "000>"
5 | 12 | 1 | A |  | Indicador de página complementaria | Obligatorio | C o blanco
6 | 13 | 1 | An |  | Tipo de declaración | Obligatorio | Ver nota 1
7 | 14 | 9 | An |  | Identificación - NIF | Obligatorio
8 | 23 | 125 | An |  | Identificación - Razón social, nombre y apellidos | Obligatorio
9 | 148 | 4 | Num |  | Ejercicio | Obligatorio
10 | 152 | 2 | An |  | Período | Obligatorio | "1T", "2T", "3T" o "4T"
11 | 154 | 100 | An |  | Identificación - Correo electrónico (email)
12 | 254 | 9 | An |  | Identificación - NIF Representante
13 | 263 | 125 | An |  | Identificación - Razón social, nombre y apellidos Representante
14 | 388 | 125 | An |  | Identificación del grupo. Denominación o nombre del grupo
15 | 513 | 2 | An |  | Identificación del grupo. País en el que reside la dominante |  | Código de País
ISO 3166-1 alfa-2
16 | 515 | 125 | An |  | Identificación del grupo. Dominante
17 | 640 | 1 | An |  | Liquidación. Base Imponible. Regularización (art. 10.3 Ley 4/2020) [A] |  | X o blanco
18 | 641 | 17 | Num |  | Liquidación. Base Imponible. 1 Servicios de publicidad en línea. Ingresos totales [01] |  | 15 ent + 2 dec
19 | 658 | 17 | Num |  | Liquidación. Base Imponible. 1 Servicios de publicidad en línea. Base imponible [02] |  | 15 ent + 2 dec
20 | 675 | 17 | N |  | Liquidación. Base Imponible. 1 Servicios de publicidad en línea. Regularización Base imponible (art. 10.3)  [03] |  | 15 ent + 2 dec
21 | 692 | 17 | Num |  | Liquidación. Base Imponible. 2. Servicios de intermediación en línea
.A Con entrega de bienes o prestación de servicios subyacentes. Ingresos totales [04] |  | 15 ent + 2 dec
22 | 709 | 17 | Num |  | Liquidación. Base Imponible. 2 Servicios de intermediación en línea
.A Con entrega de bienes o prestación de servicios subyacentes. Base imponible  [05] |  | 15 ent + 2 dec
23 | 726 | 17 | N |  | Liquidación. Base Imponible. 2. Servicios de intermediación en línea
.A Con entrega de bienes o prestación de servicios subyacentes. Regularización Base imponible (art. 10.3)  [06] |  | 15 ent + 2 dec
24 | 743 | 17 | Num |  | Liquidación. Base Imponible. 2 Servicios de intermediación en línea
.B Demás servicios de intermediación en línea. Ingresos totales [07] |  | 15 ent + 2 dec
25 | 760 | 17 | Num |  | Liquidación. Base Imponible. 2 Servicios de intermediación en línea
.B Demás servicios de intermediación en línea.  Base imponible [08] |  | 15 ent + 2 dec
26 | 777 | 17 | N |  | Liquidación. Base Imponible. 2 Servicios de intermediación en línea
.B Demás servicios de intermediación en línea. Regularización Base imponible (art. 10.3) [09] |  | 15 ent + 2 dec
27 | 794 | 17 | Num |  | Liquidación. Base Imponible. 3 Servicios de transmisión de datos. Ingresos totales [10] |  | 15 ent + 2 dec
28 | 811 | 17 | Num |  | Liquidación. Base Imponible. 3 Servicios de transmisión de datos. Base imponible [11] |  | 15 ent + 2 dec
29 | 828 | 17 | N |  | Liquidación. Base Imponible. 3 Servicios de transmisión de datos.Regularización Base imponible (art. 10.3) [12] |  | 15 ent + 2 dec
30 | 845 | 17 | Num |  | Liquidación. Base imponible total del peródo ([02] + [05 + [08] + [11])  [13] |  | 15 ent + 2 dec
31 | 862 | 17 | N |  | Liquidación. Importe regularización base imponible periodos anteriores (art. 10.3 Ley 4/2020) ([03] + [06] + [09] + [12]) [14] |  | 15 ent + 2 dec
32 | 879 | 3 | Num |  | Liquidación. Tipo [15] |  | 1 ent + 2 dec
33 | 882 | 17 | Num |  | Liquidación. Cuota íntegra ([13] x [15])  [16] |  | 15 ent + 2 dec
34 | 899 | 17 | Num |  | Cuota íntegra atribuible a la Administración del Estado ([16] x [24] [17] |  | 15 ent + 2 dec
35 | 916 | 17 | Num |  | AJUSTE CUOTA ÍNTEGRA PERIODOS REGULARIZACIÓN ([363]) [18] |  | 15 ent + 2 dec
36 | 933 | 17 | N |  | Ajuste cuota íntegra períodos regularización atribuible al Estado ([364]) [19] |  | 15 ent + 2 dec
37 | 950 | 5 | Num |  | Información de la tributación por razón de territorio - Álava [20] |  | 3 ent + 2 dec
38 | 955 | 5 | Num |  | Información de la tributación por razón de territorio - Guipúzcoa [21] |  | 3 ent + 2 dec
39 | 960 | 5 | Num |  | Información de la tributación por razón de territorio - Vizcaya  [22] |  | 3 ent + 2 dec
40 | 965 | 5 | An |  | Reservado para la Administración
41 | 970 | 5 | Num |  | Información de la tributación por razón de territorio - Territorio común [24] | Obligatorio | Ver nota 2
42 | 975 | 17 | N |  | Resultado. A deducir (exclusivamente en caso de autoliquidaciones complementarias) Resultado de la anterior o anteriores declaraciones del mismo ejercicio y periodo [25] |  | 15 ent + 2 dec
43 | 992 | 17 | N |  | Resultado de la liquidación ([17] + [19] - [25]) [26] |  | 15 ent + 2 dec
44 | 1009 | 11 | An |  | Ingreso/Devolución. Código BIC/SWIFT
45 | 1020 | 34 | An |  | Ingreso/Devolución. Código IBAN
46 | 1054 | 1 | An |  | Declaración complementaria |  | C ó blanco
47 | 1055 | 13 | An |  | Número de justificante de la declaración anterior
48 | 1068 | 1 | An |  | Declaración negativa |  | N ó blanco
49 | 1069 | 20 | An |  | Reservado para la Administración |  | Blancos
50 | 1089 | 3 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T"
51 | 1092 | 3 | Num |  | Modelo | Obligatorio | Constante "490"
52 | 1095 | 2 | Num |  | Página | Obligatorio | Constante "01"
53 | 1097 | 4 | An |  | Indicador de fin de registro | Obligatorio | Constante "000>"
 | TOTAL | 1100 | POSICIONES
Nota 1: |  |  |  |  | 1. El tipo de declaración para la presentación por lotes puede ser: 
I (Ingreso en efectivo/adeudo en cuenta)
U (Domiciliación)
N (Negativa) 
D (Devolución)
 |  |  |  |  | 2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 490.txt
 |  |  |  |  | 3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
 |  |  |  |  | 4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
 |  |  |  |  | 5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
 |  |  |  |  | 6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 2: |  |  |  |  | 2. Tres enteros y dos decimales: este campo se cumplimentará obligatoriamente, poniendo un valor 100,00 (100000) en caso de no cumplimentar las casillas [20], [21] y [22]
 | TOTAL: | -1 |  |  | POSICIONES

# DR49002

 | Agencia Tributaria
Modelo 490 |  | Diseño de registro.  Impuesto sobre Determinados Servicios Digitales.
 |  | Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Indicador de inicio de registro | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "490"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "02"
4 | 8 | 4 | An |  | Indicador de inicio de registro | Obligatorio | Constante "000>"
5 | 12 | 1 | A |  | Indicador de página complementaria | Obligatorio | C o blanco
6 | 13 | 4 | Num |  | Regularización (art. 10.3 Ley 4/2020).Ejercicio
7 | 17 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).1T [27] |  | 15 ent + 2 dec
8 | 34 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).2T [48] |  | 15 ent + 2 dec
9 | 51 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).3T [69] |  | 15 ent + 2 dec
10 | 68 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).4T [90] |  | 15 ent + 2 dec
11 | 85 | 17 | Num |  | Regularización positiva (base imponible) (b). 1T [28] |  | 15 ent + 2 dec
12 | 102 | 17 | Num |  | Regularización positiva (base imponible) (b). 2T [49] |  | 15 ent + 2 dec
13 | 119 | 17 | Num |  | Regularización positiva (base imponible) (b). 3T [70] |  | 15 ent + 2 dec
14 | 136 | 17 | Num |  | Regularización positiva (base imponible) (b). 4T [91] |  | 15 ent + 2 dec
15 | 153 | 17 | N |  | Regularización negativa (base imponible) (c ). 1T [29] |  | 15 ent + 2 dec
16 | 170 | 17 | N |  | Regularización negativa (base imponible) (c ). 2T [50] |  | 15 ent + 2 dec
17 | 187 | 17 | N |  | Regularización negativa (base imponible) (c ). 3T [71] |  | 15 ent + 2 dec
18 | 204 | 17 | N |  | Regularización negativa (base imponible) (c ). 4T [92] |  | 15 ent + 2 dec
19 | 221 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 1T [30] |  | 15 ent + 2 dec
20 | 238 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 2T [51] |  | 15 ent + 2 dec
21 | 255 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 3T [72] |  | 15 ent + 2 dec
22 | 272 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 4T [93] |  | 15 ent + 2 dec
23 | 289 | 3 | Num |  | Tipo impositivo ( e ) .1T [31] | "3,00" | 1 ent + 2 dec
24 | 292 | 3 | Num |  | Tipo impositivo ( e ) .2T [52] | "3,00" | 1 ent + 2 dec
25 | 295 | 3 | Num |  | Tipo impositivo ( e ) .3T [73] | "3,00" | 1 ent + 2 dec
26 | 298 | 3 | Num |  | Tipo impositivo ( e ) .4T [94] | "3,00" | 1 ent + 2 dec
27 | 301 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 1T [32] |  | 15 ent + 2 dec
28 | 318 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 2T [53] |  | 15 ent + 2 dec
29 | 335 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 3T [74] |  | 15 ent + 2 dec
30 | 352 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 4T [95] |  | 15 ent + 2 dec
31 | 369 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 1T [33] |  | 15 ent + 2 dec
32 | 386 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 2T [54] |  | 15 ent + 2 dec
33 | 403 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 3T [75] |  | 15 ent + 2 dec
34 | 420 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 4T [96] |  | 15 ent + 2 dec
35 | 437 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 1T [34] |  | 15 ent + 2 dec
36 | 454 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 2T [55] |  | 15 ent + 2 dec
37 | 471 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 3T [76] |  | 15 ent + 2 dec
38 | 488 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 4T [97] |  | 15 ent + 2 dec
39 | 505 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 1T [35] |  | 15 ent + 2 dec
40 | 522 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 2T [56] |  | 15 ent + 2 dec
41 | 539 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 3T [77] |  | 15 ent + 2 dec
42 | 556 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 4T [98] |  | 15 ent + 2 dec
43 | 573 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 1T [36] |  | 15 ent + 2 dec
44 | 590 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 2T [57] |  | 15 ent + 2 dec
45 | 607 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 3T [78] |  | 15 ent + 2 dec
46 | 624 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 1T [99] |  | 15 ent + 2 dec
47 | 641 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 1T [37] |  | 15 ent + 2 dec
48 | 658 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 2T [58] |  | 15 ent + 2 dec
49 | 675 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 3T [79] |  | 15 ent + 2 dec
50 | 692 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 4T [100] |  | 15 ent + 2 dec
51 | 709 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 1T [38] |  | 3 ent + 2 dec
52 | 714 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 2T [59] |  | 3 ent + 2 dec
53 | 719 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 3T [80] |  | 3 ent + 2 dec
54 | 724 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 4T [101] |  | 3 ent + 2 dec
55 | 729 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 1T [39] |  | 3 ent + 2 dec
56 | 734 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 2T [60] |  | 3 ent + 2 dec
57 | 739 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 3T [81] |  | 3 ent + 2 dec
58 | 744 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 4T [102] |  | 3 ent + 2 dec
59 | 749 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 1T [40] |  | 3 ent + 2 dec
60 | 754 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 2T [61] |  | 3 ent + 2 dec
61 | 759 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 3T [82] |  | 3 ent + 2 dec
62 | 764 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 4T [103] |  | 3 ent + 2 dec
63 | 769 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 1T [41] |  | 3 ent + 2 dec
64 | 774 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 2T [62] |  | 3 ent + 2 dec
65 | 779 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 3T [83] |  | 3 ent + 2 dec
66 | 784 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 4T [104] |  | 3 ent + 2 dec
67 | 789 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 1T [42] |  | 3 ent + 2 dec
68 | 794 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 2T [63] |  | 3 ent + 2 dec
69 | 799 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 3T [84] |  | 3 ent + 2 dec
70 | 804 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 4T [105] |  | 3 ent + 2 dec
71 | 809 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 1T [43] |  | 3 ent + 2 dec
72 | 814 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 2T [64] |  | 3 ent + 2 dec
73 | 819 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 3T [85] |  | 3 ent + 2 dec
74 | 824 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 4T [106] |  | 3 ent + 2 dec
75 | 829 | 5 | An |  | Reservado para la Administración |  | Blancos
76 | 834 | 5 | An |  | Reservado para la Administración |  | Blancos
77 | 839 | 5 | An |  | Reservado para la Administración |  | Blancos
78 | 844 | 5 | An |  | Reservado para la Administración |  | Blancos
79 | 849 | 5 | An |  | Reservado para la Administración |  | Blancos
80 | 854 | 5 | An |  | Reservado para la Administración |  | Blancos
81 | 859 | 5 | An |  | Reservado para la Administración |  | Blancos
82 | 864 | 5 | An |  | Reservado para la Administración |  | Blancos
83 | 869 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 1T [46] |  | 3 ent + 2 dec
84 | 874 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 2T [67] |  | 3 ent + 2 dec
85 | 879 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 3T [88] |  | 3 ent + 2 dec
86 | 884 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 4T [109] |  | 3 ent + 2 dec
87 | 889 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 1T [47] |  | 3 ent + 2 dec
88 | 894 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 2T [68] |  | 3 ent + 2 dec
89 | 899 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 3T [89] |  | 3 ent + 2 dec
90 | 904 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 4T [110] |  | 3 ent + 2 dec
91 | 909 | 4 | Num |  | Regularización (art. 10.3 Ley 4/2020).Ejercicio
92 | 913 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).1T [111] |  | 15 ent + 2 dec
93 | 930 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).2T [132] |  | 15 ent + 2 dec
94 | 947 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).3T [153] |  | 15 ent + 2 dec
95 | 964 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).4T [174] |  | 15 ent + 2 dec
96 | 981 | 17 | Num |  | Regularización positiva (base imponible) (b). 1T [112] |  | 15 ent + 2 dec
97 | 998 | 17 | Num |  | Regularización positiva (base imponible) (b). 2T [133] |  | 15 ent + 2 dec
98 | 1015 | 17 | Num |  | Regularización positiva (base imponible) (b). 3T [154] |  | 15 ent + 2 dec
99 | 1032 | 17 | Num |  | Regularización positiva (base imponible) (b). 4T [175] |  | 15 ent + 2 dec
100 | 1049 | 17 | N |  | Regularización negativa (base imponible) (c ). 1T [113] |  | 15 ent + 2 dec
101 | 1066 | 17 | N |  | Regularización negativa (base imponible) (c ). 2T [134] |  | 15 ent + 2 dec
102 | 1083 | 17 | N |  | Regularización negativa (base imponible) (c ). 3T [155] |  | 15 ent + 2 dec
103 | 1100 | 17 | N |  | Regularización negativa (base imponible) (c ). 4T [176] |  | 15 ent + 2 dec
104 | 1117 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 1T [114] |  | 15 ent + 2 dec
105 | 1134 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 2T [135] |  | 15 ent + 2 dec
106 | 1151 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 3T [156] |  | 15 ent + 2 dec
107 | 1168 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 4T [177] |  | 15 ent + 2 dec
108 | 1185 | 3 | Num |  | Tipo impositivo ( e ) .1T [115] | "3,00" | 1 ent + 2 dec
109 | 1188 | 3 | Num |  | Tipo impositivo ( e ) .2T [136] | "3,00" | 1 ent + 2 dec
110 | 1191 | 3 | Num |  | Tipo impositivo ( e ) .3T [157] | "3,00" | 1 ent + 2 dec
111 | 1194 | 3 | Num |  | Tipo impositivo ( e ) .4T [178] | "3,00" | 1 ent + 2 dec
112 | 1197 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 1T [116] |  | 15 ent + 2 dec
113 | 1214 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 2T [137] |  | 15 ent + 2 dec
114 | 1231 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 3T [158] |  | 15 ent + 2 dec
115 | 1248 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 4T [179] |  | 15 ent + 2 dec
116 | 1265 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 1T [117] |  | 15 ent + 2 dec
117 | 1282 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 2T [138] |  | 15 ent + 2 dec
118 | 1299 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 3T [159] |  | 15 ent + 2 dec
119 | 1316 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 4T [180] |  | 15 ent + 2 dec
120 | 1333 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 1T [118] |  | 15 ent + 2 dec
121 | 1350 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 2T [139] |  | 15 ent + 2 dec
122 | 1367 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 3T [160] |  | 15 ent + 2 dec
123 | 1384 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 4T [181] |  | 15 ent + 2 dec
124 | 1401 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 1T [119] |  | 15 ent + 2 dec
125 | 1418 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 2T [140] |  | 15 ent + 2 dec
126 | 1435 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 3T [161] |  | 15 ent + 2 dec
127 | 1452 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 4T [182] |  | 15 ent + 2 dec
128 | 1469 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 1T [120] |  | 15 ent + 2 dec
129 | 1486 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 2T [141] |  | 15 ent + 2 dec
130 | 1503 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 3T [162] |  | 15 ent + 2 dec
131 | 1520 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 1T [183] |  | 15 ent + 2 dec
132 | 1537 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 1T [121] |  | 15 ent + 2 dec
133 | 1554 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 2T [142] |  | 15 ent + 2 dec
134 | 1571 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 3T [163] |  | 15 ent + 2 dec
135 | 1588 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 4T [184] |  | 15 ent + 2 dec
136 | 1605 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 1T [122] |  | 3 ent + 2 dec
137 | 1610 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 2T [143] |  | 3 ent + 2 dec
138 | 1615 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 3T [164] |  | 3 ent + 2 dec
139 | 1620 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 4T [185] |  | 3 ent + 2 dec
140 | 1625 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 1T [123] |  | 3 ent + 2 dec
141 | 1630 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 2T [144] |  | 3 ent + 2 dec
142 | 1635 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 3T [165] |  | 3 ent + 2 dec
143 | 1640 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 4T [186] |  | 3 ent + 2 dec
144 | 1645 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 1T [124] |  | 3 ent + 2 dec
145 | 1650 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 2T [145] |  | 3 ent + 2 dec
146 | 1655 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 3T [166] |  | 3 ent + 2 dec
147 | 1660 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 4T [187] |  | 3 ent + 2 dec
148 | 1665 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 1T [125] |  | 3 ent + 2 dec
149 | 1670 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 2T [146] |  | 3 ent + 2 dec
150 | 1675 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 3T [167] |  | 3 ent + 2 dec
151 | 1680 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 4T [188] |  | 3 ent + 2 dec
152 | 1685 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 1T [126] |  | 3 ent + 2 dec
153 | 1690 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 2T [147] |  | 3 ent + 2 dec
154 | 1695 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 3T [168] |  | 3 ent + 2 dec
155 | 1700 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 4T [189] |  | 3 ent + 2 dec
156 | 1705 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 1T [127] |  | 3 ent + 2 dec
157 | 1710 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 2T [148] |  | 3 ent + 2 dec
158 | 1715 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 3T [169] |  | 3 ent + 2 dec
159 | 1720 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 4T [190] |  | 3 ent + 2 dec
160 | 1725 | 5 | An |  | Reservado para la Administración |  | Blancos
161 | 1730 | 5 | An |  | Reservado para la Administración |  | Blancos
162 | 1735 | 5 | An |  | Reservado para la Administración |  | Blancos
163 | 1740 | 5 | An |  | Reservado para la Administración |  | Blancos
164 | 1745 | 5 | An |  | Reservado para la Administración |  | Blancos
165 | 1750 | 5 | An |  | Reservado para la Administración |  | Blancos
166 | 1755 | 5 | An |  | Reservado para la Administración |  | Blancos
167 | 1760 | 5 | An |  | Reservado para la Administración |  | Blancos
168 | 1765 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 1T [130] |  | 3 ent + 2 dec
169 | 1770 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 2T [151] |  | 3 ent + 2 dec
170 | 1775 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 3T [172] |  | 3 ent + 2 dec
171 | 1780 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 4T [193] |  | 3 ent + 2 dec
172 | 1785 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 1T [131] |  | 3 ent + 2 dec
173 | 1790 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 2T [152] |  | 3 ent + 2 dec
174 | 1795 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 3T [173] |  | 3 ent + 2 dec
175 | 1800 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 4T [194] |  | 3 ent + 2 dec
176 | 1805 | 184 | An |  | Reservado para la Administración |  | Blancos
177 | 1989 | 3 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T"
178 | 1992 | 3 | Num |  | Modelo | Obligatorio | Constante "490"
179 | 1995 | 2 | Num |  | Página | Obligatorio | Constante "02"
180 | 1997 | 4 | An |  | Indicador de fin de registro | Obligatorio | Constante "000>"
 | TOTAL | 2000 | POSICIONES

# DR49003

 | Agencia Tributaria
Modelo 490 |  | Diseño de registro.  Impuesto sobre Determinados Servicios Digitales.
 |  | Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Indicador de inicio de registro | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "490"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "03"
4 | 8 | 4 | An |  | Indicador de inicio de registro | Obligatorio | Constante "000>"
5 | 12 | 1 | A |  | Indicador de página complementaria | Obligatorio | C o blanco
6 | 13 | 4 | Num |  | Regularización (art. 10.3 Ley 4/2020).Ejercicio
7 | 17 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).1T [195] |  | 15 ent + 2 dec
8 | 34 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).2T [216] |  | 15 ent + 2 dec
9 | 51 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).3T [237] |  | 15 ent + 2 dec
10 | 68 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).4T [258] |  | 15 ent + 2 dec
11 | 85 | 17 | Num |  | Regularización positiva (base imponible) (b). 1T [196] |  | 15 ent + 2 dec
12 | 102 | 17 | Num |  | Regularización positiva (base imponible) (b). 2T [217] |  | 15 ent + 2 dec
13 | 119 | 17 | Num |  | Regularización positiva (base imponible) (b). 3T [238] |  | 15 ent + 2 dec
14 | 136 | 17 | Num |  | Regularización positiva (base imponible) (b). 4T [259] |  | 15 ent + 2 dec
15 | 153 | 17 | N |  | Regularización negativa (base imponible) (c ). 1T [197] |  | 15 ent + 2 dec
16 | 170 | 17 | N |  | Regularización negativa (base imponible) (c ). 2T [218] |  | 15 ent + 2 dec
17 | 187 | 17 | N |  | Regularización negativa (base imponible) (c ). 3T [239] |  | 15 ent + 2 dec
18 | 204 | 17 | N |  | Regularización negativa (base imponible) (c ). 4T [260] |  | 15 ent + 2 dec
19 | 221 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 1T [198] |  | 15 ent + 2 dec
20 | 238 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 2T [219] |  | 15 ent + 2 dec
21 | 255 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 3T [240] |  | 15 ent + 2 dec
22 | 272 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 4T [261] |  | 15 ent + 2 dec
23 | 289 | 3 | Num |  | Tipo impositivo ( e ) .1T [199] | "3,00" | 1 ent + 2 dec
24 | 292 | 3 | Num |  | Tipo impositivo ( e ) .2T [220] | "3,00" | 1 ent + 2 dec
25 | 295 | 3 | Num |  | Tipo impositivo ( e ) .3T [241] | "3,00" | 1 ent + 2 dec
26 | 298 | 3 | Num |  | Tipo impositivo ( e ) .4T [262] | "3,00" | 1 ent + 2 dec
27 | 301 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 1T [200] |  | 15 ent + 2 dec
28 | 318 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 2T [221] |  | 15 ent + 2 dec
29 | 335 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 3T [242] |  | 15 ent + 2 dec
30 | 352 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 4T [263] |  | 15 ent + 2 dec
31 | 369 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 1T [201] |  | 15 ent + 2 dec
32 | 386 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 2T [222] |  | 15 ent + 2 dec
33 | 403 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 3T [243] |  | 15 ent + 2 dec
34 | 420 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 4T [264] |  | 15 ent + 2 dec
35 | 437 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 1T [202] |  | 15 ent + 2 dec
36 | 454 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 2T [223] |  | 15 ent + 2 dec
37 | 471 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 3T [244] |  | 15 ent + 2 dec
38 | 488 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 4T [265] |  | 15 ent + 2 dec
39 | 505 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 1T [203] |  | 15 ent + 2 dec
40 | 522 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 2T [224] |  | 15 ent + 2 dec
41 | 539 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 3T [245] |  | 15 ent + 2 dec
42 | 556 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 4T [266] |  | 15 ent + 2 dec
43 | 573 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 1T [204] |  | 15 ent + 2 dec
44 | 590 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 2T [225] |  | 15 ent + 2 dec
45 | 607 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 3T [246] |  | 15 ent + 2 dec
46 | 624 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 1T [267] |  | 15 ent + 2 dec
47 | 641 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 1T [205] |  | 15 ent + 2 dec
48 | 658 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 2T [226] |  | 15 ent + 2 dec
49 | 675 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 3T [247] |  | 15 ent + 2 dec
50 | 692 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 4T [268] |  | 15 ent + 2 dec
51 | 709 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 1T [206] |  | 3 ent + 2 dec
52 | 714 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 2T [227] |  | 3 ent + 2 dec
53 | 719 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 3T [248] |  | 3 ent + 2 dec
54 | 724 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 4T [269] |  | 3 ent + 2 dec
55 | 729 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 1T [207] |  | 3 ent + 2 dec
56 | 734 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 2T [228] |  | 3 ent + 2 dec
57 | 739 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 3T [249] |  | 3 ent + 2 dec
58 | 744 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 4T [270] |  | 3 ent + 2 dec
59 | 749 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 1T [208] |  | 3 ent + 2 dec
60 | 754 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 2T [229] |  | 3 ent + 2 dec
61 | 759 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 3T [250] |  | 3 ent + 2 dec
62 | 764 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 4T [271] |  | 3 ent + 2 dec
63 | 769 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 1T [209] |  | 3 ent + 2 dec
64 | 774 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 2T [230] |  | 3 ent + 2 dec
65 | 779 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 3T [251] |  | 3 ent + 2 dec
66 | 784 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 4T [272] |  | 3 ent + 2 dec
67 | 789 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 1T [210] |  | 3 ent + 2 dec
68 | 794 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 2T [231] |  | 3 ent + 2 dec
69 | 799 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 3T [252] |  | 3 ent + 2 dec
70 | 804 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 4T [273] |  | 3 ent + 2 dec
71 | 809 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 1T [211] |  | 3 ent + 2 dec
72 | 814 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 2T [232] |  | 3 ent + 2 dec
73 | 819 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 3T [253] |  | 3 ent + 2 dec
74 | 824 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 4T [274] |  | 3 ent + 2 dec
75 | 829 | 5 | An |  | Reservado para la Administración |  | Blancos
76 | 834 | 5 | An |  | Reservado para la Administración |  | Blancos
77 | 839 | 5 | An |  | Reservado para la Administración |  | Blancos
78 | 844 | 5 | An |  | Reservado para la Administración |  | Blancos
79 | 849 | 5 | An |  | Reservado para la Administración |  | Blancos
80 | 854 | 5 | An |  | Reservado para la Administración |  | Blancos
81 | 859 | 5 | An |  | Reservado para la Administración |  | Blancos
82 | 864 | 5 | An |  | Reservado para la Administración |  | Blancos
83 | 869 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 1T [214] |  | 3 ent + 2 dec
84 | 874 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 2T [235] |  | 3 ent + 2 dec
85 | 879 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 3T [256] |  | 3 ent + 2 dec
86 | 884 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 4T [277] |  | 3 ent + 2 dec
87 | 889 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 1T [215] |  | 3 ent + 2 dec
88 | 894 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 2T [236] |  | 3 ent + 2 dec
89 | 899 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 3T [257] |  | 3 ent + 2 dec
90 | 904 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 4T [278] |  | 3 ent + 2 dec
91 | 909 | 4 | Num |  | Regularización (art. 10.3 Ley 4/2020).Ejercicio
92 | 913 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).1T [279] |  | 15 ent + 2 dec
93 | 930 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).2T [300] |  | 15 ent + 2 dec
94 | 947 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).3T [321] |  | 15 ent + 2 dec
95 | 964 | 17 | Num |  | Base imponible declarada en período objeto de regularización (a).4T [342] |  | 15 ent + 2 dec
96 | 981 | 17 | Num |  | Regularización positiva (base imponible) (b). 1T [280] |  | 15 ent + 2 dec
97 | 998 | 17 | Num |  | Regularización positiva (base imponible) (b). 2T [301] |  | 15 ent + 2 dec
98 | 1015 | 17 | Num |  | Regularización positiva (base imponible) (b). 3T [322] |  | 15 ent + 2 dec
99 | 1032 | 17 | Num |  | Regularización positiva (base imponible) (b). 4T [343] |  | 15 ent + 2 dec
100 | 1049 | 17 | N |  | Regularización negativa (base imponible) (c ). 1T [281] |  | 15 ent + 2 dec
101 | 1066 | 17 | N |  | Regularización negativa (base imponible) (c ). 2T [302] |  | 15 ent + 2 dec
102 | 1083 | 17 | N |  | Regularización negativa (base imponible) (c ). 3T [323] |  | 15 ent + 2 dec
103 | 1100 | 17 | N |  | Regularización negativa (base imponible) (c ). 4T [344] |  | 15 ent + 2 dec
104 | 1117 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 1T [282] |  | 15 ent + 2 dec
105 | 1134 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 2T [303] |  | 15 ent + 2 dec
106 | 1151 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 3T [324] |  | 15 ent + 2 dec
107 | 1168 | 17 | N |  | Total Regularización (base imponible) (d=b+c). 4T [345] |  | 15 ent + 2 dec
108 | 1185 | 3 | Num |  | Tipo impositivo ( e ) .1T [283] | "3,00" | 1 ent + 2 dec
109 | 1188 | 3 | Num |  | Tipo impositivo ( e ) .2T [304] | "3,00" | 1 ent + 2 dec
110 | 1191 | 3 | Num |  | Tipo impositivo ( e ) .3T [325] | "3,00" | 1 ent + 2 dec
111 | 1194 | 3 | Num |  | Tipo impositivo ( e ) .4T [346] | "3,00" | 1 ent + 2 dec
112 | 1197 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 1T [284] |  | 15 ent + 2 dec
113 | 1214 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 2T [305] |  | 15 ent + 2 dec
114 | 1231 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 3T [326] |  | 15 ent + 2 dec
115 | 1248 | 17 | Num |  | Regularización positiva (cuota íntegra) (f) = (b) x ( e ). 4T [347] |  | 15 ent + 2 dec
116 | 1265 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 1T [285] |  | 15 ent + 2 dec
117 | 1282 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 2T [306] |  | 15 ent + 2 dec
118 | 1299 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 3T [327] |  | 15 ent + 2 dec
119 | 1316 | 17 | N |  | Regularización negativa (cuota íntegra) (g) = (c) x ( e ). 4T [348] |  | 15 ent + 2 dec
120 | 1333 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 1T [286] |  | 15 ent + 2 dec
121 | 1350 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 2T [307] |  | 15 ent + 2 dec
122 | 1367 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 3T [328] |  | 15 ent + 2 dec
123 | 1384 | 17 | N |  | Total regularización (cuota íntegra) (h) = (f) + (g) 4T [349] |  | 15 ent + 2 dec
124 | 1401 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 1T [287] |  | 15 ent + 2 dec
125 | 1418 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 2T [308] |  | 15 ent + 2 dec
126 | 1435 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 3T [329] |  | 15 ent + 2 dec
127 | 1452 | 17 | N |  | Regularización cuota atribuible al Estado (i) = (h) x (m) 4T [350] |  | 15 ent + 2 dec
128 | 1469 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 1T [288] |  | 15 ent + 2 dec
129 | 1486 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 2T [309] |  | 15 ent + 2 dec
130 | 1503 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 3T [330] |  | 15 ent + 2 dec
131 | 1520 | 17 | N |  | Ajuste en regularización cuota atribuible al Estado por cambio en la distribución territorio (j) = (a) x (e) x [ (m) - (l) ] 1T [351] |  | 15 ent + 2 dec
132 | 1537 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 1T [289] |  | 15 ent + 2 dec
133 | 1554 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 2T [310] |  | 15 ent + 2 dec
134 | 1571 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 3T [331] |  | 15 ent + 2 dec
135 | 1588 | 17 | N |  | Total ajuste en cuota íntegra período de regularización atribuible al Estado(k) = (i) + (j) 4T [352] |  | 15 ent + 2 dec
136 | 1605 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 1T [290] |  | 3 ent + 2 dec
137 | 1610 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 2T [311] |  | 3 ent + 2 dec
138 | 1615 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 3T [332] |  | 3 ent + 2 dec
139 | 1620 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % período objeto de regularización 4T [353] |  | 3 ent + 2 dec
140 | 1625 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 1T [291] |  | 3 ent + 2 dec
141 | 1630 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 2T [312] |  | 3 ent + 2 dec
142 | 1635 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 3T [333] |  | 3 ent + 2 dec
143 | 1640 | 5 | Num |  | Información de la tributación por razón de territorio  - Álava % con regularización incluida 4T [354] |  | 3 ent + 2 dec
144 | 1645 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 1T [292] |  | 3 ent + 2 dec
145 | 1650 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 2T [313] |  | 3 ent + 2 dec
146 | 1655 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 3T [334] |  | 3 ent + 2 dec
147 | 1660 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % período objeto de regularización 4T [355] |  | 3 ent + 2 dec
148 | 1665 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 1T [293] |  | 3 ent + 2 dec
149 | 1670 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 2T [314] |  | 3 ent + 2 dec
150 | 1675 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 3T [335] |  | 3 ent + 2 dec
151 | 1680 | 5 | Num |  | Información de la tributación por razón de territorio  - Guipúzcoa % con regularización incluida 4T [356] |  | 3 ent + 2 dec
152 | 1685 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 1T [294] |  | 3 ent + 2 dec
153 | 1690 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 2T [315] |  | 3 ent + 2 dec
154 | 1695 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 3T [336] |  | 3 ent + 2 dec
155 | 1700 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % período objeto de regularización 4T [357] |  | 3 ent + 2 dec
156 | 1705 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 1T [295] |  | 3 ent + 2 dec
157 | 1710 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 2T [316] |  | 3 ent + 2 dec
158 | 1715 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 3T [337] |  | 3 ent + 2 dec
159 | 1720 | 5 | Num |  | Información de la tributación por razón de territorio  - Vizcaya % con regularización incluida 4T [358] |  | 3 ent + 2 dec
160 | 1725 | 5 | An |  | Reservado para la Administración |  | Blancos
161 | 1730 | 5 | An |  | Reservado para la Administración |  | Blancos
162 | 1735 | 5 | An |  | Reservado para la Administración |  | Blancos
163 | 1740 | 5 | An |  | Reservado para la Administración |  | Blancos
164 | 1745 | 5 | An |  | Reservado para la Administración |  | Blancos
165 | 1750 | 5 | An |  | Reservado para la Administración |  | Blancos
166 | 1755 | 5 | An |  | Reservado para la Administración |  | Blancos
167 | 1760 | 5 | An |  | Reservado para la Administración |  | Blancos
168 | 1765 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 1T [298] |  | 3 ent + 2 dec
169 | 1770 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 2T [319] |  | 3 ent + 2 dec
170 | 1775 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 3T [340] |  | 3 ent + 2 dec
171 | 1780 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % período objeto de regularización (l) 4T [361] |  | 3 ent + 2 dec
172 | 1785 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 1T [299] |  | 3 ent + 2 dec
173 | 1790 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 2T [320] |  | 3 ent + 2 dec
174 | 1795 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 3T [341] |  | 3 ent + 2 dec
175 | 1800 | 5 | Num |  | Información de la tributación por razón de territorio  - Territorio común % con regularización incluida (m) 4T [362] |  | 3 ent + 2 dec
176 | 1805 | 17 | N |  | Total Regularización (cuota) (34) + (55) + (76) + (97) + (118) + (139) + (160) + (181) + (202) + (223) + (244) + (265) + (286) + (307) + (328) + (349) [363] |  | 15 ent + 2 dec
177 | 1822 | 17 | N |  | Total Regularización atribuible a la Administración del Estado (37) + (58) + (79) + (100) + (121) + (142) + (163) + (184) + (205) + (226) + (247) + (268) + (289) + (310) + (331) + (352) [364] |  | 15 ent + 2 dec
178 | 1839 | 150 | An |  | Reservado para la Administración |  | Blancos
179 | 1989 | 3 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T"
180 | 1992 | 3 | Num |  | Modelo | Obligatorio | Constante "490"
181 | 1995 | 2 | Num |  | Página | Obligatorio | Constante "03"
182 | 1997 | 4 | An |  | Indicador de fin de registro | Obligatorio | Constante "000>"
 | TOTAL | 2000 | POSICIONES