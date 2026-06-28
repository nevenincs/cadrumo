# Pag. 1

Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
NNº PPoossiicc.. LLoonngg.. TTiippoo DDeessccrriippcciióónn VVaalliiddaacciióónn CCoonntteenniiddoo
1 1 17 An Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "<T100020140A0000>"
2 18 5 An Constante "<AUX>"
3 23 30 An Reservado para la Administración. Rellenar con blancos BLANCOS
4 53 1 An Idioma de la declaración (**) "E", "C", "G", "V"
5 54 39 An Reservado para la Administración. Rellenar con blancos BLANCOS
66 9933 44 AAnn VVeerrssiióónn ddeell PPrrooggrraammaa ((**))
7 97 4 An Reservado para la Administración. Rellenar con blancos BLANCOS
8 101 9 An NIF Empresa Desarrollo (**)
9 110 213 An Reservado para la Administración. Rellenar con blancos BLANCOS
10 323 6 An Constante "</AUX>"
Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo
11 329Variable An documento
15*** 18 An Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "</T100020140A0000>"
16*** 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total Variable
(**) A cumplimentar por las entidades desarrolladoras (EEDD)
Idioma de la declaración: (E) Castellano, (C) Catalán, (G) Gallego, (V) Valenciano
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# Pag. 2

Páginas Complementarias
Pág APARTADO Nº máximo apart. Nº máximo págs.
1 Vivienda habitual 8 1
4 Inmuebles no afectos AAEE 60 20
4 Inmuebles arrendados por ent.reg.atrib.rentas 60 20
4 Inmuebles afectos AAEE 60 20
5 (E1) Rtos. aaee estim. directa 6 2
6 (E2) Rtos. aaee estim. objetiva 6 3
7 (E3) Rtos. activ. agricolas 6 3
8 (F) Regímenes especiales 8 4
9 (G2) G/P sometidas a retención < 1 año 60 20
9 (G2) G/P de acciones < 1 año 60 20
9 (G2) G/P otros elementos patrimoniales < 1 año 40 20
10 (G3) G/P sometidas a retención > 1 año 60 20
10 (G3) G/P de acciones > 1 año 60 20
10 (G3) G/P de valores > 1 año 60 20
10 (G3) G/P otros elementos patrimoniales > 1 año 40 20
10 ((G4)) Impputación a 2014 G/P ejjercicios anteriores ((BIA)) 15 5
11 (G5) G/P difer. por reinversión 15 5
11 (G5) Imputación de 2014 G/P ejercicios anteriores (BIG) 15 5
13 Aport. sistemas previsión social 4 2
13 Aport. Sistemas previsión social a favor de discapacitados 4 2
13 Aport. patrim. proteg. discapacit. 4 2
13 Pens. Comppens. A favor cónyyugge 4 2
13 Aport. Deportistas profesionales 4 2
14 (K) Exceso no reducido. Régimen general 4 2
14 (K) Exceso no reducido. Discapacitados 4 2
14 (K) Exceso no reducido. Patrimonios protegidos 4 2
14 (K) Exceso no reducido. Deportistas profesionales 4 2

# Pag. 3

100-01
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "01"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 9 An Primer Declarante - NIF (01) OBLIGATORIO
7 19 15 A Primer Declarante - Primer apellido (02) OBLIGATORIO
8 34 15 A Primer Declarante - Segundo apellido (03)
9 49 15 A Primer Declarante - Nombre (04) OBLIGATORIO
10 64 1 A Primer Declarante - Sexo "H" Hombre, "M" Mujer (05) OBLIGATORIO
11 65 1 Num Primer Declarante -Estado Civil. "1" Soltero/a, "2" Casado/a, "3" Viudo/a, "4" Divorciado/a o Separado/a OBLIGATORIO
12 66 8 Num Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año < 2014 (10) OBLIGATORIO
13 74 1 Num Primer Declarante - Grado de discapacidad "0", "1", "2" o "3" (11)
14 75 1 Num Primer Declarante - Cambio de domicilio "1" o cero (13)
15 76 5 A Primer Declarante - Domicilio habitual - Tipo de Vía (15)
16 81 5 Num Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Vía INE
17 86 50 An Primer Declarante - Domicilio habitual - Nombre de la Vía Pública (16)
18 136 3 An Primer Declarante - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
1199 113399 55 NNum PPriimer DDecllarantte - DDomiiciilliio hhabbiittuall - NNúúmero dde CCasa ((1188))
20 144 3 An Primer Declarante - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
21 147 3 An Primer Declarante - Domicilio habitual - Bloque (20)
22 150 3 An Primer Declarante - Domicilio habitual - Portal (21)
23 153 3 An Primer Declarante - Domicilio habitual - Escalera (22)
24 156 3 An Primer Declarante - Domicilio habitual - Planta (23)
25 159 3 An Primer Declarante - Domicilio habitual - Puerta (24)
26 162 40 An Primer Declarante - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
27 202 30 An Primer Declarante - Domicilio habitual - Localidad / Población (26)
28 232 5 Num Primer Declarante - Domicilio habitual - Código postal (27)
29 237 5 Num Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
30 242 30 An Primer Declarante - Domicilio habitual - Nombre del Municipio (28)
31 272 2 Num Primer Declarante - Domicilio habitual - Código provincia. De "01" a "52".
32 274 20 An Primer Declarante - Domicilio habitual - Provincia (29)
33 294 9 Num Primer Declarante - Domicilio habitual - Teléfono fijo (30)
34 303 9 Num Primer Declarante - Domicilio habitual - Teléfono móvil (31)
35 312 9 Num Primer Declarante - Domicilio habitual - Núm. De Fax (32)
36 321 50 An Primer Declarante - Domicilio extranjero - Domicilio/Address (35)
37 371 40 An Primer Declarante - Domicilio extranjero - Datos complementarios del domicilio (36)
38 411 30 An Primer Declarante - Domicilio extranjero - Población / Ciudad (37)
39 441 100 An Primer Declarante - Domicilio extranjero - e-mail (38)
Página 3

# Pag. 4

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
40 541 10 An Primer Declarante - Domicilio extranjero - Código Postal (39)
41 551 30 An Primer Declarante - Domicilio extranjero - Provincia / Región / Estado (40)
42 581 30 An Primer Declarante - Domicilio extranjero - País. (41)
43 611 2 An Primer Declarante - Domicilio extranjero - Código País. Código país ISO-3166 (alfabético 2 letras). (42)
44 613 15 An Primer Declarante - Domicilio extranjero - Teléfono fijo (43)
45 628 15 An Primer Declarante - Domicilio extranjero - Teléfono móvil (44)
46 643 15 An Primer Declarante - Domicilio extranjero - Núm. Fax (45)
47 658 1 Num Datos adicionales vivienda - Vivienda 1.Titularidad "1", "2", "3" o "4" (50) OBLIGATORIO
48 659 5 Num Datos adicionales vivienda - Vivienda 1.Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) *
49 664 5 Num Datos adicionales vivienda - Vivienda 1.Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) *
50 669 1 Num Datos adicionales vivienda - Vivienda 1.Situación (clave) "1", "2", "3" o "4" (53)
51 670 20 An Datos adicionales vivienda - Vivienda 1.Referencia catastral (54)
52 690 1 Num Datos adicionales vivienda - Vivienda 2.Titularidad "0", "1", "2", "3" o "4" (50)
53 691 5 Num Datos adicionales vivienda - Vivienda 2. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) *
54 696 5 Num Datos adicionales vivienda - Vivienda 2. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) *
55 701 1 Num Datos adicionales vivienda - Vivienda 2.Situación (clave) "0", "1", "2", "3" o "4" (53)
56 702 20 An Datos adicionales vivienda - Vivienda 2. Referencia catastral (54)
57 722 1 Num Datos adicionales vivienda - Vivienda 3.Titularidad "0", "1", "2", "3" o "4" (50)
58 723 5 Num Datos adicionales vivienda - Vivienda 3. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) *
59 728 5 Num Datos adicionales vivienda - Vivienda 3. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) *
60 733 1 Num Datos adicionales vivienda - Vivienda 3. Situación (clave) "0", "1", "2", "3" o "4" (53)
61 734 20 An Datos adicionales vivienda - Vivienda 3. Referencia catastral (54)
62 754 1 Num Datos adicionales vivienda - Vivienda 4.Titularidad "0", "1", "2", "3" o "4" (50)
6633 775555 55 NNuumm DDaattooss aaddiicciioonnaalleess vviivviieennddaa - VViivviieennddaa 44. PPoorrcceennttaajjee ppaarrttiicciippaacciióónn PPrriimmeerr ddeeccllaarraannttee ((ttrreess eenntteerrooss, ddooss ddeecciimmaalleess)) ((5511)) *
64 760 5 Num Datos adicionales vivienda - Vivienda 4. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) *
65 765 1 Num Datos adicionales vivienda - Vivienda 4. Situación (clave) "0", "1", "2", "3" o "4" (53)
66 766 20 An Datos adicionales vivienda - Vivienda 4. Referencia catastral (54)
67 786 1 Num Datos adicionales vivienda - Vivienda 5.Titularidad "0", "1", "2", "3" o "4" (50)
68 787 5 Num Datos adicionales vivienda - Vivienda 5. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) *
69 792 5 Num Datos adicionales vivienda - Vivienda 5. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) *
70 797 1 Num Datos adicionales vivienda - Vivienda 5. Situación (clave) "0", "1", "2", "3" o "4" (53)
71 798 20 An Datos adicionales vivienda - Vivienda 5. Referencia catastral (54)
72 818 1 Num Datos adicionales vivienda - Vivienda 6.Titularidad "0", "1", "2", "3" o "4" (50)
73 819 5 Num Datos adicionales vivienda - Vivienda 6. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) *
74 824 5 Num Datos adicionales vivienda - Vivienda 6. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) *
75 829 1 Num Datos adicionales vivienda - Vivienda 6. Situación (clave) "0", "1", "2", "3" o "4" (53)
76 830 20 An Datos adicionales vivienda - Vivienda 6. Referencia catastral (54)
77 850 1 Num Datos adicionales vivienda - Vivienda 7.Titularidad "0", "1", "2", "3" o "4" (50)
78 851 5 Num Datos adicionales vivienda - Vivienda 7. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) *
79 856 5 Num Datos adicionales vivienda - Vivienda 7. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) *
80 861 1 Num Datos adicionales vivienda - Vivienda 7. Situación (clave) "0", "1", "2", "3" o "4" (53)
81 862 20 An Datos adicionales vivienda - Vivienda 7. Referencia catastral (54)
82 882 1 Num Datos adicionales vivienda - Vivienda 8.Titularidad "0", "1", "2", "3" o "4" (50)
83 883 5 Num Datos adicionales vivienda - Vivienda 8. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) *
Página 4

# Pag. 5

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
84 888 5 Num Datos adicionales vivienda - Vivienda 8. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) *
85 893 1 Num Datos adicionales vivienda - Vivienda 8. Situación (clave) "0", "1", "2", "3" o "4" (53)
86 894 20 An Datos adicionales vivienda - Vivienda 8. Referencia catastral (54)
87 914 9 An Datos adicionales vivienda - Nif Arrendador (55)
88 923 20 An Datos adicionales vivienda - Si no tiene NIF. Nº identificación en el país de residencia (59)
89 943 9 An Cónyuge - NIF (61)
90 952 15 A Cónyuge - Primer apellido (62)
91 967 15 A Cónyuge - Segundo apellido (63)
92 982 15 A Cónyuge - Nombre (64)
93 997 1 A Cónyuge - Sexo "H" Hombre, "M" Mujer (65)
94 998 8 Num Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero. (66)
95 1006 1 Num Cónyuge - Grado de discapacidad "0", "1", "2" o "3" (67)
96 1007 1 Num Cónyuge - No residente que no es contribuyente del I.R.P.F. - "1" o cero (68)
97 1008 1 Num Cónyuge - Cambio de domicilio "1" o cero (70)
98 1009 5 A Cónyuge - Domicilio habitual - Tipo de Vía (15)
99 1014 5 Num Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Vía INE
100 1019 50 An Cónyuge - Domicilio habitual - Nombre de la Vía Pública (16)
101 1069 3 An Cónyuge - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
102 1072 5 Num Cónyuge - Domicilio habitual - Número de Casa (18)
103 1077 3 An Cónyuge - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
104 1080 3 An Cónyuge - Domicilio habitual - Bloque (20)
105 1083 3 An Cónyuge - Domicilio habitual - Portal (21)
106 1086 3 An Cónyuge - Domicilio habitual - Escalera (22)
110077 11008899 33 AAnn CCóónnyyuuggee - DDoommiicciilliioo hhaabbiittuuaall - PPllaannttaa ((2233))
108 1092 3 An Cónyuge - Domicilio habitual - Puerta (24)
109 1095 40 An Cónyuge - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
110 1135 30 An Cónyuge - Domicilio habitual - Localidad / Población (26)
111 1165 5 Num Cónyuge - Domicilio habitual - Código postal (27)
112 1170 5 Num Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
113 1175 30 An Cónyuge - Domicilio habitual - Nombre del Municipio (28)
114 1205 2 Num Cónyuge - Domicilio habitual - Código provincia. De "01" a "52".
115 1207 20 An Cónyuge - Domicilio habitual - Provincia (29)
116 1227 9 Num Cónyuge - Domicilio habitual - Teléfono fijo (30)
117 1236 9 Num Cónyuge - Domicilio habitual - Teléfono móvil (33)
118 1245 9 Num Cónyuge - Domicilio habitual - Núm. De Fax (32)
119 1254 50 An Cónyuge - Domicilio extranjero - Domicilio/Address (35)
120 1304 40 An Cónyuge - Domicilio extranjero - Datos complementarios del domicilio (36)
121 1344 30 An Cónyuge - Domicilio extranjero - Población / Ciudad (37)
122 1374 100 An Cónyuge - Domicilio extranjero - e-mail (38)
123 1474 10 An Cónyuge - Domicilio extranjero - Código Postal (39)
124 1484 30 An Cónyuge - Domicilio extranjero - Provincia / Región / Estado (40)
125 1514 30 An Cónyuge - Domicilio extranjero - País (41)
126 1544 2 An Cónyuge - Domicilio extranjero - Código País (42)
127 1546 15 An Cónyuge - Domicilio extranjero - Teléfono fijo (43)
Página 5

# Pag. 6

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
128 1561 15 An Cónyuge - Domicilio extranjero - Teléfono móvil (44)
129 1576 15 An Cónyuge - Domicilio extranjero - Núm. Fax (45)
130 1591 12 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
131 1603 9 An Representante - N.I.F. (75)
132 1612 32 An Representante - Apellidos y nombre o razón social (76)
133 1644 20 An Fecha declaración - Lugar
134 1664 2 Num Fecha declaración - Fecha -Día
135 1666 10 A Fecha declaración - Fecha - Mes
136 1676 4 Num Fecha declaración - Fecha - Año
137 1680 34 An Número de cuenta IBAN
138 1714 13 Num Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
139 1727 21 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
140 1748 13 N Resultado de la declaración
141 1761 1 Num Fraccionamiento del pago. "1" o cero
142 1762 1 Num Domiciliación 2º plazo."1" o cero
143 1763 1 Num Renuncia a la devolución. "1" o cero
144 1764 1 Num Compensación entre cónyuges. "1" o cero
145 1765 20An Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
146 1785 13An SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
147 1798 9An Identificador de Fin de registro. OBLIGATORIO Constante </T10001>
148 1807 2An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total 1808
Página 6

# Pag. 7

100-02
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "02"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 9 An Hijos y descendientes - 1º - N.I.F. (80)
7 19 40 A Hijos y descendientes - 1º - Apellidos y nombre (81)
8 59 8 Num Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año < 2014 o cero (82)
9 67 8 Num Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
10 75 1 Num Hijos y descendientes - 1º - Grado discapacidad "0", "1", "2" o "3" (84)
11 76 1 An Hijos y descendientes - 1º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
12 77 1 An Hijos y descendientes - 1º - Otras situaciones clave:"1","2","3","4" o blanco (86)
13 78 9 An Hijos y descendientes - 2º - N.I.F. (80)
14 87 40 A Hijos y descendientes - 2º - Apellidos y nombre (81)
15 127 8 Num Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año < 2014 o cero (82)
16 135 8 Num Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año < 2014 o cero (83)
17 143 1 Num Hijos y descendientes - 2º - Grado discapacidad "0", "1", "2" o "3" (84)
18 144 1 An Hijos y descendientes - 2º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
1199 114455 11 AAnn HHiijjooss yy ddeesscceennddiieenntteess - 22º - OOttrraass ssiittuuaacciioonneess "11",,"22",,"33",,"44" oo bbllaannccoo ((8866))
20 146 9 An Hijos y descendientes - 3º - N.I.F. (80)
21 155 40 A Hijos y descendientes - 3º - Apellidos y nombre (81)
22 195 8 Num Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
23 203 8 Num Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
24 211 1 Num Hijos y descendientes - 3º - Grado discapacidad "0", "1", "2" o "3" (84)
25 212 1 An Hijos y descendientes - 3º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
26 213 1 An Hijos y descendientes - 3º - Otras situaciones "1","2","3","4" o blanco (86)
27 214 9 An Hijos y descendientes - 4º - N.I.F. (80)
28 223 40 A Hijos y descendientes - 4º - Apellidos y nombre (81)
29 263 8 Num Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
30 271 8 Num Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
31 279 1 Num Hijos y descendientes - 4º - Grado discapacidad "0", "1", "2" o "3" (84)
32 280 1 An Hijos y descendientes - 4º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
33 281 1 An Hijos y descendientes - 4º - Otras situaciones "1","2","3","4" o blanco (86)
34 282 9 An Hijos y descendientes - 5º - N.I.F. (80)
35 291 40 A Hijos y descendientes - 5º - Apellidos y nombre (81)
36 331 8 Num Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
37 339 8 Num Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
38 347 1 Num Hijos y descendientes - 5º - Grado discapacidad "0", "1", "2" o "3" (84)
39 348 1 An Hijos y descendientes - 5º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
Página 7

