# T3690 Estruc. gral

 |  | Agencia Tributaria
Modelo 369 |  |  | Diseño de registro
Versión 1.1 |  |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Pos. Rel. | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Constante "<T"
2 | 3 | 3 | 3 | An | Modelo. | Constante "369"
3 | 6 | 6 | 1 | An | Discriminante | Constante "0"
4 | 7 | 7 | 4 | An | Ejercicio de devengo (EEEE)
5 | 11 | 11 | 2 | An | Periodo | ["1T".."4T"] (para trimestrales)
["01", "02".."12"] (para mensuales)
6 | 13 | 13 | 5 | An | Tipo y cierre | "0000>"
7 | 1 | 18 | 92 | An | Reservado | Blancos
8 | 1 | 110 | 9 | An | NIF del titular
9 | 1 | 119 | 210 | An | Reservado | Blancos
10 |  | 329 | variable | An | Contenido de  la presentación. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento (ver pestañas T36900 a T36912) | Posibles páginas presentación:
T36900 - común siempre se envía
Exterior: T36901 a T36903
Union: T36904 a T36909
Importación: T36910 a T36912 |  | VER detalle del contenido de estas posiciones en las pestañas con cada posible página (T36900, ..T36912)
11 | 1 |  | 3 | An | Cierre del identificador de modelo y página. | Constante "</T" |  | IMPORTANTE: | En función del régimen de la declaración a presentar se incluirán sólo las páginas correspondientes, según se explica en columna 'Contenido'
12 | 4 |  | 3 | An | Modelo. | Constante "369" |  |  | Cada fichero sólo puede contener la declaración de un único declarante y para un único régimen
13 | 7 |  | 1 | An | Discriminante | Constante "0"
14 | 8 |  | 4 | An | Ejercicio de devengo (EEEE)
15 | 12 |  | 2 | An | Periodo | ["1T".."4T"] (para trimestrales)
["01", "02".."12"] (para mensuales)
16 | 14 |  | 5 | An | Tipo y cierre | "0000>"
Total
Notas:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números más el carácter de signo negativo '-'.  Los datos numéricos deberán estar alineados a la derecha, rellenando con espacios en blanco o bien con ceros por la izquierda.
4. Los campos numéricos (Num) admiten números tanto positivos como negativos. Los datos numéricos negativos llevarán un caracter '-' inmediatamente delante de los números.
5. Los campos numéricos (Num) ocuparán 17 posiciones (15 parte entera + 2 parte decimal), y no se incluye separador de decimales. Si el dato no tiene decimales se informarán las 2 posiciones decimales del campo con ceros.
6. En general los campos que no tengan información se rellenarán las posiciones con espacios en blanco. En particular en los campo numéricos (Num) sin información se rellenarán también con espacios en blanco y nunca con ceros.
7. En los grupos de datos referidos a una misma entidad (prestación de servicios, entrega de bienes, corrección...), si se quieren dejar vacíos TODOS los campos deberán rellenarse con blancos. Por ejemplo, aunque el "Tipo de IVA" esté especificado que tenga los valores [R,S], si el bloque lleva los demás campos vacíos, dicho campo deberá contener blancos. Lo mismo aplica a los valores numéricos.
Ejemplos de campos numéricos (Num) válidos:
 |  |  |  |  | -1537'   (El dato es -15,37)
 |  |  |  |  | -0000000000001537' (El dato es -15,37
 |  |  |  |  | 280020'  (El dato es 2.800,20)

# T36900 Info Adicional

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "00"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 93 | An |  | Reservado | Obligatorio | Blancos
6 | 102 | 9 | An |  |  | Obligatorio | Constante "</T36900>"
 | TOTAL | 110 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES

# T36901 Ext

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "01"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 5 | An |  | Régimen | Obligatorio | "VOES"
6 | 14 | 1 | An |  | Categoría | Obligatorio | "D"
7 | 15 | 1 | An |  | Tipo de pago |  | ["O", "S", "I", "N", "T"]
8 | 16 | 22 | An |  | NRC Pago
9 | 38 | 17 | Num |  | Importe pagado |  | 15 enteros + 2 decimales
10 | 55 | 1 | An |  | Complementaria | Obligatorio | [blanco | constante "C"]
11 | 56 | 2 | An |  | 1. Declarante. País | Obligatorio
12 | 58 | 15 | An |  | 1. Declarante. NIF | Obligatorio
13 | 73 | 15 | An |  | 1. Declarante. Número de operador en el régimen (NEUOSS) | Obligatorio
14 | 88 | 125 | An |  | 1. Declarante . Apellidos y nombre o razón social. | Obligatorio
15 | 213 | 4 | Num |  | 2. Ejercicio y período. Ejercicio | Obligatorio
16 | 217 | 1 | An |  | 2. Ejercicio y período. Tipo de periodo | Obligatorio | "T"
17 | 218 | 2 | Num |  | 2. Ejercicio y período. Periodo | Obligatorio | 1 a 4
18 | 220 | 1 | An |  | 2. Ejercicio y período. Declaración sin actividad | Obligatorio | "0" o "1"
19 | 221 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.1
20 | 223 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.1 |  | 3 enteros + 2 decimales
21 | 228 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.1 |  | ["R","S"]
22 | 229 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).1 |  | 15 enteros + 2 decimales
23 | 246 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).1 |  | 15 enteros + 2 decimales
24 | 263 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.2
25 | 265 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.2 |  | 3 enteros + 2 decimales
26 | 270 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.2 |  | ["R","S"]
27 | 271 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).2 |  | 15 enteros + 2 decimales
28 | 288 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).2 |  | 15 enteros + 2 decimales
29 | 305 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.3
30 | 307 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.3 |  | 3 enteros + 2 decimales
31 | 312 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.3 |  | ["R","S"]
32 | 313 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).3 |  | 15 enteros + 2 decimales
33 | 330 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).3 |  | 15 enteros + 2 decimales
34 | 347 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.4
35 | 349 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.4 |  | 3 enteros + 2 decimales
36 | 354 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.4 |  | ["R","S"]
37 | 355 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).4 |  | 15 enteros + 2 decimales
38 | 372 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).4 |  | 15 enteros + 2 decimales
39 | 389 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.5
40 | 391 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.5 |  | 3 enteros + 2 decimales
41 | 396 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.5 |  | ["R","S"]
42 | 397 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).5 |  | 15 enteros + 2 decimales
43 | 414 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).5 |  | 15 enteros + 2 decimales
44 | 431 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.6
45 | 433 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.6 |  | 3 enteros + 2 decimales
46 | 438 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.6 |  | ["R","S"]
47 | 439 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).6 |  | 15 enteros + 2 decimales
48 | 456 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).6 |  | 15 enteros + 2 decimales
49 | 473 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.7
50 | 475 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.7 |  | 3 enteros + 2 decimales
51 | 480 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.7 |  | ["R","S"]
52 | 481 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).7 |  | 15 enteros + 2 decimales
53 | 498 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).7 |  | 15 enteros + 2 decimales
54 | 515 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.8
55 | 517 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.8 |  | 3 enteros + 2 decimales
56 | 522 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.8 |  | ["R","S"]
57 | 523 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).8 |  | 15 enteros + 2 decimales
58 | 540 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).8 |  | 15 enteros + 2 decimales
59 | 557 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.9
60 | 559 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.9 |  | 3 enteros + 2 decimales
61 | 564 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.9 |  | ["R","S"]
62 | 565 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).9 |  | 15 enteros + 2 decimales
63 | 582 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).9 |  | 15 enteros + 2 decimales
64 | 599 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.10
65 | 601 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.10 |  | 3 enteros + 2 decimales
66 | 606 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.10 |  | ["R","S"]
67 | 607 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).10 |  | 15 enteros + 2 decimales
68 | 624 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).10 |  | 15 enteros + 2 decimales
69 | 641 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.11
70 | 643 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.11 |  | 3 enteros + 2 decimales
71 | 648 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.11 |  | ["R","S"]
72 | 649 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).11 |  | 15 enteros + 2 decimales
73 | 666 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).11 |  | 15 enteros + 2 decimales
74 | 683 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.12
75 | 685 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.12 |  | 3 enteros + 2 decimales
76 | 690 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.12 |  | ["R","S"]
77 | 691 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).12 |  | 15 enteros + 2 decimales
78 | 708 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).12 |  | 15 enteros + 2 decimales
79 | 725 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.13
80 | 727 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.13 |  | 3 enteros + 2 decimales
81 | 732 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.13 |  | ["R","S"]
82 | 733 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).13 |  | 15 enteros + 2 decimales
83 | 750 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).13 |  | 15 enteros + 2 decimales
84 | 767 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.14
85 | 769 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.14 |  | 3 enteros + 2 decimales
86 | 774 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.14 |  | ["R","S"]
87 | 775 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).14 |  | 15 enteros + 2 decimales
88 | 792 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).14 |  | 15 enteros + 2 decimales
89 | 809 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.15
90 | 811 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.15 |  | 3 enteros + 2 decimales
91 | 816 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.15 |  | ["R","S"]
92 | 817 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).15 |  | 15 enteros + 2 decimales
93 | 834 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).15 |  | 15 enteros + 2 decimales
94 | 851 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.16
95 | 853 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.16 |  | 3 enteros + 2 decimales
96 | 858 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.16 |  | ["R","S"]
97 | 859 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).16 |  | 15 enteros + 2 decimales
98 | 876 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).16 |  | 15 enteros + 2 decimales
99 | 893 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.17
100 | 895 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.17 |  | 3 enteros + 2 decimales
101 | 900 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.17 |  | ["R","S"]
102 | 901 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).17 |  | 15 enteros + 2 decimales
103 | 918 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).17 |  | 15 enteros + 2 decimales
104 | 935 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.18
105 | 937 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.18 |  | 3 enteros + 2 decimales
106 | 942 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.18 |  | ["R","S"]
107 | 943 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).18 |  | 15 enteros + 2 decimales
108 | 960 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).18 |  | 15 enteros + 2 decimales
109 | 977 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.19
110 | 979 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.19 |  | 3 enteros + 2 decimales
111 | 984 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.19 |  | ["R","S"]
112 | 985 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).19 |  | 15 enteros + 2 decimales
113 | 1002 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).19 |  | 15 enteros + 2 decimales
114 | 1019 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.20
115 | 1021 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.20 |  | 3 enteros + 2 decimales
116 | 1026 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.20 |  | ["R","S"]
117 | 1027 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).20 |  | 15 enteros + 2 decimales
118 | 1044 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).20 |  | 15 enteros + 2 decimales
119 | 1061 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.21
120 | 1063 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.21 |  | 3 enteros + 2 decimales
121 | 1068 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.21 |  | ["R","S"]
122 | 1069 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).21 |  | 15 enteros + 2 decimales
123 | 1086 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).21 |  | 15 enteros + 2 decimales
124 | 1103 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.22
125 | 1105 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.22 |  | 3 enteros + 2 decimales
126 | 1110 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.22 |  | ["R","S"]
127 | 1111 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).22 |  | 15 enteros + 2 decimales
128 | 1128 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).22 |  | 15 enteros + 2 decimales
129 | 1145 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.23
130 | 1147 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.23 |  | 3 enteros + 2 decimales
131 | 1152 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.23 |  | ["R","S"]
132 | 1153 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).23 |  | 15 enteros + 2 decimales
133 | 1170 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).23 |  | 15 enteros + 2 decimales
134 | 1187 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.24
135 | 1189 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.24 |  | 3 enteros + 2 decimales
136 | 1194 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.24 |  | ["R","S"]
137 | 1195 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).24 |  | 15 enteros + 2 decimales
138 | 1212 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).24 |  | 15 enteros + 2 decimales
139 | 1229 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.25
140 | 1231 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.25 |  | 3 enteros + 2 decimales
141 | 1236 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.25 |  | ["R","S"]
142 | 1237 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).25 |  | 15 enteros + 2 decimales
143 | 1254 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).25 |  | 15 enteros + 2 decimales
144 | 1271 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.26
145 | 1273 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.26 |  | 3 enteros + 2 decimales
146 | 1278 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.26 |  | ["R","S"]
147 | 1279 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).26 |  | 15 enteros + 2 decimales
148 | 1296 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).26 |  | 15 enteros + 2 decimales
149 | 1313 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.27
150 | 1315 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.27 |  | 3 enteros + 2 decimales
151 | 1320 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.27 |  | ["R","S"]
152 | 1321 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).27 |  | 15 enteros + 2 decimales
153 | 1338 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).27 |  | 15 enteros + 2 decimales
154 | 1355 | 2 | An |  | 3. Prestaciones de servicios. Código de país/EM de consumo.28
155 | 1357 | 5 | Num |  | 3. Prestaciones de servicios. Tipo (%) de IVA.28 |  | 3 enteros + 2 decimales
156 | 1362 | 1 | An |  | 3. Prestaciones de servicios. Tipo IVA.28 |  | ["R","S"]
157 | 1363 | 17 | Num |  | 3. Prestaciones de servicios. Base imponible (€).28 |  | 15 enteros + 2 decimales
158 | 1380 | 17 | Num |  | 3. Prestaciones de servicios. Cuota IVA (€).28 |  | 15 enteros + 2 decimales
159 | 1397 | 17 | An |  | Reservado | Obligatorio | Blancos
160 | 1414 | 9 | An |  |  | Obligatorio | Constante "</T36901>"
 | TOTAL | 1422 | POSICIONES
