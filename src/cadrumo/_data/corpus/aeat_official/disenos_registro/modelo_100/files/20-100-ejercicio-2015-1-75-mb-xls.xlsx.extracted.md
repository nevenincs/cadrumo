# 100-00

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 17 | An | Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "<T100020150A0000>"
2 | 18 | 5 | An | Constante |  | "<AUX>"
3 | 23 | 30 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
4 | 53 | 1 | An | Idioma de la declaración (**) |  | "E", "C", "G", "V"
5 | 54 | 39 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
6 | 93 | 4 | An | Versión del Programa (**)
7 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
8 | 101 | 9 | An | NIF Empresa Desarrollo (**)
9 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
10 | 323 | 6 | An | Constante |  | "</AUX>"
11 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "</T100020150A0000>"
16 | *** | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total |  | Variable
 |  |  |  | (**) A cumplimentar por las entidades desarrolladoras (EEDD)
 |  |  |  | Idioma de la declaración: (E) Castellano, (C) Catalán, (G) Gallego, (V) Valenciano
 |  |  |  | Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
 |  |  |  | NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
 |  |  | Páginas Complementarias
 |  |  | Pág | APARTADO | Nº máximo apart. | Nº máximo págs.
 |  |  | 1 | Vivienda habitual | 8 | 1
 |  |  | 4 | Inmuebles no afectos AAEE | 60 | 20
 |  |  | 4 | Inmuebles arrendados por ent.reg.atrib.rentas | 60 | 20
 |  |  | 4 | Inmuebles afectos AAEE | 60 | 20
 |  |  | 5 | (E1) Rtos. aaee estim. directa | 6 | 2
 |  |  | 6 | (E2) Rtos. aaee estim. objetiva | 6 | 3
 |  |  | 7 | (E3) Rtos. activ. agricolas | 6 | 3
 |  |  | 8 | (F) Regímenes especiales | 8 | 4
 |  |  | 9 | (G2) G/P sometidas a retención < 1 año | 60 | 20
 |  |  | 9 | (G2) G/P de acciones < 1 año | 60 | 20
 |  |  | 9 | (G2) G/P otros elementos patrimoniales < 1 año | 40 | 20
 |  |  | 10 | (G3) G/P sometidas a retención > 1 año | 60 | 20
 |  |  | 10 | (G3) G/P de acciones > 1 año | 60 | 20
 |  |  | 10 | (G3) G/P de valores > 1 año | 60 | 20
 |  |  | 10 | (G3) G/P otros elementos patrimoniales > 1 año | 40 | 20
 |  |  | 10 | (G4) Imputación a 2014 G/P ejercicios anteriores (BIA) | 15 | 5
 |  |  | 11 | (G5) G/P difer. por reinversión | 15 | 5
 |  |  | 11 | (G5) Imputación de 2014 G/P ejercicios anteriores (BIG) | 15 | 5
 |  |  | 13 | Aport. sistemas previsión social | 4 | 2
 |  |  | 13 | Aport. Sistemas previsión social a favor de discapacitados | 4 | 2
 |  |  | 13 | Aport. patrim. proteg. discapacit. | 4 | 2
 |  |  | 13 | Pens. Compens. A favor cónyuge | 4 | 2
 |  |  | 13 | Aport. Deportistas profesionales | 4 | 2
 |  |  | 14 | (K) Exceso no reducido. Régimen general | 4 | 2
 |  |  | 14 | (K) Exceso no reducido. Discapacitados | 4 | 2
 |  |  | 14 | (K) Exceso no reducido. Patrimonios protegidos | 4 | 2
 |  |  | 14 | (K) Exceso no reducido. Deportistas profesionales | 4 | 2

# 100-01 

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "01"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 10 | 9 | An | Primer Declarante - NIF (01) | OBLIGATORIO
7 | 19 | 15 | A | Primer Declarante - Primer apellido (02) | OBLIGATORIO
8 | 34 | 15 | A | Primer Declarante - Segundo apellido (03)
9 | 49 | 15 | A | Primer Declarante - Nombre (04) | OBLIGATORIO
10 | 64 | 1 | A | Primer Declarante - Sexo "H" Hombre, "M" Mujer (05) | OBLIGATORIO
11 | 65 | 1 | Num | Primer Declarante -Estado Civil. "1" Soltero/a, "2" Casado/a, "3" Viudo/a, "4" Divorciado/a o Separado/a | OBLIGATORIO
12 | 66 | 8 | Num | Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año < 2016 (10) | OBLIGATORIO
13 | 74 | 1 | Num | Primer Declarante - Grado de discapacidad   "0", "1", "2" o "3" (11)
14 | 75 | 1 | Num | Primer Declarante - Cambio de domicilio "1" o cero (13)
15 | 76 | 5 | A | Primer Declarante - Domicilio habitual - Tipo de Vía (15)
16 | 81 | 5 | Num | Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Vía INE
17 | 86 | 50 | An | Primer Declarante - Domicilio habitual - Nombre de la Vía Pública (16)
18 | 136 | 3 | An | Primer Declarante - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
19 | 139 | 5 | Num | Primer Declarante - Domicilio habitual - Número de Casa (18)
20 | 144 | 3 | An | Primer Declarante - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
21 | 147 | 3 | An | Primer Declarante - Domicilio habitual - Bloque (20)
22 | 150 | 3 | An | Primer Declarante - Domicilio habitual - Portal (21)
23 | 153 | 3 | An | Primer Declarante - Domicilio habitual - Escalera (22)
24 | 156 | 3 | An | Primer Declarante - Domicilio habitual - Planta (23)
25 | 159 | 3 | An | Primer Declarante - Domicilio habitual - Puerta (24)
26 | 162 | 40 | An | Primer Declarante - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
27 | 202 | 30 | An | Primer Declarante - Domicilio habitual - Localidad / Población (26)
28 | 232 | 5 | Num | Primer Declarante - Domicilio habitual - Código postal (27)
29 | 237 | 5 | Num | Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
30 | 242 | 30 | An | Primer Declarante - Domicilio habitual - Nombre del Municipio (28)
31 | 272 | 2 | Num | Primer Declarante - Domicilio habitual - Código provincia. De "01" a "52".
32 | 274 | 20 | An | Primer Declarante - Domicilio habitual - Provincia (29)
33 | 294 | 9 | Num | Primer Declarante - Domicilio habitual - Teléfono fijo (30)
34 | 303 | 9 | Num | Primer Declarante - Domicilio habitual - Teléfono móvil (31)
35 | 312 | 9 | Num | Primer Declarante - Domicilio habitual - Núm. De Fax (32)
36 | 321 | 50 | An | Primer Declarante - Domicilio extranjero - Domicilio/Address (35)
37 | 371 | 40 | An | Primer Declarante - Domicilio extranjero - Datos complementarios del domicilio (36)
38 | 411 | 30 | An | Primer Declarante - Domicilio extranjero - Población / Ciudad (37)
39 | 441 | 100 | An | Primer Declarante - Domicilio extranjero - e-mail (38)
40 | 541 | 10 | An | Primer Declarante - Domicilio extranjero - Código Postal (39)
41 | 551 | 30 | An | Primer Declarante - Domicilio extranjero - Provincia / Región / Estado (40)
42 | 581 | 30 | An | Primer Declarante - Domicilio extranjero - País. (41)
43 | 611 | 2 | An | Primer Declarante - Domicilio extranjero - Código País.  Código país ISO-3166 (alfabético 2 letras). (42)
44 | 613 | 15 | An | Primer Declarante - Domicilio extranjero - Teléfono fijo (43)
45 | 628 | 15 | An | Primer Declarante - Domicilio extranjero - Teléfono móvil (44)
46 | 643 | 15 | An | Primer Declarante - Domicilio extranjero - Núm. Fax (45)
47 | 658 | 1 | Num | Datos adicionales vivienda - Vivienda 1.Titularidad "1", "2", "3" o "4" (50) | OBLIGATORIO
48 | 659 | 5 | Num | Datos adicionales vivienda - Vivienda 1.Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
49 | 664 | 5 | Num | Datos adicionales vivienda - Vivienda 1.Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
50 | 669 | 1 | Num | Datos adicionales vivienda - Vivienda 1.Situación (clave) "1", "2", "3" o "4" (53)
51 | 670 | 20 | An | Datos adicionales vivienda - Vivienda 1.Referencia catastral (54)
52 | 690 | 1 | Num | Datos adicionales vivienda - Vivienda 2.Titularidad "0", "1", "2", "3" o "4" (50)
53 | 691 | 5 | Num | Datos adicionales vivienda - Vivienda 2. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
54 | 696 | 5 | Num | Datos adicionales vivienda - Vivienda 2. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
55 | 701 | 1 | Num | Datos adicionales vivienda - Vivienda 2.Situación (clave) "0", "1", "2", "3" o "4" (53)
56 | 702 | 20 | An | Datos adicionales vivienda - Vivienda 2. Referencia catastral (54)
57 | 722 | 1 | Num | Datos adicionales vivienda - Vivienda 3.Titularidad "0", "1", "2", "3" o "4" (50)
58 | 723 | 5 | Num | Datos adicionales vivienda - Vivienda 3. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
59 | 728 | 5 | Num | Datos adicionales vivienda - Vivienda 3. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
60 | 733 | 1 | Num | Datos adicionales vivienda - Vivienda 3. Situación (clave) "0", "1", "2", "3" o "4" (53)
61 | 734 | 20 | An | Datos adicionales vivienda - Vivienda 3. Referencia catastral (54)
62 | 754 | 1 | Num | Datos adicionales vivienda - Vivienda 4.Titularidad "0", "1", "2", "3" o "4" (50)
63 | 755 | 5 | Num | Datos adicionales vivienda - Vivienda 4. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
64 | 760 | 5 | Num | Datos adicionales vivienda - Vivienda 4. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
65 | 765 | 1 | Num | Datos adicionales vivienda - Vivienda 4. Situación (clave) "0", "1", "2", "3" o "4" (53)
66 | 766 | 20 | An | Datos adicionales vivienda - Vivienda 4. Referencia catastral (54)
67 | 786 | 1 | Num | Datos adicionales vivienda - Vivienda 5.Titularidad "0", "1", "2", "3" o "4" (50)
68 | 787 | 5 | Num | Datos adicionales vivienda - Vivienda 5. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
69 | 792 | 5 | Num | Datos adicionales vivienda - Vivienda 5. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
70 | 797 | 1 | Num | Datos adicionales vivienda - Vivienda 5. Situación (clave) "0", "1", "2", "3" o "4" (53)
71 | 798 | 20 | An | Datos adicionales vivienda - Vivienda 5. Referencia catastral (54)
72 | 818 | 1 | Num | Datos adicionales vivienda - Vivienda 6.Titularidad "0", "1", "2", "3" o "4" (50)
73 | 819 | 5 | Num | Datos adicionales vivienda - Vivienda 6. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
74 | 824 | 5 | Num | Datos adicionales vivienda - Vivienda 6. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
75 | 829 | 1 | Num | Datos adicionales vivienda - Vivienda 6. Situación (clave) "0", "1", "2", "3" o "4" (53)
76 | 830 | 20 | An | Datos adicionales vivienda - Vivienda 6. Referencia catastral (54)
77 | 850 | 1 | Num | Datos adicionales vivienda - Vivienda 7.Titularidad "0", "1", "2", "3" o "4" (50)
78 | 851 | 5 | Num | Datos adicionales vivienda - Vivienda 7. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
79 | 856 | 5 | Num | Datos adicionales vivienda - Vivienda 7. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
80 | 861 | 1 | Num | Datos adicionales vivienda - Vivienda 7. Situación (clave) "0", "1", "2", "3" o "4" (53)
81 | 862 | 20 | An | Datos adicionales vivienda - Vivienda 7. Referencia catastral (54)
82 | 882 | 1 | Num | Datos adicionales vivienda - Vivienda 8.Titularidad "0", "1", "2", "3" o "4" (50)
83 | 883 | 5 | Num | Datos adicionales vivienda - Vivienda 8. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
84 | 888 | 5 | Num | Datos adicionales vivienda - Vivienda 8. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
85 | 893 | 1 | Num | Datos adicionales vivienda - Vivienda 8. Situación (clave) "0", "1", "2", "3" o "4" (53)
86 | 894 | 20 | An | Datos adicionales vivienda - Vivienda 8. Referencia catastral (54)
87 | 914 | 9 | An | Datos adicionales vivienda - Nif Arrendador (55)
88 | 923 | 20 | An | Datos adicionales vivienda - Si no tiene NIF. Nº identificación en el país de residencia (59)
89 | 943 | 9 | An | Cónyuge - NIF (61)
90 | 952 | 15 | A | Cónyuge - Primer apellido (62)
91 | 967 | 15 | A | Cónyuge - Segundo apellido (63)
92 | 982 | 15 | A | Cónyuge - Nombre (64)
93 | 997 | 1 | A | Cónyuge - Sexo "H" Hombre, "M" Mujer (65)
94 | 998 | 8 | Num | Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero. (66)
95 | 1006 | 1 | Num | Cónyuge - Grado de discapacidad   "0", "1", "2" o "3" (67)
96 | 1007 | 1 | Num | Cónyuge - No residente que no es contribuyente del I.R.P.F. - "1" o cero (68)
97 | 1008 | 1 | Num | Cónyuge - Cambio de domicilio "1" o cero (70)
98 | 1009 | 5 | A | Cónyuge - Domicilio habitual - Tipo de Vía (15)
99 | 1014 | 5 | Num | Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Vía INE
100 | 1019 | 50 | An | Cónyuge - Domicilio habitual - Nombre de la Vía Pública (16)
101 | 1069 | 3 | An | Cónyuge - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
102 | 1072 | 5 | Num | Cónyuge - Domicilio habitual - Número de Casa (18)
103 | 1077 | 3 | An | Cónyuge - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
104 | 1080 | 3 | An | Cónyuge - Domicilio habitual - Bloque (20)
105 | 1083 | 3 | An | Cónyuge - Domicilio habitual - Portal (21)
106 | 1086 | 3 | An | Cónyuge - Domicilio habitual - Escalera (22)
107 | 1089 | 3 | An | Cónyuge - Domicilio habitual - Planta (23)
108 | 1092 | 3 | An | Cónyuge - Domicilio habitual - Puerta (24)
109 | 1095 | 40 | An | Cónyuge - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
110 | 1135 | 30 | An | Cónyuge - Domicilio habitual - Localidad / Población (26)
111 | 1165 | 5 | Num | Cónyuge - Domicilio habitual - Código postal (27)
112 | 1170 | 5 | Num | Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
113 | 1175 | 30 | An | Cónyuge - Domicilio habitual - Nombre del Municipio (28)
114 | 1205 | 2 | Num | Cónyuge - Domicilio habitual - Código provincia. De "01" a "52".
115 | 1207 | 20 | An | Cónyuge - Domicilio habitual - Provincia (29)
116 | 1227 | 9 | Num | Cónyuge - Domicilio habitual - Teléfono fijo (30)
117 | 1236 | 9 | Num | Cónyuge - Domicilio habitual - Teléfono móvil (31)
118 | 1245 | 9 | Num | Cónyuge - Domicilio habitual - Núm. De Fax (32)
119 | 1254 | 50 | An | Cónyuge - Domicilio extranjero - Domicilio/Address (35)
120 | 1304 | 40 | An | Cónyuge - Domicilio extranjero - Datos complementarios del domicilio (36)
121 | 1344 | 30 | An | Cónyuge - Domicilio extranjero - Población / Ciudad (37)
122 | 1374 | 100 | An | Cónyuge - Domicilio extranjero - e-mail (38)
123 | 1474 | 10 | An | Cónyuge - Domicilio extranjero - Código Postal (39)
124 | 1484 | 30 | An | Cónyuge - Domicilio extranjero - Provincia / Región / Estado (40)
125 | 1514 | 30 | An | Cónyuge - Domicilio extranjero - País (41)
126 | 1544 | 2 | An | Cónyuge - Domicilio extranjero - Código País (42)
127 | 1546 | 15 | An | Cónyuge - Domicilio extranjero - Teléfono fijo (43)
128 | 1561 | 15 | An | Cónyuge - Domicilio extranjero - Teléfono móvil (44)
129 | 1576 | 15 | An | Cónyuge - Domicilio extranjero - Núm. Fax (45)
130 | 1591 | 12 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
131 | 1603 | 9 | An | Representante -  N.I.F. (75)
132 | 1612 | 32 | An | Representante -  Apellidos y nombre o razón social (76)
133 | 1644 | 20 | An | Fecha declaración - Lugar
134 | 1664 | 2 | Num | Fecha declaración - Fecha -Día
135 | 1666 | 10 | A | Fecha declaración - Fecha - Mes
136 | 1676 | 4 | Num | Fecha declaración - Fecha - Año
137 | 1680 | 34 | An | Número de cuenta IBAN
138 | 1714 | 13 | Num | Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
139 | 1727 | 21 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
140 | 1748 | 13 | N | Resultado de la declaración
141 | 1761 | 1 | Num | Fraccionamiento del pago. "1" o cero
142 | 1762 | 1 | Num | Domiciliación 2º plazo."1" o cero
143 | 1763 | 1 | Num | Renuncia a la devolución. "1" o cero
144 | 1764 | 1 | Num | Compensación entre cónyuges.  "1" o cero
145 | 1765 | 20 | An | Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
146 | 1785 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
147 | 1798 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10001>
148 | 1807 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total |  | 1808