# Pag. 8

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
40 349 1 An Hijos y descendientes - 5º - Otras situaciones "1","2","3","4" o blanco (86)
41 350 9 An Hijos y descendientes - 6º - N.I.F. (80)
42 359 40 A Hijos y descendientes - 6º - Apellidos y nombre (81)
43 399 8 Num Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
44 407 8 Num Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
45 415 1 Num Hijos y descendientes - 6º - Grado discapacidad "0", "1", "2" o "3" (84)
46 416 1 An Hijos y descendientes - 6º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
47 417 1 An Hijos y descendientes - 6º - Otras situaciones "1","2","3","4" o blanco (86)
48 418 9 An Hijos y descendientes - 7º - N.I.F. (80)
49 427 40 A Hijos y descendientes - 7º - Apellidos y nombre (81)
50 467 8 Num Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
51 475 8 Num Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
52 483 1 Num Hijos y descendientes - 7º - Grado discapacidad "0", "1", "2" o "3" (84)
53 484 1 An Hijos y descendientes - 7º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
54 485 1 An Hijos y descendientes - 7º - Otras situaciones "1","2","3","4" o blanco (86)
55 486 9 An Hijos y descendientes - 8º - N.I.F. (80)
56 495 40 A Hijos y descendientes - 8º - Apellidos y nombre (81)
57 535 8 Num Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
58 543 8 Num Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
59 551 1 Num Hijos y descendientes - 8º - Grado discapacidad "0", "1", "2" o "3" (84)
60 552 1 An Hijos y descendientes - 8º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
61 553 1 An Hijos y descendientes - 8º - Otras situaciones "1","2","3","4" o blanco (86)
62 554 9 An Hijos y descendientes - 9º - N.I.F. (80)
6633 556633 4400 AA HHiijjooss yy ddeesscceennddiieenntteess - 99ºº - AAppeelllliiddooss yy nnoommbbrree ((8811))
64 603 8 Num Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
65 611 8 Num Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
66 619 1 Num Hijos y descendientes - 9º - Grado discapacidad "0", "1", "2" o "3" (84)
67 620 1 An Hijos y descendientes - 9º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
68 621 1 An Hijos y descendientes - 9º - Otras situaciones "1","2","3","4" o blanco (86)
69 622 9 An Hijos y descendientes - 10º - N.I.F. (80)
70 631 40 A Hijos y descendientes - 10º - Apellidos y nombre (81)
71 671 8 Num Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
72 679 8 Num Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
73 687 1 Num Hijos y descendientes - 10º - Grado discapacidad "0", "1", "2" o "3" (84)
74 688 1 An Hijos y descendientes - 10º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
75 689 1 An Hijos y descendientes - 10º - Otras situaciones "1","2","3","4" o blanco (86)
76 690 9 An Hijos y descendientes - 11º - N.I.F. (80)
77 699 40 A Hijos y descendientes - 11º - Apellidos y nombre (81)
78 739 8 Num Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
79 747 8 Num Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
80 755 1 Num Hijos y descendientes - 11º - Grado discapacidad "0", "1", "2" o "3" (84)
81 756 1 An Hijos y descendientes - 11º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
82 757 1 An Hijos y descendientes - 11º - Otras situaciones "1","2","3","4" o blanco (86)
83 758 9 An Hijos y descendientes - 12º - N.I.F. (80)
Página 8

# Pag. 9

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
84 767 40 A Hijos y descendientes - 12º - Apellidos y nombre (81)
85 807 8 Num Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (82)
86 815 8 Num Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2014 o cero (83)
87 823 1 Num Hijos y descendientes - 12º - Grado discapacidad "0", "1", "2" o "3" (84)
88 824 1 An Hijos y descendientes - 12º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
89 825 1 An Hijos y descendientes - 12º - Otras situaciones "1","2","3","4" o blanco (86)
90 826 2 Num Hijos y descendientes - Fallecido 2014 - Nº Orden (87)
91 828 8 Num Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
92 836 2 Num Hijos y descendientes - Fallecido 2014 - Nº Orden (87)
93 838 8 Num Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
94 846 9 An Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
95 855 9 An Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
96 864 9 An Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
97 873 9 An Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
98 882 9 An Hijos y descendientes - Otro progenitor - Nif (56)
99 891 40 A Hijos y descendientes - Otro progenitor - Apellidos y nombre (57)
100 931 1 Num Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla. "1" o cero. (58)
101 932 24 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
102 956 9 An Ascendientes mayores 65 años o discapacitados - 1º - N.I.F. (90)
103 965 40 A Ascendientes mayores 65 años o discapacitados - 1º - Apellidos y nombre (91)
104 1005 8 Num Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (92)
105 1013 1 Num Ascendientes mayores 65 años o discapacitados - 1º - Grado discapacidad "0", "1", "2" o "3" (93)
106 1014 1 An Ascendientes mayores 65 años o discapacitados - 1º - Vinculación clave:"1", "2" o blanco (94)
110077 11001155 11 AAnn AAsscceennddiieenntteess mmaayyoorreess 6655 aaññooss oo ddiissccaappaacciittaaddooss - 11ºº - CCoonnvviivveenncciiaa "22" aa "99" oo bbllaannccoo ((9955))
108 1016 9 An Ascendientes mayores 65 años o discapacitados - 2º - N.I.F. (90)
109 1025 40 A Ascendientes mayores 65 años o discapacitados - 2º - Apellidos y nombre (91)
110 1065 8 Num Ascendientes mayores 65 años o discapacitados - 2º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (92)
111 1073 1 Num Ascendientes mayores 65 años o discapacitados - 2º - Grado discapacidad "0", "1", "2" o "3" (93)
112 1074 1 An Ascendientes mayores 65 años o discapacitados - 2º - Vinculación clave:"1", "2" o blanco (94)
113 1075 1 An Ascendientes mayores 65 años o discapacitados - 2º - Convivencia "2" a "9" o blanco (95)
114 1076 9 An Ascendientes mayores 65 años o discapacitados - 3º - N.I.F. (90)
115 1085 40 A Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
116 1125 8 Num Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año < 2014 o cero (92)
117 1133 1 Num Ascendientes mayores 65 años o discapacitados - 3º - Grado discapacidad "0", "1", "2" o "3" (93)
118 1134 1 An Ascendientes mayores 65 años o discapacitados - 3º - Vinculación clave:"1", "2" o blanco (94)
119 1135 1 An Ascendientes mayores 65 años o discapacitados - 3º - Convivencia "2" a "9" o blanco (95)
120 1136 9 An Ascendientes mayores 65 años o discapacitados - 4º - N.I.F. (90)
121 1145 40 A Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
122 1185 8 Num Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2014 o cero (92)
123 1193 1 Num Ascendientes mayores 65 años o discapacitados - 4º - Grado discapacidad "0", "1", "2" o "3" (93)
124 1194 1 An Ascendientes mayores 65 años o discapacitados - 4º - Vinculación clave:"1", "2" o blanco (94)
125 1195 1 An Ascendientes mayores 65 años o discapacitados - 4º - Convivencia "2" a "9" o blanco (95)
126 1196 8 Num Devengo - Fecha de finalización del período impositivo (fallecimiento 2014) (DDMMAAAA) o cero (100)
127 1204 1 Num Opción de tributación. "1" Individual, "2" Conjunta. Campo OBLIGATORIO (101) (102) OBLIGATORIO
Página 9

# Pag. 10

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
128 1205 2 Num Comunidad/Ciudad autónoma de residencia en 2014 - Clave (103) Incluido en el fichero COMAUTO.TXT OBLIGATORIO
129 1207 1 A Asignación tributaria a la Iglesia Católica. "X" o blanco. (105)
130 1208 1 A Asignación de cantidades a actividades de interés general consideradas de interés social. "X" o blanco. (106)
131 1209 1 Num Borrador Declaración o datos fiscales 2015. Obtener tributación individual. "1" o cero (111)
132 1210 1 Num Declaración complementaria - Si es complementaria por atrasos de rendimientos del trabajo. "1" o cero (121)
133 1211 1 Num Declaración complementaria - Si es complementaria por haberse producido alguna de las circunstancias previstas. "1" o cero (122)
134 1212 1 Num Declaración complementaria - Si es complementaria a devolver. "1" o cero (123)
135 1213 1 Num Declaración complementaria - Si es complementaria por traslado de residencia a otro Estado miembro, "1" o cero (124)
136 1214 1 Num Declaración complementaria - Si es complementaria en supuestos distintos "1" o cero (120)
137 1215 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10002>
138 1224 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total 1225
Página 10

# Pag. 11

100-03
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "03"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 13 N (A) Rdto. Trabajo - Retribuciones dinerarias. Importe íntegro (001)
7 23 13 N Rdto. Trabajo - Retribuciones en especie - Valoracion (002)
8 36 13 N Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta (003)
9 49 13 N Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta repercutidos (004)
10 62 13 N Rdto. Trabajo - Retribuciones en especie - Importe íntegro (005)
11 75 13 N Rdto. Trabajo - Contribuciones Planes Pensiones y Mutualidades Previsión Social (006)
12 88 13 N Rdto. Trabajo - Contribuciones empresariales a seguros colectivos dependencia. Imputado al contribuyente (007)
13 101 13 N Rdto. Trabajo - Aportaciones al patrimonio protegido de discapacitados - Importe (008)
14 114 13 N Rdto. Trabajo - Reducciones (009)
15 127 13 N Rdto. Trabajo - Total ingresos íntegros computables (010)
16 140 13 N Rdto. Trabajo - Cotizaciones Seguridad Social/Mutual. grales. funcionarios/cotiz. colegios huerfanos (011)
17 153 13 N Rdto. Trabajo - Cuotas satisfechas a sindicatos (012)
18 166 13 N Rdto. Trabajo - Cuotas a colegios profesionales (013)
19 179 13 N Rdto. Trabajo - Gastos defensa jurídica derivados litigios con empleador (014)
20 192 13 N Rdto. Trabajo - Total gastos deducibles (015)
21 205 13 N Rdto. Trabajo - Rendimiento neto (016)
2222 221188 1133 NN RRddttoo. TTrraabbaajjoo -- RReedduucccciióónn oobbtteenncciióónn rreennddiimmiieennttooss ddee ttrraabbaajjoo. CCuuaannttííaa aapplliiccaabbllee ccoonn ccaarráácctteerr ggeenneerraall ((001177))
23 231 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Incremento trabajadores activos > 65 años (018)
24 244 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Incremento contribuyentes desempleados con traslado de residencia (019)
25 257 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Reducción adicional para trabajadores activos discapacitados (020)
26 270 13 N Rdto. Trabajo - Rendimiento neto reducido (021)
27 283 13 N (B) Rdto.cap.mob.- Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (022)
28 296 13 N Rdto.cap.mob.- Base imponible ahorro - Intereses de activos financieros con derecho a bonificación (023)
29 309 13 N Rdto.cap.mob.- Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (024)
30 322 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (025)
31 335 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros (026)
32 348 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (027)
33 361 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. Procedentes de rentas que tengan por causa la imposición de capitales (028)
34 374 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. derivados de valores de deuda subordinada o participaciones preferentes. Importe positivo (029)
35 387 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. derivados de valores de deuda subordinada o participaciones preferentes. Importe negativo (030)
36 400 13 N Rdto.cap.mob.- Base imponible ahorro - Total ingresos íntegros (031)
37 413 13 N Rdto.cap.mob.- Base imponible ahorro - Gastos fiscalmente deducibles (032)
38 426 13 N Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto (033)
39 439 13 N Rdto.cap.mob.- Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (034)
40 452 13 N Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto reducido (035)
41 465 13 N (B) Rdto.cap.mob.- Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (036)
42 478 13 N Rdto.cap.mob.- Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (037)
43 491 13 N Rdto.cap.mob.- Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (038)
44 504 13 N Rdto.cap.mob.- Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (039)
45 517 13 N Rdto.cap.mob.- Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (040)
Página 11

# Pag. 12

100-03
Nº Posic. Tipo Descripción Validación Contenido
46 530 13 N Rdto.cap.mob.- Base imponible general - Total ingresos íntegros (041)
47 543 13 N Rdto.cap.mob.- Base imponible general - Gastos fiscalmente deducibles (042)
48 556 13 N Rdto.cap.mob.- Base imponible general - Rendimiento neto (043)
49 569 13 N Rdto.cap.mob.- Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (044)
50 582 13 N Rdto.cap.mob.- Base imponible general - Rendimiento neto reducido (045)
51 595 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10003>
52 604 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 605
Página 12

# Pag. 13

100-04
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "04"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 2 Num Nº de hojas adicionales que se adjuntan
7 12 1 Tit C (C) Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Contribuyente "0" a "9" (050)
8 13 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (051) *
9 18 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje usufructo (3 enteros y 2 decimales) (052) *
10 23 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Naturaleza (053)
11 24 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Uso o destino. Clave (054)
12 25 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Situación "0", "1", "2", "3" o "4" (055)
13 26 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Referencia catastral (056)
14 46 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (057) *
15 51 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Número de días (058)
16 54 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Renta imputada (059)
17 67 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Ingresos íntegros computables (060)
18 80 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (061)
1199 9933 1133 NN CC BBiieenneess iinnmmuueebblleess nnoo aaffeeccttooss. RReellaacciióónn iinnmmuueebblleess yy rreennttaass. IInnmmuueebbllee 11. AArrrreennddaaddoo oo cceeddiiddoo. GGaassttooss ddeedduucciibblleess. IInntteerreesseess. IImmppoorrttee ((006622))
20 106 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (063)
21 119 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (064)
22 132 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto (065)
23 145 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (066)
24 158 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción rendimientos más de 2 años (067)
25 171 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento mínimo computable parentesco (068)
26 184 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto reducido (069)
27 197 1 Tit C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Contribuyente "0" a "9" (050)
28 198 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (051) *
29 203 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje usufructo (3 enteros y 2 decimales) (052) *
30 208 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Naturaleza (053)
31 209 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Uso o destino. Clave (054)
32 210 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Situación "0", "1", "2", "3" o "4" (055)
33 211 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Referencia catastral (056)
34 231 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (057) *
35 236 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Número de días (058)
36 239 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Renta imputada (059)
37 252 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Ingresos íntegros computables (060)
38 265 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (061)
Página 13

# Pag. 14

100-04
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
39 278 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe (062)
40 291 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (063)
41 304 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (064)
42 317 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto (065)
43 330 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (066)
44 343 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción rendimientos más de 2 años (067)
45 356 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento mínimo computable parentesco (068)
46 369 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto reducido (069)
47 382 1 Tit C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Contribuyente "0" a "9" (050)
48 383 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (051) *
49 388 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Porcentaje usufructo (3 enteros y 2 decimales) (052) *
50 393 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Naturaleza (053)
51 394 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Uso o destino. Clave (054)
52 395 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Situación "0", "1", "2", "3" o "4" (055)
53 396 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Referencia catastral (056)
54 416 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (057) *
55 421 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Número de días (058)
56 424 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Renta imputada (059)
57 437 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Ingresos íntegros computables (060)
58 450 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (061)
59 463 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Importe (062)
60 476 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (063)
61 489 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (064)
6622 550022 1133 NN CC BBiieenneess iinnmmuueebblleess nnoo aaffeeccttooss. RReellaacciióónn iinnmmuueebblleess yy rreennttaass. IInnmmuueebbllee 33. AArrrreennddaaddoo oo cceeddiiddoo. RReennddiimmiieennttoo nneettoo ((006655))
63 515 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (066)
64 528 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Reducción rendimientos más de 2 años (067)
65 541 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento mínimo computable parentesco (068)
66 554 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento neto reducido (069)
67 567 13 N Bienes inmuebles no afectos. Rentas totales . Suma de rentas inmobiliarias imputadas (070)
68 580 13 N Bienes inmuebles no afectos. Rentas totales . Suma rendimientos netos reducidos del capital inmobiliario (071)
69 593 3 Num Número de inmuebles en declaración conjunta (Reservado para la Administración)
70 596 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Contribuyente "0" a "9" (072)
71 597 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Nº Identificación fiscal entidad (073)
72 617 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Porcentaje titularidad (3 enteros y 2 decimales) (074) *
73 622 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Naturaleza (075)
74 623 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Situación "0", "1", "2", "3" o "4" (076)
75 624 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Referencia catastral (077)
76 644 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. No Residente (078)
77 645 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Contribuyente "0" a "9" (072)
78 646 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Nº Identificación fiscal entidad (073)
79 666 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Porcentaje titularidad (3 enteros y 2 decimales) (074) *
80 671 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Naturaleza (075)
81 672 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Situación "0", "1", "2", "3" o "4" (076)
Página 14

# Pag. 15