Notas:
1. Los valores de "Tipo de pago" serán: 
I: Ingreso total, 
S: Ingreso parcial, 
O: Sin ingreso, 
N: Negativa/Pago cero, 
T: A Ingresar por transferencia
2. Los valores de "Prestaciones de servicios. Tipo IVA" serán S:Estándar, R:Reducido
3. Los códigos de país seguiran el estándar ISO-3166 de dos letras. Se utilizará "EL" para Grecia y "XI" para Irlanda del Norte, que en determinados casos actuará como un EM
 | TOTAL: | -1 |  |  | POSICIONES

# T36902 Ext

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "02"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | An |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 1
7 | 12 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 1
8 | 16 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
9 | 17 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 1
10 | 19 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 1 |  | 15 enteros + 2 decimales
11 | 36 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 2
12 | 38 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 2
13 | 42 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
14 | 43 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 2
15 | 45 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 2 |  | 15 enteros + 2 decimales
16 | 62 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 3
17 | 64 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 3
18 | 68 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
19 | 69 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 3
20 | 71 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 3 |  | 15 enteros + 2 decimales
21 | 88 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 4
22 | 90 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 4
23 | 94 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
24 | 95 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 4
25 | 97 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 4 |  | 15 enteros + 2 decimales
26 | 114 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 5
27 | 116 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 5
28 | 120 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
29 | 121 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 5
30 | 123 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 5 |  | 15 enteros + 2 decimales
31 | 140 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 6
32 | 142 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 6
33 | 146 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
34 | 147 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 6
35 | 149 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 6 |  | 15 enteros + 2 decimales
36 | 166 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 7
37 | 168 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 7
38 | 172 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
39 | 173 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 7
40 | 175 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 7 |  | 15 enteros + 2 decimales
41 | 192 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 8
42 | 194 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 8
43 | 198 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
44 | 199 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 8
45 | 201 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 8 |  | 15 enteros + 2 decimales
46 | 218 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 9
47 | 220 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 9
48 | 224 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
49 | 225 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 9
50 | 227 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 9 |  | 15 enteros + 2 decimales
51 | 244 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 10
52 | 246 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 10
53 | 250 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
54 | 251 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 10
55 | 253 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 10 |  | 15 enteros + 2 decimales
56 | 270 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 11
57 | 272 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 11
58 | 276 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo |  | "T"
59 | 277 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 11
60 | 279 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 11 |  | 15 enteros + 2 decimales
61 | 296 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 12
62 | 298 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 12
63 | 302 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 12 |  | "T"
64 | 303 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 12
65 | 305 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 12 |  | 15 enteros + 2 decimales
66 | 322 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 13
67 | 324 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 13
68 | 328 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 13 |  | "T"
69 | 329 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 13
70 | 331 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 13 |  | 15 enteros + 2 decimales
71 | 348 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 14
72 | 350 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 14
73 | 354 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 14 |  | "T"
74 | 355 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 14
75 | 357 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 14 |  | 15 enteros + 2 decimales
76 | 374 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 15
77 | 376 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 15
78 | 380 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 15 |  | "T"
79 | 381 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 15
80 | 383 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 15 |  | 15 enteros + 2 decimales
81 | 400 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 16
82 | 402 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 16
83 | 406 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 16 |  | "T"
84 | 407 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 16
85 | 409 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 16 |  | 15 enteros + 2 decimales
86 | 426 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 17
87 | 428 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 17
88 | 432 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 17 |  | "T"
89 | 433 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 17
90 | 435 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 17 |  | 15 enteros + 2 decimales
91 | 452 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 18
92 | 454 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 18
93 | 458 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 18 |  | "T"
94 | 459 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 18
95 | 461 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 18 |  | 15 enteros + 2 decimales
96 | 478 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 19
97 | 480 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 19
98 | 484 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 19 |  | "T"
99 | 485 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 19
100 | 487 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 19 |  | 15 enteros + 2 decimales
101 | 504 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 20
102 | 506 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 20
103 | 510 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 20 |  | "T"
104 | 511 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 20
105 | 513 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 20 |  | 15 enteros + 2 decimales
106 | 530 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 21
107 | 532 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 21
108 | 536 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 21 |  | "T"
109 | 537 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 21
110 | 539 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 21 |  | 15 enteros + 2 decimales
111 | 556 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 22
112 | 558 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 22
113 | 562 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 22 |  | "T"
114 | 563 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 22
115 | 565 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 22 |  | 15 enteros + 2 decimales
116 | 582 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 23
117 | 584 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 23
118 | 588 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 23 |  | "T"
119 | 589 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 23
120 | 591 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 23 |  | 15 enteros + 2 decimales
121 | 608 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 24
122 | 610 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 24
123 | 614 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 24 |  | "T"
124 | 615 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 24
125 | 617 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 24 |  | 15 enteros + 2 decimales
126 | 634 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 25
127 | 636 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 25
128 | 640 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 25 |  | "T"
129 | 641 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 25
130 | 643 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 25 |  | 15 enteros + 2 decimales
131 | 660 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 26
132 | 662 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 26
133 | 666 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 26 |  | "T"
134 | 667 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 26
135 | 669 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 26 |  | 15 enteros + 2 decimales
136 | 686 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 27
137 | 688 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 27
138 | 692 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 27 |  | "T"
139 | 693 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 27
140 | 695 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 27 |  | 15 enteros + 2 decimales
141 | 712 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 28
142 | 714 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 28
143 | 718 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo 28 |  | "T"
144 | 719 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 28
145 | 721 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 28 |  | 15 enteros + 2 decimales
146 | 738 | 17 | An |  | Reservado | Obligatorio | Blancos
147 | 755 | 9 | An |  |  | Obligatorio | Constante "</T36902>"
 | TOTAL | 763 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES

# T36903 Ext

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "03"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | A |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 2929 | An |  | Reservado | Obligatorio | Blancos
7 | 2939 | 9 | An |  |  | Obligatorio | Constante "</T36903>"
 | TOTAL | 2947 | POSICIONES