# 100-02

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "02"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 10 | 9 | An | Hijos y descendientes - 1º -  N.I.F. (80)
7 | 19 | 40 | A | Hijos y descendientes - 1º -  Apellidos y nombre  (81)
8 | 59 | 8 | Num | Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año < 2016 o cero (82)
9 | 67 | 8 | Num | Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
10 | 75 | 1 | Num | Hijos y descendientes - 1º - Grado discapacidad   "0", "1", "2" o "3" (84)
11 | 76 | 1 | An | Hijos y descendientes - 1º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (85)
12 | 77 | 1 | An | Hijos y descendientes - 1º - Otras situaciones  clave:"1","2","3","4" o blanco  (86)
13 | 78 | 9 | An | Hijos y descendientes - 2º - N.I.F. (80)
14 | 87 | 40 | A | Hijos y descendientes - 2º - Apellidos y nombre  (81)
15 | 127 | 8 | Num | Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año < 2016 o cero (82)
16 | 135 | 8 | Num | Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año < 2016 o cero (83)
17 | 143 | 1 | Num | Hijos y descendientes - 2º - Grado discapacidad   "0", "1", "2" o "3"  (84)
18 | 144 | 1 | An | Hijos y descendientes - 2º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (85)
19 | 145 | 1 | An | Hijos y descendientes - 2º - Otras situaciones  "1","2","3","4" o blanco  (86)
20 | 146 | 9 | An | Hijos y descendientes - 3º - N.I.F. (80)
21 | 155 | 40 | A | Hijos y descendientes - 3º - Apellidos y nombre  (81)
22 | 195 | 8 | Num | Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
23 | 203 | 8 | Num | Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
24 | 211 | 1 | Num | Hijos y descendientes - 3º - Grado discapacidad   "0", "1", "2" o "3"  (84)
25 | 212 | 1 | An | Hijos y descendientes - 3º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (85)
26 | 213 | 1 | An | Hijos y descendientes - 3º - Otras situaciones  "1","2","3","4" o blanco  (86)
27 | 214 | 9 | An | Hijos y descendientes - 4º - N.I.F.  (80)
28 | 223 | 40 | A | Hijos y descendientes - 4º - Apellidos y nombre  (81)
29 | 263 | 8 | Num | Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
30 | 271 | 8 | Num | Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
31 | 279 | 1 | Num | Hijos y descendientes - 4º - Grado discapacidad   "0", "1", "2" o "3"  (84)
32 | 280 | 1 | An | Hijos y descendientes - 4º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (85)
33 | 281 | 1 | An | Hijos y descendientes - 4º - Otras situaciones  "1","2","3","4" o blanco  (86)
34 | 282 | 9 | An | Hijos y descendientes - 5º - N.I.F. (80)
35 | 291 | 40 | A | Hijos y descendientes - 5º - Apellidos y nombre  (81)
36 | 331 | 8 | Num | Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
37 | 339 | 8 | Num | Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
38 | 347 | 1 | Num | Hijos y descendientes - 5º - Grado discapacidad   "0", "1", "2" o "3"  (84)
39 | 348 | 1 | An | Hijos y descendientes - 5º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (85)
40 | 349 | 1 | An | Hijos y descendientes - 5º - Otras situaciones  "1","2","3","4" o blanco  (86)
41 | 350 | 9 | An | Hijos y descendientes - 6º - N.I.F. (80)
42 | 359 | 40 | A | Hijos y descendientes - 6º - Apellidos y nombre  (81)
43 | 399 | 8 | Num | Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
44 | 407 | 8 | Num | Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
45 | 415 | 1 | Num | Hijos y descendientes - 6º - Grado discapacidad  "0", "1", "2" o "3" (84)
46 | 416 | 1 | An | Hijos y descendientes - 6º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (85)
47 | 417 | 1 | An | Hijos y descendientes - 6º - Otras situaciones  "1","2","3","4" o blanco  (86)
48 | 418 | 9 | An | Hijos y descendientes - 7º - N.I.F.  (80)
49 | 427 | 40 | A | Hijos y descendientes - 7º - Apellidos y nombre  (81)
50 | 467 | 8 | Num | Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
51 | 475 | 8 | Num | Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
52 | 483 | 1 | Num | Hijos y descendientes - 7º - Grado discapacidad  "0", "1", "2" o "3" (84)
53 | 484 | 1 | An | Hijos y descendientes - 7º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (85)
54 | 485 | 1 | An | Hijos y descendientes - 7º - Otras situaciones  "1","2","3","4" o blanco  (86)
55 | 486 | 9 | An | Hijos y descendientes - 8º - N.I.F. (80)
56 | 495 | 40 | A | Hijos y descendientes - 8º - Apellidos y nombre  (81)
57 | 535 | 8 | Num | Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
58 | 543 | 8 | Num | Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
59 | 551 | 1 | Num | Hijos y descendientes - 8º - Grado discapacidad "0", "1", "2" o "3"  (84)
60 | 552 | 1 | An | Hijos y descendientes - 8º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (85)
61 | 553 | 1 | An | Hijos y descendientes - 8º - Otras situaciones  "1","2","3","4" o blanco  (86)
62 | 554 | 9 | An | Hijos y descendientes - 9º - N.I.F. (80)
63 | 563 | 40 | A | Hijos y descendientes - 9º - Apellidos y nombre  (81)
64 | 603 | 8 | Num | Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
65 | 611 | 8 | Num | Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
66 | 619 | 1 | Num | Hijos y descendientes - 9º - Grado discapacidad  "0", "1", "2" o "3"  (84)
67 | 620 | 1 | An | Hijos y descendientes - 9º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (85)
68 | 621 | 1 | An | Hijos y descendientes - 9º - Otras situaciones  "1","2","3","4" o blanco  (86)
69 | 622 | 9 | An | Hijos y descendientes - 10º - N.I.F.  (80)
70 | 631 | 40 | A | Hijos y descendientes - 10º - Apellidos y nombre  (81)
71 | 671 | 8 | Num | Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
72 | 679 | 8 | Num | Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
73 | 687 | 1 | Num | Hijos y descendientes - 10º - Grado discapacidad "0", "1", "2" o "3"  (84)
74 | 688 | 1 | An | Hijos y descendientes - 10º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (85)
75 | 689 | 1 | An | Hijos y descendientes - 10º - Otras situaciones  "1","2","3","4" o blanco  (86)
76 | 690 | 9 | An | Hijos y descendientes - 11º - N.I.F. (80)
77 | 699 | 40 | A | Hijos y descendientes - 11º - Apellidos y nombre  (81)
78 | 739 | 8 | Num | Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
79 | 747 | 8 | Num | Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
80 | 755 | 1 | Num | Hijos y descendientes - 11º - Grado discapacidad "0", "1", "2" o "3"  (84)
81 | 756 | 1 | An | Hijos y descendientes - 11º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (85)
82 | 757 | 1 | An | Hijos y descendientes - 11º - Otras situaciones  "1","2","3","4" o blanco  (86)
83 | 758 | 9 | An | Hijos y descendientes - 12º - N.I.F. (80)
84 | 767 | 40 | A | Hijos y descendientes - 12º - Apellidos y nombre  (81)
85 | 807 | 8 | Num | Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (82)
86 | 815 | 8 | Num | Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2016 o cero (83)
87 | 823 | 1 | Num | Hijos y descendientes - 12º - Grado discapacidad  "0", "1", "2" o "3"  (84)
88 | 824 | 1 | An | Hijos y descendientes - 12º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (85)
89 | 825 | 1 | An | Hijos y descendientes - 12º - Otras situaciones  "1","2","3","4" o blanco  (86)
90 | 826 | 2 | Num | Hijos y descendientes - Fallecido 2015 - Nº Orden (87)
91 | 828 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
92 | 836 | 2 | Num | Hijos y descendientes - Fallecido 2015 - Nº Orden (87)
93 | 838 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
94 | 846 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
95 | 855 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
96 | 864 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
97 | 873 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
98 | 882 | 9 | An | Hijos y descendientes - Otro progenitor - Nif (56)
99 | 891 | 40 | A | Hijos y descendientes - Otro progenitor - Apellidos y nombre (57)
100 | 931 | 1 | Num | Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (58)
101 | 932 | 24 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
102 | 956 | 9 | An | Ascendientes mayores 65 años o discapacitados - 1º - N.I.F.  (90)
103 | 965 | 40 | A | Ascendientes mayores 65 años o discapacitados - 1º - Apellidos y nombre (91)
104 | 1005 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (92)
105 | 1013 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Grado discapacidad  "0", "1", "2" o "3" (93)
106 | 1014 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Vinculación  clave:"1", "2" o blanco (94)
107 | 1015 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Convivencia   "2" a "9" o blanco (95)
108 | 1016 | 9 | An | Ascendientes mayores 65 años o discapacitados - 2º - N.I.F.  (90)
109 | 1025 | 40 | A | Ascendientes mayores 65 años o discapacitados - 2º - Apellidos y nombre (91)
110 | 1065 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (92)
111 | 1073 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Grado discapacidad  "0", "1", "2" o "3"  (93)
112 | 1074 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Vinculación clave:"1", "2" o blanco  (94)
113 | 1075 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Convivencia  "2" a "9" o blanco  (95)
114 | 1076 | 9 | An | Ascendientes mayores 65 años o discapacitados - 3º - N.I.F.  (90)
115 | 1085 | 40 | A | Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
116 | 1125 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año < 2016 o cero (92)
117 | 1133 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Grado discapacidad  "0", "1", "2" o "3"  (93)
118 | 1134 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Vinculación  clave:"1", "2" o blanco  (94)
119 | 1135 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Convivencia   "2" a "9" o blanco  (95)
120 | 1136 | 9 | An | Ascendientes mayores 65 años o discapacitados - 4º - N.I.F.  (90)
121 | 1145 | 40 | A | Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
122 | 1185 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2016 o cero (92)
123 | 1193 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Grado discapacidad  "0", "1", "2" o "3" (93)
124 | 1194 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Vinculación  clave:"1", "2" o blanco  (94)
125 | 1195 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Convivencia  "2" a "9" o blanco  (95)
126 | 1196 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2015 - Nif (96)
127 | 1205 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
128 | 1213 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2015 - Nif (96)
129 | 1222 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
130 | 1230 | 8 | Num | Devengo - Fecha de  finalización del período impositivo (fallecimiento 2015)  (DDMMAAAA) o cero (100)
131 | 1238 | 1 | Num | Opción de tributación. "1" Individual, "2" Conjunta.  Campo OBLIGATORIO (101) (102) | OBLIGATORIO
132 | 1239 | 2 | Num | Comunidad/Ciudad autónoma de residencia en 2015 - Clave (103) Incluido en el fichero COMAUTO.TXT | OBLIGATORIO
133 | 1241 | 1 | A | Asignación tributaria a la Iglesia Católica. "X" o  blanco. (105)
134 | 1242 | 1 | A | Asignación de cantidades a actividades de interés general consideradas de interés social. "X" o  blanco. (106)
135 | 1243 | 1 | Num | Declaración complementaria - Si es complementaria por atrasos de rendimientos del trabajo.  "1" o cero (121)
136 | 1244 | 1 | Num | Declaración complementaria - Si es complementaria por haberse producido alguna de las circunstancias previstas. "1" o cero (122)
137 | 1245 | 1 | Num | Declaración complementaria - Si es complementaria a devolver. "1" o cero (123)
138 | 1246 | 1 | Num | Declaración complementaria - Si es complementaria por traslado de residencia a otro Estado miembro, "1" o cero (124)
139 | 1247 | 1 | Num | Declaración complementaria - Si es complementaria al estar motivada por haberse producido en circunstancias prevista en art. 95 bis (125)
140 | 1248 | 1 | Num | Declaración complementaria - Si es complementaria en supuestos distintos "1" o cero (120)
141 | 1249 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10002>
142 | 1258 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total |  | 1259

# 100-03

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. |  | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "03"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 13 | N | (A) Rdto. Trabajo - Retribuciones dinerarias. Importe íntegro (001)
7 | 23 | 13 | N | Rdto. Trabajo - Retribuciones en especie - Valoracion (002)
8 | 36 | 13 | N | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta (003)
9 | 49 | 13 | N | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta repercutidos (004)
10 | 62 | 13 | N | Rdto. Trabajo - Retribuciones en especie - Importe íntegro (005)
11 | 75 | 13 | N | Rdto. Trabajo - Contribuciones Planes Pensiones y Mutualidades Previsión Social  (006)
12 | 88 | 13 | N | Rdto. Trabajo - Contribuciones empresariales a seguros colectivos dependencia. Imputado al contribuyente (007)
13 | 101 | 13 | N | Rdto. Trabajo - Aportaciones al patrimonio protegido de discapacitados - Importe (008)
14 | 114 | 13 | N | Rdto. Trabajo - Reducciones (009)
15 | 127 | 13 | N | Rdto. Trabajo - Total ingresos íntegros computables (010)
16 | 140 | 13 | N | Rdto. Trabajo - Cotizaciones Seguridad Social/Mutual. grales. funcionarios/cotiz. colegios huerfanos (011)
17 | 153 | 13 | N | Rdto. Trabajo - Cuotas satisfechas a sindicatos (012)
18 | 166 | 13 | N | Rdto. Trabajo - Cuotas a colegios profesionales (013)
19 | 179 | 13 | N | Rdto. Trabajo - Gastos defensa jurídica derivados litigios con empleador (014)
20 | 192 | 13 | N | Rdto. Trabajo - Rdto. Neto previo (015)
21 | 205 | 13 | N | Rdto. Trabajo - Otros gastos deducibles (016)
22 | 218 | 13 | N | Rdto. Trabajo - Incremento contribuyentes desempleados con traslado de residencia  (017)
23 | 231 | 13 | N | Rdto. Trabajo - Incremento para trabajadores activos discapacitados (018)
24 | 244 | 13 | N | Rdto. Trabajo - Rendimiento neto  (019)
25 | 257 | 13 | N | Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Cuantía aplicable con carácter general (020)
26 | 270 | 13 | N | Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Reducción por movilidad geográfica contribuyentes con derecho a  la misma en 2014  (021)
27 | 283 | 13 | N | Rdto. Trabajo - Rendimiento neto reducido (022)
28 | 296 | 13 | N | (B) Rdto.cap.mob.- Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (023)
29 | 309 | 13 | N | Rdto.cap.mob.- Base imponible ahorro  - Intereses de activos financieros con derecho a bonificación (024)
30 | 322 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (025)
31 | 335 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (026)
32 | 348 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros (027)
33 | 361 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (028)
34 | 374 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Importe total capitales diferidos correspondientes a seguros de vida (029)
35 | 387 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Rdtos. procedentes de rentas que tengan por causa la imposición de capitales (030)
36 | 400 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Rdtos. derivados de valores de deuda subordinada o participaciones preferentes. (031)
37 | 413 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Rdtos. procedentes de seguros de vida, depósitos financieros que instrumenten Planes Ahorro (032)
38 | 426 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Total ingresos íntegros (033)
39 | 439 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Gastos fiscalmente deducibles (034)
40 | 452 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto (035)
41 | 465 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (036)
42 | 478 | 13 | N | Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto reducido (037)
43 | 491 | 13 | N | (B) Rdto.cap.mob.- Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (038)
44 | 504 | 13 | N | Rdto.cap.mob.- Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (039)
45 | 517 | 13 | N | Rdto.cap.mob.- Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (040)
46 | 530 | 13 | N | Rdto.cap.mob.- Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (041)
47 | 543 | 13 | N | Rdto.cap.mob.- Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (042)
48 | 556 | 13 | N | Rdto.cap.mob.- Base imponible general - Total ingresos íntegros (043)
49 | 569 | 13 | N | Rdto.cap.mob.- Base imponible general - Gastos fiscalmente deducibles (044)
50 | 582 | 13 | N | Rdto.cap.mob.- Base imponible general - Rendimiento neto (045)
51 | 595 | 13 | N | Rdto.cap.mob.- Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (046)
52 | 608 | 13 | N | Rdto.cap.mob.- Base imponible general - Rendimiento neto reducido (047)
53 | 621 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10003>
54 | 630 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 631