100-04
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
82 673 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Referencia catastral (077)
83 693 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. No Residente (078)
84 694 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Contribuyente "0" a "9" (072)
85 695 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Nº Identificación fiscal entidad (073)
86 715 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Porcentaje titularidad (3 enteros y 2 decimales) (074) *
87 720 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Naturaleza (075)
88 721 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Situación "0", "1", "2", "3" o "4" (076)
89 722 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Referencia catastral (077)
90 742 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. No Residente (078)
91 743 1 Tit C (D) Bienes inmuebles urbanos afectos. Inmueble 1. Contribuyente "0" a "9" (079)
92 744 5 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (080) *
93 749 5 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje usufructo (3 enteros y 2 decimales) (081) *
94 754 1 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Naturaleza (clave) (082)
95 755 1 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Situación "0", "1", "2", "3" o "4" (083)
96 756 20 An C Bienes inmuebles urbanos afectos. Inmueble 1. Referencia catastral (084)
97 776 1 Tit C Bienes inmuebles urbanos afectos. Inmueble 2. Contribuyente "0" a "9" (079)
98 777 5 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (080) *
99 782 5 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje usufructo (3 enteros y 2 decimales) (081) *
100 787 1 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Naturaleza (clave) (082)
101 788 1 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Situación "0", "1", "2", "3" o "4" (083)
102 789 20 An C Bienes inmuebles urbanos afectos. Inmueble 2. Referencia catastral (084)
103 809 1 Tit C Bienes inmuebles urbanos afectos. Inmueble 3. Contribuyente "0" a "9" (079)
104 810 5 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (080) *
110055 881155 55 NNuumm CC BBiieenneess iinnmmuueebblleess uurrbbaannooss aaffeeccttooss. IInnmmuueebbllee 33. PPoorrcceennttaajjee uussuuffrruuccttoo ((33 eenntteerrooss yy 22 ddeecciimmaalleess)) ((008811)) *
106 820 1 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Naturaleza (clave) (082)
107 821 1 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Situación "0", "1", "2", "3" o "4" (083)
108 822 20 An C Bienes inmuebles urbanos afectos. Inmueble 3. Referencia catastral (084)
109 842 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10004>
110 851 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 852
Página 15

# Pag. 16

100-05
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "05"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 3 Actividades a las que resulte aplicable un mismo régimen
7 11 1 Tit C (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Contribuyente "0" a "9" (086)
8 12 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Tipo actividad. Clave (Blanco o de "1" a "5") (087)
9 13 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Modalidad Normal (089) o Simplificada (090) "0", "1" o "2"
10 14 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Epígrafe IAE (088) (**)
11 19 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Criterio cobros/pagos. "1" o cero. (091)
12 20 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Explotación (092)
13 33 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Otros ingresos (093)
14 46 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Autoconsumo bienes/servicios (094)
15 59 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Transmisión elementos patrimoniales: exceso amortización deducida (095)
16 72 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Total ingresos computables (096)
17 85 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Consumos de explotación (097)
18 98 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Sueldos y salarios (098)
19 111 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Seguridad Social (099)
20 124 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros gastos de personal (100)
21 137 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Arrendamientos y cánones (101)
22 150 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Reparación y conservación (102)
23 163 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Servicios profesionales independientes (103)
24 176 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros servicios exteriores (104)
25 189 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Tributos fiscalmente deducibles (105)
26 202 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Gastos financieros (106)
27 215 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Amortizaciones (107)
28 228 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Pérdidas por deterioro (108)
29 241 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (convenios) (109)
30 254 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (gastos) (110)
31 267 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros conceptos fiscalmente deducibles (111)
32 280 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Suma (112)
33 293 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Normal - Provisiones (113)
34 306 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Normal - Total gastos deducibles (114)
35 319 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Diferencia (115)
36 332 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (116)
37 345 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Total gastos deducibles (117)
38 358 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Rdto. neto (118)
39 371 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Reducciones (119)
Página 16

# Pag. 17

100-05
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
40 384 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -1- Rdto. neto reducido (120)
41 397 1 Tit C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Contribuyente "0" a "9" (086)
42 398 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Tipo actividad.Clave (Blanco o de "1" a "5") (087)
43 399 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Modalidad Normal (089) o Simplificada (090) "0", "1" o "2"
44 400 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Epígrafe IAE (088) (**)
45 405 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Criterio cobros/pagos. "1" o cero. (091)
46 406 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Explotación (092)
47 419 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Otros ingresos (093)
48 432 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Autoconsumo bienes/servicios (094)
49 445 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Transmisión elementos patrimoniales: exceso amortización deducida (095)
50 458 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Total ingresos computables (096)
51 471 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Consumos de explotación (097)
52 484 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Sueldos y salarios (098)
53 497 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Seguridad Social (099)
54 510 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos de personal (100)
55 523 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Arrendamientos y cánones (101)
56 536 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Reparación y conservación (102)
57 549 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Servicios profesionales independientes (103)
58 562 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros servicios exteriores (104)
59 575 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Tributos fiscalmente deducibles (105)
60 588 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Gastos financieros (106)
61 601 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Amortizaciones (107)
62 614 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Pérdidas por deterioro (108)
63 627 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (convenios) (109)
64 640 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (gastos) (110)
65 653 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos fiscalmente deducibles (111)
66 666 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Suma de gastos (112)
67 679 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Normal - Provisiones (113)
68 692 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Normal - Total gastos deducibles (114)
69 705 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Diferencia (115)
70 718 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (116)
71 731 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Total gastos deducibles (117)
72 744 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto. neto (118)
73 757 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Reducciones (119)
74 770 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto.neto reducido (120)
75 783 1 Tit C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Contribuyente "0" a "9" (086)
76 784 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Tipo actividad.Clave (Blanco o de "1" a "5") (087)
77 785 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Modalidad Normal (089) o Simplificada (090) "0", "1" o "2"
78 786 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Epígrafe IAE (088) (**)
79 791 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Criterio cobros/pagos. "1" o cero. (091)
80 792 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Explotación (092)
81 805 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Otros ingresos (093)
82 818 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Autoconsumo bienes/servicios (094)
83 831 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Transmisión elementos patrimoniales: exceso amortización deducida (095)
Página 17

# Pag. 18

100-05
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
84 844 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Total ingresos computables (096)
85 857 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Consumos de explotación (097)
86 870 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Sueldos y salarios (098)
87 883 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Seguridad Social (099)
88 896 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos de personal (100)
89 909 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Arrendamientos y cánones (101)
90 922 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Reparación y conservación (102)
91 935 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Servicios profesionales independientes (103)
92 948 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros servicios exteriores (104)
93 961 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Tributos fiscalmente deducibles (105)
94 974 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Gastos financieros (106)
95 987 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Amortizaciones (107)
96 1000 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Pérdidas por deterioro (108)
97 1013 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (convenios) (109)
98 1026 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (gastos) (110)
99 1039 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos fiscalmente deducibles (111)
100 1052 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Suma de gastos (112)
101 1065 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Normal - Provisiones (113)
102 1078 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Normal - Total gastos deducibles (114)
103 1091 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Diferencia (115)
104 1104 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (116)
105 1117 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Total gastos deducibles (117)
106 1130 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto. neto (118)
107 1143 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Reducciones (119)
108 1156 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto.neto reducido (120)
109 1169 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Suma de rendimientos netos reducidos (121)
110 1182 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción ejercicio determinadas actividades (122)
111 1195 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción inicio actividad económica (123)
112 1208 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción por mantenimiento o creación de empleo (124)
113 1221 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Rendimiento neto reducido total (125)
114 1234 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10005>
115 1243 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1244
(**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignarán las tres cifras seguidas de dos blancos.
Página 18

# Pag. 19

100-06
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "06"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 2 actividades
7 11 5 An C (E2)Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Clasificación IAE (127) (**)
8 16 1 Tit C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Contribuyente titular actividad (126) "0" a "9"
9 17 1 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (128)
10 18 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Definición
11 42 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales) *
12 51 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales) *
13 62 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Definición
14 86 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales) *
15 95 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales) *
16 106 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Definición
17 130 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales) *
18 139 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales) *
1199 115500 2244 AA CC RRddttooss..aaccttiivv..eeccoonnóómm..eesstt..oobbjjeettiivvaa - AAcctt.. rreeaalliizz..//rrddttooss.. oobbtteenniiddooss - AAccttiivv.. 11ª - MMóódduulloo 44 - DDeeffiinniicciióónn
20 174 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales) *
21 183 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales) *
22 194 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Definición
23 218 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales) *
24 227 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales) *
25 238 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Definición
26 262 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales) *
27 271 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales) *
28 282 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Definición
29 306 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales) *
30 315 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales) *
31 326 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma) (129)
32 339 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo (130)
33 352 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (131)
34 365 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (132)
35 378 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (133) *
36 382 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (134) *
37 386 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (135) *
38 390 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (136) *
39 394 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (137) *
Página 19

# Pag. 20

100-06
Nº Posic. Long. Tipo Com Descripción Validación Contenido
40 398 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto de módulos (138)
41 411 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción de carácter general (139)
42 424 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (140)
43 437 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Gastos extraordinarios circunstancias excepcionales (141)
44 450 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Otras percepciones empresariales (142)
45 463 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª -Rendimiento neto actividad (143)
46 476 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción art. 32.1 Ley del Impuesto (144)
47 489 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rendimiento neto reducido (145)
48 502 5 An C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Clasificación IAE (127) (**)
49 507 1 Tit C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Contribuyente titular actividad (126) "0" a "9"
50 508 1 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (128)
51 509 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Definición
52 533 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales) *
53 542 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales) *
54 553 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Definición
55 577 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales) *
56 586 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales) *
57 597 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Definición
58 621 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales) *
59 630 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales) *
60 641 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Definición
61 665 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales) *
62 674 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales) *
6633 668855 2244 AA CC RRddttooss.aaccttiivv.eeccoonnóómm.eesstt.oobbjjeettiivvaa - AAcctt. rreeaalliizz.//rrddttooss. oobbtteenniiddooss - AAccttiivv. 22ª - MMóódduulloo 55 - DDeeffiinniicciióónn
64 709 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales) *
65 718 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales) *
66 729 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Definición
67 753 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales) *
68 762 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales) *
69 773 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Definición
70 797 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales) *
71 806 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales) *
72 817 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto previo (suma) (129)
73 830 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos al empleo (130)
74 843 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos a la inversion (131)
75 856 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto minorado (132)
76 869 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector especial (2 enteros y 2 decimales) (133) *
77 873 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (134) *
78 877 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de temporada (2 enteros y 2 decimales) (135) *
79 881 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de exceso (2 enteros y 2 decimales) (136) *
80 885 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (137) *
81 889 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto de módulos (138)
82 902 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción de carácter general (139)
83 915 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (140)
Página 20

# Pag. 21

100-06
Nº Posic. Long. Tipo Com Descripción Validación Contenido
84 928 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Gastos extraordinarios circunstancias excepcionales (141)
85 941 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Otras percepciones empresariales (142)
86 954 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª -Rendimiento neto actividad (143)
87 967 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción art. 32.1 Ley del Impuesto (144)
88 980 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rendimiento neto reducido (145)
89 993 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Suma rendimientos netos reducidos (148)
90 1006 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Reducción por mantenimiento o creación de empleo (149)
91 1019 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas (150)
92 1032 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10006>
93 1041 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1042
(**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos
blancos.
Página 21

# Pag. 22

100-07
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "07"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 2 Actividades
7 11 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Clave actividad: de "0" a "9" (152)
8 12 1 Tit C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Contribuyente titular de actividad: de "0" a "9" (151)
9 13 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Criterio cobros/pagos: "1" ó "0" (153)
10 14 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Ingresos íntegros
11 25 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Índice
12 31 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Rdto. base producto
13 42 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Ingresos íntegros
14 53 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Índice
15 59 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Rdto. base producto
16 70 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Ingresos íntegros
17 81 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Índice
18 87 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Rdto. base producto
1199 9988 1111 NN CC RRddttooss. aaggrríícc.ggaannaadd.yy ffoorreesstt. eesstt. oobbjjeettiivvaa -AAcctt. rreeaalliizz.//rrddttooss- AAccttiivv 11ª - PPrroodduuccttoo 44º - IInnggrreessooss íínntteeggrrooss
20 109 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 4º - Índice
21 115 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 4º - Rdto. base producto
22 126 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Ingresos íntegros
23 137 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Índice
24 143 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Rdto. base producto
25 154 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Ingresos íntegros
26 165 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Índice
27 171 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Rdto. base producto
28 182 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Ingresos íntegros
29 193 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Índice
30 199 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Rdto. base producto
31 210 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Ingresos íntegros
32 221 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Índice
33 227 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Rdto. base producto
34 238 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Ingresos íntegros
35 249 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Índice
36 255 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Rdto. base producto
37 266 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Ingresos íntegros
38 277 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Índice
Página 22

# Pag. 23

100-07
Nº Posic. Long. Tipo Com Descripción Validación Contenido
39 283 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Rdto. base producto
40 294 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Ingresos íntegros
41 305 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Índice
42 311 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Rdto. base producto
43 322 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Ingresos íntegros
44 333 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Índice
45 339 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Rdto. base producto
46 350 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Ingresos íntegros
47 361 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Índice
48 367 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Rdto. base producto
49 378 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Total ingresos íntegros (154)
50 389 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto previo (suma) (155)
51 400 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones (156)
52 411 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Amortización inmovilizado (157)
53 422 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto minorado (158)
54 433 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Medios ajenos (2 enteros y 2 decimales) (159) *
55 437 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Utiliz. personal asalariado (2 enteros y 2 decimales) (160) *
56 441 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (161) *
57 445 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (162) *
58 449 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º, >50 % (2 enteros y 2 decimales) Índice 2 (162) Ver NOTA *
59 453 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Activ.agricultura ecológica y/o cultivos en tierras de regadío (2 enteros y 2 decimales) Índice 1 (163) Ver NO *
60 457 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Activ.agricultura ecológica y/o cultivos en tierras de regadío (2 enteros y 2 decimales) Índice 2 (163) *
61 461 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales) (164) *
6622 446655 44 NNuumm CC RRddttooss. aaggrríícc.ggaannaadd.yy ffoorreesstt. eesstt. oobbjjeettiivvaa --AAcctt. rreeaalliizz.//rrddttooss-- AAccttiivv 11ª -- IInndd. ccoorrrreecctt.--DDeetteerrmmiinnaaddaass aaccttiivviiddaaddeess ffoorreessttaalleess ((22 eenntteerrooss yy 22 ddeecciimmaalleess)) ((116655)) *
63 469 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto de módulos (166)
64 482 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción carácter general (167)
65 495 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Diferencia (168)
66 508 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción agricultores jóvenes (169)
67 521 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Gastos extraordinarios por circunstancias excepcionales (170)
68 534 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto (171)
69 547 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones rendimientos generados más 2 años o forma irregular (172)
70 560 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto reducido (173)
71 573 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Clave actividad: de "0" a "9" (152)
72 574 1 Tit C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Contribuyente titular de actividad: de "0" a "9" (151)
73 575 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Criterio cobros/pagos: "1" ó "0" (153)
74 576 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Ingresos íntegros
75 587 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Índice
76 593 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Rdto. base producto
77 604 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Ingresos íntegros
78 615 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Índice
79 621 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Rdto. base producto
80 632 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Ingresos íntegros
81 643 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Índice
Página 23

# Pag. 24

100-07
Nº Posic. Long. Tipo Com Descripción Validación Contenido
82 649 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Rdto. base producto
83 660 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Ingresos íntegros
84 671 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Índice
85 677 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Rdto. base producto
86 688 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Ingresos íntegros
87 699 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Índice
88 705 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Rdto. base producto
89 716 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Ingresos íntegros
90 727 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Índice
91 733 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Rdto. base producto
92 744 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Ingresos íntegros
93 755 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Índice
94 761 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Rdto. base producto
95 772 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Ingresos íntegros
96 783 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Índice
97 789 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Rdto. base producto
98 800 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Ingresos íntegros
99 811 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Índice
100 817 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Rdto. base producto
101 828 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Ingresos íntegros
102 839 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Índice
103 845 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Rdto. base producto
104 856 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Ingresos íntegros
110055 886677 66 AAnn CC RRddttooss. aaggrríícc.ggaannaadd.yy ffoorreesstt. eesstt. oobbjjeettiivvaa -AAcctt. rreeaalliizz.//rrddttooss- AAccttiivv 22ªª - PPrroodduuccttoo 1111ºº - ÍÍnnddiiccee
106 873 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Rdto. base producto
107 884 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Ingresos íntegros
108 895 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Índice
109 901 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Rdto. base producto
110 912 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Ingresos íntegros
111 923 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Índice
112 929 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Rdto. base producto
113 940 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Total ingresos íntegros (154)
114 951 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto previo (suma) (155)
115 962 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones (156)
116 973 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Amortizacion inmovilizado (157)
117 984 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto minorado (158)
118 995 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Medios ajenos (2 enteros y 2 decimales) (159) *
119 999 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Utiliz. personal asalariado (2 enteros y 2 decimales) (160) *
120 1003 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (161) *
121 1007 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (162) *
122 1011 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º, >50 % (2 enteros y 2 decimales) Índice 2 (162) Ver NOTA *
123 1015 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Activ.agricultura ecológica y/o cultivos en tierras de regadío (2 enteros y 2 decimales) Índice 1 (163) Ver NO *
124 1019 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Activ.agricultura ecológica y/o cultivos en tierras de regadío (2 enteros y 2 decimales) Índice 2 (163) *
Página 24

# Pag. 25