# T36904 Un

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "04"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 5 | An |  | Régimen | Obligatorio | [MOSS]
6 | 14 | 1 | An |  | Categoría | Obligatorio | "D"
7 | 15 | 1 | An |  | Tipo de pago |  | ["O", "S", "I", "N", "T"]
8 | 16 | 22 | An |  | NRC Pago
9 | 38 | 17 | Num |  | Importe pagado |  | 15 enteros + 2 decimales
10 | 55 | 1 | An |  | Complementaria | Obligatorio | [blanco | constante "C"]
11 | 56 | 2 | An |  | 1. Declarante. País | Obligatorio
12 | 58 | 15 | An | X | 1. Declarante. NIF | Obligatorio
13 | 73 | 125 | An | X | 1. Declarante . Apellidos y nombre o razón social. | Obligatorio
14 | 198 | 4 | Num | X | 2. Ejercicio y período. Ejercicio | Obligatorio
15 | 202 | 1 | An | X | 2. Ejercicio y período. Tipo de periodo | Obligatorio | "T"
16 | 203 | 2 | Num | X | 2. Ejercicio y período. Periodo | Obligatorio | 1 a 4
17 | 205 | 8 | Num | X | 2. Ejercicio y periodo. Fecha desde |  | AAAAMMDD
18 | 213 | 8 | Num | X | 2. Ejercicio y período. Fecha hasta |  | AAAAMMDD
19 | 221 | 1 | An | X | 2. Ejercicio y período. Declaración sin actividad | Obligatorio | "0" o "1"
20 | 222 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.1
21 | 224 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.1 |  | 3 enteros + 2 decimales
22 | 229 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.1 |  | ["R","S"]
23 | 230 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).1 |  | 15 enteros + 2 decimales
24 | 247 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).1 |  | 15 enteros + 2 decimales
25 | 264 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.2
26 | 266 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.2 |  | 3 enteros + 2 decimales
27 | 271 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.2 |  | ["R","S"]
28 | 272 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).2 |  | 15 enteros + 2 decimales
29 | 289 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).2 |  | 15 enteros + 2 decimales
30 | 306 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.3
31 | 308 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.3 |  | 3 enteros + 2 decimales
32 | 313 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.3 |  | ["R","S"]
33 | 314 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).3 |  | 15 enteros + 2 decimales
34 | 331 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).3 |  | 15 enteros + 2 decimales
35 | 348 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.4
36 | 350 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.4 |  | 3 enteros + 2 decimales
37 | 355 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.4 |  | ["R","S"]
38 | 356 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).4 |  | 15 enteros + 2 decimales
39 | 373 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).4 |  | 15 enteros + 2 decimales
40 | 390 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.5
41 | 392 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.5 |  | 3 enteros + 2 decimales
42 | 397 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.5 |  | ["R","S"]
43 | 398 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).5 |  | 15 enteros + 2 decimales
44 | 415 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).5 |  | 15 enteros + 2 decimales
45 | 432 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.6
46 | 434 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.6 |  | 3 enteros + 2 decimales
47 | 439 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.6 |  | ["R","S"]
48 | 440 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).6 |  | 15 enteros + 2 decimales
49 | 457 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).6 |  | 15 enteros + 2 decimales
50 | 474 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.7
51 | 476 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.7 |  | 3 enteros + 2 decimales
52 | 481 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.7 |  | ["R","S"]
53 | 482 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).7 |  | 15 enteros + 2 decimales
54 | 499 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).7 |  | 15 enteros + 2 decimales
55 | 516 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.8
56 | 518 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.8 |  | 3 enteros + 2 decimales
57 | 523 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.8 |  | ["R","S"]
58 | 524 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).8 |  | 15 enteros + 2 decimales
59 | 541 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).8 |  | 15 enteros + 2 decimales
60 | 558 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.9
61 | 560 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.9 |  | 3 enteros + 2 decimales
62 | 565 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.9 |  | ["R","S"]
63 | 566 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).9 |  | 15 enteros + 2 decimales
64 | 583 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).9 |  | 15 enteros + 2 decimales
65 | 600 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.10
66 | 602 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.10 |  | 3 enteros + 2 decimales
67 | 607 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.10 |  | ["R","S"]
68 | 608 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).10 |  | 15 enteros + 2 decimales
69 | 625 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).10 |  | 15 enteros + 2 decimales
70 | 642 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.11
71 | 644 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.11 |  | 3 enteros + 2 decimales
72 | 649 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.11 |  | ["R","S"]
73 | 650 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).11 |  | 15 enteros + 2 decimales
74 | 667 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).11 |  | 15 enteros + 2 decimales
75 | 684 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.12
76 | 686 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.12 |  | 3 enteros + 2 decimales
77 | 691 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.12 |  | ["R","S"]
78 | 692 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).12 |  | 15 enteros + 2 decimales
79 | 709 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).12 |  | 15 enteros + 2 decimales
80 | 726 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.13
81 | 728 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.13 |  | 3 enteros + 2 decimales
82 | 733 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.13 |  | ["R","S"]
83 | 734 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).13 |  | 15 enteros + 2 decimales
84 | 751 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).13 |  | 15 enteros + 2 decimales
85 | 768 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.14
86 | 770 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.14 |  | 3 enteros + 2 decimales
87 | 775 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.14 |  | ["R","S"]
88 | 776 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).14 |  | 15 enteros + 2 decimales
89 | 793 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).14 |  | 15 enteros + 2 decimales
90 | 810 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.15
91 | 812 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.15 |  | 3 enteros + 2 decimales
92 | 817 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.15 |  | ["R","S"]
93 | 818 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).15 |  | 15 enteros + 2 decimales
94 | 835 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).15 |  | 15 enteros + 2 decimales
95 | 852 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.16
96 | 854 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.16 |  | 3 enteros + 2 decimales
97 | 859 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.16 |  | ["R","S"]
98 | 860 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).16 |  | 15 enteros + 2 decimales
99 | 877 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).16 |  | 15 enteros + 2 decimales
100 | 894 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.17
101 | 896 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.17 |  | 3 enteros + 2 decimales
102 | 901 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.17 |  | ["R","S"]
103 | 902 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).17 |  | 15 enteros + 2 decimales
104 | 919 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).17 |  | 15 enteros + 2 decimales
105 | 936 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.18
106 | 938 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.18 |  | 3 enteros + 2 decimales
107 | 943 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.18 |  | ["R","S"]
108 | 944 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).18 |  | 15 enteros + 2 decimales
109 | 961 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).18 |  | 15 enteros + 2 decimales
110 | 978 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.19
111 | 980 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.19 |  | 3 enteros + 2 decimales
112 | 985 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.19 |  | ["R","S"]
113 | 986 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).19 |  | 15 enteros + 2 decimales
114 | 1003 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).19 |  | 15 enteros + 2 decimales
115 | 1020 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.20
116 | 1022 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.20 |  | 3 enteros + 2 decimales
117 | 1027 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.20 |  | ["R","S"]
118 | 1028 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).20 |  | 15 enteros + 2 decimales
119 | 1045 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).20 |  | 15 enteros + 2 decimales
120 | 1062 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.21
121 | 1064 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.21 |  | 3 enteros + 2 decimales
122 | 1069 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.21 |  | ["R","S"]
123 | 1070 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).21 |  | 15 enteros + 2 decimales
124 | 1087 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).21 |  | 15 enteros + 2 decimales
125 | 1104 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.22
126 | 1106 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.22 |  | 3 enteros + 2 decimales
127 | 1111 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.22 |  | ["R","S"]
128 | 1112 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).22 |  | 15 enteros + 2 decimales
129 | 1129 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).22 |  | 15 enteros + 2 decimales
130 | 1146 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.23
131 | 1148 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.23 |  | 3 enteros + 2 decimales
132 | 1153 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.23 |  | ["R","S"]
133 | 1154 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).23 |  | 15 enteros + 2 decimales
134 | 1171 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).23 |  | 15 enteros + 2 decimales
135 | 1188 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.24
136 | 1190 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.24 |  | 3 enteros + 2 decimales
137 | 1195 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.24 |  | ["R","S"]
138 | 1196 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).24 |  | 15 enteros + 2 decimales
139 | 1213 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).24 |  | 15 enteros + 2 decimales
140 | 1230 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.25
141 | 1232 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.25 |  | 3 enteros + 2 decimales
142 | 1237 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.25 |  | ["R","S"]
143 | 1238 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).25 |  | 15 enteros + 2 decimales
144 | 1255 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).25 |  | 15 enteros + 2 decimales
145 | 1272 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.26
146 | 1274 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.26 |  | 3 enteros + 2 decimales
147 | 1279 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.26 |  | ["R","S"]
148 | 1280 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).26 |  | 15 enteros + 2 decimales
149 | 1297 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).26 |  | 15 enteros + 2 decimales
150 | 1314 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.27
151 | 1316 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.27 |  | 3 enteros + 2 decimales
152 | 1321 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.27 |  | ["R","S"]
153 | 1322 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).27 |  | 15 enteros + 2 decimales
154 | 1339 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).27 |  | 15 enteros + 2 decimales
155 | 1356 | 2 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Código de país/EM de consumo.28
156 | 1358 | 5 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo (%) de IVA.28 |  | 3 enteros + 2 decimales
157 | 1363 | 1 | An |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Tipo IVA.28 |  | ["R","S"]
158 | 1364 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Base imponible (€).28 |  | 15 enteros + 2 decimales
159 | 1381 | 17 | Num |  | 3. Prestaciones de servicios desde el EMID (España) y desde ... Cuota IVA (€).28 |  | 15 enteros + 2 decimales
160 | 1398 | 17 | An |  | Reservado | Obligatorio | Blancos
161 | 1415 | 9 | An |  |  | Obligatorio | Constante "</T36904>"
 | TOTAL | 1423 | POSICIONES
Notas:
1. Los valores de "Tipo de pago" serán: 
I: Ingreso total, 
S: Ingreso parcial, 
O: Sin ingreso, 
N: Negativa/Pago cero, 
T: A Ingresar por transferencia
2. Los valores de "Prestaciones de servicios. Tipo IVA" serán S:Estándar, R:Reducido
3. Los códigos de país seguiran el estándar ISO-3166 de dos letras. Se utilizará "EL" para Grecia y "XI" para Irlanda del Norte, que en determinados casos actuará como un EM