# 100-04

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com. | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "04"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 2 | Num |  | Nº de hojas adicionales que se adjuntan
7 | 12 | 1 | Tit | C | (C) Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Contribuyente "0" a "9" (050)
8 | 13 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (051) | *
9 | 18 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje usufructo (3 enteros y 2 decimales) (052) | *
10 | 23 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Naturaleza (053)
11 | 24 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Uso o destino. Clave   (054)
12 | 25 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Situación "0", "1", "2", "3" o "4" (055)
13 | 26 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Referencia catastral (056)
14 | 46 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (057) | *
15 | 51 | 3 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Número de días (058)
16 | 54 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Renta imputada (059)
17 | 67 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Ingresos íntegros computables (060)
18 | 80 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (061)
19 | 93 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Importe (062)
20 | 106 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (063)
21 | 119 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (064)
22 | 132 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto (065)
23 | 145 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (066)
24 | 158 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción rendimientos más de 2 años (067)
25 | 171 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento mínimo computable parentesco (068)
26 | 184 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto reducido (069)
27 | 197 | 1 | Tit | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Contribuyente "0" a "9" (050)
28 | 198 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (051) | *
29 | 203 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje usufructo (3 enteros y 2 decimales)  (052) | *
30 | 208 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Naturaleza (053)
31 | 209 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Uso o destino. Clave   (054)
32 | 210 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Situación "0", "1", "2", "3" o "4" (055)
33 | 211 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Referencia catastral (056)
34 | 231 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (057) | *
35 | 236 | 3 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Número de días (058)
36 | 239 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Renta imputada (059)
37 | 252 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Ingresos íntegros computables (060)
38 | 265 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (061)
39 | 278 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe (062)
40 | 291 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (063)
41 | 304 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (064)
42 | 317 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto (065)
43 | 330 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (066)
44 | 343 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción rendimientos más de 2 años (067)
45 | 356 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento mínimo computable parentesco (068)
46 | 369 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto reducido (069)
47 | 382 | 1 | Tit | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Contribuyente "0" a "9" (050)
48 | 383 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (051) | *
49 | 388 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Porcentaje usufructo (3 enteros y 2 decimales) (052) | *
50 | 393 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Naturaleza (053)
51 | 394 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Uso o destino. Clave   (054)
52 | 395 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Situación "0", "1", "2", "3" o "4" (055)
53 | 396 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Referencia catastral (056)
54 | 416 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (057) | *
55 | 421 | 3 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Número de días (058)
56 | 424 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Renta imputada (059)
57 | 437 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Ingresos íntegros computables (060)
58 | 450 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (061)
59 | 463 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Importe (062)
60 | 476 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (063)
61 | 489 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (064)
62 | 502 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento neto (065)
63 | 515 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (066)
64 | 528 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Reducción rendimientos más de 2 años (067)
65 | 541 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento mínimo computable parentesco (068)
66 | 554 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento neto reducido (069)
67 | 567 | 13 | N |  | Bienes inmuebles no afectos. Rentas totales . Suma de rentas inmobiliarias imputadas (070)
68 | 580 | 13 | N |  | Bienes inmuebles no afectos. Rentas totales . Suma rendimientos netos reducidos del capital inmobiliario (071)
69 | 593 | 3 | Num |  | Número de inmuebles en declaración conjunta (Reservado para la Administración)
70 | 596 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Contribuyente "0" a "9" (072)
71 | 597 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Nº Identificación fiscal entidad (073)
72 | 617 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Porcentaje titularidad (3 enteros y 2 decimales) (074) | *
73 | 622 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Naturaleza (075)
74 | 623 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Situación "0", "1", "2", "3" o "4" (076)
75 | 624 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Referencia catastral (077)
76 | 644 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. No Residente (078)
77 | 645 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Contribuyente "0" a "9" (072)
78 | 646 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Nº Identificación fiscal entidad (073)
79 | 666 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Porcentaje titularidad (3 enteros y 2 decimales) (074) | *
80 | 671 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Naturaleza (075)
81 | 672 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Situación "0", "1", "2", "3" o "4" (076)
82 | 673 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Referencia catastral (077)
83 | 693 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. No Residente (078)
84 | 694 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Contribuyente "0" a "9" (072)
85 | 695 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Nº Identificación fiscal entidad (073)
86 | 715 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Porcentaje titularidad (3 enteros y 2 decimales) (074) | *
87 | 720 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Naturaleza (075)
88 | 721 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Situación "0", "1", "2", "3" o "4" (076)
89 | 722 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Referencia catastral (077)
90 | 742 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. No Residente (078)
91 | 743 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 1. Contribuyente "0" a "9" (079)
92 | 744 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (080) | *
93 | 749 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje usufructo (3 enteros y 2 decimales)  (081) | *
94 | 754 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Naturaleza (clave) (082)
95 | 755 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1.  Situación "0", "1", "2", "3" o "4" (083)
96 | 756 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 1.  Referencia catastral (084)
97 | 776 | 1 | Tit | C | Bienes inmuebles urbanos afectos. Inmueble 2. Contribuyente "0" a "9" (079)
98 | 777 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (080) | *
99 | 782 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje usufructo (3 enteros y 2 decimales)  (081) | *
100 | 787 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Naturaleza (clave) (082)
101 | 788 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2.  Situación "0", "1", "2", "3" o "4" (083)
102 | 789 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 2.  Referencia catastral (084)
103 | 809 | 1 | Tit | C | Bienes inmuebles urbanos afectos. Inmueble 3. Contribuyente "0" a "9" (079)
104 | 810 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (080) | *
105 | 815 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje usufructo (3 enteros y 2 decimales)  (081) | *
106 | 820 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Naturaleza (clave) (082)
107 | 821 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3.  Situación "0", "1", "2", "3" o "4" (083)
108 | 822 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 3.  Referencia catastral (084)
109 | 842 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10004>
110 | 851 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 852

# 100-05

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com. | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "05"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 1 | Num |  | Nº de hojas adicionales si se declaran más de 3 Actividades a las que resulte aplicable un mismo régimen
7 | 11 | 1 | Tit | C | (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Contribuyente  "0" a "9" (086)
8 | 12 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Tipo actividad. Clave (Blanco o de "1" a "5") (087)
9 | 13 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Modalidad Normal (089)  o Simplificada (090)  "0", "1" o "2"
10 | 14 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Epígrafe IAE (088) (**)
11 | 19 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Criterio cobros/pagos. "1" o cero. (091)
12 | 20 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Explotación (092)
13 | 33 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Otros ingresos (093)
14 | 46 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Autoconsumo bienes/servicios (094)
15 | 59 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Transmisión elementos patrimoniales: exceso amortización deducida (095)
16 | 72 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Total ingresos computables (096)
17 | 85 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Consumos de explotación (097)
18 | 98 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Sueldos y salarios (098)
19 | 111 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Seguridad Social (099)
20 | 124 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros gastos de personal (100)
21 | 137 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Arrendamientos y cánones (101)
22 | 150 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Reparación y conservación (102)
23 | 163 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Servicios profesionales independientes (103)
24 | 176 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros servicios exteriores (104)
25 | 189 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Tributos fiscalmente deducibles (105)
26 | 202 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Gastos financieros (106)
27 | 215 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Amortizaciones (107)
28 | 228 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Pérdidas por deterioro (108)
29 | 241 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (convenios) (109)
30 | 254 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (gastos) (110)
31 | 267 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros conceptos fiscalmente deducibles (111)
32 | 280 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Suma  (112)
33 | 293 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Normal - Provisiones (113)
34 | 306 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Normal - Total gastos deducibles (114)
35 | 319 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Diferencia (115)
36 | 332 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (116)
37 | 345 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Total gastos deducibles (117)
38 | 358 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Rdto. neto (118)
39 | 371 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Reducciones (119)
40 | 384 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -1- Rdto. neto reducido (120)
41 | 397 | 1 | Tit | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Contribuyente  "0" a "9" (086)
42 | 398 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Tipo actividad.Clave (Blanco o de "1" a "5") (087)
43 | 399 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Modalidad Normal (089) o Simplificada (090) "0", "1" o "2"
44 | 400 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Epígrafe IAE (088) (**)
45 | 405 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Criterio cobros/pagos. "1" o cero. (091)
46 | 406 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Explotación (092)
47 | 419 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Otros ingresos (093)
48 | 432 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Autoconsumo bienes/servicios (094)
49 | 445 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Transmisión elementos patrimoniales: exceso amortización deducida (095)
50 | 458 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Total ingresos computables (096)
51 | 471 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Consumos de explotación (097)
52 | 484 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Sueldos y salarios (098)
53 | 497 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Seguridad Social (099)
54 | 510 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos de personal (100)
55 | 523 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Arrendamientos y cánones (101)
56 | 536 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Reparación y conservación (102)
57 | 549 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Servicios profesionales independientes (103)
58 | 562 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros servicios exteriores (104)
59 | 575 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Tributos fiscalmente deducibles (105)
60 | 588 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Gastos financieros (106)
61 | 601 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Amortizaciones (107)
62 | 614 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Pérdidas por deterioro (108)
63 | 627 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (convenios) (109)
64 | 640 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (gastos) (110)
65 | 653 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos fiscalmente deducibles (111)
66 | 666 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Suma de gastos (112)
67 | 679 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Normal - Provisiones (113)
68 | 692 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Normal - Total gastos deducibles (114)
69 | 705 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Diferencia (115)
70 | 718 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (116)
71 | 731 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Total gastos deducibles (117)
72 | 744 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto. neto (118)
73 | 757 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Reducciones (119)
74 | 770 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto.neto reducido  (120)
75 | 783 | 1 | Tit | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Contribuyente  "0" a "9" (086)
76 | 784 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Tipo actividad.Clave (Blanco o de "1" a "5") (087)
77 | 785 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Modalidad Normal (089) o Simplificada (090) "0", "1" o "2"
78 | 786 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Epígrafe IAE (088) (**)
79 | 791 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Criterio cobros/pagos. "1" o cero. (091)
80 | 792 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Explotación (092)
81 | 805 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Otros ingresos (093)
82 | 818 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Autoconsumo bienes/servicios (094)
83 | 831 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Transmisión elementos patrimoniales: exceso amortización deducida (095)
84 | 844 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Total ingresos computables (096)
85 | 857 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Consumos de explotación (097)
86 | 870 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Sueldos y salarios (098)
87 | 883 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Seguridad Social (099)
88 | 896 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos de personal (100)
89 | 909 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Arrendamientos y cánones (101)
90 | 922 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Reparación y conservación (102)
91 | 935 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Servicios profesionales independientes (103)
92 | 948 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros servicios exteriores (104)
93 | 961 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Tributos fiscalmente deducibles (105)
94 | 974 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Gastos financieros (106)
95 | 987 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Amortizaciones (107)
96 | 1000 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Pérdidas por deterioro (108)
97 | 1013 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (convenios) (109)
98 | 1026 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (gastos) (110)
99 | 1039 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos fiscalmente deducibles (111)
100 | 1052 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Suma de gastos (112)
101 | 1065 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Normal - Provisiones (113)
102 | 1078 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Normal - Total gastos deducibles (114)
103 | 1091 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Diferencia (115)
104 | 1104 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (116)
105 | 1117 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Total gastos deducibles (117)
106 | 1130 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto. neto (118)
107 | 1143 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Reducciones (119)
108 | 1156 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto.neto reducido  (120)
109 | 1169 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Suma de rendimientos netos reducidos (121)
110 | 1182 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción ejercicio determinadas actividades (artículo 32.2.1º) (122)
111 | 1195 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción ejercicio determinadas actividades (artículo 32.2.3º) (123)
112 | 1208 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción por inicio de una actividad económica (124)
113 | 1221 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Rendimiento neto reducido total  (125)
114 | 1234 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10005>
115 | 1243 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 1244
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignarán las tres cifras seguidas de dos blancos.

# 100-06

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "06"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 1 | Num |  | Nº de hojas adicionales si se declaran más de 2 actividades
7 | 11 | 5 | An | C | (E2)Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Clasificación IAE (127) (**)
8 | 16 | 1 | Tit | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Contribuyente titular actividad (126)  "0" a "9"
9 | 17 | 1 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (128)
10 | 18 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Definición
11 | 42 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales) | *
12 | 51 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales) | *
13 | 62 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Definición
14 | 86 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales) | *
15 | 95 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales) | *
16 | 106 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Definición
17 | 130 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales) | *
18 | 139 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales) | *
19 | 150 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Definición
20 | 174 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales) | *
21 | 183 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales) | *
22 | 194 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Definición
23 | 218 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales) | *
24 | 227 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales) | *
25 | 238 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Definición
26 | 262 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales) | *
27 | 271 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales) | *
28 | 282 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Definición
29 | 306 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales) | *
30 | 315 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales) | *
31 | 326 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma)  (129)
32 | 339 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo  (130)
33 | 352 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (131)
34 | 365 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (132)
35 | 378 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (133) | *
36 | 382 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (134) | *
37 | 386 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (135) | *
38 | 390 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (136) | *
39 | 394 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (137) | *
40 | 398 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto de módulos (138)
41 | 411 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción de carácter general (139)
42 | 424 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (140)
43 | 437 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Gastos extraordinarios circunstancias  excepcionales (141)
44 | 450 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Otras percepciones empresariales (142)
45 | 463 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª -Rendimiento neto actividad (143)
46 | 476 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción art. 32.1 Ley del Impuesto (144)
47 | 489 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rendimiento neto reducido (145)
48 | 502 | 5 | An | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Clasificación IAE (127) (**)
49 | 507 | 1 | Tit | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Contribuyente titular actividad (126)  "0" a "9"
50 | 508 | 1 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Criterio cobros/pagos: "1" ó "0" (128)
51 | 509 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Definición
52 | 533 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales) | *
53 | 542 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales) | *
54 | 553 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Definición
55 | 577 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales) | *
56 | 586 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales) | *
57 | 597 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Definición
58 | 621 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales) | *
59 | 630 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales) | *
60 | 641 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Definición
61 | 665 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales) | *
62 | 674 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales) | *
63 | 685 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Definición
64 | 709 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales) | *
65 | 718 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales) | *
66 | 729 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Definición
67 | 753 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales) | *
68 | 762 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales) | *
69 | 773 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Definición
70 | 797 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales) | *
71 | 806 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales) | *
72 | 817 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto previo (suma)  (129)
73 | 830 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos al empleo  (130)
74 | 843 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos a la inversion (131)
75 | 856 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto minorado (132)
76 | 869 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector especial (2 enteros y 2 decimales) (133) | *
77 | 873 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (134) | *
78 | 877 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de temporada (2 enteros y 2 decimales) (135) | *
79 | 881 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de exceso (2 enteros y 2 decimales) (136) | *
80 | 885 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (137) | *
81 | 889 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto de módulos (138)
82 | 902 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción de carácter general (139)
83 | 915 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (140)
84 | 928 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Gastos extraordinarios circunstancias  excepcionales (141)
85 | 941 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Otras percepciones empresariales (142)
86 | 954 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª -Rendimiento neto actividad  (143)
87 | 967 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción art. 32.1 Ley del Impuesto (144)
88 | 980 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rendimiento neto reducido (145)
89 | 993 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Suma rendimientos netos reducidos (148)
90 | 1006 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Reducción ejercicio determinadas actividades económicas (149)
91 | 1019 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas (150)
92 | 1032 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10006>
93 | 1041 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 1042
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos blancos.

# 100-07

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "07"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 1 | Num |  | Nº de hojas adicionales si se declaran más de 2 Actividades
7 | 11 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Clave actividad: de "0" a "9" (152)
8 | 12 | 1 | Tit | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Contribuyente titular de actividad: de "0" a "9"  (151)
9 | 13 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Criterio cobros/pagos:  "1" ó "0" (153)
10 | 14 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Ingresos íntegros
11 | 25 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Índice
12 | 31 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Rdto. base producto
13 | 42 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Ingresos íntegros
14 | 53 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Índice
15 | 59 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Rdto. base producto
16 | 70 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Ingresos íntegros
17 | 81 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Índice
18 | 87 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Rdto. base producto
19 | 98 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 4º - Ingresos íntegros
20 | 109 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 4º - Índice
21 | 115 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 4º - Rdto. base producto
22 | 126 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Ingresos íntegros
23 | 137 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Índice
24 | 143 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Rdto. base producto
25 | 154 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Ingresos íntegros
26 | 165 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Índice
27 | 171 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Rdto. base producto
28 | 182 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Ingresos íntegros
29 | 193 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Índice
30 | 199 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Rdto. base producto
31 | 210 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Ingresos íntegros
32 | 221 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Índice
33 | 227 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Rdto. base producto
34 | 238 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Ingresos íntegros
35 | 249 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Índice
36 | 255 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Rdto. base producto
37 | 266 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Ingresos íntegros
38 | 277 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Índice
39 | 283 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Rdto. base producto
40 | 294 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Ingresos íntegros
41 | 305 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Índice
42 | 311 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Rdto. base producto
43 | 322 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Ingresos íntegros
44 | 333 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Índice
45 | 339 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Rdto. base producto
46 | 350 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Ingresos íntegros
47 | 361 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Índice
48 | 367 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Rdto. base producto
49 | 378 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 14º - Ingresos íntegros
50 | 389 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 14º - Índice
51 | 395 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 14º - Rdto. base producto
52 | 406 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 15º - Ingresos íntegros
53 | 417 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 15º - Índice
54 | 423 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 15º - Rdto. base producto
55 | 434 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Total  ingresos íntegros (154)
56 | 445 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto previo (suma) (155)
57 | 456 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones (156)
58 | 467 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Amortización inmovilizado (157)
59 | 478 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto minorado  (158)
60 | 489 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Medios ajenos (2 enteros y 2 decimales) (159) | *
61 | 493 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Utiliz. personal asalariado (2 enteros y 2 decimales) (160) | *
62 | 497 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (161) | *
63 | 501 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (162) Ver NOTA | *
64 | 505 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 2 (162) Ver NOTA | *
65 | 509 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Actividades agricultura ecológica (2 enteros y dos decimales)  (163) | *
66 | 513 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Cultivo en tierras regadío utilice energía electrica ( 2 enteros y 2 decimales) (164) | *
67 | 517 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales)  (165) | *
68 | 521 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Determinadas actividades forestales  (2 enteros y 2 decimales)  (166) | *
69 | 525 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto de módulos (167)
70 | 538 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción carácter general (168)
71 | 551 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Diferencia (169)
72 | 564 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción agricultores jóvenes (170)
73 | 577 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Gastos extraordinarios por circunstancias excepcionales (171)
74 | 590 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto  (172)
75 | 603 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones rendimientos generados más 2 años o forma irregular (173)
76 | 616 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto reducido (174)
77 | 629 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Clave actividad: de "0" a "9" (152)
78 | 630 | 1 | Tit | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Contribuyente titular de actividad: de "0" a "9"  (151)
79 | 631 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Criterio cobros/pagos:  "1" ó "0" (153)
80 | 632 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Ingresos íntegros
81 | 643 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Índice
82 | 649 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Rdto. base producto
83 | 660 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Ingresos íntegros
84 | 671 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Índice
85 | 677 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Rdto. base producto
86 | 688 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Ingresos íntegros
87 | 699 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Índice
88 | 705 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Rdto. base producto
89 | 716 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Ingresos íntegros
90 | 727 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Índice
91 | 733 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Rdto. base producto
92 | 744 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Ingresos íntegros
93 | 755 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Índice
94 | 761 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Rdto. base producto
95 | 772 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Ingresos íntegros
96 | 783 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Índice
97 | 789 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Rdto. base producto
98 | 800 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Ingresos íntegros
99 | 811 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Índice
100 | 817 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Rdto. base producto
101 | 828 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Ingresos íntegros
102 | 839 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Índice
103 | 845 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Rdto. base producto
104 | 856 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Ingresos íntegros
105 | 867 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Índice
106 | 873 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Rdto. base producto
107 | 884 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Ingresos íntegros
108 | 895 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Índice
109 | 901 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Rdto. base producto
110 | 912 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Ingresos íntegros
111 | 923 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Índice
112 | 929 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Rdto. base producto
113 | 940 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Ingresos íntegros
114 | 951 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Índice
115 | 957 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Rdto. base producto
116 | 968 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Ingresos íntegros
117 | 979 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Índice
118 | 985 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Rdto. base producto
119 | 996 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Ingresos íntegros
120 | 1007 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Índice
121 | 1013 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Rdto. base producto
122 | 1024 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Ingresos íntegros
123 | 1035 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Índice
124 | 1041 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Rdto. base producto
125 | 1052 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Total  ingresos íntegros (154)
126 | 1063 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto previo (suma) (155)
127 | 1074 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones (156)
128 | 1085 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Amortizacion inmovilizado (157)
129 | 1096 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto minorado  (158)
130 | 1107 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Medios ajenos (2 enteros y 2 decimales) (159) | *
131 | 1111 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Utiliz. personal asalariado (2 enteros y 2 decimales) (160) | *
132 | 1115 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Cultivos tierras arrendadas (2 enteros y 2 decimales) (161) | *
133 | 1119 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (162) Ver NOTA | *
134 | 1123 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 2 (162) Ver NOTA | *
135 | 1127 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Actividades agricultura ecológica (2 enteros y dos decimales)  (163) | *
136 | 1131 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Cultivo en tierras regadío utilice energía electrica (2 enteros y 2 decimales) (164) | *
137 | 1135 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales)  (165) | *
138 | 1139 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Determinadas actividades forestales (2 enteros y 2 decimales)  (166) | *
139 | 1143 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto de módulos (167)
140 | 1156 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción carácter general (168)
141 | 1169 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Diferencia (169)
142 | 1182 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción agricultores jóvenes (170)
143 | 1195 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Gastos extraordinarios por circunstancias excepcionales (171)
144 | 1208 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto  (172)
145 | 1221 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones rendimientos generados más 2 años o forma irregular (173)
146 | 1234 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto reducido (174)
147 | 1247 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Suma rendimientos netos reducidos (178)
148 | 1260 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Reducción por ejercicio determinadas actividades económicas (179)
149 | 1273 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Rendimiento neto reducido total  (180)
150 | 1286 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10007>
151 | 1295 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 1296
 |  |  |  |  | NOTA: Cumplimentar sólo cuando el índice 2 sea distinto al índice 1.