100-07
Nº Posic. Long. Tipo Com Descripción Validación Contenido
125 1023 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales) (164) *
126 1027 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Determinadas actividades forestales (2 enteros y 2 decimales) (165) *
127 1031 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto de módulos (166)
128 1044 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción carácter general (167)
129 1057 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Diferencia (168)
130 1070 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción agricultores jóvenes (169)
131 1083 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Gastos extraordinarios por circunstancias excepcionales (170)
132 1096 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto (171)
133 1109 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones rendimientos generados más 2 años o forma irregular (172)
134 1122 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto reducido (173)
135 1135 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Suma rendimientos netos reducidos (178)
136 1148 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Reducción por mantenimiento o creación de empleo (179)
137 1161 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Rendimiento neto reducido total (180)
138 1174 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10007>
139 1183 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1184
NOTA: Cumplimentar sólo cuando el índice 2 sea distinto al índice 1.
Página 25

# Pag. 26

100-08
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "08"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 3 imputaciones
7 11 1 Tit C (F) Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (181)
8 12 20 An C Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - NIF Entidad (182)
9 32 1 Num C Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país (183)
10 33 4 Num C Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Porcentaje participación (2 enteros y dos decimales) (184) *
11 37 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (185)
12 50 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones y minoraciones (186)
13 63 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto computable (187)
14 76 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto atribuido por la entidad (188)
15 89 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. deuda subordinada o preferentes. Positivo (189)
16 102 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. deuda subordinada o preferentes. Negativo (190)
17 115 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto atribuido (191)
18 128 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Reducciones y minoraciones (192)
1199 114411 1133 NN CC RReeggss. eessppeecciiaalleess - RRééggiimmeenn aattrriibbuucciióónn rreennttaass - EEnnttiiddaadd 11 - RRddttooss. ccaappiittaall iinnmmoobbiilliiaarriioo - RRddttoo. nneettoo ccoommppuuttaabbllee ((119933))
20 154 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. neto atribuido (194)
21 167 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducciones y minoraciones (195)
22 180 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. neto computable (196)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
23 193 13 N C generación igual o inferior a un año (B.I.general) - Ganancias no derivadas de transmisiones, atribuidas por la entidad(197)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
24 206 13 N C generación igual o inferior a un año (B.I.general) - Ganancias derivadas de transmisiones, atribuidas por la entidad (198)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
25 219 13 N C generación igual o inferior a un año (B.I.general) - Pérdidas atribuidas por la entidad (199)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
26 232 13 N C integrar B.I. ahorro) - Ganancias atribuidas por la entidad (201)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
27 245 13 N C integrar B.I. ahorro) - Ganancias transmisión valores por deuda subordinada o preferentes (202)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
28 258 13 N C integrar B.I. ahorro) - Pérdidas atribuidas por la entidad (203)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
29 271 13 N C integrar B.I. ahorro) - Pérdidas transmisión valores por deuda subordinada o preferentes (204)
Página 26

# Pag. 27

100-08
Nº Posic. Long. Tipo Com Descripción Validación Contenido
30 284 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Retenciones e ingresos a cuenta. - Retenciones e ingresos a cuenta atribuidos por la entidad (205)
31 297 1 Tit C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (181)
32 298 20 An C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - NIF Entidad (182)
33 318 1 Num C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Si ha consgnado NIF de otro país (183)
34 319 4 Num C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Porcentaje participación (2 enteros y dos decimales) (184) *
35 323 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (185)
36 336 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones y minoraciones (186)
37 349 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto computable (187)
38 362 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto atribuido por la entidad (188)
39 375 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. deuda subordinada o preferentes. Positivo (189)
40 388 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. deuda subordinada o preferentes. Negativo (190)
41 401 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto atribuido (191)
42 414 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Reducciones y minoraciones (192)
43 427 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto computable (193)
44 440 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. neto atribuido (194)
45 453 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducciones y minoraciones (195)
46 466 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. neto computable (196)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
47 479 13 N C generación igual o inferior a un año (B.I.general) - Ganancias no derivadas de transmisiones, atribuidas por la entidad (197)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
48 492 13 N C generación igual o inferior a un año (B.I.general) - Ganancias derivadas de transmisiones, atribuidas por la entidad (198)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
4499 550055 1133 NN CC ggeenneerraacciióónn iigguuaall oo iinnffeerriioorr aa uunn aaññoo ((BB.II.ggeenneerraall)) - PPéérrddiiddaass aattrriibbuuiiddaass ppoorr llaa eennttiiddaadd ((119999))
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
50 518 13 N C integrar B.I. ahorro) - Ganancias atribuidas por la entidad (201)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
51 531 13 N C integrar B.I. ahorro) - Ganancias transmisión valores por deuda subordinada o preferentes (202)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
52 544 13 N C integrar B.I. ahorro) - Pérdidas atribuidas por la entidad (203)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
53 557 13 N C integrar B.I. ahorro) - Pérdidas transmisión valores por deuda subordinada o preferentes (204)
54 570 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Retenciones e ingresos a cuenta. - Retenciones e ingresos a cuenta atribuidos por la entidad (205)
55 583 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. capital mobiliario - Rdto. integrar base imponible general - Total rdto. neto computable (210)
56 596 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. capital mobiliario - Rdto. integrar base imponible ahorro - Total rdto. neto atribuido por la entidad (211)
57 609 13 N Regs. especiales - Régimen atribución rentas - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Total Rdto. deuda subordinada o preferentes. Positivo (212)
58 622 13 N Regs. especiales - Régimen atribución rentas - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Total Rdto. deuda subordinada o preferentes. Negativo (213)
59 635 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. capital inmobiliario - Total rdto. neto computable (214)
60 648 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. actividades económicas - Total rdto. neto computable (215)
Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período generación
61 661 13 N igual o inferior a un año (B.I. general) Total ganancias no derivadas de transmisiones atribuidas por la entidad (216)
Página 27

# Pag. 28

100-08
Nº Posic. Long. Tipo Com Descripción Validación Contenido
Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período generación
62 674 13 N igual o inferior a un año (B.I.general) - Total ganancias derivadas de transmisiones, atribuidas por la entidad (217)
Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período generación
63 687 13 N igual o inferior a un año (B.I. general) - Total pérdidas atribuidas por la entidad (218)
64 700 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - Derivadas transmisión - Total ganancias atribuidas por la entidad (220)
Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (B.I.
65 713 13 N ahorro) - Total ganancias transmisión valores por deuda subordinada o preferentes (221)
66 726 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - Derivadas transmisión - Total pérdidas atribuidas por la entidad (222)
Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (B.I.
67 739 13 N ahorro) - Total pérdidas transmisión va lores por deuda subordinada o preferentes (223)
68 752 13 N Regs. especiales - Régimen atribución rentas - Total - Retenciones e ingresos a cuenta - Total retenciones e ingresos atribuidos (594)
69 765 1 Tit C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. Contribuyente "0" a "9" (225)
70 766 9 An C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. N.I.F. Entidad (226)
71 775 1 An C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (227)
72 776 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Base imponible imputada (228)
73 789 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. invers. empres. (229)
74 802 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. creación empleo (230)
75 815 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (231)
76 828 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. doble impos. internac. (232)
77 841 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. Ret.e.ingresos cta. - Retenc. e ingresos a cta. imputados (233)
78 854 1 Tit C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. Contribuyente "0" a "9" (225)
79 855 9 An C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. N.I.F. Entidad (226)
80 864 1 An C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (227)
8811 886655 1133 NN CC RReeggss. eessppeecciiaalleess - AAggrruuppaacc., uuttee - EEnnttiiddaadd 22- IImmppuutt. bbaassee iimmppoonn. yy ddeedduucc. - BBaassee iimmppoonniibbllee iimmppuuttaaddaa ((222288))
82 878 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. invers. empres. (229)
83 891 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. creación empleo (230)
84 904 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (231)
85 917 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. doble impos. internac. (232)
86 930 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. Ret.e.ingresos cta. - Retenc. e ingresos a cta. imputados (233)
87 943 13 N Regs. especiales - Agrupac., ute - Total base imponible imputada (235)
88 956 13 N Regs. especiales - Agrupac., ute - Total Retenciones e ingresos a cta. imputados (595)
89 969 1 Tit C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Contribuyente "0" a "9" (236)
90 970 24 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Denominación entidad no residente (237)
91 994 1 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Criterio imput. temporal. Clave (blanco, "1" ó "2") (238)
92 995 13 N C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Importe imputación (239)
93 1008 1 Tit C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Contribuyente "0" a "9" (236)
94 1009 24 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Denominación entidad no residente (237)
95 1033 1 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Criterio imput. temporal. Clave (blanco, "1" ó "2") (238)
96 1034 13 N C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Importe imputación (239)
97 1047 13 N Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Total importe de la imputación (240)
98 1060 1 Tit Regs. especiales - Imputac. rentas derechos imagen - Contribuyente que debe efectuar la imputacion. "0" a "9" (241)
99 1061 25 An Regs. especiales - Imputac. rentas derechos imagen - NIF o denominación persona/entidad cesionaria derechos imagen (242)
100 1086 25 An Regs. especiales - Imputac. rentas derechos imagen - NIF o denominación persona/entidad relación laboral (243)
Página 28

# Pag. 29

100-08
Nº Posic. Long. Tipo Com Descripción Validación Contenido
101 1111 13 N Regs. especiales - Imputac. rentas derechos imagen - Cantidad a imputar (244)
102 1124 1 Tit C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Contribuyente "0" a "9" (245)
103 1125 24 An C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Denominación Institución (246)
104 1149 13 N C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Importe imputación (247)
105 1162 1 Tit C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Contribuyente "0" a "9" (245)
106 1163 24 An C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Denominación Institución (246)
107 1187 13 N C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Importe imputación (247)
108 1200 13 N Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - Total importe de la imputación (250)
109 1213 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10008>
110 1222 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1223
Página 29

# Pag. 30

100-09
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "09"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 10 2 Num Nº hojas adicionales que se adjuntan
7 12 13 N (G1) Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En metálico - Importe (251)
8 25 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Valoración (252)
9 38 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta (253)
10 51 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta repercutidos (254)
11 64 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Importe computable (255)
12 77 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Pérdidas patrimoniales derivadas de estos juegos (256)
13 90 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Ganancias patrimoniales netas (257)
14 103 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En metálico - Importe (258)
15 116 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Valoración (259)
16 129 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta (260)
17 142 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta repercutidos (261)
18 155 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Importe computable (262)
19 168 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Subvenciones/ayudas adquisión/rehabilitación vivienda habitual (263)
20 181 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Ganancias patrimoniales vecinos, aprovechamientos forestales (264)
21 194 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Renta básica emancipación (265)
2222 220077 1133 NN GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimmoonniiaalleess nnoo ddeerriivvaann ttrraannssmmiissiióónn -- OOttrraass GGaannaanncciiaass//ppéérrddiiddaass -- IImmppoorrttee ggaannaanncciiaass ((226666))
23 220 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe pérdidas (267)
24 233 1 Tit C (G2) Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (268)
25 234 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - N.I.F. (269)
26 243 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados positivos - Ganancias (270)
27 256 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados negativos - Pérdidas (271)
28 269 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (268)
29 270 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - N.I.F. (269)
30 279 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados positivos - Ganancias (270)
31 292 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados negativos - Pérdidas (271)
32 305 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (268)
33 306 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (269)
34 315 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados positivos - Ganancias (270)
35 328 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados negativos - Pérdidas (271)
36 341 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Totales - Total ganancias netas (274)
37 354 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Totales - Total pérdidas netas (275)
38 367 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
39 370 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Contribuyente "0" a "9" (276)
40 371 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Denominación valores (277)
41 391 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Importe global (278)
42 404 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Valor adquisición global (279)
43 417 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe obtenido (280)
44 430 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe obtenido (281)
Página 30

# Pag. 31

100-09
Nº Posic. Long. Tipo Com Descripción Validación Contenido
45 443 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe computable (282)
46 456 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Contribuyente "0" a "9" (276)
47 457 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Denominación valores (277)
48 477 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Importe global (278)
49 490 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Valor adquisición global (279)
50 503 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe obtenido (280)
51 516 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe obtenido (281)
52 529 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe computable (282)
53 542 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Contribuyente "0" a "9" (276)
54 543 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Denominación valores (277)
55 563 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Importe global (278)
56 576 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Valor adquisición global (279)
57 589 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe obtenido (280)
58 602 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe obtenido (281)
59 615 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe computable (282)
60 628 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Totales - Ganancias. Importe obtenido (284)
61 641 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Totales - Pérdidas. Importe computable (285)
62 654 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
63 657 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (286)
64 658 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (288)
65 659 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Clave "0" a "4" (289)
66 660 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Ref. catastral (290)
67 680 8 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Fecha transmisión (291)
68 688 8 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Fecha adquisición (292)
69 696 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Valor transmisión (293)
70 709 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Valor adquisición (294)
7711 772222 1133 NN CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn aaddqquuiirriiddoo ccoonn uunn aaññoo oo mmeennooss ddee aanntteellaacciióónn aa ffeecchhaa ttrraannssmmiissiióónn - OOttrrooss eelleemmeennttooss - EElleemmeennttoo 11 - DDiiffeerreenncciiaa nneeggaattiivvaa - PPéérrddiiddaa oobbtteenniiddaa ((229955))
72 735 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (296)
73 748 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (297)
74 761 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta reinversión viv. habitual (299)
75 774 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia no exenta (300)
76 787 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia no exenta imputable (301)
77 800 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Afectos - Reducción (licencia autotaxis) (302)
78 813 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia reducida (303)
79 826 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia patrimonial reducida no exenta imputable (304)
80 839 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (287)
81 840 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (286)
82 841 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (288)
83 842 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Clave "0" a "4" (289)
84 843 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Ref. catastral (290)
85 863 8 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Fecha transmisión (291)
86 871 8 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Fecha adquisición (292)
87 879 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Valor transmisión (293)
88 892 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Valor adquisición (294)
89 905 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (295)
90 918 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable (296)
91 931 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida (297)
92 944 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia exenta reinversión viv. habitual (299)
93 957 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia no exenta (300)
Página 31

# Pag. 32

100-09
Nº Posic. Long. Tipo Com Descripción Validación Contenido
94 970 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia no exenta imputable (301)
95 983 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Afectos - Reducción (licencia autotaxis) (302)
96 996 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia reducida (303)
97 1009 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia patrimonial reducida no exenta imputable (304)
98 1022 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (287)
99 1023 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Totales - Total pérdida imputable (308)
100 1036 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Totales - No afectos - Total ganancia no exenta imputable (309)
101 1049 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Totales - Afectos - Total ganancia reducida imputable (310)
102 1062 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
103 1065 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10009>
104 1074 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1075
Página 32

# Pag. 33

100-10
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "10"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 10 2 Num Nº hojas adicionales que se adjuntan
7 12 1 Tit C (G3) Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (311)
8 13 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - N.I.F. (312)
9 22 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados positivos - Ganancias (313)
10 35 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados negativos - Pérdidas (314)
11 48 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (311)
12 49 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - N.I.F. (312)
13 58 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados positivos - Ganancias (313)
14 71 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados negativos - Pérdidas (314)
15 84 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (311)
16 85 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (312)
17 94 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados positivos - Ganancias (313)
18 107 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados negativos - Pérdidas (314)
19 120 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Totales - Total ganancias netas (315)
20 133 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Totales - Total pérdidas netas (316)
21 146 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
22 149 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 1 - Contribuyente "0" a "9" (317)
23 150 20 An C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 1 - Denominación valores (318)
24 170 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 1 - Importe global (319)
25 183 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 1 - Valor adquisición global (320)
26 196 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe obtenido (321)
27 209 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe computable (322)
28 222 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe obtenido (323)
29 235 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe computable (324)
30 248 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 2 - Contribuyente "0" a "9" (317)
31 249 20 An C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 2 - Denominación valores (318)
32 269 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 2 - Importe global (319)
33 282 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 2 - Valor adquisición global (320)
34 295 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe obtenido (321)
35 308 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe computable (322)
36 321 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe obtenido (323)
37 334 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe imputable (324)
38 347 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 3 - Contribuyente "0" a "9" (317)
39 348 20 An C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 3 - Denominación valores (318)
40 368 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 3 - Importe global (319)
41 381 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 3 - Valor adquisición global (320)
42 394 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe obtenido (321)
43 407 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe computable (322)
44 420 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe obtenido (323)
45 433 13 N C Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe imputable (324)
46 446 13 N Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Totales - Ganancias. Importe computable (325)
47 459 13 N Ganancias/pérdidas patrim. deriv. transmisión acciones - Mercados oficiales - Totales - Pérdidas. Importe computable (326)

# Pag. 34

