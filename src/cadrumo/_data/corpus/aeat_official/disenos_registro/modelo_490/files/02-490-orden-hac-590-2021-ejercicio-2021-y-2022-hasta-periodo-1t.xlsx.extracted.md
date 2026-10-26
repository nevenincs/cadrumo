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
34 | 899 | 17 | N |  | Liquidación. Ajuste cuota íntegra periodo regularización ([14] x [15]) [17] |  | 15 ent + 2 dec
35 | 916 | 17 | Num |  | Resultado. A deducir (exclusivamente en caso de autoliquidaciones complementarias) Resultado de la anterior o anteriores declaraciones del mismo ejercicio y periodo [18] |  | 15 ent + 2 dec
36 | 933 | 17 | N |  | Resultado. Resultado de la liquidación ([16] + [17] - [18]) [19] |  | 15 ent + 2 dec
37 | 950 | 11 | An |  | Ingreso/Devolución. Código BIC/SWIFT
38 | 961 | 34 | An |  | Ingreso/Devolución. Código IBAN
39 | 995 | 1 | An |  | Declaración complementaria |  | C ó blanco
40 | 996 | 13 | An |  | Número de justificante de la declaración anterior
41 | 1009 | 1 | An |  | Declaración negativa |  | N ó blanco
42 | 1010 | 179 | An |  | Reservado para la Administración |  | Blancos
43 | 1189 | 3 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T"
44 | 1192 | 3 | Num |  | Modelo | Obligatorio | Constante "490"
45 | 1195 | 2 | Num |  | Página | Obligatorio | Constante "01"
46 | 1197 | 4 | An |  | Indicador de fin de registro | Obligatorio | Constante "000>"
 | TOTAL | 1200 | POSICIONES
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
6 | 13 | 4 | Num |  | Regularización (art. 10.3 Ley).Ejercicio
7 | 17 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).1T [1] |  | 15 ent + 2 dec
8 | 34 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).2T [8] |  | 15 ent + 2 dec
9 | 51 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).3T [14] |  | 15 ent + 2 dec
10 | 68 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).4T [20] |  | 15 ent + 2 dec
11 | 85 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).1T [2] |  | 15 ent + 2 dec
12 | 102 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).2T [9] |  | 15 ent + 2 dec
13 | 119 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).3T [15] |  | 15 ent + 2 dec
14 | 136 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).4T [21] |  | 15 ent + 2 dec
15 | 153 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).1T [3] |  | 15 ent + 2 dec
16 | 170 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).2T [10] |  | 15 ent + 2 dec
17 | 187 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).3T [16] |  | 15 ent + 2 dec
18 | 204 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).4T [22] |  | 15 ent + 2 dec
19 | 221 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.1T [4] | "3,00" | 1 ent + 2 dec
20 | 224 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.2T [4] | "3,00" | 1 ent + 2 dec
21 | 227 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.3T [4] | "3,00" | 1 ent + 2 dec
22 | 230 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.4T [4] | "3,00" | 1 ent + 2 dec
23 | 233 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).1T [5] |  | 15 ent + 2 dec
24 | 250 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).2T [11] |  | 15 ent + 2 dec
25 | 267 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).3T [17] |  | 15 ent + 2 dec
26 | 284 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).4T [23] |  | 15 ent + 2 dec
27 | 301 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).1T [6] |  | 15 ent + 2 dec
28 | 318 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).2T [12] |  | 15 ent + 2 dec
29 | 335 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).3T [18] |  | 15 ent + 2 dec
30 | 352 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).4T [24] |  | 15 ent + 2 dec
31 | 369 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).1T [7] |  | 15 ent + 2 dec
32 | 386 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).2T [13] |  | 15 ent + 2 dec
33 | 403 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).3T [19] |  | 15 ent + 2 dec
34 | 420 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).4T [25] |  | 15 ent + 2 dec
35 | 437 | 4 | Num |  | Regularización (art. 10.3 Ley).Ejercicio
36 | 441 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).1T [26] |  | 15 ent + 2 dec
37 | 458 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).2T [33] |  | 15 ent + 2 dec
38 | 475 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).3T [39] |  | 15 ent + 2 dec
39 | 492 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).4T [45] |  | 15 ent + 2 dec
40 | 509 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).1T [27] |  | 15 ent + 2 dec
41 | 526 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).2T [34] |  | 15 ent + 2 dec
42 | 543 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).3T [40] |  | 15 ent + 2 dec
43 | 560 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).4T [46] |  | 15 ent + 2 dec
44 | 577 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).1T [28] |  | 15 ent + 2 dec
45 | 594 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).2T [35] |  | 15 ent + 2 dec
46 | 611 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).3T [41] |  | 15 ent + 2 dec
47 | 628 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).4T [47] |  | 15 ent + 2 dec
48 | 645 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.1T [29] | "3,00" | 1 ent + 2 dec
49 | 648 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.2T [29] | "3,00" | 1 ent + 2 dec
50 | 651 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.3T [29] | "3,00" | 1 ent + 2 dec
51 | 654 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.4T [29] | "3,00" | 1 ent + 2 dec
52 | 657 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).1T [30] |  | 15 ent + 2 dec
53 | 674 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).2T [36] |  | 15 ent + 2 dec
54 | 691 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).3T [42] |  | 15 ent + 2 dec
55 | 708 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).4T [48] |  | 15 ent + 2 dec
56 | 725 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).1T [31] |  | 15 ent + 2 dec
57 | 742 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).2T [37] |  | 15 ent + 2 dec
58 | 759 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).3T [43] |  | 15 ent + 2 dec
59 | 776 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).4T [49] |  | 15 ent + 2 dec
60 | 793 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).1T [32] |  | 15 ent + 2 dec
61 | 810 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).2T [38] |  | 15 ent + 2 dec
62 | 827 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).3T [44] |  | 15 ent + 2 dec
63 | 844 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).4T [50] |  | 15 ent + 2 dec
64 | 861 | 4 | Num |  | Regularización (art. 10.3 Ley).Ejercicio
65 | 865 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).1T [51] |  | 15 ent + 2 dec
66 | 882 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).2T [58] |  | 15 ent + 2 dec
67 | 899 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).3T [64] |  | 15 ent + 2 dec
68 | 916 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).4T [70] |  | 15 ent + 2 dec
69 | 933 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).1T [52] |  | 15 ent + 2 dec
70 | 950 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).2T [59] |  | 15 ent + 2 dec
71 | 967 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).3T [65] |  | 15 ent + 2 dec
72 | 984 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).4T [71] |  | 15 ent + 2 dec
73 | 1001 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).1T [53] |  | 15 ent + 2 dec
74 | 1018 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).2T [60] |  | 15 ent + 2 dec
75 | 1035 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).3T [66] |  | 15 ent + 2 dec
76 | 1052 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).4T [72] |  | 15 ent + 2 dec
77 | 1069 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.1T [54] | "3,00" | 1 ent + 2 dec
78 | 1072 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.2T [54] | "3,00" | 1 ent + 2 dec
79 | 1075 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.3T [54] | "3,00" | 1 ent + 2 dec
80 | 1078 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.4T [54] | "3,00" | 1 ent + 2 dec
81 | 1081 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).1T [55] |  | 15 ent + 2 dec
82 | 1098 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).2T [61] |  | 15 ent + 2 dec
83 | 1115 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).3T [67] |  | 15 ent + 2 dec
84 | 1132 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).4T [73] |  | 15 ent + 2 dec
85 | 1149 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).1T [56] |  | 15 ent + 2 dec
86 | 1166 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).2T [62] |  | 15 ent + 2 dec
87 | 1183 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).3T [68] |  | 15 ent + 2 dec
88 | 1200 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).4T [74] |  | 15 ent + 2 dec
89 | 1217 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).1T [57] |  | 15 ent + 2 dec
90 | 1234 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).2T [63] |  | 15 ent + 2 dec
91 | 1251 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).3T [69] |  | 15 ent + 2 dec
92 | 1268 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).4T [75] |  | 15 ent + 2 dec
93 | 1285 | 4 | Num |  | Regularización (art. 10.3 Ley).Ejercicio
94 | 1289 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).1T [76] |  | 15 ent + 2 dec
95 | 1306 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).2T [83] |  | 15 ent + 2 dec
96 | 1323 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).3T [89] |  | 15 ent + 2 dec
97 | 1340 | 17 | Num |  | (a) Regu (art. 10.3 Ley). Regularización positiva (base imponible).4T [95] |  | 15 ent + 2 dec
98 | 1357 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).1T [77] |  | 15 ent + 2 dec
99 | 1374 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).2T [84] |  | 15 ent + 2 dec
100 | 1391 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).3T [90] |  | 15 ent + 2 dec
101 | 1408 | 17 | N |  | (b) Regu (art. 10.3 Ley). Regularización negativa (base imponible).4T [96] |  | 15 ent + 2 dec
102 | 1425 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).1T [78] |  | 15 ent + 2 dec
103 | 1442 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).2T [85] |  | 15 ent + 2 dec
104 | 1459 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).3T [91] |  | 15 ent + 2 dec
105 | 1476 | 17 | N |  | ( c ) =(a)+(b) Regu (art. 10.3 Ley).Total Regularización (base imponible).4T [97] |  | 15 ent + 2 dec
106 | 1493 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.1T [79] | "3,00" | 1 ent + 2 dec
107 | 1496 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.2T [79] | "3,00" | 1 ent + 2 dec
108 | 1499 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.3T [79] | "3,00" | 1 ent + 2 dec
109 | 1502 | 3 | Num |  | (d) Regu (art. 10.3 Ley). Tipo impositivo.4T [79] | "3,00" | 1 ent + 2 dec
110 | 1505 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).1T [80] |  | 15 ent + 2 dec
111 | 1522 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).2T [86] |  | 15 ent + 2 dec
112 | 1539 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).3T [92] |  | 15 ent + 2 dec
113 | 1556 | 17 | Num |  | (e) = (a) * (d) Regu (art. 10.3 Ley). Regularización positiva (cuota).4T [98] |  | 15 ent + 2 dec
114 | 1573 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).1T [81] |  | 15 ent + 2 dec
115 | 1590 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).2T [87] |  | 15 ent + 2 dec
116 | 1607 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).3T [93] |  | 15 ent + 2 dec
117 | 1624 | 17 | N |  | (f) = (b) * (d) Regu (art. 10.3 Ley). Regularización negativa (cuota).4T [99] |  | 15 ent + 2 dec
118 | 1641 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).1T [82] |  | 15 ent + 2 dec
119 | 1658 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).2T [88] |  | 15 ent + 2 dec
120 | 1675 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).3T [94] |  | 15 ent + 2 dec
121 | 1692 | 17 | N |  | (g) = (e) + (f) Regu (art. 10.3 Ley). Total Regularización (cuota).4T [100] |  | 15 ent + 2 dec
122 | 1709 | 17 | N |  | Total Regularización (cuota)((7) + (13) + (19) + (25) + (32) + (38) + (44) + (50) 
+ (57) + (63) + (69) + (75) + (82) + (88) + (94) + (100))  [101] |  | 15 ent + 2 dec
123 | 1726 | 263 | An |  | Reservado para la Administración |  | Blancos
124 | 1989 | 3 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T"
125 | 1992 | 3 | Num |  | Modelo | Obligatorio | Constante "490"
126 | 1995 | 2 | Num |  | Página | Obligatorio | Constante "02"
127 | 1997 | 4 | An |  | Indicador de fin de registro | Obligatorio | Constante "000>"
 | TOTAL | 2000 | POSICIONES