# 100-08

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "08"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 1 | Num |  | Nº de hojas adicionales si se declaran más de 3 imputaciones
7 | 11 | 1 | Tit | C | (F) Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (181)
8 | 12 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - NIF Entidad (182)
9 | 32 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país (183)
10 | 33 | 4 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Porcentaje participación  (2 enteros y dos decimales) (184) | *
11 | 37 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (185)
12 | 50 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Minoraciones  aplicables (186)
13 | 63 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones aplicables (187)
14 | 76 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto computable (188)
15 | 89 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Neto atribuido por la entidad . Imp. computable (189)
16 | 102 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Derivado valores deuda subordinada o partic. preferentes (190)
17 | 115 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto atribuido (191)
18 | 128 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Minoraciones aplicables (192)
19 | 141 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Reducciones aplicables (193)
20 | 154 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto computable (194)
21 | 167 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. Neto atribuido por la entidad (195)
22 | 180 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Minoraciones aplicables (196)
23 | 193 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducciones aplicables (197)
24 | 206 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. Neto computable (198)
25 | 219 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas  patrimoniales imputables 2015 - No derivadas transmisión - Ganancias patrimoniales no derivadas de transmisiones, atribuidas por la entidad (199)
26 | 232 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - No derivadas transmisión - Pérdidas patrimoniales no derivadas de transmisiones, atribuidas por la entidad (200)
27 | 245 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales (201)
28 | 258 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales - Valor transmisión a constituir renta vitalicia (202)
29 | 271 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales - Valor transmisión que resulta aplicable (203)
30 | 284 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas 50 por 100 (sólo inmuebles urbanos) (204)
31 | 297 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas reinversión renta vitalicia (205)
32 | 310 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Parte ganancias susceptibles reducción  (206)
33 | 323 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Reducciones aplicables  (207)
34 | 336 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrim. reducidas no exentas  (208)
35 | 349 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrim. reducidas no exentas aplicables 2015  (209)
36 | 362 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad  (210)
37 | 375 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución de retenciones e ingresos a cuenta -  Retenciones e ingresos a cuenta atribuidos por la entidad (211)
38 | 388 | 1 | Tit | C | (F) Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (181)
39 | 389 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - NIF Entidad (182)
40 | 409 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país (183)
41 | 410 | 4 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Porcentaje participación  (2 enteros y dos decimales) (184) | *
42 | 414 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (185)
43 | 427 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Minoraciones  aplicables (186)
44 | 440 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones aplicables (187)
45 | 453 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto computable (188)
46 | 466 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Neto atribuido por la entidad . Imp. computable (189)
47 | 479 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Derivado valores deuda subordinada o partic. preferentes (190)
48 | 492 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto atribuido (191)
49 | 505 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Minoraciones aplicables (192)
50 | 518 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Reducciones aplicables (193)
51 | 531 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto computable (194)
52 | 544 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. Neto atribuido por la entidad (195)
53 | 557 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Minoraciones aplicables (196)
54 | 570 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducciones aplicables (197)
55 | 583 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. Neto computable (198)
56 | 596 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas  patrimoniales imputables 2015 - No derivadas transmisión - Ganancias patrimoniales no derivadas de transmisiones, atribuidas por la entidad (199)
57 | 609 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - No derivadas transmisión - Pérdidas patrimoniales no derivadas de transmisiones, atribuidas por la entidad (200)
58 | 622 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales (201)
59 | 635 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales - Valor transmisión a constituir renta vitalicia (202)
60 | 648 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales - Valor transmisión que resulta aplicable (203)
61 | 661 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas 50 por 100 (sólo inmuebles urbanos) (204)
62 | 674 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas reinversión renta vitalicia (205)
63 | 687 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Parte ganancias susceptibles reducción  (206)
64 | 700 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Reducciones aplicables  (207)
65 | 713 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrim. reducidas no exentas  (208)
66 | 726 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrim. reducidas no exentas aplicables 2015  (209)
67 | 739 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales imputables 2015 - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad  (210)
68 | 752 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución de retenciones e ingresos a cuenta -  Retenciones e ingresos a cuenta atribuidos por la entidad (211)
69 | 765 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos capital mobiliario - A integrar en BI general - Rdto. Neto computable - Total (212)
70 | 778 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos capital mobiliario - A integrar en BI  ahorro - Rdto. Neto atribuido - Importe computable - Total (213)
71 | 791 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos capital mobiliario - A integrar en BI ahorro - Rdto. derivado valores deuda subordinada o participaciones preferentes - Total (214)
72 | 804 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos capital inmobiliario - Rendimiento neto computable - Total (215)
73 | 817 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos actividades económicas - Rendimiento neto computable - Total (216)
74 | 830 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  ganancias y pérdidas patrimoniales imputables 2015 -  No derivada transmisiones - Ganancias patrimoniales - Total  (217)
75 | 843 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  ganancias y pérdidas patrimoniales imputables 2015 -  No derivada transmisiones - Pérdidas patrimoniales - Total  (218)
76 | 856 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  ganancias y pérdidas patrimoniales imputables 2015 -  Derivadas  transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias reducidas no exentas imputables a 2015 - Total  (219)
77 | 869 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  ganancias y pérdidas patrimoniales imputables 2015 -  Derivadas  transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pédidas patrimoniales atribuidas por la entidad - Total  (220)
78 | 882 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución retenciones e ingresos a cuenta -  Retenciones e ingresos atribuidos por la entidad - Total  (537)
79 | 895 | 1 | Tit | C | Regs. especiales - Agrupac., ute - Entidad 1-  Entidades y contribuyentes socios. Contribuyente "0" a "9" (225)
80 | 896 | 9 | An | C | Regs. especiales - Agrupac., ute - Entidad 1-  Entidades y contribuyentes socios. N.I.F. Entidad (226)
81 | 905 | 1 | An | C | Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (227)
82 | 906 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Base imponible imputada  (228)
83 | 919 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. invers. empres. (229)
84 | 932 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. creación empleo (230)
85 | 945 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (231)
86 | 958 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. doble impos. internac. (232)
87 | 971 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 1- Imput. Ret.e.ingresos cta.  - Retenc. e ingresos a cta. imputados (233)
88 | 984 | 1 | Tit | C | Regs. especiales - Agrupac., ute - Entidad 2-  Entidades y contribuyentes socios. Contribuyente "0" a "9" (225)
89 | 985 | 9 | An | C | Regs. especiales - Agrupac., ute - Entidad 2-  Entidades y contribuyentes socios. N.I.F. Entidad (226)
90 | 994 | 1 | An | C | Regs. especiales - Agrupac., ute - Entidad 2-  Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (227)
91 | 995 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Base imponible imputada  (228)
92 | 1008 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. invers. empres. (229)
93 | 1021 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. creación empleo (230)
94 | 1034 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (231)
95 | 1047 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. doble impos. internac. (232)
96 | 1060 | 13 | N | C | Regs. especiales - Agrupac., ute - Entidad 2- Imput. Ret.e.ingresos cta.  - Retenc. e ingresos a cta. imputados (233)
97 | 1073 | 13 | N |  | Regs. especiales - Agrupac., ute - Total base imponible imputada  (235)
98 | 1086 | 13 | N |  | Regs. especiales - Agrupac., ute - Total Retenciones e ingresos a cta. imputados (538)
99 | 1099 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10008>
100 | 1108 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 1109

# 100-09

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "09"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 10 | 2 | Num |  | Nº hojas adicionales que se adjuntan
7 | 12 | 1 | Tit | C | (F) Regs. especiales - Imputac. rentas reg. transp. fiscal internacional -  Entidad 1 - Contribuyente  "0" a "9" (236)
8 | 13 | 24 | An | C | Regs. especiales - Imputac. rentas reg. transp. fiscal internacional -  Entidad 1 - Denominación entidad no residente (237)
9 | 37 | 13 | N | C | Regs. especiales - Imputac. rentas reg. transp. fiscal internacional -  Entidad 1 - Importe imputación  (239)
10 | 50 | 1 | Tit | C | Regs. especiales - Imputac. rentas reg. transp. fiscal internacional -  Entidad 2 - Contribuyente  "0" a "9" (236)
11 | 51 | 24 | An | C | Regs. especiales - Imputac. rentas reg. transp. fiscal internacional -  Entidad 2 - Denominación entidad no residente (237)
12 | 75 | 13 | N | C | Regs. especiales - Imputac. rentas reg. transp. fiscal internacional -  Entidad 2 - Importe imputación  (239)
13 | 88 | 13 | N |  | Regs. especiales - Imputac. rentas reg. transp. fiscal internacional -  Total importe de la imputación  (240)
14 | 101 | 1 | Tit |  | Regs. especiales - Imputac. rentas derechos imagen - Contribuyente que debe efectuar la imputacion.  "0" a "9" (241)
15 | 102 | 25 | An |  | Regs. especiales - Imputac. rentas derechos imagen - NIF o denominación persona/entidad cesionaria derechos imagen (242)
16 | 127 | 25 | An |  | Regs. especiales - Imputac. rentas derechos imagen - NIF o denominación persona/entidad relación laboral (243)
17 | 152 | 13 | N |  | Regs. especiales - Imputac. rentas derechos imagen - Cantidad a imputar  (244)
18 | 165 | 1 | Tit | C | Regs. especiales - Imputac.rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Contribuyente  "0" a "9" (245)
19 | 166 | 24 | An | C | Regs. especiales - Imputac.rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Denominación Institución (246)
20 | 190 | 13 | N | C | Regs. especiales - Imputac.rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Importe imputación (247)
21 | 203 | 1 | Tit | C | Regs. especiales - Imputac.rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Contribuyente  "0" a "9" (245)
22 | 204 | 24 | An | C | Regs. especiales - Imputac.rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Denominación Institución (246)
23 | 228 | 13 | N | C | Regs. especiales - Imputac.rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Importe imputación (247)
24 | 241 | 13 | N |  | Regs. especiales - Imputac.rentas  I. I.Colectiva  paraísos fiscales - Total  importe de la imputación  (250)
25 | 254 | 13 | N |  | (G1) Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En metálico - Importe (251)
26 | 267 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Valoración (252)
27 | 280 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta (253)
28 | 293 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta repercutidos (254)
29 | 306 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Importe computable (255)
30 | 319 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Pérdidas patrimoniales derivadas de estos juegos (256)
31 | 332 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Ganancias patrimoniales netas (257)
32 | 345 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En metálico - Importe (258)
33 | 358 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Valoración (259)
34 | 371 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta (260)
35 | 384 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta repercutidos (261)
36 | 397 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Importe computable (262)
37 | 410 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Subvenciones/ayudas adquisión/rehabilitación vivienda habitual (263)
38 | 423 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Ganancias patrimoniales vecinos, aprovechamientos forestales (264)
39 | 436 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Renta básica emancipación (265)
40 | 449 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas -  Importe ganancias (266)
41 | 462 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe pérdidas (267)
42 | 475 | 1 | Tit | C | (G2) Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro) - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (268)
43 | 476 | 9 | An | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - N.I.F. (269)
44 | 485 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 -  Imp. Global transmisiones 2015 (270)
45 | 498 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Imp. Global transmisiones 2015 -  Valor trans. para renta vitalicia(271)
46 | 511 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Imp. Global transmisiones 2015 -  Valor trans. Aplicable D.T.9ª(272)
47 | 524 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Importe global adquisiciones (273)
48 | 537 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 1 -Ganancias patrimoniales (274)
49 | 550 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 -Ganancias exentas reinversión rentas vitalicias (275)
50 | 563 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 1 - Parte ganancias suceptible reducción (276)
51 | 576 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 1 - Reducción aplicable (277)
52 | 589 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Ganancias patrimoniales reducidas no exentas (278)
53 | 602 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Pérdidas patrimoniales (279)
54 | 615 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Pérdidas patrimoniales imputables a 2015 (280)
55 | 628 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  -Inst. inv. Colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (268)
56 | 629 | 9 | An | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro) - Inst. inv. Colectiva  -Sociedad/Fondo 2 - N.I.F. (269)
57 | 638 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 -  Imp. Global transmisiones 2015 (270)
58 | 651 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Imp. Global transmisiones 2015 -  Valor trans. para renta vitalicia(271)
59 | 664 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Imp. Global transmisiones 2015 -  Valor trans. Aplicable D.T.9ª(272)
60 | 677 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Importe global adquisiciones (273)
61 | 690 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 2 -Ganancias patrimoniales (274)
62 | 703 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 -Ganancias exentas reinversión rentas vitalicias (275)
63 | 716 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 2 - Parte ganancias suceptible reducción (276)
64 | 729 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 2 - Reducción aplicable (277)
65 | 742 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Ganancias patrimoniales reducidas no exentas (278)
66 | 755 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Pérdidas patrimoniales (279)
67 | 768 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Pérdidas patrimoniales imputables a 2015 (280)
68 | 781 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (268)
69 | 782 | 9 | An | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (269)
70 | 791 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 -  Imp. Global transmisiones 2015 (270)
71 | 804 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Imp. Global transmisiones 2015 -  Valor trans. para renta vitalicia(271)
72 | 817 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Imp. Global transmisiones 2015 -  Valor trans. Aplicable D.T.9ª(272)
73 | 830 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Importe global adquisiciones (273)
74 | 843 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 3 -Ganancias patrimoniales (274)
75 | 856 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión  elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 -Ganancias exentas reinversión rentas vitalicias (275)
76 | 869 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 3 - Parte ganancias suceptible reducción (276)
77 | 882 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 3 - Reducción aplicable (277)
78 | 895 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Ganancias patrimoniales reducidas no exentas (278)
79 | 908 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Pérdidas patrimoniales (279)
80 | 921 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Pérdidas patrimoniales imputables a 2015 (280)
81 | 934 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. Colectiva - Resultados - Ganancias patrimoniales reducidas no exentas - Total (281)
82 | 947 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (integrar en BI ahorro)  - Inst. inv. Colectiva - Resultados - Pérdidas patrimoniales imputables 2015 - Total (282)
83 | 960 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
84 | 963 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10009>
85 | 972 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 973

# 100-10

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "10"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 10 | 2 | Num |  | Nº hojas adicionales que se adjuntan
7 | 12 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 1 -  Contribuyente valores transmitidos "0" a "9" (283)
8 | 13 | 20 | An | C | Ganancias/pérdidas patrim. deriv. Transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 1 - Denominación valores (284)
9 | 33 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 1 - Importe global efectuadas en 2015 (285)
10 | 46 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 1 - Importe global efectuadas en 2015 - Valor transmisión a constituir en renta vitalicia  (286)
11 | 59 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 1 - Importe global efectuadas en 2015 - Valor transmisión aplicable D.T.9ª (287)
12 | 72 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Valor adquisición global (288)
13 | 85 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados -  Ganancias al (289)
14 | 98 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (290)
15 | 111 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (291)
16 | 124 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Reducción aplicable (292)
17 | 137 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Ganancias patrimoniales no exentas (293)
18 | 150 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Pérdidas patrim. Importe obtenido (294)
19 | 163 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Pérdidas patrim. Importe computable (295)
20 | 176 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 2 -  Contribuyente valores transmitidos "0" a "9" (283)
21 | 177 | 20 | An | C | Ganancias/pérdidas patrim. deriv. Transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 2 - Denominación valores (284)
22 | 197 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 2 - Importe global efectuadas en 2015 (285)
23 | 210 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 2 - Importe global efectuadas en 2015 - Valor transmisión a constituir en renta vitalicia  (286)
24 | 223 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 2 - Importe global efectuadas en 2015 - Valor transmisión aplicable D.T.9ª (287)
25 | 236 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Valor adquisición global (288)
26 | 249 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados -  Ganancias al (289)
27 | 262 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (290)
28 | 275 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (291)
29 | 288 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Reducción aplicable (292)
30 | 301 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Ganancias patrimoniales no exentas (293)
31 | 314 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Pérdidas patrim. Importe obtenido (294)
32 | 327 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Pérdidas patrim. Importe computable (295)
33 | 340 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 3 -  Contribuyente valores transmitidos "0" a "9" (283)
34 | 341 | 20 | An | C | Ganancias/pérdidas patrim. deriv. Transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 3 - Denominación valores (284)
35 | 361 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 3 - Importe global efectuadas en 2015 (285)
36 | 374 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 3 - Importe global efectuadas en 2015 - Valor transmisión a constituir en renta vitalicia  (286)
37 | 387 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 3 - Importe global efectuadas en 2015 - Valor transmisión aplicable D.T.9ª (287)
38 | 400 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Valor adquisición global (288)
39 | 413 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados -  Ganancias al (289)
40 | 426 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (290)
41 | 439 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (291)
42 | 452 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Reducción aplicable (292)
43 | 465 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Ganancias patrimoniales no exentas (293)
44 | 478 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Pérdidas patrim. Importe obtenido (294)
45 | 491 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Pérdidas patrim. Importe computable (295)
46 | 504 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Resultados - Ganancias patrim. Reducidas no exentas - Totales (296)
47 | 517 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Resultados - Pérdidas patrim. Importe computable - Totales (297)
48 | 530 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
49 | 533 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (298)
50 | 534 | 1 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (300)
51 | 535 | 1 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -  Inmuebles. Situación. Clave "0" a "4" (301)
52 | 536 | 20 | An | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -   Inmuebles. Situación. Ref. catastral (302)
53 | 556 | 8 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha transmisión (303)
54 | 564 | 8 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha adquisición (304)
55 | 572 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión (305)
56 | 585 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Constituir renta vitalicia (306)
57 | 598 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - De la vivienda habitual (307)
58 | 611 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Susceptible de reducción (308)
59 | 624 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor adquisición (309)
60 | 637 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (310)
61 | 650 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable ( (311)
62 | 663 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida ( (312)
63 | 676 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta 50 por 100 ( (313)
64 | 689 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en rentas vitalicias ( (314)
65 | 702 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en vivienda habitual ( (315)
66 | 715 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia no exenta ( (316)
67 | 728 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Parte ganancia susceptible reducción ( (317)
68 | 741 | 4 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Nº años permanencia hasta 31/12/1994 ( (318)
69 | 745 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Reducción aplicable ( (319)
70 | 758 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida ( (320)
71 | 771 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida  imputable 2015( (321)
72 | 784 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Parte ganancia susceptible reducción ( (322)
73 | 797 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Reducción licencia autotaxis ( (323)
74 | 810 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida( (324)
75 | 823 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida imputable 2015( (325)
76 | 836 | 1 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (299)
77 | 837 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (298)
78 | 838 | 1 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (300)
79 | 839 | 1 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -  Inmuebles. Situación. Clave "0" a "4" (301)
80 | 840 | 20 | An | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -   Inmuebles. Situación. Ref. catastral (302)
81 | 860 | 8 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Fecha transmisión (303)
82 | 868 | 8 | Num | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Fecha adquisición (304)
83 | 876 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión (305)
84 | 889 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - Constituir renta vitalicia (306)
85 | 902 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - De la vivienda habitual (307)
86 | 915 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - Susceptible de reducción (308)
87 | 928 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor adquisición (309)
88 | 941 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (310)
89 | 954 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable ( (311)
90 | 967 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida ( (312)
91 | 980 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta 50 por 100 ( (313)
92 | 993 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta reinversión en rentas vitalicias ( (314)
93 | 1006 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta reinversión en vivienda habitual ( (315)
94 | 1019 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia no exenta ( (316)
95 | 1032 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Parte ganancia susceptible reducción ( (317)
96 | 1045 | 4 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Nº años permanencia hasta 31/12/1994 ( (318)
97 | 1049 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Reducción aplicable ( (319)
98 | 1062 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Ganancia patrimonial reducida ( (320)
99 | 1075 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Ganancia patrimonial reducida  imputable 2015( (321)
100 | 1088 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Parte ganancia susceptible reducción ( (322)
101 | 1101 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Reducción licencia autotaxis ( (323)
102 | 1114 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Ganancia patrimonial reducida( (324)
103 | 1127 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Ganancia patrimonial reducida imputable 2015( (325)
104 | 1140 | 1 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (299)
105 | 1141 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Diferencia negativa - Pérdida patrimonial imputable 2015  - Total (326)
106 | 1154 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elementos no afectos - Ganancia patrimonial imputable 2015 - Total  (327)
107 | 1167 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Otros elementos - Elementos afectos - Ganancia patrimonial imputable 2015 - Total  (328)
108 | 1180 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
109 | 1183 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 1 -  Contribuyente "0" a "9" (329)
110 | 1184 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 1 -  Importe a imputar a 2015 (330)
111 | 1197 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 2 -  Contribuyente "0" a "9" (329)
112 | 1198 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 2 -  Importe a imputar a 2015 (330)
113 | 1211 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 3 -  Contribuyente "0" a "9" (329)
114 | 1212 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 3 -  Importe a imputar a 2015 (330)
115 | 1225 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 1 -  Importe a imputar a 2015 - Total (331)
116 | 1238 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida  1 -  Contribuyente "0" a "9" (332)
117 | 1239 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida  1 -  Importe pérdida imputar a 2015 (333)
118 | 1252 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida 2 -  Contribuyente "0" a "9" (332)
119 | 1253 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida 2 -  Importe pérdida imputar a 2015 (333)
120 | 1266 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida  3 -  Contribuyente "0" a "9" (332)
121 | 1267 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida  3 -  Importe pérdida imputar a 2015 (333)
122 | 1280 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión elementos patrimoniales (a integrar en BI ahorro) (continuación) - Imputación a 2015 Ganancias/pérdidas efectuadas en ejercicios anteriores -  Importe pérdida imputar a 2015 - Total  (334)
123 | 1293 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10010>
124 | 1302 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 1303

# 100-11

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "11"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 1 | Num |  | Nº hojas adicionales que se adjuntan
7 | 11 | 1 | Tit | C | (G3) Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2015 diferimiento por reinversión - Ganancia 1 - Contribuyente "0" a "9" (335)
8 | 12 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2015 diferimiento por reinversión - Ganancia 1 - Importe ganancia (336)
9 | 25 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2015 diferimiento por reinversión - Ganancia 2 - Contribuyente "0" a "9" (335)
10 | 26 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2015 diferimiento por reinversión - Ganancia 2 - Importe ganancia (336)
11 | 39 | 1 | Tit | C | Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2015 diferimiento por reinversión - Ganancia 3 - Contribuyente "0" a "9" (335)
12 | 40 | 13 | N | C | Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2015 diferimiento por reinversión - Ganancia 3 - Importe ganancia (336)
13 | 53 | 13 | N |  | Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2015 diferimiento por reinversión - Total ganancia (337)
14 | 66 | 1 | Num |  | (G4) Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Contribuyente que ha transmitido intervivos las acciones "1" o "0"
15 | 67 | 1 | Tit | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Contribuyente valores transmitidos "0" a "9" (338)
16 | 68 | 9 | An | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Nif entidad (339)
17 | 77 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Valor acciones/participaciones (340)
18 | 90 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Valor transmisión acciones (341)
19 | 103 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Valor transmisión acciones - Aplicable D.T.9ª (342)
20 | 116 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Valor adquisición (343)
21 | 129 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Resultados - Ganancias patrimoniales (344)
22 | 142 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Resultados - Ganancias suceptibles reducción (345)
23 | 155 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Resultados - Reducción aplicable (346)
24 | 168 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 1 -  Resultados - Ganancias patrim. reducidas (347)
25 | 181 | 1 | Tit | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Contribuyente valores transmitidos "0" a "9" (338)
26 | 182 | 9 | An | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Nif entidad (339)
27 | 191 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Valor acciones/participaciones (340)
28 | 204 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Valor transmisión acciones (341)
29 | 217 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Valor transmisión acciones - Aplicable D.T.9ª (342)
30 | 230 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Valor adquisición (343)
31 | 243 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Resultados - Ganancias patrimoniales (344)
32 | 256 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Resultados - Ganancias suceptibles reducción (345)
33 | 269 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Resultados - Reducción aplicable (346)
34 | 282 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 2 -  Resultados - Ganancias patrim. reducidas (347)
35 | 295 | 1 | Tit | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Contribuyente valores transmitidos "0" a "9" (338)
36 | 296 | 9 | An | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Nif entidad (339)
37 | 305 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Valor acciones/participaciones (340)
38 | 318 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Valor transmisión acciones (341)
39 | 331 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Valor transmisión acciones - Aplicable D.T.9ª (342)
40 | 344 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Valor adquisición (343)
41 | 357 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Resultados - Ganancias patrimoniales (344)
42 | 370 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Resultados - Ganancias suceptibles reducción (345)
43 | 383 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Resultados - Reducción aplicable (346)
44 | 396 | 13 | N | C | Ganancias/pérdidas patrim. cambio residencia fuera territorio español -  Entidad 3 -  Resultados - Ganancias patrim. reducidas (347)
45 | 409 | 13 | N |  | Ganancias/pérdidas patrim. cambio residencia fuera territorio español - Resultados - Ganancias patrim. Reducidas - Total (348)
46 | 422 | 13 | N |  | (G5) Exención por reinversión ganancia patrimonial 2015 transmisión vivienda habitual - Importe transmisión susceptible reinversión (349)
47 | 435 | 13 | N |  | Exención por reinversión ganancia patrimonial 2015 transmisión vivienda habitual - Ganancia patrimonial consecuencia transmisión (350)
48 | 448 | 13 | N |  | Exención por reinversión ganancia patrimonial 2015 transmisión vivienda habitual - Importe reinvertido hasta 31-12-2015 adquisición nueva vivienda (351)
49 | 461 | 13 | N |  | Exención por reinversión ganancia patrimonial 2015 transmisión vivienda habitual - Importe se compromete reinvertir 2 años siguientes (352)
50 | 474 | 13 | N |  | Exención por reinversión ganancia patrimonial 2015 transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (353)
51 | 487 | 13 | N |  | (G6) Exención por reinversión en rentas vitalicias - Importe total transmisión elementos patrimoniales (354)
52 | 500 | 13 | N |  | Exención por reinversión en rentas vitalicias - Ganancia patrimonial obtenida (355)
53 | 513 | 13 | N |  | Exención por reinversión en rentas vitalicias - Importe reinvertido hasta 31-12-2015 en rentas vitalicias (356)
54 | 526 | 13 | N |  | Exención por reinversión en rentas vitalicias - Importe se compromete reinvertir en 2016 (357)
55 | 539 | 13 | N |  | Exención por reinversión en rentas vitalicias - Importe retención se compromete reinvertir en 2016 (358)
56 | 552 | 13 | N |  | Exención por reinversión en rentas vitalicias - Ganancia patrimonial exenta por reinversión (359)
57 | 565 | 1 | Tit |  | (G7) Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (360)
58 | 566 | 2 | Num |  | Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España -  Número de operaciones1 (361)
59 | 568 | 1 | Tit |  | Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente 2   "0" a "9" (362)
60 | 569 | 2 | Num |  | Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones 2 (363)
61 | 571 | 1 | Num |  | Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Si entidades no residentes no han aplicado régimen fiscal similar a éste "X" o blancos  (374)
62 | 572 | 13 | N |  | (G8) Integración/compensación ganancias/pérdidas patrimoniales imputables 2015 - A integrar en base imponible general -  Suma ganancias (364)
63 | 585 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2015 - A integrar base imponible general -  Suma pérdidas (365)
64 | 598 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2015 - A integrar base imponible general -  Saldo neto - Diferencia positiva (366)
65 | 611 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2015 - A integrar base imponible general -  Saldo neto - Diferencia negativa (367)
66 | 624 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2015 - A integrar base imponible ahorro - Suma ganancias (368)
67 | 637 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2015 - A integrar base imponible ahorro - Suma pérdidas (369)
68 | 650 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2015 - A integrar base imponible ahorro - Saldo neto negativo ganancias y pérdidas imputables a 2015 - positiva (370)
69 | 663 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2015 - A integrar base imponible ahorro - Saldo neto negativo ganancias y pérdidas imputables a 2015 - positiva (371)
70 | 676 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10011>
71 | 685 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 686

# 100-12

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página.Resto saldos netos negativos  ganancias/pérdidas de valores de deuda subordinada o preferentes | OBLIGATORIO | Constante "12"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 13 | N | Base imponible general y base imponible ahorro - Integración y compensación rdtos. capital mobiliario (B.I. ahorro) - Saldo neto positivo rdto. capital mobiliario imputable a 2015 (372)
7 | 23 | 13 | N | Base imponible general y base imponible ahorro - Integración y compensación rdtos. capital mobiliario (B.I. ahorro) - Saldo neto negativo rdtos. capital mobiliario imputable a 2015 (373)
8 | 36 | 13 | N | Base imponible general y base imponible ahorro - BI general - Saldo neto positivo ganancias/pérdidas 2015 a integrar base imponible general (366)
9 | 49 | 13 | N | Base imponible general y base imponible ahorro - BI general - Compensación - Saldos netos negativos ganancias/pérdidas 2011-2014  pendientes compensar (376)
10 | 62 | 13 | N | Base imponible general y base imponible ahorro - BI general - Saldos neto rendimientos a integrar en base Imponible general (377)
11 | 75 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Saldo neto negativo ganancias/pérdidas 2015 (379)
12 | 88 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Resto saldos netos negativos ganancias/pérdidas 2011 a 2014 pendientes compensación (378)
13 | 101 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Base imponible general (380)
14 | 114 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas 2015 (370)
15 | 127 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Saldo neto negativo rendimientos capital mobiliario a 2015 (382)
16 | 140 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Saldos netos negativos ganancias/pérdidas no derivadas transmisión de deuda subordinada o preferentes 2011-2014 (383)
17 | 153 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Saldos netos negativos ganancias/pérdidas derivadas transmisión de deuda subordinada o preferentes 2011-2014 (384)
18 | 166 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario de deuda subordinada o preferentes 2011-2014 (385)
19 | 179 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario a integrar en BI ahorro (372)
20 | 192 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro -  Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Saldo neto negativo ganancias/pérdidas a 2015 (387)
21 | 205 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Saldo neto negativo rdtos capital mobiliario que no derive deuda o part. preferentes 2011 a 2014 (388)
22 | 218 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Saldo neto negativo rdtos capital mobiliario que derive deuda o part. preferentes 2011 a 2014 (389)
23 | 231 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Resto saldo neto negativo de ganancias/pérdidas deuda o participaciones preferentes 2011 a 2014 (390)
24 | 244 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Base imponible del ahorro (395)
25 | 257 | 13 | N | Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo ganancias/pérdidas imputables 2015 a integrar en BI general (396)
26 | 270 | 13 | N | Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo ganancias/pérdidas imputables 2015 a integrar en BI ahorro (397)
27 | 283 | 13 | N | Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo rdtos.capital mobiliario 2015 a integrar en BI ahorro (398)
28 | 296 | 13 | N | (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidad familiar tributación conjunta (399)
29 | 309 | 1 | Tit | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 1 "0" a "9"  1(400)
30 | 310 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2010 a 2014 1  (401)
31 | 323 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 y 2014 de contribuciones a seguros colectivos de dependencia 1 (402)
32 | 336 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones del 2015  1 (403)
33 | 349 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones del 2015 a seguros colectivos 1 (404)
34 | 362 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción  1 (405)
35 | 375 | 1 | Tit | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 1 "0" a "9"  2(400)
36 | 376 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2010 a 2014  2  (401)
37 | 389 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 y 2014 de contribuciones a seguros colectivos de dependencia  2 (402)
38 | 402 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones del 2015  2 (403)
39 | 415 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones del 2015 a seguros colectivos  2 (404)
40 | 428 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción  2 (405)
41 | 441 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total derecho reducción (406)
42 | 454 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones cónyuge del contribuyente - Total derecho reducción (407)
43 | 467 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10012>
44 | 476 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 477

# 100-13

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "13"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 2 | Num |  | Nº hojas adicionales que se adjuntan
7 | 12 | 1 | Tit | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Contribuyente 1 "0" a "9" (408)
8 | 13 | 9 | An | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - NIF persona con discapacidad 1 (409)
9 | 22 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Excesos pendientes reducir 1 (410)
10 | 35 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Aportaciones 2015 propia persona discapacidad 1 (411)
11 | 48 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Aportaciones 2015 parientes o tutores 1 (412)
12 | 61 | 1 | Tit | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Contribuyente 2 "0" a "9" (408)
13 | 62 | 9 | An | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - NIF persona con discapacidad 2 (409)
14 | 71 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Excesos pendientes reducir 2 (410)
15 | 84 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Aportaciones 2014 propia persona discapacidad 2 (411)
16 | 97 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Aportaciones 2014 parientes o tutores 2 (412)
17 | 110 | 13 | N |  | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Total con derecho a reducción (413)
18 | 123 | 1 | Tit |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (414)
19 | 124 | 9 | An |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 1 (415)
20 | 133 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 1 (416)
21 | 146 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2015 1 (417)
22 | 159 | 1 | Tit |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (414)
23 | 160 | 9 | An |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 2 (415)
24 | 169 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 2 (416)
25 | 182 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2015 2 (417)
26 | 195 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Total con derecho a reducción (418)
27 | 208 | 1 | Tit |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos -  Contribuyente 1 "0" a "9" (419)
28 | 209 | 9 | An |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 1 (420)
29 | 218 | 20 | An |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si no tiene NIF Nº identificación en país residencia 1 (421)
30 | 238 | 13 | N |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 1 (422)
31 | 251 | 1 | Tit |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos -  Contribuyente 2 "0" a "9" (419)
32 | 252 | 9 | An |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 2 (420)
33 | 261 | 20 | An |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si no tiene NIF Nº identificación en país residencia 2 (421)
34 | 281 | 13 | N |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 2 (422)
35 | 294 | 13 | N |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Total derecho reducción (423)
36 | 307 | 1 | Tit |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 1 "0" a "9" (424)
37 | 308 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales -  Excesos pendientes reducir 2010-2014  1 (425)
38 | 321 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones 2015 1 (426)
39 | 334 | 1 | Tit |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 2 "0" a "9" (424)
40 | 335 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales -  Excesos pendientes reducir 2010-2014  2 (425)
41 | 348 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones 2014 2 (426)
42 | 361 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Total con derecho a reducción (427)
43 | 374 | 13 | N |  | (J) Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base imponible general (380)
44 | 387 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Tributación conjunta (428)
45 | 400 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social (régimen general) (429)
46 | 413 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social cónyuge (430)
47 | 426 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social personas discapacidad (431)
48 | 439 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones patrimonios protegidos personas discapacidad (432)
49 | 452 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Pensiones compensatorias/anualidades alimentos (433)
50 | 465 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones mutualidades prev. soc. deportistas profesionales (434)
51 | 478 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general (435)
52 | 491 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Compensación bases liquidables generales negativas (436)
53 | 504 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general sometida a gravamen (440)
54 | 517 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base imponible ahorro (395)
55 | 530 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción tributación conjunta (441)
56 | 543 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción pensiones comp./anualidades alimentos (442)
57 | 556 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base liquidable del ahorro (445)
58 | 569 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10013>
59 | 578 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 579

# 100-14

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "14"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 10 | 1 | Tit | (K) Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 1 "0" a "9" (446)
7 | 11 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2015 1 (447)
8 | 24 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuciones 2015 a seguros colectivos dependencia no aplicadas 1 (448)
9 | 37 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 2 "0" a "9" (446)
10 | 38 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2015 2 (447)
11 | 51 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuciones 2015 a seguros colectivos dependencia no aplicadas 2 (448)
12 | 64 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 1 "0" a "9" (449)
13 | 65 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2015 no aplicadas 1 (450)
14 | 78 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 2 "0" a "9" (449)
15 | 79 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2015 no aplicadas 2 (450)
16 | 92 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 3 "0" a "9" (449)
17 | 93 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2015 no aplicadas 3 (450)
18 | 106 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 4 "0" a "9" (449)
19 | 107 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2015 no aplicadas 4 (450)
20 | 120 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 5 "0" a "9" (449)
21 | 121 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2015 no aplicadas 4 (450)
22 | 134 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 6 "0" a "9" (449)
23 | 135 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2015 no aplicadas 4 (450)
24 | 148 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (451)
25 | 149 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2015 no aplicadas 1 (452)
26 | 162 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (451)
27 | 163 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2015 no aplicadas 2 (452)
28 | 176 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 1 "0" a "9" (453)
29 | 177 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2015 no aplicadas 1 (454)
30 | 190 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 2 "0" a "9" (453)
31 | 191 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2015 no aplicadas 2 (454)
32 | 204 | 13 | N | (L) Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe (455)
33 | 217 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe cálculo gravamen autonómico (456)
34 | 230 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe (457)
35 | 243 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe cálculo gravamen autonómico (458)
36 | 256 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe (459)
37 | 269 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe cálculo gravamen autonómico (460)
38 | 282 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe (461)
39 | 295 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe cálculo gravamen autonómico (462)
40 | 308 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo personal y familiar (463)
41 | 321 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe total cálculo gravamen autonómico (464)
42 | 334 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen estatal  (465)
43 | 347 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen estatal (466)
44 | 360 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general  - gravamen autonómico (467)
45 | 373 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen autonómico (468)
46 | 386 | 13 | N | (M) Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable ahorro (469)
47 | 399 | 13 | N | Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable general (470)
48 | 412 | 13 | N | Datos adicionales - Anualidades para alimentos a favor de los hijos. Importe (471)
49 | 425 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10014>
50 | 434 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 435

# 100-15

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "15"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 10 | 13 | N | (N) Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla 440 - Parte estatal (472)
7 | 23 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del  Impuesto importe casilla 440 - Parte autonómica (473)
8 | 36 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general del Impuesto importe casilla 465 - Parte estatal (474)
9 | 49 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala autonómica del Impuesto importe casilla 467 - Parte autonómica (475)
10 | 62 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte estatal (476)
11 | 75 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte autonómica (477)
12 | 88 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte estatal (478) | *
13 | 92 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte autonómica (479) | *
14 | 96 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla 445 - Parte estatal (480)
15 | 109 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla 445 - Parte autonómica (481)
16 | 122 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general del lmpuesto importe casilla 466 - Parte estatal (482)
17 | 135 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala autonómica del Impuesto importe casilla 468 - Parte Parte autonómica (483)
18 | 148 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte estatal (484)
19 | 161 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte autonómica  (485)
20 | 174 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medio gravamen - Parte estatal (486)
21 | 178 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medio gravamen - Parte autonómica (487)
22 | 182 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra estatal - Parte estatal (490)
23 | 195 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra autonómica - Parte autonómica (491)
24 | 208 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte estatal (492)
25 | 221 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte autonómica (493)
26 | 234 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión empresas nueva o reciente creación - Parte estatal (494)
27 | 247 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte estatal (495)
28 | 260 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte autonómica (496)
29 | 273 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones- Parte estatal (497)
30 | 286 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones - Parte autonómica (498)
31 | 299 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte estatal (499)
32 | 312 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte autonómica (500)
33 | 325 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte estatal (501)
34 | 338 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte autonómica (502)
35 | 351 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte estatal (503)
36 | 364 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte autonómica (504)
37 | 377 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte estatal (505)
38 | 390 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte autonómica (506)
39 | 403 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte estatal (507)
40 | 416 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte autonómica (508)
41 | 429 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras  - Por obras de mejora en la vivienda pendientes deducción - Parte estatal (509)
42 | 442 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras  - Por obras de mejora en la vivienda habitual pendientes deducción  - Parte estatal (510)
43 | 455 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - Suma deducciones autonómicas (511)
44 | 468 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida estatal - Parte estatal (515)
45 | 481 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida autonómica - Parte autonómica (516)
46 | 494 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - Parte estatal (517)
47 | 507 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - Parte estatal (518)
48 | 520 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2014 - Importe - Parte estatal (519)
49 | 533 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2014 - Intereses demora -  Parte estatal (520)
50 | 546 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2014 - Importe - Parte autonómica (521)
51 | 559 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2014 - Intereses demora - Parte autonómica (522)
52 | 572 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2014 - Importe - Parte autonómica (523)
53 | 585 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2014 - Intereses demora - Parte autonómica (524)
54 | 598 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida estatal incrementada - Parte estatal (525)
55 | 611 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida autonómica incrementada - Parte autonómica (526)
56 | 624 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota líquida incrementada total (527)
57 | 637 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones: Por doble imposición internacional, rentas obtenidas y gravadas en el extranjero (528)
58 | 650 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones: Por doble imposición internacional supuestos aplicación régimen transparencia fiscal internacional (529)
59 | 663 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones: Por doble imposición supuestos aplicación régimen imputación rentas cesión derechos imagen (530)
60 | 676 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Retenciones deducibles a rendimientos bonificados - Importe retenciones no practicadas (531)
61 | 689 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota resultante autoliquidación (532)
62 | 702 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10015>
63 | 711 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 712

# 100-16

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo |  | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num |  | Página. | OBLIGATORIO | Constante "16"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 10 | 13 | N |  | (N) Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos del trabajo (533)
7 | 23 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos del capital mobiliario (534)
8 | 36 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Arrendamientos de inmuebles urbanos (535)
9 | 49 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos de actividades económicas (536)
10 | 62 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Atribuidos por entidades en régimen de atribución de rentas (537)
11 | 75 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Imputados por agrupaciones de interés económico y UTE's (538)
12 | 88 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Ingresos a cuenta art. 92.8 Ley del Impuesto (539)
13 | 101 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Ganancias patrimoniales, incluidos premios (540)
14 | 114 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Pagos fraccionados (actividades económicas) (541)
15 | 127 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Cuotas del Impuesto sobre la Renta de no Residentes (542)
16 | 140 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Retenciones art. 11 Directiva 2003/48/CE (543)
17 | 153 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Total pagos a cuenta (544)
18 | 166 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Cuota diferencial (545)
19 | 179 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción por maternidad - Importe deducción (546)
20 | 192 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción por maternidad - Importe abono anticipado deducción (547)
21 | 205 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - NIF descendiente (548)
22 | 214 | 15 | A | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - Nombre (549)
23 | 229 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (550)
24 | 237 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (551)
25 | 245 | 2 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - Nº personas derecho mínimo (552)
26 | 247 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - Se ha cedido el derecho deducción (553) |  | "0" - blanco, "1" - Si,    "2" .- No
27 | 248 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - NIF cedente (554)
28 | 257 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - Se ha cedido el derecho deducción (555) |  | "0" - blanco, "1" - Si,    "2" .- No
29 | 258 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - NIF beneficiario (556)
30 | 267 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - Importe deducción (557)
31 | 280 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción descendientes discapacidad - Importe abono anticipado deducción (558)
32 | 293 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - NIF ascendiente (561)
33 | 302 | 15 | A | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - Nombre (562)
34 | 317 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (563)
35 | 325 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (564)
36 | 333 | 2 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - Nº personas derecho mínimo (565)
37 | 335 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - Se ha cedido el derecho deducción (566) |  | "0" - blanco, "1" - Si,    "2" .- No
38 | 336 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad  - NIF cedente 1 (567)
39 | 345 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - NIF cedente 2 (568)
40 | 354 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - NIF cedente 3 (569)
41 | 363 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - Se ha cedido el derecho deducción (570) |  | "0" - blanco, "1" - Si,    "2" .- No
42 | 364 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - NIF beneficiario (571)
43 | 373 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - Importe deducción (572)
44 | 386 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes discapacidad - Importe abono anticipado deducción (573)
45 | 399 | 30 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Nº identificación título familia numerosa (576)
46 | 429 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Categoría familia numerosa - General (577)
47 | 430 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Categoría familia numerosa - Especial (578)
48 | 431 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Fecha inicio título familia numerosa (DDMMAAAA) (579)
49 | 439 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Fecha caducidad título familia numerosa (DDMMAAAA) (580)
50 | 447 | 2 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Nº ascendientes forman parte familia numerosa  (581)
51 | 449 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Se ha cedido el derecho deducción (582) |  | "0" - blanco, "1" - Si,    "2" .- No
52 | 450 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - NIF cedente 1 (583)
53 | 459 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - NIF cedente 2 (584)
54 | 468 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - NIF cedente 3 (585)
55 | 477 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Se ha cedido el derecho deducción (586) |  | "0" - blanco, "1" - Si,    "2" .- No
56 | 478 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - NIF beneficiario (587)
57 | 487 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Importe deducción (588)
58 | 500 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción familia numerosa - Importe abono anticipado deducción (589)
59 | 513 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes, separado o sin vinculo matrimonial, dos hijos sin derecho anualidades alimentos - Importe deducción (590)
60 | 526 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción ascendientes, separado o sin vinculo matrimonial, dos hijos sin derecho anualidades alimentos - Importe abono anticipado deducción (591)
61 | 539 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Regularizaciones - Importe cobro anticipado descendientes sin derecho mínimo por descendientes (559)
62 | 552 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Regularizaciones - NIF descendientes deducción se regulariza (560)
63 | 561 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Regularizaciones - Importe cobro anticipado ascendientes sin derecho mínimo por ascendientes (574)
64 | 574 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Regularizaciones - NIF ascendientes deducción se regulariza (575)
65 | 583 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Resultado declaración (595)
66 | 596 | 9 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10016>
67 | 605 | 2 | An |  | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 606

# 100-17

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "17"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 10 | 13 | N | (O) Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2015 - Cuota líquida autonómica incrementada (596)
7 | 23 | 13 | N | Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2015 -  50% deducciones doble imposición (597)
8 | 36 | 13 | N | Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2015 - Importe IRPF Cdad Autónoma residencia contribuyente (600)
9 | 49 | 13 | N | (P) Regularización mediante declaración complemetaria (ejercicio 2015) - Resultado a ingresar anteriores autoliquidaciones o liquidaciones administrativas (601)
10 | 62 | 13 | N | Regularización mediante declaración complemetaria (ejercicio 2015) - Devoluciones acordadas Administración, consecuencia anteriores autoliquidaciones  (602)
11 | 75 | 13 | N | Regularización mediante declaración complemetaria (ejercicio 2015) - Resultado declaración complementaria (605)
12 | 88 | 13 | N | Q) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (606)
13 | 101 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (610)
14 | 114 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (607)
15 | 127 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (610)
16 | 140 | 34 | An | Número de cuenta IBAN (611)
17 | 174 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10017>
18 | 183 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 184

# Anexo A.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "18"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 10 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Inversión con derecho a deducción (A)
7 | 23 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte estatal (614)
8 | 36 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte autonómica (615)
9 | 49 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Inversión con derecho a deducción (B)
10 | 62 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte estatal (616)
11 | 75 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte autonómica (617)
12 | 88 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Inversión con derecho a deducción (C)
13 | 101 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte estatal (618)
14 | 114 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte autonómica (619)
15 | 127 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Cantidades satisfechas con derecho a deducción (E)
16 | 140 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte estatal (620)
17 | 153 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte autonómica (621)
18 | 166 | 13 | N | Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte estatal (492)
19 | 179 | 13 | N | Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte autonómica (493)
20 | 192 | 13 | N | Deducción por inversión en vivienda habitual - Datos adicionales - Importe de los pagos realizados en el ejercicio al promotor o constructor (622)
21 | 205 | 9 | An | Deducción por inversión en vivienda habitual - Datos adicionales - NIF del promotor o constructor (623)
22 | 214 | 8 | Num | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Fecha adquisición vivienda (DDMMAAAA) (624)
23 | 222 | 20 | An | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Número de identificación del préstamo hipotecario (625)
24 | 242 | 5 | Num | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Porcentaje del préstamo destinado a adquisición (3 enteros y 2 decimales)  (626) | *
25 | 247 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Cantidades suscripción acciones entidades nueva o reciente creación - Importe (627)
26 | 260 | 9 | An | Deducción inversiones en empresas de nueva o reciente creación - Entidad 1 - NIF (628)
27 | 269 | 9 | An | Deducción inversiones en empresas de nueva o reciente creación - Entidad 2 - NIF (629)
28 | 278 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Importe total deducción inversiones empresa nueva o reciente creación - Base deducción (D)
29 | 291 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Importe total deducciones empresa nueva o reciente creación - Importe deducción (494)
30 | 304 | 9 | An | Deducción por alquiler de la vivienda habitual - NIF del arrendador 1 (630)
31 | 313 | 20 | An | Deducción por alquiler de la vivienda habitual - Si no tiene NIF Nº identificación fiscal en país de residencia (631)
32 | 333 | 9 | An | Deducción por alquiler de la vivienda habitual - NIF del arrendador 2 (632)
33 | 342 | 20 | An | Deducción por alquiler de la vivienda habitual - Si no tiene NIF Nº identificación fiscal en país de residencia (633)
34 | 362 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador (634)
35 | 375 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades satisfechas con derecho a deducción (F)
36 | 388 | 13 | N | Deducción por alquiler de la vivienda habitual - Importe deducción (635)
37 | 401 | 13 | N | Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte estatal (507)
38 | 414 | 13 | N | Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte autonómica (508)
39 | 427 | 13 | N | Deducciones por donativos - Aportaciones actividades mecenazgo límite 15 % base liquidable - Importe con derecho a deducción (G)
40 | 440 | 13 | N | Deducciones por donativos - Aportaciones actividades mecenazgo límite 15 % base liquidable - Importe de la deducción (636)
41 | 453 | 13 | N | Deducciones por donativos - Donativos entidades reguladas Ley 49/2002 - Importe con derecho a deducción (H)
42 | 466 | 13 | N | Deducciones por donativos - Donativos entidades reguladas Ley 49/2002 - Importe de la deducción (637)
43 | 479 | 13 | N | Deducciones por donativos - Donativos fundaciones y asociaciones utilidad pública Ley 49/2002 - Importe con derecho a deducción (J)
44 | 492 | 13 | N | Deducciones por donativos - Donativos fundaciones y asociaciones utilidad pública Ley 49/2002 - Importe de la deducción (638)
45 | 505 | 13 | N | Deducciones por donativos - Cuotas afiliación y aportaciones partidos políticos, federaciones, coaliciones o agrupamientos electorales - Importe con derecho a deducción (M)
46 | 518 | 13 | N | Deducciones por donativos - Cuotas afiliación y aportaciones partidos políticos, federaciones, coaliciones o agrupamientos electorales - Importe con derecho a deducción - Importe de la deducción (639)
47 | 531 | 13 | N | Deducciones por donativos - Deducciones por donativos - Parte estatal (497)
48 | 544 | 13 | N | Deducciones por donativos - Deducciones por donativos - Parte autonómica (498)
49 | 557 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10018>
50 | 566 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 567

# Anexo A.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "19"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 10 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe con derecho a deducción (I)
7 | 23 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe de la deducción (640)
8 | 36 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte estatal (495)
9 | 49 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte autonómica (496)
10 | 62 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Importe total de la deducción (641)
11 | 75 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte estatal (505)
12 | 88 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte autonómica (506)
13 | 101 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011- Cantidades satisfechas (642)
14 | 114 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011 - Base deducción (K)
15 | 127 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011 - Importe deducción (643)
16 | 140 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Cantidades satisfechas (644)
17 | 153 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 -  Base deducción (L)
18 | 166 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Importe deducción (645)
19 | 179 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Importe total (509)
20 | 192 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Cantidades satisfechas (646)
21 | 205 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Base deducción (R)
22 | 218 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Importe deducción (647)
23 | 231 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Importe total (510)
24 | 244 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Importe dotaciones (648)
25 | 257 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (649)
26 | 270 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (650)
27 | 283 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Importe dotaciones (651)
28 | 296 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (652)
29 | 309 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (653)
30 | 322 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Pendiente de materializar (654)
31 | 335 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Importe dotaciones (655)
32 | 348 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (656)
33 | 361 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (657)
34 | 374 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Pendiente de materializar (658)
35 | 387 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Importe dotaciones (659)
36 | 400 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (660)
37 | 413 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (661)
38 | 426 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Pendiente de materializar (662)
39 | 439 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Importe dotaciones (663)
40 | 452 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (664)
41 | 465 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (665)
42 | 478 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Pendiente de materializar (666)
43 | 491 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Importe de la deducción 2015
44 | 504 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2015 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (667)
45 | 517 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2015 - Inversiones prev. letras C y D 2º. a 6º.) artº. 27.4 (668)
46 | 530 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10019>
47 | 539 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 540

# Anexo A.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "20"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 10 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Saldo anterior
7 | 23 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Aplicado declaración (669)
8 | 36 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Pendiente aplicación
9 | 49 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interés público - Saldo anterior
10 | 62 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interés público - Aplicado declaración (670)
11 | 75 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interes público - Pendiente aplicación
12 | 88 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i  - Deducción
13 | 101 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i - Aplicado declaración (671)
14 | 114 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i  - Pendiente aplicación
15 | 127 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos  - Deducción
16 | 140 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos - Aplicado declaración (672)
17 | 153 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos  - Pendiente aplicación
18 | 166 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS - Deducción
19 | 179 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS -  Aplicado declaración (673)
20 | 192 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS - Pendiente aplicación
21 | 205 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Deducción
22 | 218 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Aplicado declaración (674)
23 | 231 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Pendiente aplicación
24 | 244 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Deducción
25 | 257 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Aplicado declaración (970)
26 | 270 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Pendiente aplicación
27 | 283 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vuelta al Mundo a Vela Alicante 2014" - Deducción
28 | 296 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vuelta al Mundo a Vela Alicante 2014" - Aplicado declaración (675)
29 | 309 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vuelta al Mundo a Vela Alicante 2014" - Pendiente aplicación
30 | 322 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "3ª edición Barcelona World Race" - Deducción
31 | 335 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "3ª edición Barcelona World Race" - Aplicado declaración (676)
32 | 348 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "3ª edición Barcelona World Race" - Pendiente aplicación
33 | 361 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016"- Deducción
34 | 374 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016" - Aplicado declaración (677)
35 | 387 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016" - Pendiente aplicación
36 | 400 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Deducción
37 | 413 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Aplicado declaración (678)
38 | 426 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Pendiente aplicación
39 | 439 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "V Cent. Nacimiento Sta. Teresa de Jesús 2015" - Deducción
40 | 452 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "V Cent. Nacimiento Sta. Teresa de Jesús 2015" - Aplicado declaración (679)
41 | 465 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "V Cent. Nacimiento Sta. Teresa de Jesús 2015" - Pendiente aplicación
42 | 478 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Deducción
43 | 491 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Aplicado declaración (680)
44 | 504 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Pendiente aplicación
45 | 517 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Deducción
46 | 530 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Aplicado declaración (681)
47 | 543 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Pendiente aplicación
48 | 556 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "El Árbol es Vida" - Deducción
49 | 569 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "El Árbol es Vida" - Aplicado declaración  (682)
50 | 582 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "El Árbol es Vida" - Pendiente aplicación
51 | 595 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Deducción
52 | 608 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Aplicado declaración  (683)
53 | 621 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Pendiente aplicación
54 | 634 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona World Jumping Challenge" - Deducción
55 | 647 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona World Jumping Challenge" - Aplicado declaración (684)
56 | 660 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona World Jumping Challenge" - Pendiente aplicación
57 | 673 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Deducción
58 | 686 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Aplicado declaración (685)
59 | 699 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Pendiente aplicación
60 | 712 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Deducción
61 | 725 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Aplicado declaración (686)
62 | 738 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Pendiente aplicación
63 | 751 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "III Centenario de la Real Academia Española" - Deducción
64 | 764 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "III Centenario de la Real Academia Española" - Aplicado declaración (687)
65 | 777 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "III Centenario de la Real Academia Española" - Pendiente aplicación
66 | 790 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "A Coruña 2015-120 años después" - Deducción
67 | 803 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "A Coruña 2015-120 años después" - Aplicado declaracion (688)
68 | 816 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "A Coruña 2015-120 años después" - Pendiente aplicación
69 | 829 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Deducción
70 | 842 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Aplicado declaración (689)
71 | 855 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Pendiente aplicación
72 | 868 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Deducción
73 | 881 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Aplicado declaración (690)
74 | 894 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Pendiente aplicación
75 | 907 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Deducción
76 | 920 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Aplicado declaración (691)
77 | 933 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Pendiente aplicación
78 | 946 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Deducción
79 | 959 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Aplicado declaración (692)
80 | 972 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Pendiente aplicación
81 | 985 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Deducción
82 | 998 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Aplicado declaración (693)
83 | 1011 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Pendiente aplicación
84 | 1024 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Deducción
85 | 1037 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Aplicado declaración (694)
86 | 1050 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Pendiente aplicación
87 | 1063 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Deducción
88 | 1076 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Aplicado declaración (695)
89 | 1089 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Pendiente aplicación
90 | 1102 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Deducción
91 | 1115 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Aplicado declaración (696)
92 | 1128 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Pendiente aplicación
93 | 1141 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Deducción
94 | 1154 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Aplicado declaración  (697)
95 | 1167 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Pendiente aplicación
96 | 1180 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Deducción
97 | 1193 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Aplicado declaración (698)
98 | 1206 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Pendiente aplicación
99 | 1219 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME)" - Deducción
100 | 1232 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME)" - Aplicado declaración (699)
101 | 1245 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME)" - Pendiente aplicación
102 | 1258 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año internacional de la luz" y  "Plan director"- Deducción
103 | 1271 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año internacional de la luz" y "Plan director"- Aplicado declaración (700)
104 | 1284 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año internacional de la luz" y "Plan director" - Pendiente aplicación
105 | 1297 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "ORC Barcelona World Championship 2015" - Deducción
106 | 1310 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "ORC Barcelona World Championship 2015" - Aplicado declaración (701)
107 | 1323 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "ORC Barcelona World Championship 2015" - Pendiente aplicación
108 | 1336 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Equestrian Challenge" - Deducción
109 | 1349 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Equestrian Challenge" - Aplicado declaración (702)
110 | 1362 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Equestrian Challenge" - Pendiente aplicación
111 | 1375 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Deducción
112 | 1388 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Aplicado declaración (703)
113 | 1401 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Pendiente aplicación
114 | 1414 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Centenario Real Federación Andaluza Fútbol 2015" - Deducción
115 | 1427 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Centenario Real Federación Andaluza Fútbol 2015" - Aplicado declaración (704)
116 | 1440 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Centenario Real Federación Andaluza Fútbol 2015" - Pendiente aplicación
117 | 1453 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Ciclismo en Carretera Ponferrada 2014" - Deducción
118 | 1466 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Ciclismo en Carretera Ponferrada 2014" - Aplicado declaración (971)
119 | 1479 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Ciclismo en Carretera Ponferrada 2014" - Pendiente aplicación
120 | 1492 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. económicas (705)
121 | 1505 | 4 | Num | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Período impositivo   (706)
122 | 1509 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (707)
123 | 1522 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (708)
124 | 1535 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Saldo anterior
125 | 1548 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Aplicado declaración (709)
126 | 1561 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Pendiente aplicación
127 | 1574 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Saldo anterior
128 | 1587 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Aplicado declaración (710)
129 | 1600 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Pendiente aplicación
130 | 1613 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. investigación, desarrollo e innovación tecnológica, artº. 35 LIS - Deducción
131 | 1626 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. investigación, desarrollo e innovación tecnológica, artº. 35 LIS - Aplicado declaración (711)
132 | 1639 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. investigación, desarrollo e innovación tecnológica, artº. 35 LIS- Pendiente aplicación
133 | 1652 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Deducción
134 | 1665 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS (712)
135 | 1678 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Pendiente aplicación
136 | 1691 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Deducción
137 | 1704 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Aplicado declaración (713)
138 | 1717 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad,  artº. 38 LIS - Pendiente de aplicación
139 | 1730 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994  - Deducción
140 | 1743 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994 - Aplicado declaración (714)
141 | 1756 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994  - Pendiente aplicación
142 | 1769 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Deducción
143 | 1782 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Aplicado declaración (715)
144 | 1795 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Pendiente aplicación
145 | 1808 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Importe total de las deducciones (716)
146 | 1821 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Deducciones - Parte estatal (449)
147 | 1834 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Deducciones - Parte autonómica (500)
148 | 1847 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10020>
149 | 1856 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 1857

# Anexo B.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "21"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 10 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios de ayudas familiares (717)
7 | 23 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios ayudas viviendas protegidas (718)
8 | 36 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión vivienda habitual protegida/personas jóvenes (719)
9 | 49 | 9 | An | Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - NIF arrendador (720)
10 | 58 | 13 | N | Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - Importe (721)
11 | 71 | 20 | An | Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - Si no tiene NIF Nº identificación en País de residencia (722)
12 | 91 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión en la adquisición de acciones y participaciones  (723)
13 | 104 | 13 | N | Deducciones Autonómicas - Andalucía - Por adopción de hijos ámbito internacional (724)
14 | 117 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con discapacidad (725)
15 | 130 | 13 | N | Deducciones Autonómicas - Andalucía - Para padre/madre de familia monoparental con ascendientes mayores 75 años (726)
16 | 143 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Deducción con carácter general  (727)
17 | 156 | 11 | An | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Cuenta cotización (728)
18 | 167 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Importe (729)
19 | 180 | 11 | An | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Cuenta cotización (730)
20 | 191 | 13 | N | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Importe (731)
21 | 204 | 13 | N | Deducciones Autonómicas - Andalucía - Para trabajadores por gastos de defensa jurídica de la relación laboral (732)
22 | 217 | 13 | N | Deducciones Autonómicas - Andalucía - Por obras en vivienda (Cantidades 2012 pdtes. deducción 4 años exceder en 2012 base deducción) (733)
23 | 230 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con cónyuges o parejas de hecho con discapacidad (734)
24 | 243 | 13 | N | Deducciones Autonómicas - Andalucía - Otras deducciones (735)
25 | 256 | 13 | N | Deducciones Autonómicas - Andalucía - Total deducciones autonómicas (511)
26 | 269 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del tercer hijo o sucesivos (736)
27 | 282 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción de un hijo en atención al grado discapacidad (737)
28 | 295 | 13 | N | Deducciones Autonómicas - Aragón - Por adopción internacional de niños (738)
29 | 308 | 13 | N | Deducciones Autonómicas - Aragón - Por el cuidado de personas dependientes (739)
30 | 321 | 13 | N | Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico (740)
31 | 334 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo  (741)
32 | 347 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en acciones de entidades que cotizan en Mercado Alternativo Bursátil (742)
33 | 360 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en la adquisición de acciones o participaciones sociales (743)
34 | 373 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición o rehabilitación de vivienda habitual en núcleos rurales o análogos (744)
35 | 386 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición libros de texto y material escolar (745)
36 | 399 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual vinculado operaciones dación en pago. Importe  (746)
37 | 412 | 9 | An | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual vinculado operaciones dación en pago - NIF arrendador ( (747)
38 | 421 | 20 | An | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual vinculado operaciones dación en pago. Si no tiene NIF Nº identificación en País de residencia (748)
39 | 441 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda social (deducción arrendador) (749)
40 | 454 | 13 | N | Deducciones Autonómicas - Aragón - Para mayores de 70 años (750)
41 | 467 | 13 | N | Deducciones Autonómicas - Aragón - Por gasto en primas individuales en seguros de salud (751)
42 | 480 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del primer y/o segundo hijo en poblaciones de menos de 10.000 habitantes (752)
43 | 493 | 13 | N | Deducciones Autonómicas - Aragón - Por gasto de guardería de hijos menores de 3 años (753)
44 | 506 | 13 | N | Deducciones Autonómicas - Aragón - Por determinadas subvenciones y/o ayudas obtenidas por daños sufridos inundaciones cuenca río Ebro (754)
45 | 519 | 13 | N | Deducciones Autonómicas - Aragón -  Otras deducciones (755)
46 | 532 | 13 | N | Deducciones Autonómicas - Aragón - Total deducciones autonómicas (511)
47 | 545 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (756)
48 | 558 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes con discapacidad (757)
49 | 571 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes con discapacidad (758)
50 | 584 | 13 | N | Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (759)
51 | 597 | 9 | An | Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - NIF arrendador (760)
52 | 606 | 13 | N | Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - Importe (761)
53 | 619 | 20 | An | Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual. Si no tiene NIF Nº identificación en País de residencia (762)
54 | 639 | 13 | N | Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (763)
55 | 652 | 13 | N | Deducciones Autonómicas - Asturias - Por adopción internacional de menores (764)
56 | 665 | 13 | N | Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones constituidas en la misma fecha  (765)
57 | 678 | 13 | N | Deducciones Autonómicas - Asturias - Para familias numerosas (766)
58 | 691 | 13 | N | Deducciones Autonómicas - Asturias - Para familias monoparentales (767)
59 | 704 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (768)
60 | 717 | 13 | N | Deducciones Autonómicas - Asturias - Por certificación de gestión forestal sostenible (769)
61 | 730 | 13 | N | Deducciones Autonómicas - Asturias - Por gastos de descendientes en centros de 0 a 3 años (770)
62 | 743 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición de libros de texto y material escolar (771)
63 | 756 | 13 | N | Deducciones Autonómicas - Asturias -  Otras deducciones (772)
64 | 769 | 13 | N | Deducciones Autonómicas - Asturias - Total deducciones autonómicas (511)
65 | 782 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10021>
66 | 791 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 792

# Anexo B.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "22"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 10 | 13 | N | Deducciones Autonómicas - Illes Balears - Por determinadas inversiones de mejora de sostenibilidad vivienda habitual (773)
7 | 23 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos adquisición libros de texto (774)
8 | 36 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos de aprendizaje extraescolar de idiomas extranjeros (775)
9 | 49 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones entidades destinadas investigación, desarrollo científico o tecnológico o innovación  (776)
10 | 62 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones, cesiones uso o contratos comodato y convenios colaboración empresarial  (777)
11 | 75 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos en primas de seguros individuales de salud (aplicables contribuyentes fallecidos antes 31/12/2015) (778)
12 | 88 | 13 | N | Deducciones Autonómicas - Illes Balears - Por inversión en la adquisición de acciones o participaciones sociales de nuevas entidades (779)
13 | 101 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones, cesiones uso o contrato de comodato y convenios colaboración, mecenazgo deportivo (780)
14 | 114 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones a determinadas entidades fomento lengua catalana (968)
15 | 127 | 13 | N | Deducciones Autonómicas - Illes Balears - Para declarentes con discapacidad física, psiquica o sensorial o con descendientes con esta condición  (969)
16 | 140 | 13 | N | Deducciones Autonómicas - Illes Balears -  Otras deducciones (781)
17 | 153 | 13 | N | Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (511)
18 | 166 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones con finalidad ecológica (782)
19 | 179 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones rehabilitación o conservación patrimonio histórico de Canarias (783)
20 | 192 | 13 | N | Deducciones Autonómicas - Canarias - Por cantidades destinadas restauración/rehabilitación/reparación bienes inmuebles declarados de Interés Cultural (784)
21 | 205 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de estudios (785)
22 | 218 | 13 | N | Deducciones Autonómicas - Canarias - Por trasladar residencia a otra isla para realizar actividad laboral cuenta ajena/actividad económica (786)
23 | 231 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones en metálico a descendientes menores 35 años para adquisición/rehabilitación primera vivienda habitual (787)
24 | 244 | 13 | N | Deducciones Autonómicas - Canarias - Por nacimiento o adopción de hijos (788)
25 | 257 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes con discapacidad y mayores de 65 años (789)
26 | 270 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de guardería (790)
27 | 283 | 13 | N | Deducciones Autonómicas - Canarias - Por familia numerosa (791)
28 | 296 | 13 | N | Deducciones Autonómicas - Canarias - Por inversión en vivienda habitual (792)
29 | 309 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de adecuación vivienda habitual por razón discapacidad (793)
30 | 322 | 9 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - NIF arrendador (794)
31 | 331 | 13 | N | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Importe (795)
32 | 344 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene NIF Nº identificación en País de residencia (796)
33 | 364 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral (797)
34 | 384 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral. 1 o cero (798)
35 | 385 | 13 | N | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Cantidades totales satisfechas al arrendador (799)
36 | 398 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes desempleados (800)
37 | 411 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de rehabilitación o reforma en vivienda (pdte. deducción exceso base ejercicios anteriores)  (801)
38 | 424 | 13 | N | Deducciones Autonómicas - Canarias - Otras deducciones (802)
39 | 437 | 13 | N | Deducciones Autonómicas - Canarias - Total deducciones autonómicas (511)
40 | 450 | 9 | An | Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con discapacidad - NIF arrendador (803)
41 | 459 | 13 | N | Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con  discapacidad - Importe (804)
42 | 472 | 20 | An | Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con discapacidad. Si no tiene NIF Nº identificación en País de residencia (805)
43 | 492 | 13 | N | Deducciones Autonómicas - Cantabria - Por cuidado de familiares (806)
44 | 505 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora. Importe 2013 y/o 2014 pendiente de aplicación (807)
45 | 518 | 9 | An | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - NIF persona/entidad  obras (808)
46 | 527 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - Importe deducción (809 )
47 | 540 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora generada 2015 a deducir en 2 años siguientes (810)
48 | 553 | 13 | N | Deducciones Autonómicas - Cantabria - Por donativos a fundaciones o al Fondo Cantabria Coopera (811)
49 | 566 | 13 | N | Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (812)
50 | 579 | 13 | N | Deducciones Autonómicas - Cantabria - Por inversión adquisición acciones/participaciones sociales nuevas entidades o reciente creación (813)
51 | 592 | 13 | N | Deducciones Autonómicas - Cantabria - Por gastos de enfermedad (814)
52 | 605 | 13 | N | Deducciones Autonómicas - Cantabria - Otras deducciones (815)
53 | 618 | 13 | N | Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (511)
54 | 631 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10022>
55 | 640 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 641

# Anexo B.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "23"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 10 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Para el fomento del autoempleo. Deducción 2012 pendiente de aplicación (816)
7 | 23 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (817)
8 | 36 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (818)
9 | 49 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (819)
10 | 62 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (820)
11 | 75 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (821)
12 | 88 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por cantidades para la Cooperación Internacional, lucha contra pobreza y exclusión social  (822)
13 | 101 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por familia numerosa (823)
14 | 114 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por donaciones con finalidad en investigación y desarrollo e innovación empresarial (824)
15 | 127 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por gastos en la adquisición de libros de texto y enseñanza de idiomas (825)
16 | 140 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento familiar no rumunerado de menores (826)
17 | 153 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento no remunerado de mayores de 65 años y/o discapacitados (827)
18 | 166 | 9 | An | Deducciones Autonómicas - Castilla-La Mancha -  Por arrendamiento de vivienda habitual por menores de 36 años. Nif del arrendador  (828)
19 | 175 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha -  Por arrendamiento de vivienda habitual por menores de 36 años. Importe (829)
20 | 188 | 20 | An | Deducciones Autonómicas - Castilla-La Mancha -  Por arrendamiento de vivienda habitual por menores de 36 años. Si no tiene NIF Nº identificación en País de residencia (830)
21 | 208 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Otras deducciones (831)
22 | 221 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (511)
23 | 234 | 13 | N | Deducciones Autonómicas - Castilla y León - Para contribuyentes afectados por discapacidad (832)
24 | 247 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales  (833)
25 | 260 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cantidades donadas a fundaciones (834)
26 | 273 | 13 | N | Deducciones Autonómicas - Castilla y León - Poro cantidades donadas para el fomento de la investigación, desarrollo e innovación (835)
27 | 286 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión en patrimonio histórico, cultural y natural  (836)
28 | 299 | 9 | An | Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años - Nif arrendador  (837)
29 | 308 | 13 | N | Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años - Importe  (838)
30 | 321 | 20 | An | Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual menores de 36 años. Si no tiene NIF Nº identificación en País de residencia (839)
31 | 341 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión instalaciones medioambientales/adaptación a personas con discapacidad en vvda.habitual (840)
32 | 354 | 8 | Num | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Fecha visado proyecto (841)
33 | 362 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Importe  (842)
34 | 375 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducción para el fomento de emprendimiento (843)
35 | 388 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones para el fomento del autoempleo mujeres, jóvenes y autónomos abandono actividad por crisis. Importe generado 2012 pdte. aplicación (964)
36 | 401 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones para el fomento del autoempleo mujeres, jóvenes y autónomos abandono actividad por crisis. Importe generado 2013 pdte. aplicación (844)
37 | 414 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones para el fomento del autoempleo mujeres, jóvenes y autónomos abandono actividad por crisis. Importe generado 2013 pdte. aplicación (845)
38 | 427 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2012 pdte. aplicación (965)
39 | 440 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2013 pdte. aplicación (966)
40 | 453 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2014 pdte. aplicación (846)
41 | 466 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2014 pdte. aplicación (847)
42 | 479 | 13 | N | Deducciones Autonómicas - Castilla y León - Por familia numerosa (848)
43 | 492 | 13 | N | Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (849)
44 | 505 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas (850)
45 | 518 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas en 2013  y/o 2014 (851)
46 | 531 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Nif persona empleada (852)
47 | 540 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Importe (853)
48 | 553 | 13 | N | Deducciones Autonómicas - Castilla y León - Por paternidad  (854)
49 | 566 | 13 | N | Deducciones Autonómicas - Castilla y León - Por gastos de adopción (855)
50 | 579 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuota Seg.Social empleados del hogar - Nif persona empleada (856)
51 | 588 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuota Seg.Social empleados del hogar - Importe (857)
52 | 601 | 13 | N | Deducciones Autonómicas - Castilla y León - Importe total aplicado  (858)
53 | 614 | 13 | N | Deducciones Autonómicas - Castilla y León - Otras deducciones (859)
54 | 627 | 13 | N | Deducciones Autonómicas - Castilla y León - Total deducciones autonómicas  (511)
55 | 640 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones fomento autoempleo mujeres y jóvenes y autónomos - Pendiente de aplicación (860)
56 | 653 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2013, 2014 y 2015. Importe generado 2013 pdte. aplicación (967)
57 | 666 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2013, 2014 y 2015. Importe generado 2014 pdte. aplicación (861)
58 | 679 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2013, 2014 y 2015. Importe generado 2015 pdte. aplicación  (862)
59 | 692 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10023>
60 | 701 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 702

# Anexo B.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "24"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 10 | 13 | N | Deducciones Autonómicas - Cataluña - Por nacimiento o adopción hijos (863)
7 | 23 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan el uso lengua catalana (864)
8 | 36 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan la investigación científica (865)
9 | 49 | 9 | An | Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - NIF arrendador (866)
10 | 58 | 13 | N | Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - Importe (867)
11 | 71 | 20 | An | Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - Si no tiene NIF Nº identificación en País de residencia (868)
12 | 91 | 13 | N | Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudios universitarios de master y doctorado (869)
13 | 104 | 13 | N | Deducciones Autonómicas - Cataluña - Para los contribuyentes que queden viudos (870)
14 | 117 | 13 | N | Deducciones Autonómicas - Cataluña - Por rehabilitación vivienda habitual (871)
15 | 130 | 13 | N | Deducciones Autonómicas - Cataluña - Por donaciones en beneficio del medio ambiente (872)
16 | 143 | 13 | N | Deducciones Autonómicas - Cataluña - Por inversión adquisición de acciones o participaciones sociales entidades nuevas o de creación reciente (873)
17 | 156 | 13 | N | Deducciones Autonómicas - Cataluña - Por inversión en acciones de entidades que cotizan en empresas en expansión (874)
18 | 169 | 13 | N | Deducciones Autonómicas - Cataluña - Otras deducciones (875)
19 | 182 | 13 | N | Deducciones Autonómicas - Cataluña - Total deducciones autonómicas  (511)
20 | 195 | 13 | N | Deducciones Autonómicas - Extremadura - Por adquisición o rehabilitación vivienda habitual para jóvenes y víctimas del terrorismo (876)
21 | 208 | 13 | N | Deducciones Autonómicas - Extremadura - Por trabajo dependiente (877)
22 | 221 | 13 | N | Deducciones Autonómicas - Extremadura - Por cuidado de familiares con discapacidad (878)
23 | 234 | 13 | N | Deducciones Autonómicas - Extremadura - Por acogimiento de menores (879)
24 | 247 | 13 | N | Deducciones Autonómicas - Extremadura - Por  partos múltiples (880)
25 | 260 | 13 | N | Deducciones Autonómicas - Extremadura - Por compra de material escolar (881)
26 | 273 | 13 | N | Deducciones Autonómicas - Extremadura - Por inversión en la adquisición de acciones o participaciones sociales (882)
27 | 286 | 13 | N | Deducciones Autonómicas - Extremadura - Por gastos de guardería para hijos menores de 4 años (883)
28 | 299 | 13 | N | Deducciones Autonómicas - Extremadura - Para contribuyentes viudos (884)
29 | 312 | 9 | An | Deducciones Autonómicas - Extremadura - Por arrendamiento vivienda habitual contribuyentes < 36 años - Nif arrendador (885)
30 | 321 | 13 | N | Deducciones Autonómicas - Extremadura - Por arrendamiento vivienda habitual contribuyentes < 36 años - Importe (886)
31 | 334 | 20 | An | Deducciones Autonómicas - Extremadura - Por arrendamiento vivienda habitual contribuyentes < 36 años - Si no tiene NIF Nº identificación en País de residencia (887)
32 | 354 | 13 | N | Deducciones Autonómicas - Extremadura - Por adquisición o rehabilitación segunda vivienda en el medio rural (888)
33 | 367 | 13 | N | Deducciones Autonómicas - Extremadura -  Otras deducciones (889)
34 | 380 | 13 | N | Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (511)
35 | 393 | 13 | N | Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (890)
36 | 406 | 13 | N | Deducciones Autonómicas - Galicia - Por familia numerosa (891)
37 | 419 | 13 | N | Deducciones Autonómicas - Galicia - Por cuidado hijos menores (892)
38 | 432 | 13 | N | Deducciones Autonómicas - Galicia - Por contribuyentes con discapacidad = > 65 años que precisan ayuda de terceras personas (893)
39 | 445 | 13 | N | Deducciones Autonómicas - Galicia - Por gastos de nuevas tecnologías en hogares gallegos (894)
40 | 458 | 9 | An | Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - NIF arrendador (895)
41 | 467 | 13 | N | Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - Importe (896)
42 | 480 | 20 | An | Deducciones Autonómicas - Galicia - Por alquiler vivienda habitual. Si no tiene NIF Nº identificación en País de residencia (897)
43 | 500 | 13 | N | Deducciones Autonómicas - Galicia - Por acogimiento familiar de menores (898)
44 | 513 | 13 | N | Deducciones Autonómicas - Galicia - Por creación nuevas empresas o ampliación actividad (899)
45 | 526 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación (900)
46 | 539 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones de entidades empresas en expansión Mercado Alternativo Bolsista (901)
47 | 552 | 13 | N | Deducciones Autonómicas - Galicia - Por donaciones finalidad en investigacion y desarrollo científico e innovación tecnológica (902)
48 | 565 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables (903)
49 | 578 | 20 | An | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables - Código de instalación (904)
50 | 598 | 13 | N | Deducciones Autonómicas - Galicia - Otras deducciones (905)
51 | 611 | 13 | N | Deducciones Autonómicas - Galicia - Total deducciones autonómicas (511)
52 | 624 | 13 | N | Deducciones Autonómicas - Madrid - Por nacimiento o adopción de hijos (906)
53 | 637 | 13 | N | Deducciones Autonómicas - Madrid - Por adopción internacional de niños (907)
54 | 650 | 13 | N | Deducciones Autonómicas - Madrid - Por acogimiento familiar de menores (908)
55 | 663 | 13 | N | Deducciones Autonómicas - Madrid - Por acogimiento no remunerado de mayores 65 años y/o con discapacidad (909)
56 | 676 | 9 | An | Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - NIF arrendador (910)
57 | 685 | 13 | N | Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - Importe (911)
58 | 698 | 20 | An | Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años. Si no tiene NIF Nº identificación en País de residencia  (912)
59 | 718 | 13 | N | Deducciones Autonómicas - Madrid - Por gastos educativos (913)
60 | 731 | 13 | N | Deducciones Autonómicas - Madrid - Para familias con dos o más descendientes e ingresos reducidos (914)
61 | 744 | 13 | N | Deducciones Autonómicas - Madrid - Por inversión en adquisición de acciones y participaciones sociales de nuevas entidades (915)
62 | 757 | 13 | N | Deducciones Autonómicas - Madrid -  Para el fomento del autoempleo de jóvenes menores de 35 años (916)
63 | 770 | 13 | N | Deducciones Autonómicas - Madrid - Por inversiones en entidades cotizadas en el Mercado Alternativo Bursátil (917)
64 | 783 | 13 | N | Deducciones Autonómicas - Madrid - Otras deducciones (918)
65 | 796 | 13 | N | Deducciones Autonómicas - Madrid - Total deducciones autonómicas (511)
66 | 809 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10024>
67 | 818 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 819

# Anexo B.5

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. | OBLIGATORIO | Constante "25"
4 | 8 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 10 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión vivienda habitual jóvenes edad igual/inferior 35 años (incluido rég. transitorio) (919)
7 | 23 | 13 | N | Deducciones Autonómicas - Murcia - Por donativos para la protección del patrimonio histórico Región Murcia (920)
8 | 36 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de guardería para hijos menores de 3 años (921)
9 | 49 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (922)
10 | 62 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (923)
11 | 75 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en la adquisición de acciones y participaciones sociales (924)
12 | 88 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en entidades cotizadas Mercado Alternativo Bursátil (925)
13 | 101 | 13 | N | Deducciones Autonómicas - Murcia - Otras deducciones (926)
14 | 114 | 13 | N | Deducciones Autonómicas - Murcia - Total deducciones autonómicas (511)
15 | 127 | 13 | N | Deducciones Autonómicas - La Rioja - Por nacimiento y adopción de segundo o ulterior hijo (927)
16 | 140 | 13 | N | Deducciones Autonómicas - La Rioja - Por inversión adquisición/rehabilitación vivienda habitual para jóvenes (928)
17 | 153 | 4 | Num | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Código municipio (929)
18 | 157 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Importe  (930)
19 | 170 | 13 | N | Deducciones Autonómicas - La Rioja - Por inversión rehabilitación vivienda habitual (931)
20 | 183 | 13 | N | Deducciones Autonómicas - La Rioja - Otras deducciones (932)
21 | 196 | 13 | N | Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (511)
22 | 209 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento, adopción o acogimiento familiar (933)
23 | 222 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento o adopción múltiples (934)
24 | 235 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento o adopción hijos con discapacidad (935)
25 | 248 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por familia numerosa (936)
26 | 261 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por custodia en guarderías y primer ciclo educación infantil hijos menores de 3 años (937)
27 | 274 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por conciliación del trabajo con la vida familiar (938)
28 | 287 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Para contribuyentes con un grado de discapacidad igual o superior al 33 por 100, de edad igual o superior a 65 años (939)
29 | 300 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por ascendientes > 75 años ó > 65 años que sean personas con discapacidad (940)
30 | 313 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por realización de labores no remuneradas en el hogar (941)
31 | 326 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por primera adquisición vivienda habitual para contribuyentes edad igual o inferior 35 años (942)
32 | 339 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición vivienda habitual por personas con discapacidad (943)
33 | 352 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades adquisición o rehabilitación vivienda habitual, procedentes ayudas públicas (944)
34 | 365 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de la vivienda habitual - NIF arrendador (945)
35 | 374 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de la vivienda habitual - Importe (946)
36 | 387 | 20 | An | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de vivienda habitual - Si no tiene NIF Nº identificación en País de residencia (947)
37 | 407 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - NIF arrendador (948)
38 | 416 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Importe (949)
39 | 429 | 20 | An | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Si no tiene NIF Nº identificación en País de residencia (950)
40 | 449 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades inversiones fuentes energía renovables en vivienda habitual (951)
41 | 462 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones con finalidad ecológica (952)
42 | 475 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (953)
43 | 488 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades donadas para la conservación, reparación y restauración de bienes (954)
44 | 501 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades destinadas a la conservación, reparación y restauración de bienes (955)
45 | 514 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por donaciones al fomento de la Lengua Valenciana (956)
46 | 527 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por contribuyentes con dos o más descendientes (957)
47 | 540 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (958)
48 | 553 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición material escolar (959)
49 | 566 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual  - NIF persona o entidad (960)
50 | 575 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual - Importe  (961)
51 | 588 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones importes dinerarios otros fines culturales (962)
52 | 601 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Otras deducciones (963)
53 | 614 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Total deduciones autonómicas (511)
54 | 627 | 9 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10025>
55 | 636 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 637

# I-D

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2015
Nº | Posic. | Long. | Tipo | Descripción |  | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. |  | OBLIGATORIO | Constante "100"
3 | 6 | 2 | Num | Página. |  | OBLIGATORIO | Constante "26"
4 | 8 | 1 | An | Fin de identificador de modelo. |  | OBLIGATORIO | Constante ">"
5 | 9 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 10 | 13 | N | Resultado declaración (2) - Base liquidable general sometida a gravamen [440]
7 | 23 | 13 | N | Resultado declaración (2) - Base liquidable del ahorro [445]
8 | 36 | 13 | N | Resultado declaración (2) - Cuota íntegra estatal [490]
9 | 49 | 13 | N | Resultado declaración (2) - Cuota íntegra autonómica [491]
10 | 62 | 13 | N | Resultado declaración (2) - Cuota líquida estatal [515]
11 | 75 | 13 | N | Resultado declaración (2) - Cuota líquida autonómica [516]
12 | 88 | 13 | N | Resultado declaración (2) - Resultado a ingresar o a devolver [610]
13 | 101 | 1 | Num | Resultado declaración (2) - Solicitud de suspensión ingreso cónyuge/Renuncia cobro devolución otro cónyuge. "1" o "0" [7]
14 | 102 | 13 | N | Declaración Complementaria (3) - Resultado de Declaración Complementaria [605]
15 | 115 | 1 | Num | Ingreso (4) - Casilla 610 positiva - NO FRACCIONA el pago [1]  "1" o "0"
16 | 116 | 1 | Num | Ingreso (4) - Casilla 610 positiva - SÍ FRACCIONA el pago [6] "1" o "0"
17 | 117 | 13 | N | Ingreso (4) - Casilla 610 positiva - Importe del ingreso [I1]
18 | 130 | 1 | Num | Ingreso (4) - Casilla 610 positiva - Forma de pago -"0" No consta; "1" Efectivo; "2" Adeudo en Cuenta; "3" Domiciliación
19 | 131 | 1 | Num | Opciones de pago 2º plazo (5) - NO DOMICILIA el pago [2]   "1" o "0"
20 | 132 | 1 | Num | Opciones de pago 2º plazo (5) - SÍ DOMICILIA el pago [3] "1" o "0"
21 | 133 | 13 | N | Opciones de pago 2º plazo (5) - Importe del 2º plazo [I2]
22 | 146 | 1 | Num | Devolución (6) - Casilla 610 negativa - "0" No consta, "1" Devolución y "2" renuncia devolución
23 | 147 | 13 | N | Devolución (6) - Casilla 610 negativa - Importe [D]
24 | 160 | 34 | An | Número de cuenta IBAN
25 | 194 | 9 | An | Identificador de Fin de registro. |  | OBLIGATORIO | Constante </T10026>
26 | 203 | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: |  | 204