100-10
48 472 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
49 475 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 1 - Contribuyente "0" a "9" (327)
50 476 20 An C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 1 - Denominación valores (328)
51 496 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 1 - Importe global (329)
52 509 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 1 - Valor adquisición global (330)
53 522 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 1 - Resultados - Ganancias. Importe obtenido y computable (331)
54 535 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 1 - Resultados - Pérdidas. Importe obtenido (332)
55 548 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 1 - Resultados - Pérdidas. Importe computable (333)
56 561 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 2 - Contribuyente "0" a "9" (327)
57 562 20 An C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 2 - Denominación valores (328)
58 582 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 2 - Importe global (329)
59 595 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 2 - Valor adquisición global (330)
60 608 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 2 - Resultados - Ganancias. Importe obtenido y computable (331)
61 621 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 2 - Resultados - Pérdidas. Importe obtenido (332)
62 634 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 2 - Resultados - Pérdidas. Importe imputable (333)
63 647 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 3 - Contribuyente "0" a "9" (327)
64 648 20 An C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 3 - Denominación valores (328)
65 668 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 3 - Importe global (329)
66 681 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 3 - Valor adquisición global (330)
67 694 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 3 - Resultados - Ganancias. Importe obtenido y computable (331)
68 707 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 3 - Resultados - Pérdidas. Importe obtenido (332)
69 720 13 N C Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Entidad 3 - Resultados - Pérdidas. Importe imputable (333)
70 733 13 N Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Totales - Ganancias. Importe computable (335)
71 746 13 N Ganancias/pérdidas patrim. deriv. transmisión valores deuda subordinada o participaciones preferentes - Totales - Pérdidas. Importe computable (336)
72 759 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
73 762 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (337)
74 763 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (339)
75 764 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Clave "0" a "4" (340)
76 765 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Ref. catastral (341)
77 785 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Fecha transmisión (342)
7788 779933 88 NNuumm CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm.. ddeerriivv.. ttrraannssmmiissiióónn -- OOttrrooss eelleemmeennttooss -- EElleemmeennttoo 11 -- FFeecchhaa aaddqquuiissiicciióónn ((334433))
79 801 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Valor transmisión (344)
80 814 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Valor adquisición (345)
81 827 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (346)
82 840 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (347)
83 853 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (348)
84 866 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Parte ganancia susceptible reducción (349)
85 879 4 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Años permanencia hasta 31-12-94 (350)
86 883 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Reducción aplicable (351)
87 896 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida (352)
88 909 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta 50 por 100 (353)
89 922 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta reinversión viv. habitual (354)
90 935 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida no exenta (355)
91 948 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida no exenta imputable (356)
92 961 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Reducción (licencia autotaxis) (357)
93 974 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia reducida (358)
94 987 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia exenta 50 por 100 (359)
95 1000 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia patrimonial reducida no exenta (360)
96 1013 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia patrimonial reducida no exenta imputable (361)
97 1026 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (338)
98 1027 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (337)
99 1028 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (339)
100 1029 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Clave "0" a "4" (340)
101 1030 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Ref. catastral (341)
102 1050 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Fecha transmisión (342)

# Pag. 35

100-10
103 1058 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Fecha adquisición (343)
104 1066 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Valor transmisión (344)
105 1079 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Valor adquisición (345)
106 1092 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (346)
107 1105 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable (347)
108 1118 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida (348)
109 1131 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Parte ganancia susceptible reducción (349)
110 1144 4 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Años permanencia hasta 31-12-94 (350)
111 1148 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Reducción aplicable (351)
112 1161 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida (352)
113 1174 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia exenta 50 por 100 (353)
114 1187 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia exenta reinversión viv. habitual (354)
115 1200 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida no exenta (355)
116 1213 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida no exenta imputable (356)
117 1226 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Reducción (licencia autotaxis) (357)
118 1239 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia reducida (358)
119 1252 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia exenta 50 por 100 (359)
120 1265 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia patrimonial reducida no exenta (360)
121 1278 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia patrimonial reducida no exenta imputable (361)
122 1291 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (338)
123 1292 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - Total pérdida imputable (363)
124 1305 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - No afectos - Total ganancia reducida no exenta imputable (364)
125 1318 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - Afectos - Total ganancia reducida imputable (365)
126 1331 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
127 1334 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10010>
128 1343 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1344

# Pag. 36

100-11
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "11"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº hojas adicionales que se adjuntan
7 11 1 Tit C (G4) Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Ganancia 1 - Contribuyente "0" a "9" (370)
8 12 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Ganancia 1 - Importe ganancia (371)
9 25 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Ganancia 2 - Contribuyente "0" a "9" (370)
10 26 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Ganancia 2 - Importe ganancia (371)
11 39 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Ganancia 3 - Contribuyente "0" a "9" (370)
12 40 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Ganancia 3 - Importe ganancia (371)
13 53 13 N Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Total ganancias (372)
14 66 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Pérdida 1 - Contribuyente "0" a "9" (373)
15 67 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Pérdida 1 - Importe pérdida (374)
16 80 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Pérdida 1 - Importe pérdidas por transmisión deuda subordinada o preferentes (375)
17 93 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Pérdida 2 - Contribuyente "0" a "9" (373)
18 94 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Pérdida 2 - Importe pérdida (374)
19 107 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Pérdida 2 - Importe pérdidas por transmisión deuda subordinada o preferentes (375)
2200 112200 11 TTiitt CC GGananciias//péérddiiddas pattriim. dderiiv. ttransmiisiióón ((BBII ahhorro)) - IImputtaciióón 22001144 ejjerciiciios antteriiores - PPéérddiidda 33 - CConttriibbuyentte ""00"" a ""99"" ((337733))
21 121 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Pérdida 3 - Importe pérdida (374)
22 134 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Pérdida 3 - Importe pérdidas por transmisión deuda subordinada o preferentes (375)
23 147 13 N Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Total pérdidas (376)
24 160 13 N Ganancias/pérdidas patrim. deriv. transmisión (BI ahorro) - Imputación 2014 ejercicios anteriores - Total pérdidas por transmisión deuda subordinada o preferentes (377)
25 173 1 Tit C (G5) Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 diferimiento por reinversión - Ganancia 1 - Contribuyente "0" a "9" (378)
26 174 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 diferimiento por reinversión - Ganancia 1 - Importe ganancia (379)
27 187 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 diferimiento por reinversión - Ganancia 2 - Contribuyente "0" a "9" (378)
28 188 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 diferimiento por reinversión - Ganancia 2 - Importe ganancia (379)
29 201 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 diferimiento por reinversión - Ganancia 3 - Contribuyente "0" a "9" (378)
30 202 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 diferimiento por reinversión - Ganancia 3 - Importe ganancia (379)
31 215 13 N Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 diferimiento por reinversión - Total ganancia (380)
32 228 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Ganancia 1 - Contribuyente "0" a "9" (381)
33 229 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Ganancia 1 - Importe Ganancia (382)
34 242 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Ganancia 2 - Contribuyente "0" a "9" (381)
35 243 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Ganancia 2 - Importe Ganancia (382)
36 256 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Ganancia 3 - Contribuyente "0" a "9" (381)
37 257 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Ganancia 3 - Importe Ganancia (382)
38 270 13 N Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Total ganancia (383)
39 283 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Pérdida 1 - Contribuyente "0" a "9" (384)
40 284 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Pérdida 1 - Importe pérdida (385)
41 297 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Pérdida 2 - Contribuyente "0" a "9" (384)
Página 36

# Pag. 37

100-11
Nº Posic. Long. Tipo Com Descripción Validación Contenido
42 298 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Pérdida 2 - Importe pérdida (385)
43 311 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Pérdida 3 - Contribuyente "0" a "9" (384)
44 312 13 N C Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Pérdida 3 - Importe pérdida (385)
45 325 13 N Ganancias/pérdidas patrim. deriv. transmisión (BI general) - Imputación 2014 ganancias/pérdidas ejercicios anteriores - Total pérdida (386)
46 338 13 N (G6) Exención por reinversión ganancia patrimonial 2014 transmisión vivienda habitual - Importe transmisión susceptible reinversión (387)
47 351 13 N Exención por reinversión ganancia patrimonial 2014 transmisión vivienda habitual - Ganancia patrimonial consecuencia transmisión (388)
48 364 13 N Exención por reinversión ganancia patrimonial 2014 transmisión vivienda habitual - Importe reinvertido hasta 31-12-2014 adquisición nueva vivienda (389)
49 377 13 N Exención por reinversión ganancia patrimonial 2014 transmisión vivienda habitual - Importe se compromete reinvertir 2 años siguientes (390)
50 390 13 N Exención por reinversión ganancia patrimonial 2014 transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (391)
51 403 1 Tit (G7) Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (392)
52 404 2 Num Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones1 (393)
53 406 1 Tit Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente2 "0" a "9" (394)
54 407 2 Num Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones2 (395)
55 409 13 N (G8) Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar en base imponible general - Suma ganancias (396)
56 422 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar base imponible general - Suma pérdidas (397)
57 435 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar base imponible general - Saldo neto - Diferencia positiva (398)
58 448 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar base imponible general - Saldo neto - Diferencia negativa (399)
59 461 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar base imponible ahorro - Suma ganancias (400)
60 474 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar base imponible ahorro - Suma pérdidas (401)
61 487 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar base imponible ahorro - Saldo neto positivo (402)
62 500 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar base imponible ahorro - Saldo neto negativo ganancias y pérdidas imputables a 2014 (405)
63 513 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2014 - A integrar base imponible ahorro - Saldo neto negativo de pérdidas por transmisión valores a compensar con rdtos. capital mobiliario (406)
64 526 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10011>
65 535 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
TTottall: 553366
Página 37

# Pag. 38

100-12
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo yy pággina. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página.Resto saldos netos negativos ganancias/pérdidas de valores de deuda subordinada o preferentes OBLIGATORIO Constante "12"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Base imponible general y base imponible ahorro - Integración y compensación rdtos. capital mobiliario (B.I. ahorro) - Saldo neto positivo rdto. capital mobiliario imputable a 2014 (415)
7 23 13 N Base imponible general y base imponible ahorro - Integración y compensación rdtos. capital mobiliario (B.I. ahorro) - Saldo neto negativo rdtos. capital mobiliario imputable a 2014 (416)
8 36 13 N Base imponible ggeneral yy base imponible ahorro - Integgración yy compensación rdtos. capital mobiliario ((B.I. ahorro)) - Saldo neggativo de valores de deuda subordinada o preferentes a compensar ((417))
9 49 13 N Base imponible general y base imponible ahorro - BI general - Saldo neto positivo ganancias/pérdidas 2014 a integrar base imponible general (398)
10 62 13 N Base imponible general y base imponible ahorro - BI general - Resto saldos netos negativos rdtos.capital mobiliario 2010-2013 derivados de valores de deuda subordinada o preferentes(419)
11 75 13 N Base imponible general y base imponible ahorro - BI general - Resto saldos netos negativos ganancias/pérdidas 2010-2013 derivados de transmisión valores de deuda subordinada o preferentes (420)
12 88 13 N Base imponible general y base imponible ahorro - BI general - Resto saldos netos negativos rdtos.capital mobiliario derivados de valores de deuda subordinada o preferentes (421)
13 101 13 N Base imponible general y base imponible ahorro - BI general - Resto saldos netos negativos ganancias/pérdidas derivados de transmisión valores de deuda subordinada o preferentes (422)
14 114 13 N Base imponible general y base imponible ahorro - BI general - Saldos netos negativos ganancias/pérdidas 2010-2013 pendientes de compensación (423)
15 127 13 N Base imponible ggeneral yy base imponible ahorro - BI ggeneral - Saldo neto rendimientos a integgrar en base imponible ggeneral/imputaciones renta ((424))
16 140 13 N Base imponible general y base imponible ahorro - BI general - Compensaciones - Saldos netos negativos ganancias/pérdidas 2010-2012 (425)
17 153 13 N Base imponible general y base imponible ahorro - BI general - Compensaciones - Saldo neto negativo ganancias/pérdidas 2013 (426)
18 166 13 N Base imponible general y base imponible ahorro - BI general - Compensaciones - Saldo neto negativo ganancias/pérdidas 2014 (427)
19 179 13 N Base imponible general y base imponible ahorro - BI general - Base imponible general (430)
20 192 13 N Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas 2014 (402)
21 205 13 N Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas que no deriven transmisión de deuda subordinada o preferentes 2010-2013 (432)
22 218 13 N Base imponible ggeneral yy base imponible ahorro - BI ahorro - Compensaciones - Saldos netos neggativos gganancias/pérdidas derivados transmisión de deuda subordinada o preferentes 2010-2013 ((433))
23 231 13 N Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario de deuda subordinada o preferentes 2010-2013 (434)
24 244 13 N Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldo neto negativo rdtos.capital mobiliario derivado de valores de deuda subordinada o preferentes (435)
25 257 13 N Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rdtos.capital mobiliario derivado de valores de deuda subordinada o preferentes (415)
26 270 13 N Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos rdtos.capital mobiliario que no deriven de deuda subordinada o preferentes 2010-2013 (437)
27 283 13 N Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos rdtos.capital mobiliario que deriven de deuda subordinada o preferentes 2010-2013 (438)
28 296 13 N Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos ganancias/pérdidas de transmisión valores de deuda subordinada o preferentes 2010-2013 (439)
29 309 13 N Base imponible ggeneral yy base imponible ahorro - BI ahorro - Compensaciones - Saldo neto neggativo gganancias/pérdidas de transmisión de valores de deuda subordinada o preferentes 2014 ((440))
30 322 13 N Base imponible general y base imponible ahorro - BI ahorro - Base imponible del ahorro (445)
31 335 13 N Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo ganancias/pérdidas 2014 B.I general (446)
Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo ganancias/pérdidas 2014 que no derivan transmisión valores por
32 348 13 N deuda subordinada o preferentes B.I ahorro (405)
Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo rdtos.capital mobiliario 2014 que no derivan de deuda
33 361 13 N subordinada o preferentes B.I ahorro (416)
BBaassee iimmppoonniibbllee ggeenneerraall yy bbaassee iimmppoonniibbllee aahhoorrrroo -- IImmppoorrtteess ppeennddiieenntteess ccoommppeennssaarr 44 eejjeerrcciicciiooss ssiigguuiieenntteess -- SSaallddoo nneettoo nneeggaattiivvoo ggaannaanncciiaass//ppéérrddiiddaass 22001144 ddee ddeeuuddaa ssuubboorrddiinnaaddaa oo pprreeffeerreenntteess BB.II
34 374 13 N ahorro (449)
Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo rdtos.capital mobiliario 2014 de deuda subordinada o preferentes
35 387 13 N B.I ahorro (450)
36 400 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10012>
37 409 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 410

# Pag. 39