# T36905 Un

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "05"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | A |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 1
7 | 12 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 1 |  | 3 enteros + 2 decimales
8 | 17 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 1 |  | ["R","S"]
9 | 18 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 1 |  | 15 enteros + 2 decimales
10 | 35 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 1 |  | 15 enteros + 2 decimales
11 | 52 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 2
12 | 54 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 2 |  | 3 enteros + 2 decimales
13 | 59 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 2 |  | ["R","S"]
14 | 60 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 2 |  | 15 enteros + 2 decimales
15 | 77 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 2 |  | 15 enteros + 2 decimales
16 | 94 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 3
17 | 96 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 3 |  | 3 enteros + 2 decimales
18 | 101 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 3 |  | ["R","S"]
19 | 102 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 3 |  | 15 enteros + 2 decimales
20 | 119 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 3 |  | 15 enteros + 2 decimales
21 | 136 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 4
22 | 138 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 4 |  | 3 enteros + 2 decimales
23 | 143 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 4 |  | ["R","S"]
24 | 144 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 4 |  | 15 enteros + 2 decimales
25 | 161 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 4 |  | 15 enteros + 2 decimales
26 | 178 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 5
27 | 180 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 5 |  | 3 enteros + 2 decimales
28 | 185 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 5 |  | ["R","S"]
29 | 186 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 5 |  | 15 enteros + 2 decimales
30 | 203 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 5 |  | 15 enteros + 2 decimales
31 | 220 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 6
32 | 222 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 6 |  | 3 enteros + 2 decimales
33 | 227 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 6 |  | ["R","S"]
34 | 228 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 6 |  | 15 enteros + 2 decimales
35 | 245 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 6 |  | 15 enteros + 2 decimales
36 | 262 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 7
37 | 264 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 7 |  | 3 enteros + 2 decimales
38 | 269 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 7 |  | ["R","S"]
39 | 270 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 7 |  | 15 enteros + 2 decimales
40 | 287 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 7 |  | 15 enteros + 2 decimales
41 | 304 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 8
42 | 306 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 8 |  | 3 enteros + 2 decimales
43 | 311 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 8 |  | ["R","S"]
44 | 312 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 8 |  | 15 enteros + 2 decimales
45 | 329 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 8 |  | 15 enteros + 2 decimales
46 | 346 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 9
47 | 348 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 9 |  | 3 enteros + 2 decimales
48 | 353 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 9 |  | ["R","S"]
49 | 354 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 9 |  | 15 enteros + 2 decimales
50 | 371 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 9 |  | 15 enteros + 2 decimales
51 | 388 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 10
52 | 390 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 10 |  | 3 enteros + 2 decimales
53 | 395 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 10 |  | ["R","S"]
54 | 396 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 10 |  | 15 enteros + 2 decimales
55 | 413 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 10 |  | 15 enteros + 2 decimales
56 | 430 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 11
57 | 432 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 11 |  | 3 enteros + 2 decimales
58 | 437 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 11 |  | ["R","S"]
59 | 438 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 11 |  | 15 enteros + 2 decimales
60 | 455 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 11 |  | 15 enteros + 2 decimales
61 | 472 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 12
62 | 474 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 12 |  | 3 enteros + 2 decimales
63 | 479 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 12 |  | ["R","S"]
64 | 480 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 12 |  | 15 enteros + 2 decimales
65 | 497 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 12 |  | 15 enteros + 2 decimales
66 | 514 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 13
67 | 516 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 13 |  | 3 enteros + 2 decimales
68 | 521 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 13 |  | ["R","S"]
69 | 522 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 13 |  | 15 enteros + 2 decimales
70 | 539 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 13 |  | 15 enteros + 2 decimales
71 | 556 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 14
72 | 558 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 14 |  | 3 enteros + 2 decimales
73 | 563 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 14 |  | ["R","S"]
74 | 564 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 14 |  | 15 enteros + 2 decimales
75 | 581 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 14 |  | 15 enteros + 2 decimales
76 | 598 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 15
77 | 600 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 15 |  | 3 enteros + 2 decimales
78 | 605 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 15 |  | ["R","S"]
79 | 606 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 15 |  | 15 enteros + 2 decimales
80 | 623 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 15 |  | 15 enteros + 2 decimales
81 | 640 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 16
82 | 642 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 16 |  | 3 enteros + 2 decimales
83 | 647 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 16 |  | ["R","S"]
84 | 648 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 16 |  | 15 enteros + 2 decimales
85 | 665 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 16 |  | 15 enteros + 2 decimales
86 | 682 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 17
87 | 684 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 17 |  | 3 enteros + 2 decimales
88 | 689 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 17 |  | ["R","S"]
89 | 690 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 17 |  | 15 enteros + 2 decimales
90 | 707 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 17 |  | 15 enteros + 2 decimales
91 | 724 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 18
92 | 726 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 18 |  | 3 enteros + 2 decimales
93 | 731 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 18 |  | ["R","S"]
94 | 732 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 18 |  | 15 enteros + 2 decimales
95 | 749 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 18 |  | 15 enteros + 2 decimales
96 | 766 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 19
97 | 768 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 19 |  | 3 enteros + 2 decimales
98 | 773 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 19 |  | ["R","S"]
99 | 774 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 19 |  | 15 enteros + 2 decimales
100 | 791 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 19 |  | 15 enteros + 2 decimales
101 | 808 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 20
102 | 810 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 20 |  | 3 enteros + 2 decimales
103 | 815 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 20 |  | ["R","S"]
104 | 816 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 20 |  | 15 enteros + 2 decimales
105 | 833 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 20 |  | 15 enteros + 2 decimales
106 | 850 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 21
107 | 852 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 21 |  | 3 enteros + 2 decimales
108 | 857 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 21 |  | ["R","S"]
109 | 858 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 21 |  | 15 enteros + 2 decimales
110 | 875 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 21 |  | 15 enteros + 2 decimales
111 | 892 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 22
112 | 894 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 22 |  | 3 enteros + 2 decimales
113 | 899 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 22 |  | ["R","S"]
114 | 900 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 22 |  | 15 enteros + 2 decimales
115 | 917 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 22 |  | 15 enteros + 2 decimales
116 | 934 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 23
117 | 936 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 23 |  | 3 enteros + 2 decimales
118 | 941 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 23 |  | ["R","S"]
119 | 942 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 23 |  | 15 enteros + 2 decimales
120 | 959 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 23 |  | 15 enteros + 2 decimales
121 | 976 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 24
122 | 978 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 24 |  | 3 enteros + 2 decimales
123 | 983 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 24 |  | ["R","S"]
124 | 984 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 24 |  | 15 enteros + 2 decimales
125 | 1001 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 24 |  | 15 enteros + 2 decimales
126 | 1018 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 25
127 | 1020 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 25 |  | 3 enteros + 2 decimales
128 | 1025 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 25 |  | ["R","S"]
129 | 1026 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 25 |  | 15 enteros + 2 decimales
130 | 1043 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 25 |  | 15 enteros + 2 decimales
131 | 1060 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 26
132 | 1062 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 26 |  | 3 enteros + 2 decimales
133 | 1067 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 26 |  | ["R","S"]
134 | 1068 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 26 |  | 15 enteros + 2 decimales
135 | 1085 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 26 |  | 15 enteros + 2 decimales
136 | 1102 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 27
137 | 1104 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 27 |  | 3 enteros + 2 decimales
138 | 1109 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 27 |  | ["R","S"]
139 | 1110 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 27 |  | 15 enteros + 2 decimales
140 | 1127 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 27 |  | 15 enteros + 2 decimales
141 | 1144 | 2 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Código País EM de consumo. 28
142 | 1146 | 5 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo (%) de IVA. 28 |  | 3 enteros + 2 decimales
143 | 1151 | 1 | An |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Tipo IVA.. 28 |  | ["R","S"]
144 | 1152 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Base imponible (€). 28 |  | 15 enteros + 2 decimales
145 | 1169 | 17 | Num |  | 4. Entregas de bienes expedidos o transportados desde EMID España. Cuota IVA (€). 28 |  | 15 enteros + 2 decimales
146 | 1186 | 17 | An |  | Reservado | Obligatorio | Blancos
147 | 1203 | 9 | An |  |  | Obligatorio | Constante "</T36905>"
 | TOTAL | 1211 | POSICIONES