100-13
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "13"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 13 N (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidad familiar tributación conjunta (451)
7 23 1 Tit Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 1 "0" a "9" (452)
8 24 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2009 a 2013 1 (453)
9 37 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 de contribuciones a seguros colectivos de dependencia 1 (454)
10 50 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones 2014 1 (455)
11 63 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuciones seguros colectivos de dependencia 1 (456)
12 76 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción 1 (457)
13 89 1 Tit Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 2 "0" a "9" (452)
14 90 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2009 a 2013 2 (453)
15 103 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 de contribuciones a seguros colectivos de dependencia 2 (454)
16 116 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones 2014 2 (455)
17 129 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuciones seguros colectivos de dependencia 2 (456)
18 142 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción 2 (457)
19 155 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total derecho reducción (458)
20 168 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones cónyuge del contribuyente - Total derecho reducción (459)
21 181 1 Num Nº hojas adicionales que se adjuntan
2222 118822 11 TTiitt CC RReedduucccciioonneess bbaassee iimmppoonniibbllee -- AAppoorrttaacciioonneess aa ffaavvoorr ppeerrssoonnaass ccoonn ddiissccaappaacciiddaadd -- CCoonnttrriibbuuyyeennttee 11 "00" aa "99" ((446600))
23 183 9 An C Reducciones base imponible - Aportaciones a favor personas con discapacidad - NIF persona con discapacidad 1 (461)
24 192 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Excesos pendientes reducir 1 (462)
25 205 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2014 propia persona discapacidad 1 (463)
26 218 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2014 parientes o tutores 1 (464)
27 231 1 Tit C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Contribuyente 2 "0" a "9" (460)
28 232 9 An C Reducciones base imponible - Aportaciones a favor personas con discapacidad - NIF persona con discapacidad 2 (461)
29 241 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Excesos pendientes reducir 2 (462)
30 254 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2014 propia persona discapacidad 2 (463)
31 267 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2014 parientes o tutores 2 (464)
32 280 13 N Reducciones base imponible - Aportaciones a favor personas con discapacidad - Total con derecho a reducción (465)
33 293 1 Tit Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (466)
34 294 9 An Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 1 (467)
35 303 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 1 (468)
36 316 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2014 1 (469)
37 329 1 Tit Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (466)
38 330 9 An Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 2 (467)
39 339 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 2 (468)
40 352 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2014 2 (469)
41 365 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Total con derecho a reducción (470)
42 378 1 Tit Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Contribuyente 1 "0" a "9" (471)
43 379 9 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 1 (472)
44 388 20 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si no tiene NIF Nº identificación en país residencia 1 (473)
45 408 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 1 (474)
Página 39

# Pag. 40

100-13
Nº Posic. Long. Tipo Com Descripción Validación Contenido
46 421 1 Tit Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Contribuyente 2 "0" a "9" (471)
47 422 9 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 2 (472)
48 431 20 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si no tiene NIF Nº identificación en país residencia 2 (473)
49 451 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 2 (474)
50 464 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Total derecho reducción (475)
51 477 1 Tit Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 1 "0" a "9" (476)
52 478 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Excesos pendientes reducir 2009-2013 1 (477)
53 491 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones 2014 1 (478)
54 504 1 Tit Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 2 "0" a "9" (476)
55 505 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Excesos pendientes reducir 200-2013 2 (477)
56 518 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones 2014 2 (478)
57 531 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Total con derecho a reducción (479)
58 544 13 N (J) Base liquidable general/base liquidable ahorro - Determinación base general - Base imponible general (430)
59 557 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Tributación conjunta (480)
60 570 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social (régimen general) (481)
61 583 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social cónyuge (482)
62 596 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social personas discapacidad (483)
63 609 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones patrimonios protegidos personas discapacidad (484)
64 622 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Pensiones compensatorias/anualidades alimentos (485)
65 635 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Cuotas afiliación y demás aportaciones (486)
66 648 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones mutualidades prev. soc. deportistas profesionales (487)
67 661 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Base liquidable general (488)
68 674 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Compensación bases liquidables generales negativas (489)
69 687 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Base liquidable general sometida a gravamen (490)
70 700 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10013>
71 709 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
TToottaall:: 771100
Página 40

# Pag. 41

100-14
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "14"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 13 N (J) Base liquidable general/base liquidable ahorro (continuación) - Determinación base ahorro - Base imponible ahorro (445)
7 23 13 N Base liquidable general/base liquidable ahorro (continuación) - Determinación base ahorro - Remanente reducciones no aplicadas - Reducción tributación conjunta (491)
8 36 13 N Base liquidable general/base liquidable ahorro (continuación) - Determinación base ahorro - Remanente reducciones no aplicadas - Reducción pensiones comp./anualidades alimentos (492)
9 49 13 N Base liquidable general/base liquidable ahorro (continuación) - Determinación base ahorro - Cuotas de afiliación y demás aportaciones (493)
10 62 13 N Base liquidable general/base liquidable ahorro (continuación)- Determinación base ahorro - Base liquidable del ahorro (495)
11 75 1 Tit (K) Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 1 "0" a "9" (496)
12 76 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2014 1 (497)
13 89 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuciones 2014 a seguros colectivos dependencia no aplicadas 1 (498)
14 102 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 2 "0" a "9" (496)
15 103 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2014 2 (497)
16 116 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuciones 2014 a seguros colectivos dependencia no aplicadas 2 (498)
17 129 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 1 "0" a "9" (499)
18 130 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2014 no aplicadas 1 (500)
19 143 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 2 "0" a "9" (499)
20 144 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2014 no aplicadas 2 (500)
21 157 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 3 "0" a "9" (499)
22 158 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2014 no aplicadas 3 (500)
23 171 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 4 "0" a "9" (499)
24 172 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2014 no aplicadas 4 (500)
25 185 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 5 "0" a "9" (499)
26 186 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2014 no aplicadas 4 (500)
27 199 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 6 "0" a "9" (499)
28 200 13 N Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2014 no aplicadas 4 (500)
29 213 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (501)
30 214 13 N Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2014 no aplicadas 1 (502)
31 227 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (501)
32 228 13 N Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2014 no aplicadas 2 (502)
33 241 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 1 "0" a "9" (503)
34 242 13 N Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2014 no aplicadas 1 (504)
35 255 1 Tit Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 2 "0" a "9" (503)
36 256 13 N Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2014 no aplicadas 2 (504)
37 269 13 N (L) Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe (505)
38 282 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe cálculo gravamen autonómico (506)
39 295 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe (507)
40 308 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe cálculo gravamen autonómico (508)
41 321 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe (509)
42 334 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe cálculo gravamen autonómico (510)
43 347 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe (511)
44 360 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe cálculo gravamen autonómico (512)
45 373 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo personal y familiar (515)
46 386 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe total cálculo gravamen autonómico (516)
Página 41

# Pag. 42

100-14
Nº Posic. Long. Tipo Descripción Validación Contenido
47 399 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen estatal (517)
48 412 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen estatal (518)
49 425 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen autonómico (519)
50 438 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen autonómico (520)
51 451 13 N (M) Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable ahorro (521)
52 464 13 N Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable general (522)
53 477 13 N Datos adicionales - Anualidades para alimentos a favor de los hijos. Importe (523)
54 490 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10014>
55 499 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 500
Página 42

# Pag. 43

100-15
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "15"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N (N) Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla 490 - Parte estatal (524)
7 23 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla 490 - Parte autonómica (525)
8 36 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala gravamen complementaria - Parte estatal (526)
9 49 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general Impuesto importe casilla 517 - Parte estatal (527)
10 62 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala gravamen complementaria - Parte estatal (528)
11 75 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota derivada escala gravamen general estatal (529)
12 88 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota derivada escala gravamen complementaria (530)
13 101 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala autonómica Impuesto importe casilla 519 - Parte autonómica (531)
14 114 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte estatal (532)
15 127 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte autonómica (533)
16 140 4 Num Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte estatal (TME) *
17 144 4 Num Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte autonómica (TMA) *
18 148 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Base liquidable ahorro sometida gravamen - Parte estatal (536)
19 161 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Base liquidable ahorro sometida gravamen - Parte autonómica (537)
20 174 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación de la escala general y autonómica al importe de las casillas 538 y 539 - Parte estatal (538)
21 187 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación de la escala general y autonómica al importe de las casillas 538 y 539 - Parte Parte autonómica (539)
22 200 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación de la escala de gravamen complementaria al importe de la casilla 538 - Importe resultante (540)
23 213 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte estatal (541)
24 226 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte autonómica (542)
25 239 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota íntegra estatal - Parte estatal (545)
26 252 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota íntegra autonómica - Parte autonómica (546)
27 265 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte estatal (547)
28 278 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte autonómica (548)
29 291 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión empresas nueva creación - Parte estatal (549)
30 304 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte estatal (550)
31 317 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte autonómica (551)
32 330 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos - Parte estatal (552)
33 343 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos - Parte autonómica (553)
34 356 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Incentivos inversión empresarial - Parte estatal (554)
35 369 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Incentivos inversión empresarial - Parte autonómica (555)
36 382 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Dotaciones Reserva Canarias - Parte estatal (556)
37 395 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Dotaciones Reserva Canarias - Parte autonómica (557)
38 408 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rendimientos venta bienes Canarias - Parte estatal (558)
39 421 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rendimientos venta bienes Canarias - Parte autonómica (559)
40 434 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte estatal (560)
41 447 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte autonómica (561)
42 460 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Cantidades depositadas cuentas ahorro-empresa - Parte estatal (562)
43 473 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Cantidades depositadas cuentas ahorro-empresa - Parte autonómica (563)
44 486 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte estatal (564)
45 499 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte autonómica (565)
46 512 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Por obras de mejora en la vivienda habitual pendientes deducción - Parte estatal (566)
Página 43

# Pag. 44

100-15
Nº Posic. Long. Tipo Descripción Validación Contenido
47 525 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Por obras de mejora en la vivienda pendientes deducción - Parte estatal (567)
48 538 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - (568)
49 551 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota líquida estatal - Parte estatal (570)
50 564 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota líquida autonómica - Parte autonómica (571)
51 577 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - Parte estatal (572)
52 590 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - Parte estatal (573)
53 603 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2013 - Importe - Parte estatal (574)
54 616 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2013 - Intereses demora - Parte estatal (575)
55 629 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2013 - Importe - Parte autonómica (576)
56 642 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2013 - Intereses demora - Parte autonómica (577)
57 655 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2013 - Importe - Parte autonómica (578)
58 668 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2013 - Intereses demora - Parte autonómica (579)
59 681 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Cuotas líquidas incrementadas - Parte estatal (580)
60 694 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Cuotas líquidas incrementadas - Parte autonómica (581)
61 707 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota líquida incrementada total (582)
62 720 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Rentas obtenidas y gravadas en el extranjero (583)
63 733 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducción obtención rendimientos trabajo o act. económicas (584)
64 746 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Aplicación régimen transparencia fiscal internacional (585)
65 759 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Aplicación régimen imputación rentas cesión derechos imagen (586)
66 772 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10015>
67 781 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 782
Página 44

# Pag. 45

100-16
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "16"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N (N) Cálculo impuesto y resultado declaración (continuación) - Cuota resultante autoliquidación - Compensación fiscal - Percepción rdtos.capital mobiliario > 2 años (587)
7 23 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota resultante autoliquidación - Retenciones deducibles rendimientos bonificados - Importe retenciones no practicadas (588)
8 36 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota resultante autoliquidación - Cuota resultante autoliquidación (589)
9 49 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos del trabajo (590)
10 62 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos del capital mobiliario (591)
11 75 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Arrendamientos de inmuebles urbanos (592)
12 88 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos de actividades económicas (593)
13 101 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Atribuidos por entidades en régimen de atribución de rentas (594)
14 114 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Imputados por agrupaciones de interés económico y UTE's (595)
15 127 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Ingresos a cuenta art. 92.8 Ley del Impuesto (596)
16 140 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Ganancias patrimoniales, incluidos premios (597)
17 153 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Pagos fraccionados (actividades económicas) (598)
18 166 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Cuotas del Impuesto sobre la Renta de no Residentes (599)
19 179 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Retenciones art. 11 Directiva 2003/48/CE (600)
20 192 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Total pagos a cuenta (601)
21 205 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Cuota diferencial (605)
22 218 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción por maternidad - Importe de la deducción (606)
23 231 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Importe del abono anticipado correspondiente a 2014 (607)
24 244 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Resultado de la declaración (610)
25 257 13 N (O) Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - Cuota líquida autonómica incrementada (622)
26 270 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% deducciones doble imposición (623)
27 283 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% compensación fiscal percepción rendimientos capital mobiliario (624)
28 296 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - Importe IRPF que corresponde a la Comunidad Autónoma de residencia (625)
29 309 13 N (P) Regularización mediante declaración complementaria (ejercicio 2014) - Resultados a ingresar anteriores autoliquidaciones o liquidaciones administrativas (611)
30 322 13 N Regularización mediante declaración complementaria (ejercicio 2014) - Devoluciones acordadas por la Administración, consecuencia anteriores autoliquidaciones (612)
31 335 13 N Regularización mediante declaración complementaria (ejercicio 2014) - Resultado de la declaración complementaria (615)
32 348 13 N (Q) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (618)
33 361 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (620)
34 374 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (619)
35 387 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (620)
36 400 34 An Número de cuenta IBAN (621)
37 434 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10016>
38 443 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 444
Página 45

# Pag. 46

Anexo A.1
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "17"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Inversión con derecho a deducción (A)
7 23 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte estatal (626)
8 36 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte autonómica (627)
9 49 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Inversión con derecho a deducción (B)
10 62 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte estatal (628)
11 75 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte autonómica (629)
12 88 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Inversión con derecho a deducción (C)
13 101 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte estatal (630)
14 114 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte autonómica (631)
15 127 13 N Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Cantidades satisfechas con derecho a deducción (E)
16 140 13 N Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte estatal (632)
17 153 13 N Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte autonómica (633)
18 166 13 N Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte estatal (547)
19 179 13 N Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte autonómica (548)
20 192 13 N Deducción por inversión en vivienda habitual - Datos adicionales - Importe de los pagos realizados en el ejercicio al promotor o constructor (634)
21 205 9 An Deducción por inversión en vivienda habitual - Datos adicionales - NIF del promotor o constructor (635)
22 214 8 An Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Fecha adquisición vivienda (DDMMAAAA) (636)
23 222 20 An Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Número de identificación del préstamo hipotecario (637)
24 242 5 Num Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Porcentaje del préstamo destinado a adquisición (3 enteros y 2 decimales) (638) *
25 247 13 N Deducción inversiones en empresas de nueva o reciente creación - Cantidades suscripción acciones entidades nueva o reciente creación - Importe (639)
26 260 9 An Deducción inversiones en empresas de nueva o reciente creación - Entidad 1 - NIF (640)
27 269 9 An Deducción inversiones en empresas de nueva o reciente creación - Entidad 2 - NIF (641)
28 278 13 N Deducción inversiones en empresas de nueva o reciente creación - Importe total deducción inversiones empresa nueva o reciente creación - Base deducción (D)
29 291 13 N Deducción inversiones en empresas de nueva o reciente creación - Importe total deducciones empresa nueva o reciente creación - Importe deducción (549)
30 304 9 An Deducción por alquiler de la vivienda habitual - NIF del arrendador 1 (643)
31 313 20 An Deducción por alquiler de la vivienda habitual - Si no tiene NIF Nº identificación fiscal en país de residencia (644)
32 333 13 N Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 1 (645)
33 346 9 An Deducción por alquiler de la vivienda habitual - NIF del arrendador 2 (646)
34 355 20 An Deducción por alquiler de la vivienda habitual - Si no tiene NIF Nº identificación fiscal en país de residencia (647)
35 375 13 N Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 2 (648)
36 388 13 N Deducción por alquiler de la vivienda habitual - Cantidades satisfechas con derecho a deducción (F)
37 401 13 N Deducción por alquiler de la vivienda habitual - Importe deducción (650)
38 414 13 N Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte estatal (564)
39 427 13 N Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte autonómica (565)
40 440 13 N Deducciones por donativos - Donativos límite 15% base liquidable - Importe con derecho a deducción (G)
Página 46

# Pag. 47

Anexo A.1
Nº Posic. Long. Tipo Descripción Validación Contenido
41 453 13 N Deducciones por donativos - Donativos límite 15% base liquidable - Importe de la deducción (651)
42 466 13 N Deducciones por donativos - Donativos límite 10% base liquidable - Importe con derecho a deducción (H)
43 479 13 N Deducciones por donativos - Donativos límite 10% base liquidable - Importe de la deducción (652)
44 492 13 N Deducciones por donativos - Deducciones por donativos - Parte estatal (552)
45 505 13 N Deducciones por donativos - Deducciones por donativos - Parte autonómica (553)
46 518 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10017>
47 527 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 528
Página 47

# Pag. 48

Anexo A.2
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "18"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe con derecho a deducción (I)
7 23 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe de la deducción (653)
8 36 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte estatal (550)
9 49 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte autonómica (551)
10 62 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Importe total de la deducción (654)
11 75 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte estatal (560)
12 88 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte autonómica (561)
13 101 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Cantidades depositadas (J)
14 114 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Importe total de la deducción (655)
15 127 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Deducción - Parte estatal (562)
16 140 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Deducción - Parte autonómica (563)
17 153 1 Tit Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Titular
18 154 8 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Fecha de apertura "DDMMAAAA"
19 162 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Entidad
20 166 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Oficina
21 170 2 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - DC
22 172 10 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Número de cuenta
23 182 1 Tit Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Titular
24 183 8 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Fecha de apertura
25 191 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Entidad
26 195 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Oficina
27 199 2 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - DC
28 201 10 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Número de cuenta
29 211 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011- Cantidades satisfechas (656)
30 224 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011 - Base deducción (K)
31 237 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011 - Importe deducción (657)
32 250 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Cantidades satisfechas (658)
33 263 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Base deducción (L)
34 276 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Importe deducción (659)
35 289 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Importe total (567)
36 302 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 14 abril al 31 diciembre 2010 - Cantidades satisfechas (661)
37 315 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 14 abril al 31 diciembre 2010 - Base deducción (Q)
38 328 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 14 abril al 31 diciembre 2010 - Importe deducción (662)
39 341 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Cantidades satisfechas (663)
40 354 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Base deducción (R)
41 367 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Importe deducción (664)
42 380 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Importe total (566)

# Pag. 49

Anexo A.2
Nº Posic. Long. Tipo Descripción Validación Contenido
43 393 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Importe dotaciones (666)
44 406 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (667)
45 419 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (668)
46 432 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Importe dotaciones (669)
47 445 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (670)
48 458 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (671)
49 471 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Pendiente de materializar (672)
50 484 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Importe dotaciones (673)
51 497 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (674)
52 510 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (675)
53 523 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Pendiente de materializar (676)
54 536 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Importe dotaciones (677)
55 549 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (678)
56 562 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (679)
57 575 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Pendiente de materializar (680)
58 588 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Importe dotaciones (681)
59 601 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (682)
60 614 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (683)
61 627 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Pendiente de materializar (684)
62 640 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Importe de la deducción 2014
63 653 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2014 - Inversiones prev. letras A, B y D (1º.) artº. 27.4 (685)
64 666 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2014 - Inversiones prev. letras C y D 2º. a 6º.) artº. 27.4 (686)
65 679 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10018>
66 688 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 689

# Pag. 50

Anexo A.3
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "19"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Saldo anterior
7 23 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Aplicado declaración (687)
8 36 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Pendiente aplicación
9 49 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interés público - Saldo anterior
10 62 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interés público - Aplicado declaración (688)
11 75 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interes público - Pendiente aplicación
12 88 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i - Deducción
13 101 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i - Aplicado declaración (689)
14 114 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i - Pendiente aplicación
15 127 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión beneficios - Deducción
16 140 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión beneficios - Aplicado declaración (690)
17 153 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión beneficios - Pendiente aplicación
18 166 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones/gastos art.º 38.2 LIS- Deducción
19 179 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones/gastos art.º 38.2 LIS- Aplicado declaración (691)
20 192 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones/gastos art.º 38.2 LIS- Pendiente aplicación
21 205 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones medioambientales - Deducción
22 218 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones medioambientales - Aplicado declaración (692)
23 231 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones medioambientales - Pendiente aplicación
24 244 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Util. nuevas tecnologías empleados - Deducción
25 257 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Util. nuevas tecnologías empleados - Aplicado declaración (693)
26 270 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Util. nuevas tecnologías empleados - Pendiente aplicación
27 283 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad - Deducción
28 296 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad - Aplicado declaración (694)
29 309 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad - Pendiente aplicación
30 322 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo artº. 43 LIS - Deducción
31 335 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo artº. 43 LIS - Aplicado declaración (695)
32 348 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo artº. 43 LIS - Pendiente aplicación
33 361 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vuelta al Mundo a Vela Alicante 2014" - Deducción
34 374 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vuelta al Mundo a Vela Alicante 2014" - Aplicado declaración (696)
35 387 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vuelta al Mundo a Vela Alicante 2014" - Pendiente aplicación
36 400 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "3ª edición Barcelona World Race" - Deducción
37 413 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "3ª edición Barcelona World Race" - Aplicado declaración (697)
38 426 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "3ª edición Barcelona World Race" - Pendiente aplicación
39 439 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016"- Deducción
40 452 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016" - Aplicado declaración (698)
41 465 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016" - Pendiente aplicación
42 478 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Deducción
43 491 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Aplicado declaración (699)
44 504 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Pendiente aplicación

# Pag. 51

Anexo A.3
Nº Posic. Long. Tipo Descripción Validación Contenido
45 517 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "V Cent. Nacimiento Sta. Teresa de Jesús 2015" - Deducción
46 530 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "V Cent. Nacimiento Sta. Teresa de Jesús 2015" - Aplicado declaración (700)
47 543 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "V Cent. Nacimiento Sta. Teresa de Jesús 2015" - Pendiente aplicación
48 556 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vitoria Gasteiz Capital Verde Europea 2012" - Deducción
49 569 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vitoria Gasteiz Capital Verde Europea 2012" - Aplicado declaración (701)
50 582 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Vitoria Gasteiz Capital Verde Europea 2012" - Pendiente aplicación
51 595 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Vela (ISAF) Santander 2014" - Deducción
52 608 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Vela (ISAF) Santander 2014" - Aplicado declaración (702)
53 621 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Vela (ISAF) Santander 2014" - Pendiente aplicación
54 634 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Deducción
55 647 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Aplicado declaración (703)
56 660 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Pendiente aplicación
57 673 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Deducción
58 686 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Aplicado declaración (704)
59 699 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Pendiente aplicación
60 712 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año Santo Jubilar Mariano 2013-2014 Sevilla" - Deducción
61 725 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año Santo Jubilar Mariano 2013-2014 Sevilla" - Aplicado declaración (705)
62 738 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año Santo Jubilar Mariano 2013-2014 Sevilla" - Pendiente aplicación
63 751 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "El Árbol es Vida" - Deducción
64 764 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "El Árbol es Vida" - Aplicado declaración (706)
65 777 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "El Árbol es Vida" - Pendiente aplicación
66 790 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Mundo Basket 2014" - Deducción
67 803 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Mundo Basket 2014" - Aplicado declaración (707)
68 816 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Mundo Basket 2014" - Pendiente aplicación
69 829 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Escalada 2014, Gijón" - Deducción
70 842 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Escalada 2014, Gijón" - Aplicado declaración (708)
71 855 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo de Escalada 2014, Gijón" - Pendiente aplicación
72 868 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año de España en Japón" - Deducción
73 881 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año de España en Japón" - Aplicado declaracion (709)
74 894 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año de España en Japón" - Pendiente aplicación
75 907 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario fallecimiento El Greco" - Deducción
76 920 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario fallecimiento El Greco" - Aplicado declaración (710)
77 933 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario fallecimiento El Greco" - Pendiente aplicación
78 946 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Patrimonio Cultural de Lorca" - Deducción
79 959 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Patrimonio Cultural de Lorca" - Aplicado declaración (711)
80 972 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Patrimonio Cultural de Lorca" - Pendiente aplicación
81 985 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Deducción
82 998 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Aplicado declaración (712)
83 1011 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Pendiente aplicación
84 1024 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato Ciclismo en Carretera Ponferrada 2014" - Deducción
85 1037 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato Ciclismo en Carretera Ponferrada 2014" - Aplicado declaración (713)
86 1050 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato Ciclismo en Carretera Ponferrada 2014" - Pendiente aplicación
87 1063 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona World Jumping Challenge" - Deducción
88 1076 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona World Jumping Challenge" - Aplicado declaración (714)
89 1089 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona World Jumping Challenge" - Pendiente aplicación
90 1102 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo Patinaje Artístico Reus 2014" - Deducción
91 1115 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo Patinaje Artístico Reus 2014" - Aplicado declaración (715)
92 1128 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato del Mundo Patinaje Artístico Reus 2014" - Pendiente aplicación

# Pag. 52

Anexo A.3
Nº Posic. Long. Tipo Descripción Validación Contenido
93 1141 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Deducción
94 1154 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Aplicado declaración (716)
95 1167 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Pendiente aplicación
96 1180 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato Tiro Olímpico Las Gabias 2014" - Deducción
97 1193 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato Tiro Olímpico Las Gabias 2014" - Aplicado declaración (717)
98 1206 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Campeonato Tiro Olímpico Las Gabias 2014" - Pendiente aplicación
99 1219 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Deducción
100 1232 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Aplicado declaración (718)
101 1245 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Pendiente aplicación
102 1258 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "2014 Año Internacional Dieta Mediterránea" - Deducción
103 1271 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "2014 Año Internacional Dieta Mediterránea" - Aplicado declaración (719)
104 1284 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "2014 Año Internacional Dieta Mediterránea" - Pendiente aplicación
105 1297 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "III Centenario de la Real Academia Española" - Deducción
106 1310 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "III Centenario de la Real Academia Española" - Aplicado declaración (720)
107 1323 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "III Centenario de la Real Academia Española" - Pendiente aplicación
108 1336 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Alicante 2011" - Deducción
109 1349 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Alicante 2011" - Aplicado declaración (721)
110 1362 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Alicante 2011" - Pendiente aplicación
111 1375 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "A Coruña 2015-120 años después" - Deducción
112 1388 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "A Coruña 2015-120 años después" - Aplicado declaración (722)
113 1401 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "A Coruña 2015-120 años después" - Pendiente aplicación
114 1414 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Deducción
115 1427 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Aplicado declaración (723)
116 1440 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Pendiente aplicación
117 1453 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Deducción
118 1466 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Aplicado declaración (724)
119 1479 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Pendiente aplicación
120 1492 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Deducción
121 1505 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Aplicado declaración (725)
122 1518 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Pendiente aplicación
123 1531 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Sesenta Edición Festival Internacional Teatro Clásico de Mérida" - Deducción
124 1544 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Sesenta Edición Festival Internacional Teatro Clásico de Mérida" - Aplicado declaración (726)
125 1557 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Sesenta Edición Festival Internacional Teatro Clásico de Mérida" - Pendiente aplicación
126 1570 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año de la biotecnología en España" - Deducción
127 1583 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año de la biotecnología en España" - Aplicado declaración (727)
128 1596 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Año de la biotecnología en España" - Pendiente aplicación
129 1609 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10019>
130 1618 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1619

# Pag. 53