# T36906 Un

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "06"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | A |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 1
7 | 12 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 1
8 | 27 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 1
9 | 29 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 1 |  | 3 enteros + 2 decimales
10 | 34 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 1 |  | [R,S]
11 | 35 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 1 |  | 15 enteros + 2 decimales
12 | 52 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 1 |  | 15 enteros + 2 decimales
13 | 69 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 2
14 | 71 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 2
15 | 86 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 2
16 | 88 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 2 |  | 3 enteros + 2 decimales
17 | 93 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 2 |  | ["R","S"]
18 | 94 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 2 |  | 15 enteros + 2 decimales
19 | 111 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 2 |  | 15 enteros + 2 decimales
20 | 128 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 3
21 | 130 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 3
22 | 145 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 3
23 | 147 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 3 |  | 3 enteros + 2 decimales
24 | 152 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 3 |  | ["R","S"]
25 | 153 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 3 |  | 15 enteros + 2 decimales
26 | 170 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 3 |  | 15 enteros + 2 decimales
27 | 187 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 4
28 | 189 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 4
29 | 204 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 4
30 | 206 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 4 |  | 3 enteros + 2 decimales
31 | 211 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 4 |  | ["R","S"]
32 | 212 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 4 |  | 15 enteros + 2 decimales
33 | 229 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 4 |  | 15 enteros + 2 decimales
34 | 246 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 5
35 | 248 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 5
36 | 263 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 5
37 | 265 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 5 |  | 3 enteros + 2 decimales
38 | 270 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 5 |  | ["R","S"]
39 | 271 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 5 |  | 15 enteros + 2 decimales
40 | 288 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 5 |  | 15 enteros + 2 decimales
41 | 305 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 6
42 | 307 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 6
43 | 322 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 6
44 | 324 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 6 |  | 3 enteros + 2 decimales
45 | 329 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 6 |  | ["R","S"]
46 | 330 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 6 |  | 15 enteros + 2 decimales
47 | 347 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 6 |  | 15 enteros + 2 decimales
48 | 364 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 7
49 | 366 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 7
50 | 381 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 7
51 | 383 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 7 |  | 3 enteros + 2 decimales
52 | 388 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 7 |  | ["R","S"]
53 | 389 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 7 |  | 15 enteros + 2 decimales
54 | 406 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 7 |  | 15 enteros + 2 decimales
55 | 423 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 8
56 | 425 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 8
57 | 440 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 8
58 | 442 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 8 |  | 3 enteros + 2 decimales
59 | 447 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 8 |  | ["R","S"]
60 | 448 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 8 |  | 15 enteros + 2 decimales
61 | 465 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 8 |  | 15 enteros + 2 decimales
62 | 482 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 9
63 | 484 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 9
64 | 499 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 9
65 | 501 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 9 |  | 3 enteros + 2 decimales
66 | 506 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 9 |  | ["R","S"]
67 | 507 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 9 |  | 15 enteros + 2 decimales
68 | 524 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 9 |  | 15 enteros + 2 decimales
69 | 541 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 10
70 | 543 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 10
71 | 558 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 10
72 | 560 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 10 |  | 3 enteros + 2 decimales
73 | 565 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 10 |  | ["R","S"]
74 | 566 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 10 |  | 15 enteros + 2 decimales
75 | 583 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 10 |  | 15 enteros + 2 decimales
76 | 600 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 11
77 | 602 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 11
78 | 617 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 11
79 | 619 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 11 |  | 3 enteros + 2 decimales
80 | 624 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 11 |  | ["R","S"]
81 | 625 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 11 |  | 15 enteros + 2 decimales
82 | 642 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 11 |  | 15 enteros + 2 decimales
83 | 659 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 12
84 | 661 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 12
85 | 676 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 12
86 | 678 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 12 |  | 3 enteros + 2 decimales
87 | 683 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 12 |  | ["R","S"]
88 | 684 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 12 |  | 15 enteros + 2 decimales
89 | 701 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 12 |  | 15 enteros + 2 decimales
90 | 718 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 13
91 | 720 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 13
92 | 735 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 13
93 | 737 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 13 |  | 3 enteros + 2 decimales
94 | 742 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 13 |  | ["R","S"]
95 | 743 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 13 |  | 15 enteros + 2 decimales
96 | 760 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 13 |  | 15 enteros + 2 decimales
97 | 777 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 14
98 | 779 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 14
99 | 794 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 14
100 | 796 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 14 |  | 3 enteros + 2 decimales
101 | 801 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 14 |  | ["R","S"]
102 | 802 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 14 |  | 15 enteros + 2 decimales
103 | 819 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 14 |  | 15 enteros + 2 decimales
104 | 836 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 15
105 | 838 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 15
106 | 853 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 15
107 | 855 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 15 |  | 3 enteros + 2 decimales
108 | 860 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 15 |  | ["R","S"]
109 | 861 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 15 |  | 15 enteros + 2 decimales
110 | 878 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 15 |  | 15 enteros + 2 decimales
111 | 895 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 16
112 | 897 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 16
113 | 912 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 16
114 | 914 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 16 |  | 3 enteros + 2 decimales
115 | 919 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 16 |  | ["R","S"]
116 | 920 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 16 |  | 15 enteros + 2 decimales
117 | 937 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 16 |  | 15 enteros + 2 decimales
118 | 954 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 17
119 | 956 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 17
120 | 971 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 17
121 | 973 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 17 |  | 3 enteros + 2 decimales
122 | 978 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 17 |  | ["R","S"]
123 | 979 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 17 |  | 15 enteros + 2 decimales
124 | 996 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 17 |  | 15 enteros + 2 decimales
125 | 1013 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 18
126 | 1015 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 18
127 | 1030 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 18
128 | 1032 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 18 |  | 3 enteros + 2 decimales
129 | 1037 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 18 |  | ["R","S"]
130 | 1038 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 18 |  | 15 enteros + 2 decimales
131 | 1055 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 18 |  | 15 enteros + 2 decimales
132 | 1072 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 19
133 | 1074 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 19
134 | 1089 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 19
135 | 1091 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 19 |  | 3 enteros + 2 decimales
136 | 1096 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 19 |  | ["R","S"]
137 | 1097 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 19 |  | 15 enteros + 2 decimales
138 | 1114 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 19 |  | 15 enteros + 2 decimales
139 | 1131 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 20
140 | 1133 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 20
141 | 1148 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 20
142 | 1150 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA.20 |  | 3 enteros + 2 decimales
143 | 1155 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 20 |  | ["R","S"]
144 | 1156 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 20 |  | 15 enteros + 2 decimales
145 | 1173 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 20 |  | 15 enteros + 2 decimales
146 | 1190 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 21
147 | 1192 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 21
148 | 1207 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 21
149 | 1209 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 21 |  | 3 enteros + 2 decimales
150 | 1214 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 21 |  | ["R","S"]
151 | 1215 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 21 |  | 15 enteros + 2 decimales
152 | 1232 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 21 |  | 15 enteros + 2 decimales
153 | 1249 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 22
154 | 1251 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 22
155 | 1266 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 22
156 | 1268 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 22 |  | 3 enteros + 2 decimales
157 | 1273 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 22 |  | ["R","S"]
158 | 1274 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 22 |  | 15 enteros + 2 decimales
159 | 1291 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 22 |  | 15 enteros + 2 decimales
160 | 1308 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 23
161 | 1310 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 23
162 | 1325 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 23
163 | 1327 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 23 |  | 3 enteros + 2 decimales
164 | 1332 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 23 |  | ["R","S"]
165 | 1333 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 23 |  | 15 enteros + 2 decimales
166 | 1350 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 23 |  | 15 enteros + 2 decimales
167 | 1367 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 24
168 | 1369 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 24
169 | 1384 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 24
170 | 1386 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 24 |  | 3 enteros + 2 decimales
171 | 1391 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 24 |  | ["R","S"]
172 | 1392 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 24 |  | 15 enteros + 2 decimales
173 | 1409 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 24 |  | 15 enteros + 2 decimales
174 | 1426 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 25
175 | 1428 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 25
176 | 1443 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 25
177 | 1445 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 25 |  | 3 enteros + 2 decimales
178 | 1450 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 25 |  | ["R","S"]
179 | 1451 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 25 |  | 15 enteros + 2 decimales
180 | 1468 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 25 |  | 15 enteros + 2 decimales
181 | 1485 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 26
182 | 1487 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 26
183 | 1502 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 26
184 | 1504 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 26 |  | 3 enteros + 2 decimales
185 | 1509 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 26 |  | ["R","S"]
186 | 1510 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 26 |  | 15 enteros + 2 decimales
187 | 1527 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 26 |  | 15 enteros + 2 decimales
188 | 1544 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 27
189 | 1546 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 27
190 | 1561 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 27
191 | 1563 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 27 |  | 3 enteros + 2 decimales
192 | 1568 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 27 |  | ["R","S"]
193 | 1569 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 27 |  | 15 enteros + 2 decimales
194 | 1586 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 27 |  | 15 enteros + 2 decimales
195 | 1603 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. Código País. 28
196 | 1605 | 15 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Establecimiento Permanente. NIVA/Otros códigos identificativos. 28
197 | 1620 | 2 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Código País/EM de consumo. 28
198 | 1622 | 5 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España.Tipo (%) de IVA. 28 |  | 3 enteros + 2 decimales
199 | 1627 | 1 | An |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Tipo de IVA. 28 |  | ["R","S"]
200 | 1628 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Base imponible (€). 28 |  | 15 enteros + 2 decimales
201 | 1645 | 17 | Num |  | 5. Prestaciones de servicios desde establecimientos permanentes en otros EM distintos de España. Cuota IVA (€). 28 |  | 15 enteros + 2 decimales
202 | 1662 | 17 | An |  | Reservado | Obligatorio | Blancos
203 | 1679 | 9 | An |  |  | Obligatorio | Constante "</T36906>"
 | TOTAL | 1687 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES

# T36907 Un

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "07"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | A |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 1
7 | 12 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 1
8 | 27 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 1
9 | 29 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 1 |  | 3 enteros + 2 decimales
10 | 34 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 1 |  | ["R","S"]
11 | 35 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 1 |  | 15 enteros + 2 decimales
12 | 52 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 1 |  | 15 enteros + 2 decimales
13 | 69 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 2
14 | 71 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 2
15 | 86 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 2
16 | 88 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 2 |  | 3 enteros + 2 decimales
17 | 93 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 2 |  | ["R","S"]
18 | 94 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 2 |  | 15 enteros + 2 decimales
19 | 111 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 2 |  | 15 enteros + 2 decimales
20 | 128 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 3
21 | 130 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 3
22 | 145 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 3
23 | 147 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 3 |  | 3 enteros + 2 decimales
24 | 152 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 3 |  | ["R","S"]
25 | 153 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 3 |  | 15 enteros + 2 decimales
26 | 170 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 3 |  | 15 enteros + 2 decimales
27 | 187 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 4
28 | 189 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 4
29 | 204 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 4
30 | 206 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 4 |  | 3 enteros + 2 decimales
31 | 211 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 4 |  | ["R","S"]
32 | 212 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 4 |  | 15 enteros + 2 decimales
33 | 229 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 4 |  | 15 enteros + 2 decimales
34 | 246 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 5
35 | 248 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 5
36 | 263 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 5
37 | 265 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 5 |  | 3 enteros + 2 decimales
38 | 270 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 5 |  | ["R","S"]
39 | 271 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 5 |  | 15 enteros + 2 decimales
40 | 288 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 5 |  | 15 enteros + 2 decimales
41 | 305 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 6
42 | 307 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 6
43 | 322 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 6
44 | 324 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 6 |  | 3 enteros + 2 decimales
45 | 329 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 6 |  | ["R","S"]
46 | 330 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 6 |  | 15 enteros + 2 decimales
47 | 347 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 6 |  | 15 enteros + 2 decimales
48 | 364 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 7
49 | 366 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 7
50 | 381 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 7
51 | 383 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 7 |  | 3 enteros + 2 decimales
52 | 388 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 7 |  | ["R","S"]
53 | 389 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 7 |  | 15 enteros + 2 decimales
54 | 406 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 7 |  | 15 enteros + 2 decimales
55 | 423 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 8
56 | 425 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 8
57 | 440 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 8
58 | 442 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 8 |  | 3 enteros + 2 decimales
59 | 447 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 8 |  | ["R","S"]
60 | 448 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 8 |  | 15 enteros + 2 decimales
61 | 465 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 8 |  | 15 enteros + 2 decimales
62 | 482 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 9
63 | 484 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 9
64 | 499 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 9
65 | 501 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 9 |  | 3 enteros + 2 decimales
66 | 506 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 9 |  | ["R","S"]
67 | 507 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 9 |  | 15 enteros + 2 decimales
68 | 524 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 9 |  | 15 enteros + 2 decimales
69 | 541 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 10
70 | 543 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 10
71 | 558 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 10
72 | 560 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 10 |  | 3 enteros + 2 decimales
73 | 565 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 10 |  | ["R","S"]
74 | 566 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 10 |  | 15 enteros + 2 decimales
75 | 583 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 10 |  | 15 enteros + 2 decimales
76 | 600 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 11
77 | 602 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 11
78 | 617 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 11
79 | 619 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 11 |  | 3 enteros + 2 decimales
80 | 624 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 11 |  | ["R","S"]
81 | 625 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 11 |  | 15 enteros + 2 decimales
82 | 642 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 11 |  | 15 enteros + 2 decimales
83 | 659 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 12
84 | 661 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 12
85 | 676 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 12
86 | 678 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 12 |  | 3 enteros + 2 decimales
87 | 683 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 12 |  | ["R","S"]
88 | 684 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 12 |  | 15 enteros + 2 decimales
89 | 701 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 12 |  | 15 enteros + 2 decimales
90 | 718 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 13
91 | 720 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 13
92 | 735 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 13
93 | 737 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 13 |  | 3 enteros + 2 decimales
94 | 742 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 13 |  | ["R","S"]
95 | 743 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 13 |  | 15 enteros + 2 decimales
96 | 760 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 13 |  | 15 enteros + 2 decimales
97 | 777 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 14
98 | 779 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 14
99 | 794 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 14
100 | 796 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 14 |  | 3 enteros + 2 decimales
101 | 801 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 14 |  | ["R","S"]
102 | 802 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 14 |  | 15 enteros + 2 decimales
103 | 819 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 14 |  | 15 enteros + 2 decimales
104 | 836 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 15
105 | 838 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 15
106 | 853 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 15
107 | 855 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 15 |  | 3 enteros + 2 decimales
108 | 860 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 15 |  | ["R","S"]
109 | 861 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 15 |  | 15 enteros + 2 decimales
110 | 878 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 15 |  | 15 enteros + 2 decimales
111 | 895 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 16
112 | 897 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 16
113 | 912 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 16
114 | 914 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 16 |  | 3 enteros + 2 decimales
115 | 919 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 16 |  | ["R","S"]
116 | 920 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 16 |  | 15 enteros + 2 decimales
117 | 937 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 16 |  | 15 enteros + 2 decimales
118 | 954 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 17
119 | 956 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 17
120 | 971 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 17
121 | 973 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 17 |  | 3 enteros + 2 decimales
122 | 978 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 17 |  | ["R","S"]
123 | 979 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 17 |  | 15 enteros + 2 decimales
124 | 996 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 17 |  | 15 enteros + 2 decimales
125 | 1013 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País. 18
126 | 1015 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 18
127 | 1030 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 18
128 | 1032 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 18 |  | 3 enteros + 2 decimales
129 | 1037 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 18 |  | ["R","S"]
130 | 1038 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 18 |  | 15 enteros + 2 decimales
131 | 1055 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 18 |  | 15 enteros + 2 decimales
132 | 1072 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 19
133 | 1074 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 19
134 | 1089 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 19
135 | 1091 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 19 |  | 3 enteros + 2 decimales
136 | 1096 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 19 |  | ["R","S"]
137 | 1097 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 19 |  | 15 enteros + 2 decimales
138 | 1114 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 19 |  | 15 enteros + 2 decimales
139 | 1131 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 20
140 | 1133 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 20
141 | 1148 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 20
142 | 1150 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 20 |  | 3 enteros + 2 decimales
143 | 1155 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 20 |  | ["R","S"]
144 | 1156 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 20 |  | 15 enteros + 2 decimales
145 | 1173 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 20 |  | 15 enteros + 2 decimales
146 | 1190 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 21
147 | 1192 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 21
148 | 1207 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 21
149 | 1209 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 21 |  | 3 enteros + 2 decimales
150 | 1214 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 21 |  | ["R","S"]
151 | 1215 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 21 |  | 15 enteros + 2 decimales
152 | 1232 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 21 |  | 15 enteros + 2 decimales
153 | 1249 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 22
154 | 1251 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 22
155 | 1266 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 22
156 | 1268 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 22 |  | 3 enteros + 2 decimales
157 | 1273 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 22 |  | ["R","S"]
158 | 1274 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 22 |  | 15 enteros + 2 decimales
159 | 1291 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 22 |  | 15 enteros + 2 decimales
160 | 1308 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 23
161 | 1310 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 23
162 | 1325 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 23
163 | 1327 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 23 |  | 3 enteros + 2 decimales
164 | 1332 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 23 |  | ["R","S"]
165 | 1333 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 23 |  | 15 enteros + 2 decimales
166 | 1350 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 23 |  | 15 enteros + 2 decimales
167 | 1367 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 24
168 | 1369 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 24
169 | 1384 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 24
170 | 1386 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 24 |  | 3 enteros + 2 decimales
171 | 1391 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 24 |  | ["R","S"]
172 | 1392 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 24 |  | 15 enteros + 2 decimales
173 | 1409 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 24 |  | 15 enteros + 2 decimales
174 | 1426 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 25
175 | 1428 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 25
176 | 1443 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 25
177 | 1445 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 25 |  | 3 enteros + 2 decimales
178 | 1450 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 25 |  | ["R","S"]
179 | 1451 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 25 |  | 15 enteros + 2 decimales
180 | 1468 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 25 |  | 15 enteros + 2 decimales
181 | 1485 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 26
182 | 1487 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 26
183 | 1502 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 26
184 | 1504 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 26 |  | 3 enteros + 2 decimales
185 | 1509 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 26 |  | ["R","S"]
186 | 1510 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 26 |  | 15 enteros + 2 decimales
187 | 1527 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 26 |  | 15 enteros + 2 decimales
188 | 1544 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 27
189 | 1546 | 15 | An |  | 76. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 27
190 | 1561 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 27
191 | 1563 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 27 |  | 3 enteros + 2 decimales
192 | 1568 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 27 |  | ["R","S"]
193 | 1569 | 17 | Num |  | 76. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 2 |  | 15 enteros + 2 decimales
194 | 1586 | 17 | Num |  | 76. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 2 |  | 15 enteros + 2 decimales
195 | 1603 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. Código País. 28
196 | 1605 | 15 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.. NIVA/Otros códigos identificativos. 28
197 | 1620 | 2 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Código País/EM de consumo. 28
198 | 1622 | 5 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España.Tipo (%) de IVA. 28 |  | 3 enteros + 2 decimales
199 | 1627 | 1 | An |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Tipo de IVA. 28 |  | ["R","S"]
200 | 1628 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Base imponible (€). 28 |  | 15 enteros + 2 decimales
201 | 1645 | 17 | Num |  | 6. Entregas de bienes expedidos o transportados desde otros EM distintos de España. Cuota IVA (€). 28 |  | 15 enteros + 2 decimales
202 | 1662 | 17 | An |  | Reservado | Obligatorio | Blancos
203 | 1679 | 9 | An |  |  | Obligatorio | Constante "</T36907>"
 | TOTAL | 1687 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES

# T36908 Un

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "08"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | A |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 1
7 | 12 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 1
8 | 16 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
9 | 17 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 1
10 | 19 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 1 |  | 15 enteros + 2 decimales
11 | 36 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 2
12 | 38 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 2
13 | 42 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
14 | 43 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 2
15 | 45 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 2 |  | 15 enteros + 2 decimales
16 | 62 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 3
17 | 64 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 3
18 | 68 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
19 | 69 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 3
20 | 71 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 3 |  | 15 enteros + 2 decimales
21 | 88 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 4
22 | 90 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 4
23 | 94 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
24 | 95 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 4
25 | 97 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 4 |  | 15 enteros + 2 decimales
26 | 114 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 5
27 | 116 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 5
28 | 120 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
29 | 121 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 5
30 | 123 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 5 |  | 15 enteros + 2 decimales
31 | 140 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 6
32 | 142 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 6
33 | 146 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
34 | 147 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 6
35 | 149 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 6 |  | 15 enteros + 2 decimales
36 | 166 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 7
37 | 168 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 7
38 | 172 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
39 | 173 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 7
40 | 175 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 7 |  | 15 enteros + 2 decimales
41 | 192 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 8
42 | 194 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 8
43 | 198 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
44 | 199 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 8
45 | 201 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 8 |  | 15 enteros + 2 decimales
46 | 218 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 9
47 | 220 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 9
48 | 224 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
49 | 225 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 9
50 | 227 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 9 |  | 15 enteros + 2 decimales
51 | 244 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 10
52 | 246 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 10
53 | 250 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
54 | 251 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 10
55 | 253 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 10 |  | 15 enteros + 2 decimales
56 | 270 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 11
57 | 272 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 11
58 | 276 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. |  | "T"
59 | 277 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 11
60 | 279 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 11 |  | 15 enteros + 2 decimales
61 | 296 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 12
62 | 298 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 12
63 | 302 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.12 |  | "T"
64 | 303 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 12
65 | 305 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 12 |  | 15 enteros + 2 decimales
66 | 322 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 13
67 | 324 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 13
68 | 328 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.13 |  | "T"
69 | 329 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 13
70 | 331 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 13 |  | 15 enteros + 2 decimales
71 | 348 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 14
72 | 350 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 14
73 | 354 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.14 |  | "T"
74 | 355 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 14
75 | 357 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 14 |  | 15 enteros + 2 decimales
76 | 374 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 15
77 | 376 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 15
78 | 380 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.15 |  | "T"
79 | 381 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 15
80 | 383 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 15 |  | 15 enteros + 2 decimales
81 | 400 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 16
82 | 402 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 16
83 | 406 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.16 |  | "T"
84 | 407 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 16
85 | 409 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 16 |  | 15 enteros + 2 decimales
86 | 426 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 17
87 | 428 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 17
88 | 432 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.17 |  | "T"
89 | 433 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 17
90 | 435 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 17 |  | 15 enteros + 2 decimales
91 | 452 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 18
92 | 454 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 18
93 | 458 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.18 |  | "T"
94 | 459 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 18
95 | 461 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 18 |  | 15 enteros + 2 decimales
96 | 478 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 19
97 | 480 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 19
98 | 484 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.19 |  | "T"
99 | 485 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 19
100 | 487 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 19 |  | 15 enteros + 2 decimales
101 | 504 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 20
102 | 506 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 20
103 | 510 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.20 |  | "T"
104 | 511 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 20
105 | 513 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 20 |  | 15 enteros + 2 decimales
106 | 530 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 21
107 | 532 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 21
108 | 536 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.21 |  | "T"
109 | 537 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 21
110 | 539 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 21 |  | 15 enteros + 2 decimales
111 | 556 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 22
112 | 558 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 22
113 | 562 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.22 |  | "T"
114 | 563 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 22
115 | 565 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 22 |  | 15 enteros + 2 decimales
116 | 582 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 23
117 | 584 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 23
118 | 588 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.23 |  | "T"
119 | 589 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 23
120 | 591 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 23 |  | 15 enteros + 2 decimales
121 | 608 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 24
122 | 610 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 24
123 | 614 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.24 |  | "T"
124 | 615 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 24
125 | 617 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 24 |  | 15 enteros + 2 decimales
126 | 634 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 25
127 | 636 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 25
128 | 640 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo. 25 |  | "T"
129 | 641 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 25
130 | 643 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 25 |  | 15 enteros + 2 decimales
131 | 660 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 26
132 | 662 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 26
133 | 666 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.26 |  | "T"
134 | 667 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 26
135 | 669 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 26 |  | 15 enteros + 2 decimales
136 | 686 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 27
137 | 688 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 27
138 | 692 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.27 |  | "T"
139 | 693 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 27
140 | 695 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 27 |  | 15 enteros + 2 decimales
141 | 712 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 28
142 | 714 | 4 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 28
143 | 718 | 1 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Tipo de periodo.28 |  | "T"
144 | 719 | 2 | An |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Período. 28
145 | 721 | 17 | Num |  | 7. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 28 |  | 15 enteros + 2 decimales
146 | 738 | 17 | An |  | Reservado | Obligatorio | Blancos
147 | 755 | 9 | An |  |  | Obligatorio | Constante "</T36908>"
 | TOTAL | 763 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES

# T36909 Un

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "09"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | A |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 5785 | An |  | Reservado | Obligatorio | Blancos
7 | 5795 | 9 | An |  |  | Obligatorio | Constante "</T36909>"
 | TOTAL | 5803 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES

# T36910 Imp

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "10"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 5 | An |  | Régimen | Obligatorio | "IMPO"
6 | 14 | 1 | An |  | Categoría | Obligatorio | "D"
7 | 15 | 1 | An |  | Tipo de pago |  | ["O", "S", "I", "N", "T"]
8 | 16 | 22 | An |  | NRC Pago
9 | 38 | 17 | Num |  | Importe pagado |  | 15 enteros + 2 decimales
10 | 55 | 1 | An |  | Complementaria | Obligatorio | [blanco | constante "C"]
11 | 56 | 2 | An |  | 1. Declarante. País | Obligatorio
12 | 58 | 15 | An |  | 1. Declarante. NIF | Obligatorio
13 | 73 | 15 | An |  | 1. Declarante. Número de operador en el régimen (NIOSS) | Obligatorio
14 | 88 | 125 | An |  | 1. Declarante . Apellidos y nombre o razón social. | Obligatorio
15 | 213 | 1 | An |  | 1. Actúa a través de intermediario | Obligatorio | "0" o "1"
16 | 214 | 15 | An |  | 1. Nº de identificación del intermediario (NIOSSIn) | Obligatorio
17 | 229 | 4 | Num |  | 2. Ejercicio y período. Ejercicio | Obligatorio
18 | 233 | 1 | An |  | 2. Ejercicio y período. Tipo de periodo | Obligatorio | "M"
19 | 234 | 2 | Num |  | 2. Ejercicio y período. Periodo | Obligatorio | 1 a 12
20 | 236 | 8 | Num |  | 2. Ejercicio y periodo. Fecha desde |  | AAAAMMDD
21 | 244 | 8 | Num |  | 2. Ejercicio y período. Fecha hasta |  | AAAAMMDD
22 | 252 | 1 | An |  | 2. Ejercicio y período. Declaración sin actividad | Obligatorio | "0" o "1"
23 | 253 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.1
24 | 255 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.1 |  | 3 enteros + 2 decimales
25 | 260 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.1 |  | ["R","S"]
26 | 261 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).1 |  | 15 enteros + 2 decimales
27 | 278 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).1 |  | 15 enteros + 2 decimales
28 | 295 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.2
29 | 297 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.2 |  | 3 enteros + 2 decimales
30 | 302 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.2 |  | ["R","S"]
31 | 303 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).2 |  | 15 enteros + 2 decimales
32 | 320 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).2 |  | 15 enteros + 2 decimales
33 | 337 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.3
34 | 339 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.3 |  | 3 enteros + 2 decimales
35 | 344 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.3 |  | ["R","S"]
36 | 345 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).3 |  | 15 enteros + 2 decimales
37 | 362 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).3 |  | 15 enteros + 2 decimales
38 | 379 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.4
39 | 381 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.4 |  | 3 enteros + 2 decimales
40 | 386 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.4 |  | ["R","S"]
41 | 387 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).4 |  | 15 enteros + 2 decimales
42 | 404 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).4 |  | 15 enteros + 2 decimales
43 | 421 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.5
44 | 423 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.5 |  | 3 enteros + 2 decimales
45 | 428 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.5 |  | ["R","S"]
46 | 429 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).5 |  | 15 enteros + 2 decimales
47 | 446 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).5 |  | 15 enteros + 2 decimales
48 | 463 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.6
49 | 465 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.6 |  | 3 enteros + 2 decimales
50 | 470 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.6 |  | ["R","S"]
51 | 471 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).6 |  | 15 enteros + 2 decimales
52 | 488 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).6 |  | 15 enteros + 2 decimales
53 | 505 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.7
54 | 507 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.7 |  | 3 enteros + 2 decimales
55 | 512 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.7 |  | ["R","S"]
56 | 513 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).7 |  | 15 enteros + 2 decimales
57 | 530 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).7 |  | 15 enteros + 2 decimales
58 | 547 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.8
59 | 549 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.8 |  | 3 enteros + 2 decimales
60 | 554 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.8 |  | ["R","S"]
61 | 555 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).8 |  | 15 enteros + 2 decimales
62 | 572 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).8 |  | 15 enteros + 2 decimales
63 | 589 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.9
64 | 591 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.9 |  | 3 enteros + 2 decimales
65 | 596 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.9 |  | ["R","S"]
66 | 597 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).9 |  | 15 enteros + 2 decimales
67 | 614 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).9 |  | 15 enteros + 2 decimales
68 | 631 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.10
69 | 633 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.10 |  | 3 enteros + 2 decimales
70 | 638 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.10 |  | ["R","S"]
71 | 639 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).10 |  | 15 enteros + 2 decimales
72 | 656 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).10 |  | 15 enteros + 2 decimales
73 | 673 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.11
74 | 675 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.11 |  | 3 enteros + 2 decimales
75 | 680 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.11 |  | ["R","S"]
76 | 681 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).11 |  | 15 enteros + 2 decimales
77 | 698 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).11 |  | 15 enteros + 2 decimales
78 | 715 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.12
79 | 717 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.12 |  | 3 enteros + 2 decimales
80 | 722 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.12 |  | ["R","S"]
81 | 723 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).12 |  | 15 enteros + 2 decimales
82 | 740 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).12 |  | 15 enteros + 2 decimales
83 | 757 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.13
84 | 759 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.13 |  | 3 enteros + 2 decimales
85 | 764 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.13 |  | ["R","S"]
86 | 765 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).13 |  | 15 enteros + 2 decimales
87 | 782 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).13 |  | 15 enteros + 2 decimales
88 | 799 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.14
89 | 801 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.14 |  | 3 enteros + 2 decimales
90 | 806 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.14 |  | ["R","S"]
91 | 807 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).14 |  | 15 enteros + 2 decimales
92 | 824 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).14 |  | 15 enteros + 2 decimales
93 | 841 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.15
94 | 843 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.15 |  | 3 enteros + 2 decimales
95 | 848 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.15 |  | ["R","S"]
96 | 849 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).15 |  | 15 enteros + 2 decimales
97 | 866 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).15 |  | 15 enteros + 2 decimales
98 | 883 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.16
99 | 885 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.16 |  | 3 enteros + 2 decimales
100 | 890 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.16 |  | ["R","S"]
101 | 891 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).16 |  | 15 enteros + 2 decimales
102 | 908 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).16 |  | 15 enteros + 2 decimales
103 | 925 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.17
104 | 927 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.17 |  | 3 enteros + 2 decimales
105 | 932 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.17 |  | ["R","S"]
106 | 933 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).17 |  | 15 enteros + 2 decimales
107 | 950 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).17 |  | 15 enteros + 2 decimales
108 | 967 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.18
109 | 969 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.18 |  | 3 enteros + 2 decimales
110 | 974 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.18 |  | ["R","S"]
111 | 975 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).18 |  | 15 enteros + 2 decimales
112 | 992 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).18 |  | 15 enteros + 2 decimales
113 | 1009 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.19
114 | 1011 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.19 |  | 3 enteros + 2 decimales
115 | 1016 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.19 |  | ["R","S"]
116 | 1017 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).19 |  | 15 enteros + 2 decimales
117 | 1034 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).19 |  | 15 enteros + 2 decimales
118 | 1051 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.20
119 | 1053 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.20 |  | 3 enteros + 2 decimales
120 | 1058 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.20 |  | ["R","S"]
121 | 1059 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).20 |  | 15 enteros + 2 decimales
122 | 1076 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).20 |  | 15 enteros + 2 decimales
123 | 1093 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.21
124 | 1095 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.21 |  | 3 enteros + 2 decimales
125 | 1100 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.21 |  | ["R","S"]
126 | 1101 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).21 |  | 15 enteros + 2 decimales
127 | 1118 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).21 |  | 15 enteros + 2 decimales
128 | 1135 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.22
129 | 1137 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.22 |  | 3 enteros + 2 decimales
130 | 1142 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.22 |  | ["R","S"]
131 | 1143 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).22 |  | 15 enteros + 2 decimales
132 | 1160 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).22 |  | 15 enteros + 2 decimales
133 | 1177 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.23
134 | 1179 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.23 |  | 3 enteros + 2 decimales
135 | 1184 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.23 |  | ["R","S"]
136 | 1185 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).23 |  | 15 enteros + 2 decimales
137 | 1202 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).23 |  | 15 enteros + 2 decimales
138 | 1219 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.24
139 | 1221 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.24 |  | 3 enteros + 2 decimales
140 | 1226 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.24 |  | ["R","S"]
141 | 1227 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).24 |  | 15 enteros + 2 decimales
142 | 1244 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).24 |  | 15 enteros + 2 decimales
143 | 1261 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.25
144 | 1263 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.25 |  | 3 enteros + 2 decimales
145 | 1268 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.25 |  | ["R","S"]
146 | 1269 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).25 |  | 15 enteros + 2 decimales
147 | 1286 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).25 |  | 15 enteros + 2 decimales
148 | 1303 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.26
149 | 1305 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.26 |  | 3 enteros + 2 decimales
150 | 1310 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.26 |  | ["R","S"]
151 | 1311 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).26 |  | 15 enteros + 2 decimales
152 | 1328 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).26 |  | 15 enteros + 2 decimales
153 | 1345 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.27
154 | 1347 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.27 |  | 3 enteros + 2 decimales
155 | 1352 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.27 |  | ["R","S"]
156 | 1353 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).27 |  | 15 enteros + 2 decimales
157 | 1370 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).27 |  | 15 enteros + 2 decimales
158 | 1387 | 2 | An |  | 3. Importaciones de bienes de menos de 150 €. Código de país/EM de consumo.28
159 | 1389 | 5 | Num |  | 3. Importaciones de bienes de menos de 150 €. Tipo (%) de IVA.28 |  | 3 enteros + 2 decimales
160 | 1394 | 1 | An |  | 3. Importaciones de bienes de menos de 150 €. Tipo IVA.28 |  | ["R","S"]
161 | 1395 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Base imponible (€).28 |  | 15 enteros + 2 decimales
162 | 1412 | 17 | Num |  | 3. Importaciones de bienes de menos de 150 €. Cuota IVA (€).28 |  | 15 enteros + 2 decimales
163 | 1429 | 17 | An |  | Reservado | Obligatorio | Blancos
164 | 1446 | 9 | An |  |  | Obligatorio | Constante "</T36910>"
 | TOTAL | 1454 | POSICIONES