Anexo A.4
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "20"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Saldo anterior
7 23 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Aplicado declaración (728)
8 36 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Pendiente aplicación
9 49 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Saldo anterior
10 62 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Aplicado declaración (729)
11 75 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Pendiente aplicación
12 88 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Deducción
13 101 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Aplicado declaración (730)
14 114 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Pendiente aplicación
15 127 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - L.I.S.: Inversión beneficios artº. 37 LIS - Deducción
16 140 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - L.I.S.: Inversión beneficios artº. 37 LIS - Aplicado declaración (731)
17 153 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - L.I.S.: Inversión beneficios artº. 37 LIS - Pendiente aplicación
18 166 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Deducción
19 179 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Aplicado declaración (732)
20 192 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Pendiente de aplicación
21 205 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Util. nuevas tecnologías empleados - Deducción
22 218 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Util. nuevas tecnologías empleados - Aplicado declaración (733)
23 231 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Util. nuevas tecnologías empleados - Pendiente aplicación
24 244 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad - Deducción
25 257 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad - Aplicado declaración (734)
26 270 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad - Pendiente aplicación
27 283 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Inversiones en la adquisición de activos fijos - Deducción
28 296 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Inversiones en la adquisición de activos fijos - Aplicado declaración (735)
29 309 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Inversiones en la adquisición de activos fijos - Pendiente aplicación
3300 332222 1133 NN DDeedduucccciioonneess ppoorr iinncceennttiivvooss yy eessttíímmuuloloss aa lalai ninvveersrsióiónne emmppreressaarirailal D- Dedeudcuccicoinoense:si:m impoprotertea palpiclaicdaodo I-m Impoproterteto ttoatladle dlea sladse ddeudcucciocnioense(s7 3(763)
31 335 13 N Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Deducciones - Parte estatal (554)
32 348 13 N Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Deducciones - Parte autonómica (555)
33 361 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10020>
34 370 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 371

# Pag. 54

Anexo B.1
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "21"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Andalucía - Para beneficiarios de ayudas familiares (740)
7 23 13 N Deducciones Autonómicas - Andalucía - Para beneficiarios ayudas viviendas protegidas (741)
8 36 13 N Deducciones Autonómicas - Andalucía - Por inversión vivienda habitual protegida/personas jóvenes (742)
9 49 9 An Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - NIF arrendador (743)
10 58 13 N Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - Importe (744)
11 71 20 An Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - Si no tiene NIF Nº identificación en País de residencia (745)
12 91 13 N Deducciones Autonómicas - Andalucía - Por inversión en la adquisición de acciones y participaciones (746)
13 104 13 N Deducciones Autonómicas - Andalucía - Por adopción de hijos ámbito internacional (747)
14 117 13 N Deducciones Autonómicas - Andalucía - Para contribuyentes con discapacidad (748)
15 130 13 N Deducciones Autonómicas - Andalucía - Para padre/madre de familia monoparental con ascendientes mayores 75 años (749)
16 143 13 N Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Deducción con carácter general (750)
17 156 11 An Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Cuenta cotización (751)
18 167 13 N Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Importe (752)
1199 118800 1111 AAnn DDeedduucccciioonneess AAuuttoonnóómmiiccaass - AAnnddaalluuccííaa - PPoorr aayyuuddaa ddoommééssttiiccaa. CCuueennttaa ccoottiizzaacciióónn ((775533))
20 191 13 N Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Importe (754)
21 204 13 N Deducciones Autonómicas - Andalucía - Para trabajadores por gastos de defensa jurídica de la relación laboral (755)
22 217 13 N Deducciones Autonómicas - Andalucía - Por obras en vivienda (Cantidades 2012 pdtes. deducción 4 años exceder en 2012 base deducción) (756)
23 230 13 N Deducciones Autonómicas - Andalucía - Para contribuyentes con cónyuges o parejas de hecho con discapacidad (757)
24 243 13 N Deducciones Autonómicas - Andalucía - Otras deducciones (758)
25 256 13 N Deducciones Autonómicas - Andalucía - Total deducciones autonómicas (568)
26 269 13 N Deducciones Autonómicas - Aragón - Por nacimiento o adopción tercer hijo o sucesivos o segundo hijo si éste o el primer hijo es persona con discapacidad (759)
27 282 13 N Deducciones Autonómicas - Aragón - Por adopción internacional de niños (760)
28 295 13 N Deducciones Autonómicas - Aragón - Por el cuidado de personas dependientes (761)
29 308 13 N Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico (762)
30 321 13 N Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo (763)
31 334 13 N Deducciones Autonómicas - Aragón - Por inversión en acciones de entidades que cotizan en Mercado Alternativo Bursátil (764)
32 347 13 N Deducciones Autonómicas - Aragón - Por inversión en la adquisición de acciones o participaciones sociales (765)
33 360 13 N Deducciones Autonómicas - Aragón - Por adquisición de vivienda en núcleos rurales (766)
34 373 13 N Deducciones Autonómicas - Aragón - Por adquisición libros de texto y material escolar (767)
35 386 9 An Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual - NIF arrendador (768)
36 395 13 N Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual (769)
37 408 20 An Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual. Si no tiene NIF Nº identificación en País de residencia (770)
38 428 13 N Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda social (deducción arrendador) (771)
39 441 13 N Deducciones Autonómicas - Aragón - Para mayores de 70 años (772)
Página 54

# Pag. 55

Anexo B.1
Nº Posic. Long. Tipo Descripción Validación Contenido
40 454 13 N Deducciones Autonómicas - Aragón - Por gasto en primas individuales en seguros de salud (773)
41 467 13 N Deducciones Autonómicas - Aragón - Por nacimiento o adopción del primer y/o segundo hijo en poblaciones de menos de 10.000 habitantes (774)
42 480 13 N Deducciones Autonómicas - Aragón - Otras deducciones (775)
43 493 13 N Deducciones Autonómicas - Aragón - Total deducciones autonómicas (568)
44 506 13 N Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (776)
45 519 13 N Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes con discapacidad (777)
46 532 13 N Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes con discapacidad (778)
47 545 13 N Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (779)
48 558 9 An Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - NIF arrendador (780)
49 567 13 N Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - Importe (781)
50 580 20 An Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual. Si no tiene NIF Nº identificación en País de residencia (782)
51 600 13 N Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (783)
52 613 13 N Deducciones Autonómicas - Asturias - Por adopción internacional de menores (784)
53 626 13 N Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones (785)
54 639 13 N Deducciones Autonómicas - Asturias - Para familias numerosas (786)
55 652 13 N Deducciones Autonómicas - Asturias - Para familias monoparentales (787)
56 665 13 N Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (788)
57 678 13 N Deducciones Autonómicas - Asturias - Por gestión forestal sostenible (789)
58 691 13 N Deducciones Autonómicas - Asturias - Otras deducciones (790)
59 704 13 N Deducciones Autonómicas - Asturias - Total deducciones autonómicas (568)
60 717 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10021>
61 726 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 727
Página 55

# Pag. 56

Anexo B.2
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "22"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Illes Balears - Por gastos adquisición libros de texto (791)
7 23 13 N Deducciones Autonómicas - Illes Balears - Para contribuyentes edad igual o superior a 65 años (792)
8 36 13 N Deducciones Autonómicas - Illes Balears - Para los declarantes con minusvalía física/psíquica o descendientes con esa condición (793)
9 49 13 N Deducciones Autonómicas - Illes Balears - Por adopción de hijos (794)
10 62 13 N Deducciones Autonómicas - Illes Balears - Por inversión en la adquisición de acciones o participaciones (795)
11 75 13 N Deducciones Autonómicas - Illes Balears - Por gastos en primas de seguro individuales de salud (796)
12 88 13 N Deducciones Autonómicas - Illes Balears - Otras deducciones (797)
13 101 13 N Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (568)
14 114 13 N Deducciones Autonómicas - Canarias - Por donaciones con finalidad ecológica (798)
15 127 13 N Deducciones Autonómicas - Canarias - Por donaciones rehabilitación/conservación patrimonio histórico de Canarias (799)
16 140 13 N Deducciones Autonómicas - Canarias - Por cantidades destinadas restauración/rehabilitación/reparación bienes inmuebles declarados de Interés Cultural (800)
17 153 13 N Deducciones Autonómicas - Canarias - Por gastos de estudios (801)
18 166 13 N Deducciones Autonómicas - Canarias - Por traslado residencia a otra isla para realizar actividad laboral cuenta ajena/actividad económica (802)
1199 117799 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass - CCaannaarriiaass - PPoorr ddoonnaacciioonneess eenn mmeettáálliiccoo aa ddeesscceennddiieenntteess mmeennoorreess 3355 aaññooss ppaarraa aaddqquuiissiicciióónn//rreehhaabbiilliittaacciióónn pprriimmeerraa vviivviieennddaa hhaabbiittuuaall ((880033))
20 192 13 N Deducciones Autonómicas - Canarias - Por nacimiento o adopción de hijos (804)
21 205 13 N Deducciones Autonómicas - Canarias - Por contribuyentes minusválidos y mayores de 65 años (805)
22 218 13 N Deducciones Autonómicas - Canarias - Por gastos de guardería (806)
23 231 13 N Deducciones Autonómicas - Canarias - Por familia numerosa (807)
24 244 13 N Deducciones Autonómicas - Canarias - Por inversión en vivienda habitual (808)
25 257 13 N Deducciones Autonómicas - Canarias - Por obras de adecuación vivienda habitual por razón discapacidad (809)
26 270 9 An Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - NIF arrendador (810)
27 279 13 N Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Importe (811)
28 292 20 An Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene NIF Nº identificación en País de residencia (812)
29 312 20 An Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral (813)
30 332 1 Num Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral. 1 o cero (814)
31 333 13 N Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Cantidades totales satisfechas al arrendador (815)
32 346 13 N Deducciones Autonómicas - Canarias - Por contribuyentes desempleados (816)
33 359 13 N Deducciones Autonómicas - Canarias - Por obras de rehabilitación o reforma en vivienda (pdte. deducción exceso base 2012) (817)
34 372 13 N Deducciones Autonómicas - Canarias - Otras deducciones (818)
35 385 13 N Deducciones Autonómicas - Canarias - Total deducciones autonómicas (568)
36 398 9 An Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con discapacidad - NIF arrendador (819)
37 407 13 N Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con discapacidad - Importe (820)
38 420 20 An Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con discapacidad. Si no tiene NIF Nº identificación en País de residencia (821)
39 440 13 N Deducciones Autonómicas - Cantabria - Por cuidado de familiares (822)
Página 56

# Pag. 57

Anexo B.2
Nº Posic. Long. Tipo Descripción Validación Contenido
40 453 13 N Deducciones Autonómicas - Cantabria - Por obras de mejora. Importe 2013 pendiente de aplicación (823)
41 466 9 An Deducciones Autonómicas - Cantabria - Por obras mejora viviendas - NIF persona/entidad obras (824)
42 475 13 N Deducciones Autonómicas - Cantabria - Por obras mejora viviendas - Importe deducción (825 )
43 488 13 N Deducciones Autonómicas - Cantabria - Por obras mejora viviendas - Deducción por obras generada 2014 a deducir en 2 años siguientes (826)
44 501 13 N Deducciones Autonómicas - Cantabria - Por donativos a fundaciones (827)
45 514 13 N Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (828)
46 527 13 N Deducciones Autonómicas - Cantabria - Por inversión adquisición acciones/participaciones sociales nuevas entidades o reciente creación (829)
47 540 13 N Deducciones Autonómicas - Cantabria - Por gastos de enfermedad (830)
48 553 13 N Deducciones Autonómicas - Cantabria - Otras deducciones (831)
49 566 13 N Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (568)
50 579 13 N Deducciones Autonómicas - Castilla-La Mancha - Para el fomento del autoempleo. Deducción 2012 pendiente de aplicación (832)
51 592 13 N Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (833)
52 605 13 N Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (834)
53 618 13 N Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (835)
54 631 13 N Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (836)
55 644 13 N Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (837)
56 657 13 N Deducciones Autonómicas - Castilla-La Mancha - Por cantidades para la Cooperación Internacional, lucha contra pobreza y exclusión social (838)
57 670 13 N Deducciones Autonómicas - Castilla-La Mancha - Por familia numerosa (839)
58 683 13 N Deducciones Autonómicas - Castilla-La Mancha - Por donaciones con finalidad en investigación y desarrollo (840)
59 696 13 N Deducciones Autonómicas - Castilla-La Mancha - Por gastos en la adquisición de libros de texto y enseñanza de idiomas (841)
60 709 13 N Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento familiar no rumunerado de menores (842)
61 722 13 N Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento no remunerado de mayores de 65 años y/o discapacitados (843)
62 735 9 An Deducciones Autonómicas - Castilla-La Mancha - Por arrendamiento de vivienda habitual por menores de 36 años. Nif del arrendador (844)
6633 774444 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass - CCaassttiillllaa-LLaa MMaanncchhaa - PPoorr aarrrreennddaammiieennttoo ddee vviivviieennddaa hhaabbiittuuaall ppoorr mmeennoorreess ddee 3366 aaññooss. IImmppoorrttee ((884455))
64 757 20 An Deducciones Autonómicas - Castilla-La Mancha - Por arrendamiento de vivienda habitual por menores de 36 años. Si no tiene NIF Nº identificación en País de residencia (972)
65 777 13 N Deducciones Autonómicas - Castilla-La Mancha - Por inversión en adquisición participaciones sociales en Sociedades Cooperativas (846)
66 790 13 N Deducciones Autonómicas - Castilla-La Mancha - Otras deducciones (847)
67 803 13 N Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (568)
68 816 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10022>
69 825 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 826
Página 57

# Pag. 58

Anexo B.3
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "23"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Castilla y León - Para contribuyentes afectados por discapacidad (848)
7 23 13 N Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales (849)
8 36 13 N Deducciones Autonómicas - Castilla y León - Por cantidades donadas a fundaciones (850)
9 49 13 N Deducciones Autonómicas - Castilla y León - Poro cantidades donadas para el fomento de la investigación, desarrollo e innovación (851)
10 62 13 N Deducciones Autonómicas - Castilla y León - Por inversión en patrimonio histórico, cultural y natural (852)
11 75 9 An Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años - Nif arrendador (853)
12 84 13 N Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años - Importe (854)
13 97 20 An Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual menores de 36 años. Si no tiene NIF Nº identificación en País de residencia (855)
14 117 13 N Deducciones Autonómicas - Castilla y León - Por inversión instalaciones medioambientales/adaptación a personas con discapacidad en vvda.habitual (856)
15 130 8 Num Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Fecha visado proyecto (857)
16 138 13 N Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Importe (858)
17 151 13 N Deducciones Autonómicas - Castilla y León - Deducción para el fomento de emprendimiento (859)
18 164 13 N Deducciones Autonómicas - Castilla y León - Deducción para el fomento del autoempleo mujeres, jóvenes y autónomos abandono actividad por crisis. Importes pdtes. aplicación (860)
19 177 13 N Deducciones Autonómicas - Castilla y León - Deducción para el fomento del autoempleo mujeres, jóvenes y autónomos abandono actividad por crisis. Importes pdtes. aplicación (861)
20 190 13 N Deducciones Autonómicas - Castilla y León - Por familia numerosa, nacimiento o adopción, etc. Importes pdtes. aplicación (862)
21 203 13 N Deducciones Autonómicas - Castilla y León - Por familia numerosa, nacimiento o adopción, etc. Importes pdtes. aplicación (863)
22 216 13 N Deducciones Autonómicas - Castilla y León - Por familia numerosa (864)
23 229 13 N Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (865)
24 242 13 N Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas (866)
25 255 13 N Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas en 2012 y/o 2013 (867)
26 268 9 An Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Nif persona empleada (868)
27 277 13 N Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores (869)
28 290 13 N Deducciones Autonómicas - Castilla y León - Por paternidad (870)
29 303 13 N Deducciones Autonómicas - Castilla y León - Por gastos de adopción (871)
30 316 9 An Deducciones Autonómicas - Castilla y León - Por cuota Seg.Social empleados del hogar - Nif persona empleada (872)
31 325 13 N Deducciones Autonómicas - Castilla y León - Por cuota Seg.Social empleados del hogar - Importe (873)
32 338 13 N Deducciones Autonómicas - Castilla y León - Importe total aplicado (874)
33 351 13 N Deducciones Autonómicas - Castilla y León - Otras deducciones (875)
34 364 13 N Deducciones Autonómicas - Castilla y León - Total deducciones autonómicas (568)
35 377 13 N Deducciones Autonómicas - Castilla y León - Deducciones fomento autoempleo mujeres y jóvenes y autónomos - Pendiente de aplicación (876)
36 390 13 N Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2012 y 2013 Pendiente de aplicación (877)
37 403 13 N Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2014 Pendiente de aplicación (878)
38 416 13 N Deducciones Autonómicas - Cataluña - Por nacimiento o adopción hijos (879)
39 429 13 N Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan el uso lengua catalana (880)
40 442 13 N Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan la investigación científica (881)
Página 58

# Pag. 59

Anexo B.3
Nº Posic. Long. Tipo Descripción Validación Contenido
41 455 9 An Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - NIF arrendador (882)
42 464 13 N Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - Importe (883)
43 477 20 An Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - Si no tiene NIF Nº identificación en País de residencia (884)
44 497 13 N Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudios universitarios de master y doctorado (885)
45 510 13 N Deducciones Autonómicas - Cataluña - Para los contribuyentes que queden viudos (886)
46 523 13 N Deducciones Autonómicas - Cataluña - Por rehabilitación vivienda habitual (887)
47 536 13 N Deducciones Autonómicas - Cataluña - Por donaciones en beneficio del medio ambiente (888)
48 549 13 N Deducciones Autonómicas - Cataluña - Por inversión adquisición de acciones o participaciones sociales entidades nuevas o de creación reciente (889)
49 562 13 N Deducciones Autonómicas - Cataluña - Por inversión en acciones de entidades que cotizan en empresas en expansión (890)
50 575 13 N Deducciones Autonómicas - Cataluña - Otras deducciones (891)
51 588 13 N Deducciones Autonómicas - Cataluña - Total deducciones autonómicas (568)
52 601 13 N Deducciones Autonómicas - Extremadura - Por adquisición vivienda habitual para jóvenes y víctimas del terrorismo (892)
53 614 13 N Deducciones Autonómicas - Extremadura - Por trabajo dependiente (893)
54 627 13 N Deducciones Autonómicas - Extremadura - Por cuidado de familiares con discapacidad (894)
55 640 13 N Deducciones Autonómicas - Extremadura - Por acogimiento de menores (895)
56 653 13 N Deducciones Autonómicas - Extremadura - Por partos múltiples (896)
57 666 13 N Deducciones Autonómicas - Extremadura - Por compra de material escolar (897)
58 679 13 N Deducciones Autonómicas - Extremadura - Por inversión en la adquisición de acciones o participaciones sociales (898)
59 692 13 N Deducciones Autonómicas - Extremadura - Por gastos de guardería para hijos menores de 4 años (899)
60 705 13 N Deducciones Autonómicas - Extremadura - Para contribuyentes viudos (900)
61 718 13 N Deducciones Autonómicas - Extremadura - Otras deducciones (901)
62 731 13 N Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (568)
63 744 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10023>
64 753 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 754
Página 59

# Pag. 60

Anexo B.4
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "24"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (902)
7 23 13 N Deducciones Autonómicas - Galicia - Por familia numerosa (903)
8 36 13 N Deducciones Autonómicas - Galicia - Por cuidado hijos menores (904)
9 49 13 N Deducciones Autonómicas - Galicia - Por contribuyentes con discapacidad = > 65 años que precisan ayuda de terceras personas (905)
10 62 13 N Deducciones Autonómicas - Galicia - Por gastos de nuevas tecnologías en hogares gallegos (906)
11 75 9 An Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - NIF arrendador (907)
12 84 13 N Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - Importe (908)
13 97 20 An Deducciones Autonómicas - Galicia - Por alquiler vivienda habitual. Si no tiene NIF Nº identificación en País de residencia (909)
14 117 13 N Deducciones Autonómicas - Galicia - Por acogimiento familiar de menores (910)
15 130 13 N Deducciones Autonómicas - Galicia - Por creación nuevas empresas o ampliación actividad (911)
16 143 13 N Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación y su financiación (912)
17 156 13 N Deducciones Autonómicas - Galicia - Por inversión en acciones de entidades emppresas en exppansión Mercado Alternativo Bursátil ((913))
18 169 13 N Deducciones Autonómicas - Galicia - Otras deducciones (914)
19 182 13 N Deducciones Autonómicas - Galicia - Total deducciones autonómicas (568)
20 195 13 N Deducciones Autonómicas - Madrid - Por nacimiento o adopción de hijos (915)
21 208 13 N Deducciones Autonómicas - Madrid - Por adopción internacional de niños (916)
22 221 13 N Deducciones Autonómicas - Madrid - Por acogimiento familiar de menores (917)
23 234 13 N Deducciones Autonómicas - Madrid - Por acogimiento no remunerado de mayores 65 años y/o con discapacidad (918)
24 247 9 An Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - NIF arrendador (919)
25 256 13 N Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - Importe (920)
26 269 20 An Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años. Si no tiene NIF Nº identificación en País de residencia (921)
27 289 13 N Deducciones Autonómicas - Madrid - Por gastos educativos (922)
28 302 13 N Deducciones Autonómicas - Madrid - Para familias con dos o más descendientes e ingresos reducidos (923)
29 315 13 N Deducciones Autonómicas - Madrid - Por inversión en adquisición de acciones y participaciones sociales de nuevas entidades (924)
30 328 13 N Deducciones Autonómicas - Madrid - Para el fomento del autoempleo de jóvenes menores de 35 años (925)
31 341 13 N Deducciones Autonómicas - Madrid - Por inversiones en entidades cotizadas en el Mercado Alternativo Bursátil (926)
32 354 13 N Deducciones Autonómicas - Madrid - Otras deducciones (927)
33 367 13 N Deducciones Autonómicas - Madrid - Total deducciones autonómicas (568)
34 380 13 N Deducciones Autonómicas - Murcia - Por inversión vivienda habitual jóvenes edad igual/inferior 35 años (incluido rég. transitorio) (928)
35 393 13 N Deducciones Autonómicas - Murcia - Por donativos para la protección del patrimonio histórico Región Murcia (929)
Página 60

# Pag. 61

Anexo B.4
Nº Posic. Long. Tipo Descripción Validación Contenido
36 406 13 N Deducciones Autonómicas - Murcia - Por gastos de guardería para hijos menores de 3 años (930)
37 419 13 N Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (931)
38 432 13 N Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (932)
39 445 13 N Deducciones Autonómicas - Murcia - Por inversión en la adquisición de acciones y participaciones sociales (933)
40 458 13 N Deducciones Autonómicas - Murcia - Por inversiones en entidades cotizadas Mercado Alternativo Bursátil (934)
41 471 13 N Deducciones Autonómicas - Murcia - Otras deducciones (935)
42 484 13 N Deducciones Autonómicas - Murcia - Total deducciones autonómicas (568)
43 497 13 N Deducciones Autonómicas - La Rioja - Por nacimiento y adopción de segundo o ulterior hijo (936)
44 510 13 N Deducciones Autonómicas - La Rioja - Por inversión adquisición/rehabilitación vivienda habitual para jóvenes (937)
45 523 4 Num Deducciones Autonómicas - La Rioja - Por adquisición/rehabilitación 2ª vivienda en el medio rural - Código municipio (938)
46 527 13 N Deducciones Autonómicas - La Rioja - Por adquisición/rehabilitación 2ª vivienda en el medio rural - Importe (939)
47 540 13 N Deducciones Autonómicas - La Rioja - Por inversión rehabilitación vivienda habitual (940)
48 553 13 N Deducciones Autonómicas - La Rioja - Otras deducciones (941)
49 566 13 N Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (568)
50 579 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10024>
51 588 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 589
Página 61

# Pag. 62

Anexo B.5
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
11 11 22 AAnn IInniicciioo ddeell iiddeennttiiffiiccaaddoorr ddee mmooddeelloo y ppáággiinnaa. OOBBLLIIGGAATTOORRIIOO CCoonnssttaannttee ""<<TT""
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "25"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento/adopción de hijos (942)
7 23 13 N Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento/adopción múltiples (943)
8 36 13 N Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento/adopción hijos con discapacidad (944)
9 49 13 N Deducciones Autonómicas - Comunitat Valenciana - Por familia numerosa (945)
10 62 13 N Deducciones Autonómicas - Comunitat Valenciana - Por custodia en guarderías y primer ciclo educación infantil hijos menores de 3 años (946)
11 75 13 N Deducciones Autonómicas - Comunitat Valenciana - Por conciliación del trabajo con la vida familiar (947)
12 88 13 N Deducciones Autonómicas - Comunitat Valenciana - Para contribuyentes con un grado de discapacidad igual o superior al 33 por 100, de edad igual o superior a 65 años (948)
13 101 13 N Deducciones Autonómicas - Comunitat Valenciana - Por ascendientes > 75 años ó > 65 años que sean personas con discapacidad (949)
1144 111144 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass - CCoommuunniittaatt VVaalleenncciiaannaa - PPoorr rreeaalliizzaacciióónn ddee llaabboorreess nnoo rreemmuunneerraaddaass eenn eell hhooggaarr ((995500))
15 127 13 N Deducciones Autonómicas - Comunitat Valenciana - Por primera adquisición vivienda habitual para contribuyentes edad igual o inferior 35 años (951)
16 140 13 N Deducciones Autonómicas - Comunitat Valenciana - Por adquisición vivienda habitual por personas con discapacidad (952)
17 153 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades adquisición/rehabilitación vivienda habitual, procedentes ayudas públicas (953)
18 166 9 An Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de vivienda habitual - NIF arrendador (954)
19 175 13 N Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de vivienda habitual - Importe (955)
20 188 20 An Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de vivienda habitual - Si no tiene NIF Nº identificación en País de residencia (956)
21 208 9 An Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - NIF arrendador (957)
22 217 13 N Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Importe (958)
23 230 20 An Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Si no tiene NIF Nº identificación en País de residencia (970)
24 250 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades inversiones fuentes energía renovables en vivienda habitual (959)
25 263 13 N Deducciones Autonómicas - Comunitat Valenciana - Por donaciones con finalidad ecológica (960)
26 276 13 N Deducciones Autonómicas - Comunitat Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (961)
2277 228899 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass - CCoommuunniittaatt VVaalleenncciiaannaa - PPoorr ccaannttiiddaaddeess ddoonnaaddaass ppaarraa llaa ccoonnsseerrvvaacciióónn yy rreessttaauurraacciióónn ddee bbiieenneess ((996622))
28 302 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades destinadas a la conservación y restauración de bienes (963)
29 315 13 N Deducciones Autonómicas - Comunitat Valenciana - Por donaciones al fomento de la Lengua Valenciana (964)
30 328 13 N Deducciones Autonómicas - Comunitat Valenciana - Por contribuyentes con dos o más descendientes (965)
31 341 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (966)
32 354 13 N Deducciones Autonómicas - Comunitat Valenciana - Por adquisición material escolar (967)
33 367 9 An Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual - NIF persona o entidad (968)
34 376 13 N Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual (969)
35 389 13 N Deducciones Autonómicas - Comunitat Valenciana - Otras deducciones (971)
36 402 13 N Deducciones Autonómicas - Comunitat Valenciana - Total deduciones autonómicas (568)
37 415 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10025>
38 424 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 425

# Pag. 63

I-D
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2014
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "26"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Liquidación (2) - Resultado a ingresar o a devolver [620]
7 23 1 Num Liquidación (2) - Solicitud de suspensión ingreso cónyuge/Renuncia cobro devolución otro cónyuge. "1" o "0" [7]
8 24 13 N Declaración Complementaria (3) - Resultado de Declaración Complementaria [615]
9 37 1 Num Ingreso (4) - Casilla 620 positiva - NO FRACCIONA el pago [1] "1" o "0"
10 38 1 Num Ingreso (4) - Casilla 620 positiva - SÍ FRACCIONA el pago [6] "1" o "0"
11 39 13 N Ingreso (4) - Casilla 620 positiva - Importe del ingreso [I1]
12 52 1 Num Ingreso (4) - Casilla 620 positiva - Forma de pago -"0" No consta; "1" Efectivo; "2" Adeudo en Cuenta; "3" Domiciliación
13 53 1 Num Opciones de pago 2º plazo (5) - NO DOMICILIA el pago [2] "1" o "0"
14 54 1 Num Opciones de pago 2º plazo (5) - SÍ DOMICILIA el pago [3] "1" o "0"
15 55 13 N Opciones de pago 2º plazo (5) - Importe del 2º plazo [I2]
1166 6688 11 NNuumm DDeevvoolluucciióónn ((66)) - CCaassiillllaa 662200 nneeggaattiivvaa - "00" NNoo ccoonnssttaa,, "11" DDeevvoolluucciióónn yy "22" rreennuunncciiaa ddeevvoolluucciióónn
17 69 13 N Devolución (6) - Casilla 620 negativa - Importe [D]
18 82 34 An Número de cuenta IBAN
19 116 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10026>
20 125 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 126
Página 63