Notas:
1. Los valores de "Tipo de pago" serán: 
I: Ingreso total, 
S: Ingreso parcial, 
O: Sin ingreso, 
N: Negativa/Pago cero, 
T: A Ingresar por transferencia
2. Los valores de "Prestaciones de servicios. Tipo IVA" serán S:Estándar, R:Reducido
3. Los códigos de país seguiran el estándar ISO-3166 de dos letras. Se utilizará "EL" para Grecia y "XI" para Irlanda del Norte, que en determinados casos actuará como un EM

# T36911 Imp

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "11"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | An |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 1
7 | 12 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 1
8 | 16 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
9 | 17 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 1
10 | 19 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 1 |  | 15 enteros + 2 decimales
11 | 36 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 2
12 | 38 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 2
13 | 42 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
14 | 43 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 2
15 | 45 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 2 |  | 15 enteros + 2 decimales
16 | 62 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 3
17 | 64 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 3
18 | 68 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
19 | 69 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 3
20 | 71 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 3 |  | 15 enteros + 2 decimales
21 | 88 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 4
22 | 90 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 4
23 | 94 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
24 | 95 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 4
25 | 97 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 4 |  | 15 enteros + 2 decimales
26 | 114 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 5
27 | 116 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 5
28 | 120 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
29 | 121 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 5
30 | 123 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 5 |  | 15 enteros + 2 decimales
31 | 140 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 6
32 | 142 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 6
33 | 146 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
34 | 147 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 6
35 | 149 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 6 |  | 15 enteros + 2 decimales
36 | 166 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 7
37 | 168 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 7
38 | 172 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
39 | 173 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 7
40 | 175 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 7 |  | 15 enteros + 2 decimales
41 | 192 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 8
42 | 194 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 8
43 | 198 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
44 | 199 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 8
45 | 201 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 8 |  | 15 enteros + 2 decimales
46 | 218 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 9
47 | 220 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 9
48 | 224 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
49 | 225 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 9
50 | 227 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 9 |  | 15 enteros + 2 decimales
51 | 244 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 10
52 | 246 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 10
53 | 250 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
54 | 251 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 10
55 | 253 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 10 |  | 15 enteros + 2 decimales
56 | 270 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 11
57 | 272 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 11
58 | 276 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo |  | "M"
59 | 277 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 11
60 | 279 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 11 |  | 15 enteros + 2 decimales
61 | 296 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 12
62 | 298 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 12
63 | 302 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 12 |  | "M"
64 | 303 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 12
65 | 305 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 12 |  | 15 enteros + 2 decimales
66 | 322 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 13
67 | 324 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 13
68 | 328 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 13 |  | "M"
69 | 329 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 13
70 | 331 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 13 |  | 15 enteros + 2 decimales
71 | 348 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 14
72 | 350 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 14
73 | 354 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 14 |  | "M"
74 | 355 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 14
75 | 357 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 14 |  | 15 enteros + 2 decimales
76 | 374 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 15
77 | 376 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 15
78 | 380 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 15 |  | "M"
79 | 381 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 15
80 | 383 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 15 |  | 15 enteros + 2 decimales
81 | 400 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 16
82 | 402 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 16
83 | 406 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 16 |  | "M"
84 | 407 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 16
85 | 409 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 16 |  | 15 enteros + 2 decimales
86 | 426 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 17
87 | 428 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 17
88 | 432 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 17 |  | "M"
89 | 433 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 17
90 | 435 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 17 |  | 15 enteros + 2 decimales
91 | 452 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 18
92 | 454 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 18
93 | 458 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 18 |  | "M"
94 | 459 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 18
95 | 461 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 18 |  | 15 enteros + 2 decimales
96 | 478 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 19
97 | 480 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 19
98 | 484 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 19 |  | "M"
99 | 485 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 19
100 | 487 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 19 |  | 15 enteros + 2 decimales
101 | 504 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 20
102 | 506 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 20
103 | 510 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 20 |  | "M"
104 | 511 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 20
105 | 513 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 20 |  | 15 enteros + 2 decimales
106 | 530 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 21
107 | 532 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 21
108 | 536 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 21 |  | "M"
109 | 537 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 21
110 | 539 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 21 |  | 15 enteros + 2 decimales
111 | 556 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 22
112 | 558 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 22
113 | 562 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 22 |  | "M"
114 | 563 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 22
115 | 565 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 22 |  | 15 enteros + 2 decimales
116 | 582 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 23
117 | 584 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 23
118 | 588 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 23 |  | "M"
119 | 589 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 23
120 | 591 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 23 |  | 15 enteros + 2 decimales
121 | 608 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 24
122 | 610 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 24
123 | 614 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 24 |  | "M"
124 | 615 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 24
125 | 617 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 24 |  | 15 enteros + 2 decimales
126 | 634 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 25
127 | 636 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 25
128 | 640 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo 25 |  | "M"
129 | 641 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 25
130 | 643 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 25 |  | 15 enteros + 2 decimales
131 | 660 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 26
132 | 662 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 26
133 | 666 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo. 26 |  | "M"
134 | 667 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 26
135 | 669 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 26 |  | 15 enteros + 2 decimales
136 | 686 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 27
137 | 688 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 27
138 | 692 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo. 27 |  | "M"
139 | 693 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 27
140 | 695 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 27 |  | 15 enteros + 2 decimales
141 | 712 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Código País EM de consumo. 28
142 | 714 | 4 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Ejercicio. 28
143 | 718 | 1 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años).  Tipo de periodo. 28 |  | "M"
144 | 719 | 2 | An |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Periodo. 28
145 | 721 | 17 | Num |  | 4. Correcciones de declaraciones de períodos anteriores (máx. 3 años). Cuota IVA corregida (€). 28 |  | 15 enteros + 2 decimales
146 | 738 | 17 | An |  | Reservado | Obligatorio | Blancos
147 | 755 | 9 | An |  |  | Obligatorio | Constante "</T36911>"
 | TOTAL | 763 | POSICIONES

# T36912 Imp

 | Agencia Tributaria
Modelo 369 |  | Diseño de registro. Castellano.
Versión 1.1 |  | IMPUESTO SOBRE EL VALOR AÑADIDO. Regímenes especiales aplicables a los servicios  prestados a personas que no tengan la condición de sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. Autoliquidación
Nº | Posic. | Lon | Tipo | Comp | Descripción | Oblig. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "369"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "12"
4 | 8 | 1 | An |  | Fin de identificador de modelo | Obligatorio | Constante ">"
5 | 9 | 1 | A |  | Complementaria | Obligatorio | [blanco | constante "C"]
6 | 10 | 2929 | An |  | Reservado | Obligatorio | Blancos
7 | 2939 | 9 | An |  |  | Obligatorio | Constante "</T36912>"
 | TOTAL | 2947 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES