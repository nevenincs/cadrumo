# Pag. 1

Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
NNº PPoossiicc.. LLoonngg.. TTiippoo DDeessccrriippcciióónn VVaalliiddaacciióónn CCoonntteenniiddoo
1 1 17 An Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "<T100020130A0000>"
2 18 5 An Constante "<AUX>"
3 23 30 An Reservado para la Administración. Rellenar con blancos BLANCOS
4 53 1 An Idioma de la declaración (**) "E", "C", "G", "V"
5 54 39 An Reservado para la Administración. Rellenar con blancos BLANCOS
66 9933 44 AAnn VVeerrssiióónn ddeell PPrrooggrraammaa ((**))
7 97 4 An Reservado para la Administración. Rellenar con blancos BLANCOS
8 101 9 An NIF Empresa Desarrollo (**)
9 110 213 An Reservado para la Administración. Rellenar con blancos BLANCOS
10 323 6 An Constante "</AUX>"
11 329 8 An Constante "<VECTOR>"
Vector de páginas. Para su cumplimentación se debe indicar de forma secuencial las páginas que forman parte de esta declaración. Cada página se indicará con 3
digitos. Después de la última página se pondrá el identificador "FIN". Por ejemplo, en un fichero que contenga una página 1, una 2, una 3, cuatro páginas 4, una 10,
una 11, una 12, una 13 y una página 19, debería rellenarse el vector con el siguiente contenido: 001002003004004004004010011012013019FIN (y el resto a blancos
12 337 300 An hasta completar las 300 posiciones
13 637 9 An Constante "</VECTOR>"
Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo
14 646Variable An documento
15*** 18 An Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "</T100020130A0000>"
16*** 2An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
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
8 (F) Regímenes especiales 6 3
9 (G2) G/P sometidas a retención < 1 año 72 24
9 (G2) G/P de acciones < 1 año 72 24
9 (G2) G/P otros elementos patrimoniales < 1 año 48 24
10 (G3) G/P sometidas a retención > 1 año 72 24
10 (G3) G/P de acciones > 1 año 72 24
10 (G3) G/P otros elementos patrimoniales > 1 año 48 24
10 (G4) Imputación a 2009 G/P ejercicios anteriores 15 5
11 ((G4)) G/P difer. ppor reinversión 15 5
12 Aport. sistemas previsión social 4 2
12 Aport. Sistemas previsión social a favor de discapacitados 4 2
12 Aport. patrim. proteg. discapacit. 4 2
12 Pens. Compens. A favor cónyuge 4 2
12 Aport. Deportistas profesionales 4 2
13 ((K)) Exceso no reducido. Réggimen ggeneral 4 2
13 (K) Exceso no reducido. Discapacitados 4 2
13 (K) Exceso no reducido. Patrimonios protegidos 4 2
13 (K) Exceso no reducido. Deportistas profesionales 4 2

# Pag. 3

100-01
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
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
12 66 8 Num Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año < 2013 (10) OBLIGATORIO
13 74 1 Num Primer Declarante - Grado de discapacidad "0", "1", "2" o "3" (11)
14 75 1 Num Primer Declarante - Cambio de domicilio "1" o cero (13)
15 76 5 A Primer Declarante - Domicilio habitual - Tipo de Vía (15)
16 81 5 Num Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Vía INE
17 86 50 An Primer Declarante - Domicilio habitual - Nombre de la Vía Pública (16)
18 136 3 An Primer Declarante - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
1199 113399 55 NNuumm PPrriimmeerr DDeeccllaarraannttee - DDoommiicciilliioo hhaabbiittuuaall - NNúúmmeerroo ddee CCaassaa ((1188))
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
48 659 5 Num Datos adicionales vivienda - Vivienda 1.Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
49 664 5 Num Datos adicionales vivienda - Vivienda 1.Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
50 669 1 Num Datos adicionales vivienda - Vivienda 1.Situación (clave) "1", "2", "3" o "4" (53)
51 670 20 An Datos adicionales vivienda - Vivienda 1.Referencia catastral (54)
52 690 1 Num Datos adicionales vivienda - Vivienda 2.Titularidad "0", "1", "2", "3" o "4" (50)
53 691 5 Num Datos adicionales vivienda - Vivienda 2. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
54 696 5 Num Datos adicionales vivienda - Vivienda 2. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
55 701 1 Num Datos adicionales vivienda - Vivienda 2.Situación (clave) "0", "1", "2", "3" o "4" (53)
56 702 20 An Datos adicionales vivienda - Vivienda 2. Referencia catastral (54)
57 722 1 Num Datos adicionales vivienda - Vivienda 3.Titularidad "0", "1", "2", "3" o "4" (50)
58 723 5 Num Datos adicionales vivienda - Vivienda 3. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
59 728 5 Num Datos adicionales vivienda - Vivienda 3. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
60 733 1 Num Datos adicionales vivienda - Vivienda 3. Situación (clave) "0", "1", "2", "3" o "4" (53)
61 734 20 An Datos adicionales vivienda - Vivienda 3. Referencia catastral (54)
62 754 1 Num Datos adicionales vivienda - Vivienda 4.Titularidad "0", "1", "2", "3" o "4" (50)
6633 775555 55 NNuumm DDaattooss aaddiicciioonnaalleess vviivviieennddaa -- VViivviieennddaa 44. PPoorrcceennttaajjee ppaarrttiicciippaacciióónn PPrriimmeerr ddeeccllaarraannttee ((ttrreess eenntteerrooss, ddooss ddeecciimmaalleess)) ((5511))
64 760 5 Num Datos adicionales vivienda - Vivienda 4. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
65 765 1 Num Datos adicionales vivienda - Vivienda 4. Situación (clave) "0", "1", "2", "3" o "4" (53)
66 766 20 An Datos adicionales vivienda - Vivienda 4. Referencia catastral (54)
67 786 1 Num Datos adicionales vivienda - Vivienda 5.Titularidad "0", "1", "2", "3" o "4" (50)
68 787 5 Num Datos adicionales vivienda - Vivienda 5. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
69 792 5 Num Datos adicionales vivienda - Vivienda 5. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
70 797 1 Num Datos adicionales vivienda - Vivienda 5. Situación (clave) "0", "1", "2", "3" o "4" (53)
71 798 20 An Datos adicionales vivienda - Vivienda 5. Referencia catastral (54)
72 818 1 Num Datos adicionales vivienda - Vivienda 6.Titularidad "0", "1", "2", "3" o "4" (50)
73 819 5 Num Datos adicionales vivienda - Vivienda 6. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
74 824 5 Num Datos adicionales vivienda - Vivienda 6. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
75 829 1 Num Datos adicionales vivienda - Vivienda 6. Situación (clave) "0", "1", "2", "3" o "4" (53)
76 830 20 An Datos adicionales vivienda - Vivienda 6. Referencia catastral (54)
77 850 1 Num Datos adicionales vivienda - Vivienda 7.Titularidad "0", "1", "2", "3" o "4" (50)
78 851 5 Num Datos adicionales vivienda - Vivienda 7. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
79 856 5 Num Datos adicionales vivienda - Vivienda 7. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
80 861 1 Num Datos adicionales vivienda - Vivienda 7. Situación (clave) "0", "1", "2", "3" o "4" (53)
81 862 20 An Datos adicionales vivienda - Vivienda 7. Referencia catastral (54)
82 882 1 Num Datos adicionales vivienda - Vivienda 8.Titularidad "0", "1", "2", "3" o "4" (50)
83 883 5 Num Datos adicionales vivienda - Vivienda 8. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
Página 4

# Pag. 5

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
84 888 5 Num Datos adicionales vivienda - Vivienda 8. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
85 893 1 Num Datos adicionales vivienda - Vivienda 8. Situación (clave) "0", "1", "2", "3" o "4" (53)
86 894 20 An Datos adicionales vivienda - Vivienda 8. Referencia catastral (54)
87 914 9 An Datos adicionales vivienda - Nif Arrendador (55)
88 923 20 An Datos adicionales vivienda - Si no tiene NIF. Nº identificación en el país de residencia (59)
89 943 9 An Cónyuge - NIF (61)
90 952 15 A Cónyuge - Primer apellido (62)
91 967 15 A Cónyuge - Segundo apellido (63)
92 982 15 A Cónyuge - Nombre (64)
93 997 1 A Cónyuge - Sexo "H" Hombre, "M" Mujer (65)
94 998 8 Num Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero. (66)
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
110077 11008899 33 AAnn CCóónnyyuuggee -- DDoommiicciilliioo hhaabbiittuuaall -- PPllaannttaa ((2233))
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
130 1591 1 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
131 1592 9 An Representante - N.I.F. (75)
132 1601 32 An Representante - Apellidos y nombre o razón social (76)
133 1633 20 An Fecha declaración - Lugar
134 1653 2 Num Fecha declaración - Fecha -Día
135 1655 10 A Fecha declaración - Fecha - Mes
136 1665 4 Num Fecha declaración - Fecha - Año
137 1669 34 An Número de cuenta IBAN
138 1703 13 Num Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
139 1716 21 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
140 1737 13 N Resultado de la declaración
141 1750 1 Num Fraccionamiento del pago. "1" o cero
142 1751 1 Num Domiciliación 2º plazo."1" o cero
143 1752 1 Num Renuncia a la devolución. "1" o cero
144 1753 1 Num Compensación entre cónyuges. "1" o cero
145 1754 20An Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
146 1774 13An SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
147 1787 9An Identificador de Fin de registro. OBLIGATORIO Constante </T10001>
148 1796 2An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total 1797
Página 6

# Pag. 7

100-02
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "02"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 9 An Hijos y descendientes - 1º - N.I.F. (80)
7 19 33 A Hijos y descendientes - 1º - Apellidos y nombre (81)
8 52 8 Num Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año < 2013 o cero (82)
9 60 8 Num Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
10 68 1 Num Hijos y descendientes - 1º - Grado discapacidad "0", "1", "2" o "3" (84)
11 69 1 An Hijos y descendientes - 1º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
12 70 1 An Hijos y descendientes - 1º - Otras situaciones clave:"1","2","3","4" o blanco (86)
13 71 9 An Hijos y descendientes - 2º - N.I.F. (80)
14 80 33 A Hijos y descendientes - 2º - Apellidos y nombre (81)
15 113 8 Num Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año < 2013 o cero (82)
16 121 8 Num Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año < 2013 o cero (83)
17 129 1 Num Hijos y descendientes - 2º - Grado discapacidad "0", "1", "2" o "3" (84)
18 130 1 An Hijos y descendientes - 2º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
1199 113311 11 AAnn HHiijjooss yy ddeesscceennddiieenntteess - 22º - OOttrraass ssiittuuaacciioonneess "11",,"22",,"33",,"44" oo bbllaannccoo ((8866))
20 132 9 An Hijos y descendientes - 3º - N.I.F. (80)
21 141 33 A Hijos y descendientes - 3º - Apellidos y nombre (81)
22 174 8 Num Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
23 182 8 Num Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
24 190 1 Num Hijos y descendientes - 3º - Grado discapacidad "0", "1", "2" o "3" (84)
25 191 1 An Hijos y descendientes - 3º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
26 192 1 An Hijos y descendientes - 3º - Otras situaciones "1","2","3","4" o blanco (86)
27 193 9 An Hijos y descendientes - 4º - N.I.F. (80)
28 202 33 A Hijos y descendientes - 4º - Apellidos y nombre (81)
29 235 8 Num Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
30 243 8 Num Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
31 251 1 Num Hijos y descendientes - 4º - Grado discapacidad "0", "1", "2" o "3" (84)
32 252 1 An Hijos y descendientes - 4º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
33 253 1 An Hijos y descendientes - 4º - Otras situaciones "1","2","3","4" o blanco (86)
34 254 9 An Hijos y descendientes - 5º - N.I.F. (80)
35 263 33 A Hijos y descendientes - 5º - Apellidos y nombre (81)
36 296 8 Num Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
37 304 8 Num Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
38 312 1 Num Hijos y descendientes - 5º - Grado discapacidad "0", "1", "2" o "3" (84)
39 313 1 An Hijos y descendientes - 5º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
Página 7

# Pag. 8

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
40 314 1 An Hijos y descendientes - 5º - Otras situaciones "1","2","3","4" o blanco (86)
41 315 9 An Hijos y descendientes - 6º - N.I.F. (80)
42 324 33 A Hijos y descendientes - 6º - Apellidos y nombre (81)
43 357 8 Num Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
44 365 8 Num Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
45 373 1 Num Hijos y descendientes - 6º - Grado discapacidad "0", "1", "2" o "3" (84)
46 374 1 An Hijos y descendientes - 6º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
47 375 1 An Hijos y descendientes - 6º - Otras situaciones "1","2","3","4" o blanco (86)
48 376 9 An Hijos y descendientes - 7º - N.I.F. (80)
49 385 33 A Hijos y descendientes - 7º - Apellidos y nombre (81)
50 418 8 Num Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
51 426 8 Num Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
52 434 1 Num Hijos y descendientes - 7º - Grado discapacidad "0", "1", "2" o "3" (84)
53 435 1 An Hijos y descendientes - 7º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
54 436 1 An Hijos y descendientes - 7º - Otras situaciones "1","2","3","4" o blanco (86)
55 437 9 An Hijos y descendientes - 8º - N.I.F. (80)
56 446 33 A Hijos y descendientes - 8º - Apellidos y nombre (81)
57 479 8 Num Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
58 487 8 Num Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
59 495 1 Num Hijos y descendientes - 8º - Grado discapacidad "0", "1", "2" o "3" (84)
60 496 1 An Hijos y descendientes - 8º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
61 497 1 An Hijos y descendientes - 8º - Otras situaciones "1","2","3","4" o blanco (86)
62 498 9 An Hijos y descendientes - 9º - N.I.F. (80)
6633 550077 3333 AA HHiijjooss yy ddeesscceennddiieenntteess -- 99ºº -- AAppeelllliiddooss yy nnoommbbrree ((8811))
64 540 8 Num Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
65 548 8 Num Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
66 556 1 Num Hijos y descendientes - 9º - Grado discapacidad "0", "1", "2" o "3" (84)
67 557 1 An Hijos y descendientes - 9º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
68 558 1 An Hijos y descendientes - 9º - Otras situaciones "1","2","3","4" o blanco (86)
69 559 9 An Hijos y descendientes - 10º - N.I.F. (80)
70 568 33 A Hijos y descendientes - 10º - Apellidos y nombre (81)
71 601 8 Num Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
72 609 8 Num Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
73 617 1 Num Hijos y descendientes - 10º - Grado discapacidad "0", "1", "2" o "3" (84)
74 618 1 An Hijos y descendientes - 10º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
75 619 1 An Hijos y descendientes - 10º - Otras situaciones "1","2","3","4" o blanco (86)
76 620 9 An Hijos y descendientes - 11º - N.I.F. (80)
77 629 33 A Hijos y descendientes - 11º - Apellidos y nombre (81)
78 662 8 Num Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
79 670 8 Num Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
80 678 1 Num Hijos y descendientes - 11º - Grado discapacidad "0", "1", "2" o "3" (84)
81 679 1 An Hijos y descendientes - 11º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
82 680 1 An Hijos y descendientes - 11º - Otras situaciones "1","2","3","4" o blanco (86)
83 681 9 An Hijos y descendientes - 12º - N.I.F. (80)
Página 8

# Pag. 9

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
84 690 33 A Hijos y descendientes - 12º - Apellidos y nombre (81)
85 723 8 Num Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (82)
86 731 8 Num Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2013 o cero (83)
87 739 1 Num Hijos y descendientes - 12º - Grado discapacidad "0", "1", "2" o "3" (84)
88 740 1 An Hijos y descendientes - 12º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
89 741 1 An Hijos y descendientes - 12º - Otras situaciones "1","2","3","4" o blanco (86)
90 742 2 Num Hijos y descendientes - Fallecido 2013 - Nº Orden (87)
91 744 8 Num Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
92 752 2 Num Hijos y descendientes - Fallecido 2013 - Nº Orden (87)
93 754 8 Num Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
94 762 9 An Hijos y descendientes - A efectos de la declaración conjunta los hijos 1 y 2 son relacionados con los NIF
95 771 9 An Hijos y descendientes - A efectos de la declaración conjunta los hijos 1 y 2 son relacionados con los NIF
96 780 9 An Hijos y descendientes - Otro progenitor - Nif (56)
97 789 33 A Hijos y descendientes - Otro progenitor - Apellidos y nombre (57)
98 822 1 Num Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla. "1" o cero. (58)
99 823 24 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
100 847 9 An Ascendientes mayores 65 años o discapacitados - 1º - N.I.F. (90)
101 856 33 A Ascendientes mayores 65 años o discapacitados - 1º - Apellidos y nombre (91)
102 889 8 Num Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (92)
103 897 1 Num Ascendientes mayores 65 años o discapacitados - 1º - Grado discapacidad "0", "1", "2" o "3" (93)
104 898 1 An Ascendientes mayores 65 años o discapacitados - 1º - Vinculación clave:"1", "2" o blanco (94)
105 899 1 An Ascendientes mayores 65 años o discapacitados - 1º - Convivencia "2" a "9" o blanco (95)
106 900 9 An Ascendientes mayores 65 años o discapacitados - 2º - N.I.F. (90)
110077 990099 3333 AA AAsscceennddiieenntteess mmaayyoorreess 6655 aaññooss oo ddiissccaappaacciittaaddooss -- 22ºº -- AAppeelllliiddooss yy nnoommbbrree ((9911))
108 942 8 Num Ascendientes mayores 65 años o discapacitados - 2º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (92)
109 950 1 Num Ascendientes mayores 65 años o discapacitados - 2º - Grado discapacidad "0", "1", "2" o "3" (93)
110 951 1 An Ascendientes mayores 65 años o discapacitados - 2º - Vinculación clave:"1", "2" o blanco (94)
111 952 1 An Ascendientes mayores 65 años o discapacitados - 2º - Convivencia "2" a "9" o blanco (95)
112 953 9 An Ascendientes mayores 65 años o discapacitados - 3º - N.I.F. (90)
113 962 33 A Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
114 995 8 Num Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año < 2013 o cero (92)
115 1003 1 Num Ascendientes mayores 65 años o discapacitados - 3º - Grado discapacidad "0", "1", "2" o "3" (93)
116 1004 1 An Ascendientes mayores 65 años o discapacitados - 3º - Vinculación clave:"1", "2" o blanco (94)
117 1005 1 An Ascendientes mayores 65 años o discapacitados - 3º - Convivencia "2" a "9" o blanco (95)
118 1006 9 An Ascendientes mayores 65 años o discapacitados - 4º - N.I.F. (90)
119 1015 33 A Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
120 1048 8 Num Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2013 o cero (92)
121 1056 1 Num Ascendientes mayores 65 años o discapacitados - 4º - Grado discapacidad "0", "1", "2" o "3" (93)
122 1057 1 An Ascendientes mayores 65 años o discapacitados - 4º - Vinculación clave:"1", "2" o blanco (94)
123 1058 1 An Ascendientes mayores 65 años o discapacitados - 4º - Convivencia "2" a "9" o blanco (95)
124 1059 8 Num Devengo - Fecha de finalización del período impositivo (fallecimiento 2013) (DDMMAAAA) o cero (100)
125 1067 1 Num Opción de tributación. "1" Individual, "2" Conjunta. Campo OBLIGATORIO (101) (102) OBLIGATORIO
126 1068 2 Num Comunidad/Ciudad autónoma de residencia en 2013 - Clave (103) Incluido en el fichero COMAUTO.TXT OBLIGATORIO
127 1070 1 A Asignación tributaria a la Iglesia Católica. "X" o blanco. (105)
Página 9

# Pag. 10

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
128 1071 1 A Asignación de cantidades a fines sociales. "X" o blanco. (106)
129 1072 1 Num Borrador Declaración o datos fiscales 2014. Recibir por correo ordinario y no visualizarlo por internet. "1" o cero (110)
130 1073 1 Num Borrador Declaración o datos fiscales 2014. Obtener tributación individual. "1" o cero (111)
131 1074 1 Num Declaración complementaria - Si es complementaria por atrasos de rendimientos del trabajo. "1" o cero (121)
132 1075 1 Num Declaración complementaria - Si es complementaria por haberse producido alguno de los supuestos especiales. "1" o cero (122)
133 1076 1 Num Declaración complementaria - Si es complementaria a devolver. "1" o cero (123)
134 1077 1 Num Declaración complementaria - Si es complementaria por traslado de residencia a otro Estado miembro, "1" o cero (124)
135 1078 1 Num Declaración complementaria - Si es complementaria por supuestos distintos "1" o cero (120)
136 1079 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10002>
137 1088 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total 1089
Página 10

# Pag. 11

100-03
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
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
11 75 13 N Rdto. Trabajo - Contribuciones Planes Pensiones y Mutualidades Previsión Social - Importes (006)
12 88 13 N Rdto. Trabajo - Contribuciones empresariales a seguros colectivos dependencia. Imputado al contribuyente (043)
13 101 13 N Rdto. Trabajo - Aportaciones al patrimonio protegido de discapacitados - Importe (007)
14 114 13 N Rdto. Trabajo - Reducciones - Importe (008)
15 127 13 N Rdto. Trabajo - Total ingresos íntegros computables (009)
16 140 13 N Rdto. Trabajo - Cotizaciones Seguridad Social/Mutual. grales. funcionarios/cotiz. colegios huerfanos (010)
17 153 13 N Rdto. Trabajo - Cuotas satisfechas a sindicatos (011)
18 166 13 N Rdto. Trabajo - Cuotas a colegios profesionales (012)
19 179 13 N Rdto. Trabajo - Gastos defensa jurídica derivados litigios con empleador (013)
20 192 13 N Rdto. Trabajo - Total gastos deducibles (014)
21 205 13 N Rdto. Trabajo - Rendimiento neto (015)
2222 221188 1133 NN RRddttoo. TTrraabbaajjoo -- RReedduucccciióónn oobbtteenncciióónn rreennddiimmiieennttooss ddee ttrraabbaajjoo. CCuuaannttííaa aapplliiccaabbllee ccoonn ccaarráácctteerr ggeenneerraall ((001166))
23 231 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Incremento trabajadores activos > 65 años (017)
24 244 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Incremento contribuyentes desempleados con traslado de residencia (018)
25 257 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Reducción adicional para trabajadores activos discapacitados (019)
26 270 13 N Rdto. Trabajo - Rendimiento neto reducido (020)
27 283 13 N (B) Rdto.cap.mob.- Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (021)
28 296 13 N Rdto.cap.mob.- Base imponible ahorro - Intereses de activos financieros con derecho a bonificación (022)
29 309 13 N Rdto.cap.mob.- Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (023)
30 322 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (024)
31 335 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros(025)
32 348 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (026)
33 361 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. Procedentes de rentas que tengan por causa la imposición de capitales (027)
34 374 13 N Rdto.cap.mob.- Base imponible ahorro - Total ingresos íntegros (028)
35 387 13 N Rdto.cap.mob.- Base imponible ahorro - Gastos fiscalmente deducibles (029)
36 400 13 N Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto (030)
37 413 13 N Rdto.cap.mob.- Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (031)
38 426 13 N Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto reducido (032)
39 439 13 N (B) Rdto.cap.mob.- Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (033)
40 452 13 N Rdto.cap.mob.- Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (034)
41 465 13 N Rdto.cap.mob.- Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (035)
42 478 13 N Rdto.cap.mob.- Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (036)
43 491 13 N Rdto.cap.mob.- Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (037)
44 504 13 N Rdto.cap.mob.- Base imponible general - Total ingresos íntegros (038)
45 517 13 N Rdto.cap.mob.- Base imponible general - Gastos fiscalmente deducibles (039)
Página 11

# Pag. 12

100-03
Nº Posic. Tipo Descripción Validación Contenido
46 530 13 N Rdto.cap.mob.- Base imponible general - Rendimiento neto (040)
47 543 13 N Rdto.cap.mob.- Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (041)
48 556 13 N Rdto.cap.mob.- Base imponible general - Rendimiento neto reducido (042)
49 569 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10003>
50 578 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 579
Página 12

# Pag. 13

100-04
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "04"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 2 Num Nº de hojas adicionales que se adjuntan
7 12 1 Tit C (C) Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Contribuyente "0" a "9" (045)
8 13 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (046)
9 18 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje usufructo (047)
10 23 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Naturaleza (048)
11 24 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Uso o destino. Clave (049)
12 25 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Situación "0", "1", "2", "3" o "4" (050)
13 26 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Referencia catastral (051)
14 46 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (052)
15 51 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Número de días (053)
16 54 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Renta imputada (054)
17 67 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Ingresos íntegros computables (055)
18 80 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (056)
1199 9933 1133 NN CC BBiieenneess iinnmmuueebblleess nnoo aaffeeccttooss. RReellaacciióónn iinnmmuueebblleess yy rreennttaass. IInnmmuueebbllee 11. AArrrreennddaaddoo oo cceeddiiddoo. GGaassttooss ddeedduucciibblleess. IInntteerreesseess. IImmppoorrttee 22001133 ((005577))
20 106 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (058)
21 119 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (059)
22 132 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto (060)
23 145 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (061)
24 158 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción rendimientos más de 2 años (062)
25 171 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento mínimo computable parentesco (063)
26 184 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto reducido (064)
27 197 1 Tit C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Contribuyente "0" a "9" (045)
28 198 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (046)
29 203 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje usufructo (047)
30 208 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Naturaleza (048)
31 209 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Uso o destino. Clave (049)
32 210 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Situación "0", "1", "2", "3" o "4" (050)
33 211 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Referencia catastral (051)
34 231 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (052)
35 236 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Número de días (053)
36 239 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Renta imputada (054)
37 252 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Ingresos íntegros computables (055)
38 265 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (056)
Página 13

# Pag. 14

100-04
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
39 278 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe (057)
40 291 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (058)
41 304 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (059)
42 317 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto (060)
43 330 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (061)
44 343 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción rendimientos más de 2 años (062)
45 356 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento mínimo computable parentesco (063)
46 369 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto reducido (064)
47 382 1 Tit C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Contribuyente "0" a "9" (045)
48 383 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (046)
49 388 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Porcentaje usufructo (047)
50 393 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Naturaleza (048)
51 394 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Uso o destino. Clave (049)
52 395 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Situación "0", "1", "2", "3" o "4" (050)
53 396 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Referencia catastral (051)
54 416 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (052)
55 421 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Número de días (053)
56 424 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Renta imputada (054)
57 437 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Ingresos íntegros computables (055)
58 450 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (056)
59 463 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Importe (057)
60 476 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (058)
61 489 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (059)
6622 550022 1133 NN CC BBiieenneess iinnmmuueebblleess nnoo aaffeeccttooss. RReellaacciióónn iinnmmuueebblleess yy rreennttaass. IInnmmuueebbllee 33. AArrrreennddaaddoo oo cceeddiiddoo. RReennddiimmiieennttoo nneettoo ((006600))
63 515 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (061)
64 528 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Reducción rendimientos más de 2 años (062)
65 541 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento mínimo computable parentesco (063)
66 554 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento neto reducido (064)
67 567 13 N Bienes inmuebles no afectos. Rentas totales . Suma de rentas inmobiliarias imputadas (067)
68 580 13 N Bienes inmuebles no afectos. Rentas totales . Suma rendimientos netos reducidos del capital inmobiliario (068)
69 593 3 Num Número de inmuebles en declaración conjunta (Reservado para la Administración)
70 596 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Contribuyente "0" a "9" (069)
71 597 9 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. NIF entidad (070)
72 606 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Porcentaje titularidad (3 enteros y 2 decimales) (071)
73 611 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Naturaleza (072)
74 612 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Situación "0", "1", "2", "3" o "4" (073)
75 613 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Referencia catastral (074)
76 633 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Contribuyente "0" a "9" (069)
77 634 9 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. NIF entidad (070)
78 643 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Porcentaje titularidad (3 enteros y 2 decimales) (071)
79 648 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Naturaleza (072)
80 649 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Situación "0", "1", "2", "3" o "4" (073)
81 650 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Referencia catastral (074)
Página 14

# Pag. 15

100-04
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
82 670 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Contribuyente "0" a "9" (069)
83 671 9 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. NIF entidad (070)
84 680 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Porcentaje titularidad (3 enteros y 2 decimales) (071)
85 685 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Naturaleza (072)
86 686 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Situación "0", "1", "2", "3" o "4" (073)
87 687 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Referencia catastral (074)
88 707 1 Tit C (D) Bienes inmuebles urbanos afectos. Inmueble 1. Contribuyente "0" a "9" (076)
89 708 5 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (077)
90 713 5 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje usufructo (078)
91 718 1 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Naturaleza (clave) (079)
92 719 1 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Situación "0", "1", "2", "3" o "4" (080)
93 720 20 An C Bienes inmuebles urbanos afectos. Inmueble 1. Referencia catastral (081)
94 740 1 Tit C Bienes inmuebles urbanos afectos. Inmueble 2. Contribuyente "0" a "9" (076)
95 741 5 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (077)
96 746 5 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje usufructo (078)
97 751 1 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Naturaleza (clave) (079)
98 752 1 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Situación "0", "1", "2", "3" o "4" (080)
99 753 20 An C Bienes inmuebles urbanos afectos. Inmueble 2. Referencia catastral (081)
100 773 1 Tit C Bienes inmuebles urbanos afectos. Inmueble 3. Contribuyente "0" a "9" (076)
101 774 5 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (077)
102 779 5 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje usufructo (078)
103 784 1 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Naturaleza (clave) (079)
104 785 1 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Situación "0", "1", "2", "3" o "4" (080)
110055 778866 2200 AAnn CC BBiieenneess iinnmmuueebblleess uurrbbaannooss aaffeeccttooss. IInnmmuueebbllee 33. RReeffeerreenncciiaa ccaattaassttrraall ((008811))
106 806 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10004>
107 815 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 816
Página 15

# Pag. 16

100-05
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "05"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 3 Actividades a las que resulte aplicable un mismo régimen
7 11 1 Tit C (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Contribuyente "0" a "9" (084)
8 12 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Tipo actividad. Clave (Blanco o de "1" a "5") (085)
9 13 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Modalidad Normal (087) o Simplificada (088) "0", "1" o "2"
10 14 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Epígrafe IAE (086) (**)
11 19 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Criterio cobros/pagos. "1" o cero. (089)
12 20 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Explotación (090)
13 33 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Otros ingresos (091)
14 46 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Autoconsumo bienes/servicios (092)
15 59 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Transmisión elementos patrimoniales: exceso amortización deducida (093)
16 72 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Total ingresos computables (094)
17 85 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Consumos de explotación (095)
18 98 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Sueldos y salarios (096)
19 111 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Seguridad Social (097)
20 124 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros gastos de personal (098)
21 137 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Arrendamientos y cánones (099)
22 150 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Reparación y conservación (100)
23 163 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Servicios profesionales independientes (101)
24 176 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros servicios exteriores (102)
25 189 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Tributos fiscalmente deducibles (103)
26 202 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Gastos financieros (104)
27 215 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Amortizaciones (105)
28 228 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Pérdidas por deterioro (106)
29 241 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (convenios) (107)
30 254 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (gastos) (108)
31 267 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros conceptos fiscalmente deducibles (109)
32 280 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Suma (110)
33 293 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Normal - Provisiones (111)
34 306 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Normal - Total gastos deducibles (112)
35 319 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Diferencia (113)
36 332 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (114)
37 345 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Total gastos deducibles (115)
38 358 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Rdto. neto (116)
39 371 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Reducciones (117)
Página 16

# Pag. 17

100-05
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
40 384 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -1- Rto. Neto reduc.(118)
41 397 1 Tit C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Contribuyente "0" a "9" (084)
42 398 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Tipo actividad.Clave (Blanco o de "1" a "5") (085)
43 399 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Modalidad Normal (087) o Simplificada (088) "0", "1" o "2"
44 400 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Epígrafe IAE (086) (**)
45 405 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Criterio cobros/pagos. "1" o cero. (089)
46 406 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Explotación (090)
47 419 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Otros ingresos (091)
48 432 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Autoconsumo bienes/servicios (092)
49 445 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Transmisión elementos patrimoniales: exceso amortización deducida (093)
50 458 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Total ingresos computables (094)
51 471 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Consumos de explotación (095)
52 484 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Sueldos y salarios (096)
53 497 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Seguridad Social (097)
54 510 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos de personal (098)
55 523 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Arrendamientos y cánones (099)
56 536 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Reparación y conservación (100)
57 549 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Servicios profesionales independientes (101)
58 562 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros servicios exteriores (102)
59 575 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Tributos fiscalmente deducibles (103)
60 588 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Gastos financieros (104)
61 601 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Amortizaciones (105)
62 614 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Pérdidas por deterioro (106)
63 627 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (convenios) (107)
64 640 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (gastos) (108)
65 653 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos fiscalmente deducibles (109)
66 666 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Suma de gastos (110)
67 679 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Normal - Provisiones (111)
68 692 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Normal - Total gastos deducibles (112)
69 705 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Diferencia (113)
70 718 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (114)
71 731 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Total gastos deducibles (115)
72 744 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto. neto (116)
73 757 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Reducciones (117)
74 770 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rto.neto reduc. (118)
75 783 1 Tit C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Contribuyente "0" a "9" (084)
76 784 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Tipo actividad.Clave (Blanco o de "1" a "5") (085)
77 785 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Modalidad Normal (087) o Simplificada (088) "0", "1" o "2"
78 786 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Epígrafe IAE (086) (**)
79 791 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Criterio cobros/pagos. "1" o cero. (089)
80 792 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Explotación (090)
81 805 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Otros ingresos (091)
82 818 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Autoconsumo bienes/servicios (092)
83 831 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Transmisión elementos patrimoniales: exceso amortización deducida (093)
Página 17

# Pag. 18

100-05
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
84 844 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Total ingresos computables (094)
85 857 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Consumos de explotación (095)
86 870 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Sueldos y salarios (096)
87 883 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Seguridad Social (097)
88 896 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos de personal (098)
89 909 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Arrendamientos y cánones (099)
90 922 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Reparación y conservación (100)
91 935 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Servicios profesionales independientes (101)
92 948 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros servicios exteriores (102)
93 961 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Tributos fiscalmente deducibles (103)
94 974 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Gastos financieros (104)
95 987 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Amortizaciones (105)
96 1000 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Pérdidas por deterioro (106)
97 1013 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (convenios) (107)
98 1026 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (gastos) (108)
99 1039 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos fiscalmente deducibles (109)
100 1052 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Suma de gastos (110)
101 1065 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Normal - Provisiones (111)
102 1078 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Normal - Total gastos deducibles (112)
103 1091 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Diferencia (113)
104 1104 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (114)
105 1117 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Total gastos deducibles (115)
106 1130 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto. neto (116)
107 1143 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Reducciones (117)
108 1156 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rto.neto reduc. (118)
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
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
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
11 42 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales)
12 51 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales)
13 62 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Definición
14 86 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales)
15 95 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales)
16 106 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Definición
17 130 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales)
18 139 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales)
1199 115500 2244 AA CC RRddttooss..aaccttiivv..eeccoonnóómm..eesstt..oobbjjeettiivvaa - AAcctt.. rreeaalliizz..//rrddttooss.. oobbtteenniiddooss - AAccttiivv.. 11ª - MMóódduulloo 44 - DDeeffiinniicciióónn
20 174 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales)
21 183 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales)
22 194 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Definición
23 218 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales)
24 227 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales)
25 238 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Definición
26 262 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales)
27 271 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales)
28 282 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Definición
29 306 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales)
30 315 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales)
31 326 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma) (129)
32 339 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo (130)
33 352 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (131)
34 365 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (132)
35 378 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (133)
36 382 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (134)
37 386 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (135)
38 390 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (136)
39 394 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (137)
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
52 533 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales)
53 542 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales)
54 553 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Definición
55 577 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales)
56 586 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales)
57 597 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Definición
58 621 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales)
59 630 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales)
60 641 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Definición
61 665 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales)
62 674 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales)
6633 668855 2244 AA CC RRddttooss..aaccttiivv..eeccoonnóómm..eesstt..oobbjjeettiivvaa -- AAcctt.. rreeaalliizz..//rrddttooss.. oobbtteenniiddooss -- AAccttiivv.. 22ª -- MMóódduulloo 55 -- DDeeffiinniicciióónn
64 709 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales)
65 718 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales)
66 729 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Definición
67 753 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales)
68 762 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales)
69 773 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Definición
70 797 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales)
71 806 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales)
72 817 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto previo (suma) (129)
73 830 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos al empleo (130)
74 843 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos a la inversion (131)
75 856 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto minorado (132)
76 869 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector especial (2 enteros y 2 decimales) (133)
77 873 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (134)
78 877 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de temporada (2 enteros y 2 decimales) (135)
79 881 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de exceso (2 enteros y 2 decimales) (136)
80 885 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (137)
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
1042
(**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos
blancos.
Página 21

# Pag. 22

100-07
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
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
1199 9988 1111 NN CC RRddttooss. aaggrríícc.ggaannaadd.yy ffoorreesstt. eesstt. oobbjjeettiivvaa --AAcctt. rreeaalliizz.//rrddttooss-- AAccttiivv 11ªª -- PPrroodduuccttoo 44ºº -- IInnggrreessooss íínntteeggrrooss
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
54 433 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Medios ajenos (2 enteros y 2 decimales) (159)
55 437 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Utiliz. personal asalariado (2 enteros y 2 decimales) (160)
56 441 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (161)
57 445 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (162)
58 449 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º, >50 % (2 enteros y 2 decimales) Índice 2 (162) Ver NOTA
59 453 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Activ.agricultura ecológica (2 enteros y 2 decimales) (163)
60 457 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Empresa no supera 9447,91 € (2 enteros y 2 decimales) (164)
61 461 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Determin. activ. forestales (2 enteros y 2 decimales) (165)
6622 446655 1133 NN CC RRddttooss. aaggrríícc.ggaannaadd.yy ffoorreesstt. eesstt. oobbjjeettiivvaa --AAcctt. rreeaalliizz.//rrddttooss-- AAccttiivv 11ªª -- RRddttoo. nneettoo ddee mmóódduullooss ((116666))
63 478 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción carácter general (167)
64 491 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Diferencia (168)
65 504 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción agricultores jóvenes (169)
66 517 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Gastos extraordinarios por circunstancias excepcionales (170)
67 530 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto (171)
68 543 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones rendimientos generados más 2 años o forma irregular (172)
69 556 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto reducido (173)
70 569 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Clave actividad: de "0" a "9" (152)
71 570 1 Tit C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Contribuyente titular de actividad: de "0" a "9" (151)
72 571 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Criterio cobros/pagos: "1" ó "0" (153)
73 572 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Ingresos íntegros
74 583 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Índice
75 589 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Rdto. base producto
76 600 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Ingresos íntegros
77 611 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Índice
78 617 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Rdto. base producto
79 628 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Ingresos íntegros
80 639 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Índice
81 645 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Rdto. base producto
Página 23

# Pag. 24

100-07
Nº Posic. Long. Tipo Com Descripción Validación Contenido
82 656 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Ingresos íntegros
83 667 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Índice
84 673 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Rdto. base producto
85 684 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Ingresos íntegros
86 695 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Índice
87 701 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Rdto. base producto
88 712 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Ingresos íntegros
89 723 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Índice
90 729 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Rdto. base producto
91 740 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Ingresos íntegros
92 751 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Índice
93 757 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Rdto. base producto
94 768 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Ingresos íntegros
95 779 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Índice
96 785 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Rdto. base producto
97 796 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Ingresos íntegros
98 807 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Índice
99 813 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Rdto. base producto
100 824 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Ingresos íntegros
101 835 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Índice
102 841 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Rdto. base producto
103 852 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Ingresos íntegros
104 863 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Índice
110055 886699 1111 NN CC RRddttooss. aaggrríícc.ggaannaadd.yy ffoorreesstt. eesstt. oobbjjeettiivvaa --AAcctt. rreeaalliizz.//rrddttooss-- AAccttiivv 22ªª -- PPrroodduuccttoo 1111ºº -- RRddttoo. bbaassee pprroodduuccttoo
106 880 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Ingresos íntegros
107 891 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Índice
108 897 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Rdto. base producto
109 908 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Ingresos íntegros
110 919 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Índice
111 925 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Rdto. base producto
112 936 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Total ingresos íntegros (154)
113 947 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto previo (suma) (155)
114 958 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones (156)
115 969 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Amortizacion inmovilizado (157)
116 980 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto minorado (158)
117 991 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Medios ajenos (2 enteros y 2 decimales) (159)
118 995 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Utiliz. personal asalariado (2 enteros y 2 decimales) (160)
119 999 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (161)
120 1003 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (162)
121 1007 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º, >50 % (2 enteros y 2 decimales) Índice 2 (162) Ver NOTA
122 1011 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Activ.agricultura ecológica (2 enteros y 2 decimales) (163)
123 1015 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Empresa no supera 9447,91 € (2 enteros y 2 decimales) (164)
124 1019 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Determin. activ. forestales (2 enteros y 2 decimales) (165)
Página 24

# Pag. 25

100-07
Nº Posic. Long. Tipo Com Descripción Validación Contenido
125 1023 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto de módulos (166)
126 1036 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción carácter general (167)
127 1049 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Diferencia (168)
128 1062 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción agricultores jóvenes (169)
129 1075 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Gastos extraordinarios por circunstancias excepcionales (170)
130 1088 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto (171)
131 1101 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones rendimientos generados más 2 años o forma irregular (172)
132 1114 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto reducido (173)
133 1127 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Suma rendimientos netos reducidos (178)
134 1140 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Reducción por mantenimiento o creación de empleo (179)
135 1153 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Rendimiento neto reducido total (180)
136 1166 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10007>
137 1175 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1176
NOTA: Cumplimentar sólo cuando el índice 2 sea distinto al índice 1.
Página 25

# Pag. 26

100-08
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "08"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 3 imputaciones
7 11 1 Tit C (F) Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (181)
8 12 9 An C Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - NIF Entidad (182)
9 21 20 An C Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Si no residente Nº de identificación en el país de residencia (199)
10 41 4 Num C Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Porcentaje participación (183)
11 45 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (184)
12 58 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones y minoraciones (185)
13 71 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto computable (186)
14 84 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto (187)
15 97 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto atribuido (188)
16 110 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Reducciones y minoraciones (189)
17 123 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto computable (190)
18 136 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. neto atribuido (191)
1199 114499 1133 NN CC RReeggss. eessppeecciiaalleess -- RRééggiimmeenn aattrriibbuucciióónn rreennttaass -- EEnnttiiddaadd 11 -- RRddttooss. aaccttiivviiddaaddeess eeccoonnóómmiiccaass -- RReedduucccciioonneess yy mmiinnoorraacciioonneess ((119922))
20 162 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. neto computable (193)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
21 175 13 N C generación igual o inferior a un año (B.I.general) - Ganancias (194)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
22 188 13 N C generación igual o inferior a un año (B.I.general) - Pérdidas (195)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
23 201 13 N C integrar B.I. ahorro) - Ganancias (196)
Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
24 214 13 N C integrar B.I. ahorro) - Pérdidas (197)
25 227 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Retenciones e ingresos a cuenta. - Retenciones e ingresos atribuidos (198)
26 240 1 Tit C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (181)
27 241 9 An C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - NIF Entidad (182)
28 250 20 An C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Si no residente Nº de identificación en el país de residencia (199)
29 270 4 Num C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Porcentaje participación (183)
30 274 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (184)
31 287 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones y minoraciones (185)
32 300 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto computable (186)
33 313 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto (187)
Página 26

# Pag. 27

100-08
Nº Posic. Long. Tipo Com Descripción Validación Contenido
34 326 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto atribuido (188)
35 339 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Reducciones y minoraciones (189)
36 352 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto computable (190)
37 365 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. neto atribuido (191)
38 378 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducciones y minoraciones (192)
39 391 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. neto computable (193)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
40 404 13 N C generación igual o inferior a un año (B.I.general) - Ganancias (194)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - No derivadas transmisión y derivadas transmisión elementos patrimoniales período
41 417 13 N C generación igual o inferior a un año (B.I.general) - Pérdidas (195)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
42 430 13 N C integrar B.I. ahorro) - Ganancias (196)
Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - Derivadas transmisión elementos patrimoniales período generación superior a un año (a
43 443 13 N C integrar B.I. ahorro) -Pérdidas (197)
44 456 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Retenciones e ingresos a cuenta. - Retenciones e ingresos atribuidos (198)
45 469 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. capital mobiliario - Rdto. integrar base imponible general - Total rdto. neto computable (200)
46 482 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. capital mobiliario - Rdto. integrar base imponible ahorro - Total rdto. neto atribuido (201)
47 495 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. capital inmobiliario - Total rdto. neto computable (202)
48 508 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. actividades económicas - Total rdto. neto computable (203)
49 521 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - No derivadas transmisión - Total ganancias (204)
50 534 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - No derivadas transmisión - Total pérdidas (205)
51 547 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - Derivadas transmisión - Total ganancias (206)
52 560 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - Derivadas transmisión - Total pérdidas (207)
53 573 13 N Regs. especiales - Régimen atribución rentas - Total - Retenciones e ingresos a cuenta - Total retenciones e ingresos atribuidos (516)
54 586 1 Tit C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. Contribuyente "0" a "9" (208)
55 587 9 An C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. N.I.F. Entidad (209)
56 596 1 An C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (210)
57 597 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Base imponible imputada (211)
58 610 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. invers. empres. (212)
59 623 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. creación empleo (213)
60 636 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (214)
61 649 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. doble impos. internac. (215)
62 662 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. Ret.e.ingresos cta. - Retenc. e ingresos a cta. imputados (216)
63 675 1 Tit C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. Contribuyente "0" a "9" (208)
64 676 9 An C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. N.I.F. Entidad (209)
65 685 1 An C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (210)
66 686 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Base imponible imputada (211)
67 699 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. invers. empres. (212)
68 712 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. creación empleo (213)
69 725 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (214)
70 738 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. doble impos. internac. (215)
71 751 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. Ret.e.ingresos cta. - Retenc. e ingresos a cta. imputados (216)
Página 27

# Pag. 28

100-08
Nº Posic. Long. Tipo Com Descripción Validación Contenido
72 764 13 N Regs. especiales - Agrupac., ute - Total base imponible imputada (218)
73 777 13 N Regs. especiales - Agrupac., ute - Total Retenciones e ingresos a cta. imputados (517)
74 790 1 Tit C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Contribuyente "0" a "9" (219)
75 791 24 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Denominación entidad no residente (220)
76 815 1 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Criterio imput. temporal. Clave (blanco, "1" ó "2") (221)
77 816 13 N C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Importe imputación (222)
78 829 1 Tit C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Contribuyente "0" a "9" (219)
79 830 24 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Denominación entidad no residente (220)
80 854 1 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Criterio imput. temporal. Clave (blanco, "1" ó "2") (221)
81 855 13 N C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Importe imputación (222)
82 868 13 N Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Total importe de la imputación (224)
83 881 1 Tit Regs. especiales - Imputac. rentas derechos imagen - Contribuyente que debe efectuar la imputacion. "0" a "9" (225)
84 882 25 An Regs. especiales - Imputac. rentas derechos imagen - NIF o denominación persona/entidad cesionaria derechos imagen (226)
85 907 25 An Regs. especiales - Imputac. rentas derechos imagen - NIF o denominación persona/entidad relación laboral (227)
86 932 13 N Regs. especiales - Imputac. rentas derechos imagen - Cantidad a imputar (228)
87 945 1 Tit C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Contribuyente "0" a "9" (229)
88 946 24 An C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Denominación Institución (230)
89 970 13 N C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Importe imputación (231)
90 983 1 Tit C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Contribuyente "0" a "9" (229)
91 984 24 An C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Denominación Institución (230)
92 1008 13 N C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Importe imputación (231)
93 1021 13 N Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - Total importe de la imputación (233)
94 1034 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10008>
9955 11004433 22 AAnn CC FFiinn ddee RReeggiissttrroo.. CCoonnssttaannttee CCRRLLFF(( HHeexxaaddeecciimmaall 00DD00AA,, DDeecciimmaall 11331100))
Total: 1044
Página 28

# Pag. 29

100-09
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "09"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 10 2 Num Nº hojas adicionales que se adjuntan
7 12 13 N (G1) Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premio en metálico - Importe total (234)
8 25 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premio en especie - Valoración (235)
9 38 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premio en especie - Ingresos a cuenta (236)
10 51 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premio en especie - Ingresos a cuenta repercutidos (237)
11 64 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premios en especie - Importe computable (238)
12 77 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Subvenciones/ayudas adquisión/rehabilitación vivienda habitual (239)
13 90 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Ganancias patrimoniales vecinos, aprovechamientos forestales (240)
14 103 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Renta básica emancipación (241)
15 116 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe ganancias (242)
16 129 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe pérdidas (243)
17 142 1 Tit C (G2) Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (244)
18 143 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - N.I.F. (245)
19 152 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados netos positivos - Ganancias netas (246)
20 165 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados netos negativos - Pérdidas netas (247)
21 178 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (244)
2222 117799 99 AAnn CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn aaddqquuiirriiddoo ccoonn uunn aaññoo oo mmeennooss ddee aanntteellaacciióónn aa ffeecchhaa ttrraannssmmiissiióónn -- IInnsstt. iinnvv. ccoolleeccttiivvaa -- SSoocciieeddaadd//FFoonnddoo 22 -- NN.II.FF. ((224455))
23 188 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados netos positivos - Ganancias netas (246)
24 201 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados netos negativos - Pérdidas netas (247)
25 214 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (244)
26 215 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (245)
27 224 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados netos positivos - Ganancias netas (246)
28 237 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados netos negativos - Pérdidas netas (247)
29 250 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Totales - Total ganancias netas (249)
30 263 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Inst. inv. colectiva - Totales - Total pérdidas netas (250)
31 276 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
32 279 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Contribuyente "0" a "9" (251)
33 280 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Denominación valores (252)
34 300 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Importe global (253)
35 313 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Valor adquisición global (254)
36 326 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe obtenido (255)
37 339 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe obtenido (256)
38 352 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe computable (257)
39 365 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Contribuyente "0" a "9" (251)
40 366 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Denominación valores (252)
41 386 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Importe global (253)
42 399 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Valor adquisición global (254)
43 412 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe obtenido (255)
44 425 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe obtenido (256)
Página 29

# Pag. 30

100-09
Nº Posic. Long. Tipo Com Descripción Validación Contenido
45 438 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe computable (257)
46 451 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Contribuyente "0" a "9" (251)
47 452 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Denominación valores (252)
48 472 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Importe global (253)
49 485 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Valor adquisición global (254)
50 498 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe obtenido (255)
51 511 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe obtenido (256)
52 524 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe computable (257)
53 537 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Totales - Ganancias. Importe obtenido (260)
54 550 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Mercados oficiales - Totales - Pérdidas. Importe computable (261)
55 563 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
56 566 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (262)
57 567 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (264)
58 568 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Clave "0" a "4" (265)
59 569 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Ref. catastral (266)
60 589 8 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Fecha transmisión (267)
61 597 8 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Fecha adquisición (268)
62 605 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Valor transmisión (269)
63 618 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Valor adquisición (270)
64 631 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (271)
65 644 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (272)
66 657 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (273)
67 670 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta 50 por 100 (274)
68 683 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta reinversión viv. habitual (275)
69 696 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia no exenta (276)
70 709 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia no exenta imputable (277)
7711 772222 1133 NN CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn aaddqquuiirriiddoo ccoonn uunn aaññoo oo mmeennooss ddee aanntteellaacciióónn aa ffeecchhaa ttrraannssmmiissiióónn -- OOttrrooss eelleemmeennttooss -- EElleemmeennttoo 11 -- AAffeeccttooss -- RReedduucccciióónn ((lliicceenncciiaa aauuttoottaaxxiiss)) ((227788))
72 735 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia reducida (279)
73 748 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia exenta (280)
74 761 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia patrimonial reducida no exenta (281)
75 774 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia patrimonial reducida no exenta imputable (282)
76 787 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (263)
77 788 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (262)
78 789 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (264)
79 790 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Clave "0" a "4" (265)
80 791 20 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Ref. catastral (266)
81 811 8 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Fecha transmisión (267)
82 819 8 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Fecha adquisición (268)
83 827 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Valor transmisión (269)
84 840 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Valor adquisición (270)
85 853 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (271)
86 866 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable (272)
87 879 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida (273)
88 892 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta 50 por 100 (274)
89 905 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia exenta reinversión viv. habitual (275)
90 918 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia no exenta (276)
91 931 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia no exenta imputable (277)
92 944 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Afectos - Reducción (licencia autotaxis) (278)
93 957 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia reducida (279)
Página 30

# Pag. 31

100-09
Nº Posic. Long. Tipo Com Descripción Validación Contenido
94 970 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia exenta (280)
95 983 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia patrimonial reducida no exenta (281)
96 996 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia patrimonial reducida no exenta imputable (282)
97 1009 1 Num C Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Elemento 2 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (263)
98 1010 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Totales - Total pérdida imputable (284)
99 1023 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Totales - No afectos - Total ganancia no exenta imputable (285)
100 1036 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido con un año o menos de antelación a fecha transmisión - Otros elementos - Totales - Afectos - Total ganancia reducida imputable (286)
101 1049 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
102 1052 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10009>
103 1061 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1062
Página 31

# Pag. 32

100-10
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "10"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 10 2 Num Nº hojas adicionales que se adjuntan
7 12 1 Tit C (G3) Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (287)
8 13 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - N.I.F. (288)
9 22 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados netos positivos - Ganancias netas (289)
10 35 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados netos negativos - Pérdidas netas (290)
11 48 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (287)
12 49 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - N.I.F. (288)
13 58 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados netos positivos - Ganancias netas (289)
14 71 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados netos negativos - Pérdidas netas (290)
15 84 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (287)
16 85 9 An C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (288)
17 94 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados netos positivos - Ganancias netas (289)
18 107 13 N C Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados netos negativos - Pérdidas netas (290)
19 120 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Totales - Total ganancias netas (292)
20 133 13 N Ganancias/pérdidas patrim. deriv. transmisión adquirido más de un año de antelación fecha transmisión - Inst. inv. colectiva - Totales - Total pérdidas netas (293)
21 146 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
22 149 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Contribuyente "0" a "9" (294)
2233 115500 2200 AAn CC GGananciias//péérddiiddas pattriim. dderiiv. ttransmiisiióón - MMercaddos offiiciialels - EEnttididadd 11 - DDenominiacióión valolres (2(29955))
24 170 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Importe global (296)
25 183 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Valor adquisición global (297)
26 196 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe obtenido (298)
27 209 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe computable (299)
28 222 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe obtenido (300)
29 235 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe computable (301)
30 248 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Contribuyente "0" a "9" (294)
31 249 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Denominación valores (295)
32 269 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Importe global (296)
33 282 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Valor adquisición global (297)
34 295 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe obtenido (298)
35 308 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe reducido (299)
36 321 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe obtenido (300)
37 334 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe imputable (301)
38 347 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Contribuyente "0" a "9" (294)
39 348 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Denominación valores (295)
40 368 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Importe global (296)
41 381 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Valor adquisición global (297)
42 394 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe obtenido (298)
43 407 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe reducido (299)
44 420 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe obtenido (300)
45 433 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe imputable (301)
46 446 13 N Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Totales - Ganancias. Importe computable (303)
47 459 13 N Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Totales - Pérdidas. Importe computable (304)

# Pag. 33

100-10
48 472 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
49 475 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (305)
50 476 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (307)
51 477 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Clave "0" a "4" (308)
52 478 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Ref. catastral (309)
53 498 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Fecha transmisión (310)
54 506 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Fecha adquisición (311)
55 514 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Valor transmisión (312)
56 527 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Valor adquisición (313)
57 540 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (314)
58 553 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (315)
59 566 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (316)
60 579 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Parte ganancia susceptible reducción (317)
61 592 4 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Años permanencia hasta 31-12-94 (318)
62 596 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Reducción aplicable (319)
63 609 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida (320)
64 622 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta 50 por 100 (321)
65 635 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta reinversión viv. habitual (322)
66 648 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida no exenta (323)
67 661 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida no exenta imputable (324)
68 674 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Reducción (licencia autotaxis) (325)
69 687 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia reducida (326)
70 700 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia exenta 50 por 100 (327)
71 713 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia patrimonial reducida no exenta (328)
72 726 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia patrimonial reducida no exenta imputable (329)
73 739 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (306)
74 740 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (305)
75 741 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (307)
76 742 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Clave "0" a "4" (308)
77 743 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Ref. catastral (309)
7788 776633 88 NNuumm CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm.. ddeerriivv.. ttrraannssmmiissiióónn -- OOttrrooss eelleemmeennttooss -- EElleemmeennttoo 22 -- FFeecchhaa ttrraannssmmiissiióónn ((331100))
79 771 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Fecha adquisición (311)
80 779 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Valor transmisión (312)
81 792 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Valor adquisición (313)
82 805 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (314)
83 818 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable (315)
84 831 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida (316)
85 844 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Parte ganancia susceptible reducción (317)
86 857 4 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Años permanencia hasta 31-12-94 (318)
87 861 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Reducción aplicable (319)
88 874 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida (320)
89 887 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta 50 por 100 (321)
90 900 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia exenta reinversión viv. habitual (322)
91 913 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida no exenta (323)
92 926 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida no exenta imputable (324)
93 939 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Reducción (licencia autotaxis) (325)
94 952 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia reducida (326)
95 965 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia exenta 50 por 100 (327)
96 978 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia patrimonial reducida no exenta (328)
97 991 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia patrimonial reducida no exenta imputable (329)
98 1004 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (306)
99 1005 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - Total pérdida imputable (331)
100 1018 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - No afectos - Total ganancia reducida no exenta imputable (332)
101 1031 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - Afectos - Total ganancia reducida imputable (333)
102 1044 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)

# Pag. 34

100-10
103 1047 1 Tit C (G4) Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Ganancia 1 - Contribuyente "0" a "9" (335)
104 1048 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Ganancia 1 - Importe ganancia (336)
105 1061 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Ganancia 2 - Contribuyente "0" a "9" (335)
106 1062 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Ganancia 2 - Importe ganancia (336)
107 1075 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Ganancia 3 - Contribuyente "0" a "9" (335)
108 1076 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Ganancia 3 - Importe ganancia (336)
109 1089 13 N Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Total ganancias (337)
110 1102 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Pérdida 1 - Contribuyente "0" a "9" (338)
111 1103 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Pérdida 1 - Importe pérdida (339)
112 1116 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Pérdida 2 - Contribuyente "0" a "9" (338)
113 1117 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Pérdida 2 - Importe pérdida (339)
114 1130 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Pérdida 3 - Contribuyente "0" a "9" (338)
115 1131 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Pérdida 3 - Importe pérdida (339)
116 1144 13 N Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2013 ejercicios anteriores - Total pérdidas (340)
117 1157 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10010>
118 1166 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1167

# Pag. 35

100-11
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "11"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº hojas adicionales que se adjuntan
7 11 1 Tit C (G4) Ganancias/pérdidas patrim. deriv. transmisión (Continuación) - Imputación 2013 diferimiento por reinversión - Ganancia 1 - Contribuyente "0" a "9" (341)
8 12 13 N C Ganancias/pérdidas patrim. deriv. transmisión (Continuación)- Imputación 2013 diferimiento por reinversión - Ganancia 1 - Importe ganancia (342)
9 25 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (Continuación) - Imputación 2013 diferimiento por reinversión - Ganancia 2 - Contribuyente "0" a "9" (341)
10 26 13 N C Ganancias/pérdidas patrim. deriv. transmisión (Continuación) - Imputación 2013 diferimiento por reinversión - Ganancia 2 - Importe ganancia (342)
11 39 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión (Continuación) - Imputación 2013 diferimiento por reinversión - Ganancia 3 - Contribuyente "0" a "9" (341)
12 40 13 N C Ganancias/pérdidas patrim. deriv. transmisión (Continuación) - Imputación 2013 diferimiento por reinversión - Ganancia 3 - Importe ganancia (342)
13 53 13 N Ganancias/pérdidas patrim. deriv. transmisión (Continuación) - Imputación 2013 diferimiento por reinversión - Total ganancia (345)
14 66 13 N (G5) Exención por reinversión ganancia patrimonial 2013 transmisión vivienda habitual - Importe transmisión susceptible reinversión (346)
15 79 13 N Exención por reinversión ganancia patrimonial 2013 transmisión vivienda habitual - Ganancia patrimonial consecuencia transmisión (347)
16 92 13 N Exención por reinversión ganancia patrimonial 2013 transmisión vivienda habitual - Importe reinvertido hasta 31-12-2013 adquisición nueva vivienda (348)
17 105 13 N Exención por reinversión ganancia patrimonial 2013 transmisión vivienda habitual - Importe se compromete reinvertir 2 años siguientes (349)
18 118 13 N Exención por reinversión ganancia patrimonial 2013 transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (350)
19 131 1 Tit (G6) Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (351)
2200 113322 22 NNuumm OOppcciióónn rrééggiimmeenn eessppeecciiaall ffuussiioonneess, eesscciissiioonneess yy ccaannjjee vvaalloorreess eennttiiddaaddeess nnoo rreessiiddeenntteess eenn EEssppaaññaa - NNúúmmeerroo ddee ooppeerraacciioonneess11 ((335522))
21 134 1 Tit Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente2 "0" a "9" (353)
22 135 2 Num Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones2 (354)
23 137 13 N (G7) Integración/compensación ganancias/pérdidas patrimoniales imputables 2013 - A integrar en base imponible general - Suma ganancias (355)
24 150 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2013 - A integrar en base imponible general - Suma pérdidas (356)
25 163 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2013 - A integrar en base imponible general - Saldo neto - Diferencia positiva (361)
26 176 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2013 - A integrar en base imponible general - Saldo neto - Diferencia negativa (357)
27 189 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2013 - A integrar en base imponible ahorro - Suma ganancias (358)
28 202 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2013 - A integrar en base imponible ahorro - Suma pérdidas (359)
29 215 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2013 - A integrar en base imponible ahorro - Saldo neto positivo (368)
30 228 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2013 - A integrar en base imponible ahorro - Saldo neto negativo (360)
31 241 13 N (H) Base imponible general y base imponible ahorro - Base imponible general - Saldo neto positivo ganancias/pérdidas 2013 a integrar (361)
32 254 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldos netos negativos ganancias/pérdidas 2009 a 2012 a integrar (362)
33 267 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldo neto rendimientos a integrar en base imponible general/imputaciones renta (363)
34 280 13 N Base imponible general y base imponible ahorro - Base imponible general - Compensaciones - Resto saldos netos negativos 2009 a 2012 a integrar, límite 25 por 100 casilla 363 (364)
35 293 13 N Base imponible general y base imponible ahorro - Base imponible general - Compensaciones - Saldo neto negativo ganancias/pérdidas imputables 2013 a integrar, límite 25 por 100 casilla 363 (365)
36 306 13 N Base imponible general y base imponible ahorro - Base imponible general - Base imponible general (366)
37 319 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldo neto negativo ganancias/pérdidas 2013: importe pendiente de compensar (367)
38 332 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Saldo neto positivo ganancias/pérdidas 2013 (368)
39 345 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Compensación - Saldos netos negativos ganancias/pérdidas 2009-2012 a integrar (369)
40 358 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Saldo rendimientos capital mobiliario. Saldo neto negativo (370)
41 371 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Saldo rendimientos capital mobiliario. Saldo neto positivo (371)
Página 35

# Pag. 36

100-11
Nº Posic. Long. Tipo Com Descripción Validación Contenido
42 384 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Compensación. Saldo neto negativo capital mobiliario 2009 a 2012 (372)
43 397 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Base imponible ahorro (374)
44 410 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10011>
45 419 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 420
Página 36

# Pag. 37

100-12
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "12"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 13 N (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidad familiar tributación conjunta (375)
7 23 1 Tit Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 1 "0" a "9" (376)
8 24 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2008-2012 1(377)
9 37 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones 2013 1 (378)
10 50 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuciones seguros colectivos de dependencia 1 (379)
11 63 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción 1 (380)
12 76 1 Tit Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 2 "0" a "9" (376)
13 77 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2008-2012 2 (377)
14 90 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones 2013 2 (378)
15 103 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuciones seguros colectivos de dependencia 2 (379)
16 116 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción 2 (380)
17 129 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total derecho reducción (381)
18 142 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones cónyuge del contribuyente - Total derecho reducción (382)
19 155 1 Num Nº hojas adicionales que se adjuntan
20 156 1 Tit C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Contribuyente 1 "0" a "9" (383)
21 157 9 An C Reducciones base imponible - Aportaciones a favor personas con discapacidad - NIF persona con discapacidad 1 (384)
2222 116666 1133 NN CC RReedduucccciioonneess bbaassee iimmppoonniibbllee -- AAppoorrttaacciioonneess aa ffaavvoorr ppeerrssoonnaass ccoonn ddiissccaappaacciiddaadd -- EExxcceessooss ppeennddiieenntteess rreedduucciirr 11 ((338855))
23 179 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2013 propia persona discapacidad 1 (386)
24 192 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2013 parientes o tutores 1 (387)
25 205 1 Tit C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Contribuyente 2 "0" a "9" (383)
26 206 9 An C Reducciones base imponible - Aportaciones a favor personas con discapacidad - NIF persona con discapacidad 2 (384)
27 215 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Excesos pendientes reducir 2 (385)
28 228 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2013 propia persona discapacidad 2 (386)
29 241 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2013 parientes o tutores 2 (387)
30 254 13 N Reducciones base imponible - Aportaciones a favor personas con discapacidad - Total con derecho a reducción (388)
31 267 1 Tit Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (389)
32 268 9 An Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 1 (390)
33 277 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 1 (391)
34 290 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2013 1 (392)
35 303 1 Tit Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (389)
36 304 9 An Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 2 (390)
37 313 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 2 (391)
38 326 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2013 2 (392)
39 339 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Total con derecho a reducción (393)
40 352 1 Tit Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Contribuyente 1 "0" a "9" (394)
41 353 9 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 1 (395)
42 362 20 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si no tiene NIF Nº identificación en país residencia 1 (396)
43 382 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 1 (397)
44 395 1 Tit Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Contribuyente 2 "0" a "9" (394)
45 396 9 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 2 (395)
Página 37

# Pag. 38

100-12
Nº Posic. Long. Tipo Com Descripción Validación Contenido
46 405 20 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si no tiene NIF Nº identificación en país residencia 2 (396)
47 425 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 2 (397)
48 438 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Total derecho reducción (398)
49 451 1 Tit Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 1 "0" a "9" (399)
50 452 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Excesos pendientes reducir 2008-2012 1 (400)
51 465 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones 2013 1 (401)
52 478 1 Tit Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 2 "0" a "9" (399)
53 479 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Excesos pendientes reducir 2008-2012 2 (400)
54 492 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones 2013 2 (401)
55 505 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Total con derecho a reducción (402)
56 518 13 N (J) Base liquidable general/base liquidable ahorro - Determinación base general - Base imponible general (366)
57 531 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Tributación conjunta (403)
58 544 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social (régimen general) (404)
59 557 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social cónyuge (405)
60 570 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social personas discapacidad (406)
61 583 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones patrimonios protegidos personas discapacidad (407)
62 596 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Pensiones compensatorias/anualidades alimentos (408)
63 609 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Cuotas afiliación y demás aportaciones (409)
64 622 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones mutualidades prev. soc. deportistas profesionales (410)
65 635 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Base liquidable general (411)
66 648 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Compensación (bases liquidables generales negativas) (412)
67 661 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Base liquidable general sometida a gravamen (415)
68 674 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10012>
69 683 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 684
Página 38

# Pag. 39

100-13
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "13"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 13 N (J) Base liquidable general/base liquidable ahorro (continuación) - Determinación base ahorro - Base imponible ahorro (374)
7 23 13 N Base liquidable general/base liquidable ahorro (continuación) - Determinación base ahorro - Remanente reducciones no aplicadas - Reducción tributación conjunta (416)
8 36 13 N Base liquidable general/base liquidable ahorro (continuación) - Determinación base ahorro - Remanente reducciones no aplicadas - Reducción pensiones comp./anualidades alimentos (417)
9 49 13 N Base liquidable general/base liquidable ahorro (continuación) - Determinación base ahorro - Cuotas de afiliación y demás aportaciones (418)
10 62 13 N Base liquidable general/base liquidable ahorro (continuación)- Determinación base ahorro - Base liquidable del ahorro (419)
11 75 1 Tit (K) Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 1 "0" a "9" (420)
12 76 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2013 1 (421)
13 89 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión social (régimen general) - Contribuciones 2013 a seguros colectivos dependencia no aplicadas 1 (422)
14 102 1 Tit Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 2 "0" a "9" (420)
15 103 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2013 2 (421)
16 116 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión social (régimen general) - Contribuciones 2013 a seguros colectivos dependencia no aplicadas 2 (422)
17 129 1 Tit Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 1 "0" a "9" (423)
18 130 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2013 no aplicadas 1 (424)
19 143 1 Tit Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 2 "0" a "9" (423)
20 144 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2013 no aplicadas 2 (424)
21 157 1 Tit Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 3 "0" a "9" (423)
22 158 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2013 no aplicadas 3 (424)
2233 117711 11 TTiitt RRedducciiones bbase iimponiibblle no aplliicaddas 22001133 - EExceso aporttaciiones siisttemas previisiióón a ffavor personas ddiiscapaciiddadd - CConttriibbuyentte 44 ""00"" a ""99"" ((442233))
24 172 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2013 no aplicadas 4 (424)
25 185 1 Tit Reducciones base imponible no aplicadas 2013 - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (425)
26 186 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2013 no aplicadas 1 (426)
27 199 1 Tit Reducciones base imponible no aplicadas 2013 - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (425)
28 200 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2013 no aplicadas 2 (426)
29 213 1 Tit Reducciones base imponible no aplicadas 2013 - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 1 "0" a "9" (427)
30 214 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2012 no aplicadas 1 (428)
31 227 1 Tit Reducciones base imponible no aplicadas 2013 - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 2 "0" a "9" (427)
32 228 13 N Reducciones base imponible no aplicadas 2013 - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2012 no aplicadas 2 (428)
33 241 13 N (L) Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe (429)
34 254 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe cálculo gravamen autonómico (434)
35 267 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe (430)
36 280 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe cálculo gravamen autonómico (435)
37 293 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe (431)
38 306 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe cálculo gravamen autonómico (436)
39 319 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe (432)
40 332 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe cálculo gravamen autonómico (437)
41 345 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo personal y familiar (433)
42 358 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe total cálculo gravamen autonómico (438)
43 371 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen estatal (439)
44 384 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen estatal (440)
45 397 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen autonómico (441)
46 410 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen autonómico (442)
Página 39

# Pag. 40

100-13
Nº Posic. Long. Tipo Descripción Validación Contenido
47 423 13 N (M) Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable ahorro (443)
48 436 13 N Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable general (444)
49 449 13 N Datos adicionales - Anualidades para alimentos a favor de los hijos. Importe (445)
50 462 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10013>
51 471 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 472
Página 40

# Pag. 41

100-14
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "14"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N (N) Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla 415 - Parte estatal (446)
7 23 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla 415 - Parte autonómica (447)
8 36 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala gravamen complementaria - Parte estatal (448)
9 49 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general Impuesto importe casilla 439 - Parte estatal (449)
10 62 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala gravamen complementaria - Parte estatal (450)
11 75 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota derivada escala gravamen general estatal (451)
12 88 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota derivada escala gravamen complementaria (452)
13 101 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala autonómica Impuesto importe casilla 441 - Parte autonómica (453)
14 114 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte estatal (454)
15 127 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte autonómica (455)
16 140 4 Num Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte estatal (TME)
17 144 4 Num Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte autonómica (TMA)
18 148 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Base liquidable ahorro sometida gravamen - Parte estatal (458)
19 161 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Base liquidable ahorro sometida gravamen - Parte autonómica (459)
20 174 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación de la escala general y autonómica al importe de las casillas 458 y 459 - Parte estatal (460)
21 187 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación de la escala general y autonómica al importe de las casillas 458 y 459 - Parte Parte autonómica (461)
22 200 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación de la escala de gravamen complementaria al importe de la casilla 458 - Importe resultante (462)
23 213 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte estatal (463)
24 226 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte autonómica (464)
25 239 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota íntegra estatal - Parte estatal (465)
26 252 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota íntegra autonómica - Parte autonómica (466)
27 265 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte estatal (470)
28 278 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte autonómica (471)
29 291 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión empresas nueva creación - Parte estatal (472)
30 304 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte estatal (473)
31 317 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte autonómica (474)
32 330 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos - Parte estatal (475)
33 343 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos - Parte autonómica (476)
34 356 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Incentivos inversión empresarial - Parte estatal (477)
35 369 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Incentivos inversión empresarial - Parte autonómica (478)
36 382 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Dotaciones Reserva Canarias - Parte estatal (479)
37 395 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Dotaciones Reserva Canarias - Parte autonómica (480)
38 408 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rendimientos venta bienes Canarias - Parte estatal (481)
39 421 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rendimientos venta bienes Canarias - Parte autonómica (482)
40 434 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte estatal (483)
41 447 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte autonómica (484)
42 460 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Cantidades depositadas cuentas ahorro-empresa - Parte estatal (485)
43 473 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Cantidades depositadas cuentas ahorro-empresa - Parte autonómica (486)
44 486 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte estatal (487)
45 499 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte autonómica (488)
46 512 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Por obras de mejora en la vivienda habitual pendientes deducción - Parte estatal (489)
Página 41

# Pag. 42

100-14
Nº Posic. Long. Tipo Descripción Validación Contenido
47 525 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Por obras de mejora en la vivienda pendientes deducción - Parte estatal (490)
48 538 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - (491)
49 551 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota líquida estatal - Parte estatal (492)
50 564 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota líquida autonómica - Parte autonómica (493)
51 577 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - Parte estatal (494)
52 590 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - Parte estatal (495)
53 603 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2012 - Importe - Parte estatal (496)
54 616 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2012 - Intereses demora - Parte estatal (497)
55 629 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2012 - Importe - Parte autonómica (498)
56 642 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2012 - Intereses demora - Parte autonómica (499)
57 655 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2012 - Importe - Parte autonómica (500)
58 668 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2012 - Intereses demora - Parte autonómica (501)
59 681 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Cuotas líquidas incrementadas - Parte estatal (502)
60 694 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Cuotas líquidas incrementadas - Parte autonómica (503)
61 707 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota líquida incrementada total (504)
62 720 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Rentas obtenidas y gravadas en el extranjero (505)
63 733 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducción obtención rendimientos trabajo o act. económicas (506)
64 746 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Aplicación régimen transparencia fiscal internacional (507)
65 759 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Aplicación régimen imputación rentas cesión derechos imagen (508)
66 772 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10014>
67 781 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 782
Página 42

# Pag. 43

100-15
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "15"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N (N) Cálculo impuesto y resultado declaración (continuación) - Cuota resultante autoliquidación - Compensación fiscal - Percepción rdtos.capital mobiliario > 2 años (509)
7 23 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota resultante autoliquidación - Retenciones deducibles rendimientos bonificados - Importe retenciones no practicadas (510)
8 36 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota resultante autoliquidación - Cuota resultante autoliquidación (511)
9 49 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos del trabajo (512)
10 62 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos del capital mobiliario (513)
11 75 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Arrendamientos de inmuebles urbanos (514)
12 88 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos de actividades económicas (515)
13 101 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Atribuidos por entidades en régimen de atribución de rentas (516)
14 114 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Imputados por agrupaciones de interés económico y UTE's (517)
15 127 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Ingresos a cuenta art. 92.8 Ley del Impuesto (518)
16 140 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Ganancias patrimoniales, incluidos premios (519)
17 153 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Pagos fraccionados (actividades económicas) (520)
18 166 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Cuotas del Impuesto sobre la Renta de no Residentes (521)
19 179 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Retenciones art. 11 Directiva 2003/48/CE (522)
20 192 13 N Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Total pagos a cuenta (524)
21 205 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Cuota diferencial (525)
22 218 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Deducción por maternidad - Importe de la deducción (526)
23 231 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Importe del abono anticipado correspondiente a 2013 (527)
24 244 13 N Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado declaración - Resultado de la declaración (530)
25 257 13 N (O) Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - Cuota líquida autonómica incrementada (542)
26 270 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% deducciones doble imposición (543)
27 283 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% compensación fiscal percepción rendimientos capital mobiliario (544)
28 296 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - Importe IRPF que corresponde a la Comunidad Autónoma de residencia (545)
29 309 13 N (P) Regularización mediante declaración complementaria (ejercicio 2013) - Resultados a ingresar anteriores autoliquidaciones o liquidaciones administrativas ejercicio 2013 (531)
30 322 13 N Regularización mediante declaración complementaria (ejercicio 2013) - Devoluciones acordadas por la Administración, consecuencia anteriores autoliquidaciones ejercicio 2013 (532)
31 335 13 N Regularización mediante declaración complementaria (ejercicio 2013) - Resultado de la declaración complementaria (535)
32 348 13 N (Q) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (538)
33 361 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (540)
34 374 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (539)
35 387 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (540)
36 400 34 An Número de cuenta IBAN (541)
37 434 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10015>
38 443 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 444
Página 43

# Pag. 44

Anexo A.1
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "16"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Inversión con derecho a deducción (A)
7 23 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte estatal (546)
8 36 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte autonómica (547)
9 49 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Inversión con derecho a deducción (B)
10 62 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte estatal (548)
11 75 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte autonómica (549)
12 88 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Inversión con derecho a deducción (C)
13 101 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte estatal (550)
14 114 13 N Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte autonómica (551)
15 127 13 N Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Cantidades satisfechas con derecho a deducción (E)
16 140 13 N Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte estatal (552)
17 153 13 N Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte autonómica (553)
18 166 13 N Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte estatal (470)
19 179 13 N Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte autonómica (471)
20 192 13 N Deducción por inversión en vivienda habitual - Datos adicionales - Importe de los pagos realizados en el ejercicio al promotor o constructor (554)
21 205 9 An Deducción por inversión en vivienda habitual - Datos adicionales - NIF del promotor o constructor (555)
22 214 8 An Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Fecha adquisición vivienda (DDMMAAAA) (556)
23 222 20 An Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Número de identificación del préstamo hipotecario (557)
24 242 5 Num Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Porcentaje del préstamo destinado a adquisición (558)
25 247 13 N Deducción inversiones en empresas de nueva o reciente creación - Cantidades suscripción acciones entidades nueva o reciente creación - Importe (559)
26 260 9 An Deducción inversiones en empresas de nueva o reciente creación - Entidad 1 - NIF (560)
27 269 9 An Deducción inversiones en empresas de nueva o reciente creación - Entidad 2 - NIF (561)
28 278 13 N Deducción inversiones en empresas de nueva o reciente creación - Importe total deducción inversiones empresa nueva o reciente creación - Base deducción (D)
29 291 13 N Deducción inversiones en empresas de nueva o reciente creación - Importe total deducciones empresa nueva o reciente creación - Importe deducción (472)
30 304 9 An Deducción por alquiler de la vivienda habitual - NIF del arrendador 1 (563)
31 313 20 An Deducción por alquiler de la vivienda habitual - Si no tiene NIF Nº identificación fiscal en país de residencia (564)
32 333 13 N Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 1 (565)
33 346 9 An Deducción por alquiler de la vivienda habitual - NIF del arrendador 2 (566)
34 355 20 An Deducción por alquiler de la vivienda habitual - Si no tiene NIF Nº identificación fiscal en país de residencia (567)
35 375 13 N Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 2 (568)
36 388 13 N Deducción por alquiler de la vivienda habitual - Cantidades satisfechas con derecho a deducción (F)
37 401 13 N Deducción por alquiler de la vivienda habitual - Importe deducción (570)
38 414 13 N Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte estatal (487)
39 427 13 N Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte autonómica (488)
40 440 13 N Deducciones por donativos - Donativos límite 15% base liquidable - Importe con derecho a deducción (G)
Página 44

# Pag. 45

Anexo A.1
Nº Posic. Long. Tipo Descripción Validación Contenido
41 453 13 N Deducciones por donativos - Donativos límite 15% base liquidable - Importe de la deducción (571)
42 466 13 N Deducciones por donativos - Donativos límite 10% base liquidable - Importe con derecho a deducción (H)
43 479 13 N Deducciones por donativos - Donativos límite 10% base liquidable - Importe de la deducción (572)
44 492 13 N Deducciones por donativos - Deducciones por donativos - Parte estatal (475)
45 505 13 N Deducciones por donativos - Deducciones por donativos - Parte autonómica (476)
46 518 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10016>
47 527 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 528
Página 45

# Pag. 46

Anexo A.2
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "17"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe con derecho a deducción (I)
7 23 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe de la deducción (573)
8 36 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte estatal (473)
9 49 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte autonómica (474)
10 62 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Importe total de la deducción (574)
11 75 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte estatal (483)
12 88 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte autonómica (484)
13 101 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Cantidades depositadas (J)
14 114 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Importe total de la deducción (575)
15 127 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Deducción - Parte estatal (485)
16 140 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Deducción - Parte autonómica (486)
17 153 1 Tit Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Titular
18 154 8 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Fecha de apertura "DDMMAAAA"
19 162 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Entidad
20 166 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Oficina
21 170 2 Num Otras deducciones ggenerales de la cuota ínteggra - Deducción ppor cantidades deppositadas en cuenta ahorro-emppresa - Identificación cuentas - Cuenta 1 - DC
22 172 10 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Número de cuenta
23 182 1 Tit Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Titular
24 183 8 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Fecha de apertura
25 191 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Entidad
26 195 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Oficina
27 199 2 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - DC
28 201 10 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Número de cuenta
29 211 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011- Cantidades satisfechas (576)
30 224 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011 - Base deducción (K)
31 237 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 7 de mayo al 31 de diciembre 2011 - Importe deducción (577)
32 250 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Cantidades satisfechas (578)
33 263 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Base deducción (L)
34 276 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Importe deducción (579)
35 289 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Importe total (490)
36 302 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 14 abril al 31 diciembre 2010 - Cantidades satisfechas (581)
37 315 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 14 abril al 31 diciembre 2010 - Base deducción (Q)
38 328 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 14 abril al 31 diciembre 2010 - Importe deducción (582)
39 341 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Cantidades satisfechas (583)
40 354 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Base deducción (R)
41 367 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Desde el 1 de enero al 6 de mayo 2011- Importe deducción (584)
42 380 13 N Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Importe total (489 )

# Pag. 47

Anexo A.2
Nº Posic. Long. Tipo Descripción Validación Contenido
43 393 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2009 - Importe dotaciones (590)
44 406 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2009 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (591)
45 419 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2009 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (592)
46 432 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Importe dotaciones (593)
47 445 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (594)
48 458 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (595)
49 471 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Pendiente de materializar (596)
50 484 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Importe dotaciones (597)
51 497 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (598)
52 510 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (599)
53 523 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Pendiente de materializar (600)
54 536 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Importe dotaciones (601)
55 549 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (602)
56 562 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (603)
57 575 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2012 - Pendiente de materializar (604)
58 588 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Importe dotaciones (605)
59 601 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (606)
60 614 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (607)
61 627 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Pendiente de materializar (608)
62 640 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Importe de la deducción 2013
63 653 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2013 - Inversiones prev. letras A, B y D (1º.) artº. 27.4 (609)
64 666 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2013 - Inversiones prev. letras C y D 2º. a 6º.) artº. 27.4 (610)
65 679 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10017>
66 688 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 689

# Pag. 48

Anexo A.3
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "18"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Saldo anterior
7 23 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Aplicado declaración (611)
8 36 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Pendiente aplicación
9 49 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interés público - Saldo anterior
10 62 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interés público - Aplicado declaración (612)
11 75 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interes público - Pendiente aplicación
12 88 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Actv. I+D+i - Deducción 2013
13 101 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Actv. I+D+i - Aplicado declaración (613)
14 114 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Actv. I+D+i - Pendiente aplicación
15 127 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversión beneficios - Deducción 2013
16 140 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversión beneficios - Aplicado declaración (614 )
17 153 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversión beneficios - Pendiente aplicación
18 166 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversiones/gastos art.º 38.1, 2 y 3 - Deducción 2013
19 179 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversiones/gastos art.º 38.1, 2 y 3 - Aplicado declaración (615)
20 192 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversiones/gastos art.º 38.1, 2 y 3 - Pendiente aplicación
21 205 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversiones medioambientales - Deducción 2013
22 218 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversiones medioambientales - Aplicado declaración (616)
23 231 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Inversiones medioambientales - Pendiente aplicación
24 244 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Util. nuevas tecnologías empleados - Deducción 2013
25 257 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Util. nuevas tecnologías empleados - Aplicado declaración (617)
26 270 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Util. nuevas tecnologías empleados - Pendiente aplicación
27 283 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Creación empleo trabajadores con discapacidad - Deducción 2013
28 296 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Creación empleo trabajadores con discapacidad - Aplicado declaración (618)
29 309 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Creación empleo trabajadores con discapacidad - Pendiente aplicación
30 322 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Creación empleo artº. 43 LIS - Deducción 2013
31 335 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Creación empleo artº. 43 LIS - Aplicado declaración (619)
32 348 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. g. LIS - Creación empleo artº. 43 LIS - Pendiente aplicación
33 361 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2012. R. acontecimientos e. i. p. - "Vuelta al Mundo a Vela Alicante 2014" - Deducción 2013
34 374 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2012. R. acontecimientos e. i. p. - "Vuelta al Mundo a Vela Alicante 2014" - Aplicado declaración (620)
35 387 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2012. R. acontecimientos e. i. p. - "Vuelta al Mundo a Vela Alicante 2014" - Pendiente aplicación
36 400 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "3ª edición Barcelona World Race" - Deducción 2013
37 413 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "3ª edición Barcelona World Race" - Aplicado declaración (621)
38 426 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "3ª edición Barcelona World Race" - Pendiente aplicación
39 439 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - Prog. Prep. Depor. Juegos "Río de Janeiro 2016"- Deducción 2013
40 452 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - Prog. Prep. Depor. Juegos "Río de Janeiro 2016" - Aplicado declaración (622)
41 465 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - Prog. Prep. Depor. Juegos "Río de Janeiro 2016" - Pendiente aplicación
42 478 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Deducción 2013
43 491 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Aplicado declaración (623)
44 504 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "VIII Cent. Pereg. San Fco. Asís a Compostela " - Pendiente aplicación
45 517 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "V Cent. Nacimiento Sta. Teresa Avila 2015" - Deducción 2013
46 530 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "V Cent. Nacimiento Sta. Teresa Avila 2015" - Aplicado declaración (624)

# Pag. 49

Anexo A.3
Nº Posic. Long. Tipo Descripción Validación Contenido
47 543 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "V Cent. Nacimiento Sta. Teresa Avila 2015" - Pendiente aplicación
48 556 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Vitoria Gasteiz Capital Verde Europea 2012" - Deducción 2013
49 569 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Vitoria Gasteiz Capital Verde Europea 2012" - Aplicado declaración (625)
50 582 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Vitoria Gasteiz Capital Verde Europea 2012" - Pendiente aplicación
51 595 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato del Mundo de Vela (ISAF) Santander 2014" - Deducción 2013
52 608 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato del Mundo de Vela (ISAF) Santander 2014" - Aplicado declaración (626)
53 621 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato del Mundo de Vela (ISAF) Santander 2014" - Pendiente aplicación
54 634 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Milenio Reino Granada" - Deducción 2013
55 647 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Milenio Reino Granada" - Aplicado declaración (627)
56 660 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Milenio Reino Granada" - Pendiente aplicación
57 673 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Junípero Serra 2013" - Deducción 2013
58 686 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Junípero Serra 2013" - Aplicado declaración (628)
59 699 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Junípero Serra 2013" - Pendiente aplicación
60 712 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Santo Jubilar Mariano 2013-2014 Sevilla" - Deducción 2013
61 725 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Santo Jubilar Mariano 2013-2014 Sevilla" - Aplicado declaración (629)
62 738 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Santo Jubilar Mariano 2013-2014 Sevilla" - Pendiente aplicación
63 751 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "El Árbol es Vida" - Deducción 2013
64 764 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "El Árbol es Vida" - Aplicado declaración (630)
65 777 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "El Árbol es Vida" - Pendiente aplicación
66 790 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Mundo Basket 2014" - Deducciones 2013
67 803 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Mundo Basket 2014" - Aplicado declaración (631)
68 816 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Mundo Basket 2014" - Pendiente aplicación
69 829 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "C. M. Balonmano 2013" - Deducciones 2013
70 842 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "C. M. Balonmano 2013" - Aplicado declaración (632)
71 855 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "C. M. Balonmano 2013" - Pendiente aplicación
72 868 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año de España en Japón" - Deducción 2013
73 881 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año de España en Japón" - Aplicado declaracion (633)
74 894 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año de España en Japón" - Pendiente aplicación
75 907 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "IV Centenario fallecimiento El Greco" - Deducción 2013
76 920 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "IV Centenario fallecimiento El Greco" - Aplicado declaración (634)
77 933 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "IV Centenario fallecimiento El Greco" - Pendiente aplicación
78 946 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Patrimonio Cultural de Lorca" - Deducción 2013
79 959 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Patrimonio Cultural de Lorca" - Aplicado declaración (635)
80 972 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Patrimonio Cultural de Lorca" - Pendiente aplicación
81 985 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Universiada invierno de Granada 2015" - Deducción 2013
82 998 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Universiada invierno de Granada 2015" - Aplicado declaración (636)
83 1011 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Universiada invierno de Granada 2015" - Pendiente aplicación
84 1024 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato ciclismo en Carretera Ponferrada 2014" - Deducción 2013
85 1037 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato ciclismo en Carretera Ponferrada 2014" - Aplicado declaración (637)
86 1050 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato ciclismo en Carretera Ponferrada 2014" - Pendiente aplicación
87 1063 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Barcelona World Jumping Challenge" - Deducción 2013
88 1076 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Barcelona World Jumping Challenge" - Aplicado declaración (638)
89 1089 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Barcelona World Jumping Challenge" - Pendiente aplicación
90 1102 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato Natación Barcelona 2013" - Deducción 2013
91 1115 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato Natación Barcelona 2013" - Aplicado declaración (639)
92 1128 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato Natación Barcelona 2013" - Pendiente aplicación
93 1141 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Barcelona Mobile World Capital" - Deducción 2013
94 1154 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Barcelona Mobile World Capital" - Aplicado declaración (640)
95 1167 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Barcelona Mobile World Capital" - Pendiente aplicación

# Pag. 50

Anexo A.3
Nº Posic. Long. Tipo Descripción Validación Contenido
96 1180 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato Tiro Olímpico Las Gabias 2014" - Deducción 2013
97 1193 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato Tiro Olímpico Las Gabias 2014" - Aplicado declaración (641)
98 1206 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Campeonato Tiro Olímpico Las Gabias 2014" - Pendiente aplicación
99 1219 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Santo Jubilar Mariano en Almonte" - Deducción 2013
100 1232 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Santo Jubilar Mariano en Almonte" - Aplicado declaración (642)
101 1245 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Año Santo Jubilar Mariano en Almonte" - Pendiente aplicación
102 1258 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "2014 Año Internacional Dieta Mediterránea" - Deducción 2013
103 1271 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "2014 Año Internacional Dieta Mediterránea" - Aplicado declaración (643)
104 1284 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "2014 Año Internacional Dieta Mediterránea" - Pendiente aplicación
105 1297 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Candidatura Madrid 2020" - Deducción 2013
106 1310 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Candidatura Madrid 2020" - Aplicado declaración (644)
107 1323 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Candidatura Madrid 2020" - Pendiente aplicación
108 1336 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Alicante 2011" - Deducción 2013
109 1349 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Alicante 2011" - Aplicado declaración (645)
110 1362 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2013. R. acontecimientos e. i. p. - "Alicante 2011" - Pendiente aplicación
111 1375 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Saldo anterior
112 1388 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Aplicado declaración (650)
113 1401 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Pendiente aplicación
114 1414 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Saldo anterior
115 1427 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Aplicado declaración (651)
116 1440 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Pendiente aplicación
117 1453 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Deducción 2013
118 1466 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Aplicado declaración (652)
119 1479 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Pendiente aplicación
120 1492 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - L.I.S.: Inversión beneficios artº. 37 LIS - Deducción 2013
121 1505 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - L.I.S.: Inversión beneficios artº. 37 LIS - Aplicado declaración (653)
122 1518 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - L.I.S.: Inversión beneficios artº. 37 LIS - Pendiente aplicación
123 1531 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Deducción 2013
124 1544 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Aplicado declaración (654)
125 1557 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Pendiente de aplicación
126 1570 39 N RESERVADO PARA LA ADMINISTRACIÓN (rellenar a ceros)
127 1609 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Util. nuevas tecnologías empleados - Deducción 2013
128 1622 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Util. nuevas tecnologías empleados - Aplicado declaración (656)
129 1635 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Util. nuevas tecnologías empleados - Pendiente aplicación
130 1648 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Creación empleo trabajadores minusválidos - Deducción 2013
131 1661 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Creación empleo trabajadores minusválidos - Aplicado declaración (657)
132 1674 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Modalidades LIS - Creación empleo trabajadores minusválidos - Pendiente aplicación
133 1687 39 N RESERVADO PARA LA ADMINISTRACIÓN (rellenar a ceros)
134 1726 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Inversiones en la adquisición de activos fijos - Deducción 2013
135 1739 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Inversiones en la adquisición de activos fijos - Aplicado declaración (659)
136 1752 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2013. Inversiones en la adquisición de activos fijos - Pendiente aplicación
137 1765 13 N Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Importe total de las deducciones (665)
138 1778 13 N Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Deducciones - Parte estatal (477)
139 1791 13 N Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Deducciones - Parte autonómica (478)
140 1804 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10018>
141 1813 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1814

# Pag. 51

Anexo B.1
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "19"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Andalucía - Para beneficiarios de ayudas familiares (700)
7 23 13 N Deducciones Autonómicas - Andalucía - Para beneficiarios ayudas viviendas protegidas (701)
8 36 13 N Deducciones Autonómicas - Andalucía - Por inversión vivienda habitual protegida/personas jóvenes (702)
9 49 9 An Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - NIF arrendador (703)
10 58 13 N Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - Importe (704)
11 71 13 N Deducciones Autonómicas - Andalucía - Por inversión en la adquisición de acciones y participaciones (706)
12 84 13 N Deducciones Autonómicas - Andalucía - Por adopción de hijos ámbito internacional (707)
13 97 13 N Deducciones Autonómicas - Andalucía - Para contribuyentes con discapacidad (708)
14 110 13 N Deducciones Autonómicas - Andalucía - Para padre/madre de familia monoparental con ascendientes mayores 75 años (709)
15 123 13 N Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Deducción con carácter general (710)
16 136 11 An Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Cuenta cotización (711)
17 147 13 N Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Importe (712)
18 160 11 An Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Cuenta cotización (713)
1199 117711 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass -- AAnnddaalluuccííaa -- PPoorr aayyuuddaa ddoommééssttiiccaa. IImmppoorrttee ((771144))
20 184 13 N Deducciones Autonómicas - Andalucía - Para trabajadores por gastos de defensa jurídica de la relación laboral (715)
21 197 13 N Deducciones Autonómicas - Andalucía - Por obras en vivienda (Cantidades 2012 pdtes. deducción 4 años exceder en 2012 base deducción) (716)
22 210 13 N Deducciones Autonómicas - Andalucía - Para contribuyentes con cónyuges o parejas de hecho con discapacidad (717)
23 223 13 N Deducciones Autonómicas - Andalucía - Total deducciones autonómicas (491)
24 236 13 N Deducciones Autonómicas - Aragón - Por nacimiento o adopción tercer hijo o sucesivos o segundo hijo si éste o el primer hijo es discapacitado (720)
25 249 13 N Deducciones Autonómicas - Aragón - Por adopción internacional de niños (721)
26 262 13 N Deducciones Autonómicas - Aragón - Por el cuidado de personas dependientes (722)
27 275 13 N Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico (723)
28 288 13 N Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo (724)
29 301 13 N Deducciones Autonómicas - Aragón - Por inversión en acciones de entidades que cotizan en Mercado bursátil (725)
30 314 13 N Deducciones Autonómicas - Aragón - Por inversión en la adquisición de acciones o participaciones (726)
31 327 13 N Deducciones Autonómicas - Aragón - Por adquisición de vivienda en núcleos rurales (727)
32 340 13 N Deducciones Autonómicas - Aragón - Por adquisición libros de texto (728)
33 353 9 An Deducciones Autonómicas - Aragón - Por arrendamiento vvda. Habitual - NIF arrendador (729)
34 362 13 N Deducciones Autonómicas - Aragón - Por arrendamiento vvda. habitual (730)
35 375 13 N Deducciones Autonómicas - Aragón - Por arrendamiento vvda. social (deducción arrendador) (731)
36 388 13 N Deducciones Autonómicas - Aragón - Total deducciones autonómicas (491)
37 401 13 N Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (734)
38 414 13 N Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes discapacitados (735)
39 427 13 N Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes discapacitados (736)
Página 51

# Pag. 52

Anexo B.1
Nº Posic. Long. Tipo Descripción Validación Contenido
40 440 13 N Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (737)
41 453 9 An Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - NIF arrendador (738)
42 462 13 N Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - Importe (739)
43 475 13 N Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (742)
44 488 13 N Deducciones Autonómicas - Asturias - Por adopción internacional de menores (743)
45 501 13 N Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones (744)
46 514 13 N Deducciones Autonómicas - Asturias - Para familias numerosas (745)
47 527 13 N Deducciones Autonómicas - Asturias - Para familias monoparentales (746)
48 540 13 N Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (747)
49 553 13 N Deducciones Autonómicas - Asturias - Por gestión forestal sostenible (748)
50 566 13 N Deducciones Autonómicas - Asturias - Total deducciones autonómicas (491)
51 579 13 N Deducciones Autonómicas - Illes Balears - Por gastos adquisición libros de texto (751)
52 592 13 N Deducciones Autonómicas - Illes Balears - Para contribuyentes edad igual o superior a 65 años (752)
53 605 13 N Deducciones Autonómicas - Illes Balears - Para los declarantes con minusvalía física/psíquica o descendientes con esa condición (753)
54 618 13 N Deducciones Autonómicas - Illes Balears - Por adopción de hijos (754)
55 631 13 N Deducciones Autonómicas - Illes Balears - Por inversión en la adquisición de acciones o participaciones (755)
56 644 13 N Deducciones Autonómicas - Illes Balears - Por gastos en primas de seguro individuales de salud (756)
57 657 13 N Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (491)
58 670 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10019>
59 679 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 680
Página 52

# Pag. 53

Anexo B.2
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "20"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Canarias - Por donaciones con finalidad ecológica (759)
7 23 13 N Deducciones Autonómicas - Canarias - Por donaciones rehabilitación/conservación patrimonio histórico de Canarias (760)
8 36 13 N Deducciones Autonómicas - Canarias - Por cantidades destinadas restauración/rehabilitación/reparación bienes inmuebles declarados de Interés Cultural (761)
9 49 13 N Deducciones Autonómicas - Canarias - Por gastos de estudios (762)
10 62 13 N Deducciones Autonómicas - Canarias - Por traslado residencia a otra isla para realizar actividad laboral cuenta ajena/actividad económica (763)
11 75 13 N Deducciones Autonómicas - Canarias - Por donaciones en metálico a descendientes menores 35 años para adquisición/rehabilitación primera vivienda habitual (764)
12 88 13 N Deducciones Autonómicas - Canarias - Por nacimiento o adopción de hijos (765)
13 101 13 N Deducciones Autonómicas - Canarias - Por contribuyentes minusválidos y mayores de 65 años (766)
14 114 13 N Deducciones Autonómicas - Canarias - Por gastos de guardería (767)
15 127 13 N Deducciones Autonómicas - Canarias - Por familia numerosa (768)
16 140 13 N Deducciones Autonómicas - Canarias - Por inversión en vivienda habitual (769)
17 153 13 N Deducciones Autonómicas - Canarias - Por obras de adecuación vivienda habitual por razón discapacidad (770)
18 166 9 An Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - NIF arrendador (771)
1199 117755 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass -- CCaannaarriiaass -- PPoorr aallqquuiilleerr ddee vviivviieennddaa hhaabbiittuuaall -- IImmppoorrttee ((777722))
20 188 20 An Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral (773)
21 208 1 Num Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral. 1 o cero (774)
22 209 13 N Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Cantidades totales satisfechas al arrendador (775)
23 222 13 N Deducciones Autonómicas - Canarias - Por contribuyentes desempleados (776)
24 235 13 N Deducciones Autonómicas - Canarias - Por obras de rehabilitación o reforma en vivienda (pdte. deducción exceso base 2012) (777)
25 248 13 N Deducciones Autonómicas - Canarias - Total deducciones autonómicas (491)
26 261 9 An Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores, discapacitados - NIF arrendador (780)
27 270 13 N Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores, discapacitados - Importe (781)
28 283 13 N Deducciones Autonómicas - Cantabria - Por cuidado de familiares (782)
29 296 9 An Deducciones Autonómicas - Cantabria - Por obras mejora viviendas - NIF persona/entidad obras (783)
30 305 13 N Deducciones Autonómicas - Cantabria - Por obras mejora viviendas - Deducción (784 )
31 318 13 N Deducciones Autonómicas - Cantabria - Por obras mejora viviendas - Deducción generada 2013 a deducir en 2 años siguientes (785)
32 331 13 N Deducciones Autonómicas - Cantabria - Por donativos a fundaciones (786)
33 344 13 N Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (787)
34 357 13 N Deducciones Autonómicas - Cantabria - Por inversión adquisición acciones/participaciones sociales entidades nueva creación (788)
35 370 13 N Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (491)
36 383 13 N Deducciones Autonómicas - Castilla-La Mancha - Para el fomento del autoempleo. Generado 2012 pendiente de aplicación (793)
37 396 13 N Deducciones Autonómicas - Castilla-La Mancha - Para el fomento del autoempleo. Deducción generada en 2013 (794)
38 409 13 N Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (796)
39 422 13 N Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (797)
Página 53

# Pag. 54

Anexo B.2
Nº Posic. Long. Tipo Descripción Validación Contenido
40 435 13 N Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (798)
41 448 13 N Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (799)
42 461 13 N Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (800)
43 474 13 N Deducciones Autonómicas - Castilla-La Mancha - Por cantidades para la Cooperación Internacional, lucha contra pobreza y exclusión social (801)
44 487 13 N Deducciones Autonómicas - Castilla-La Mancha - Por familia numerosa (802)
45 500 13 N Deducciones Autonómicas - Castilla-La Mancha - Por donaciones con finalidad en investigación y desarrollo (803)
46 513 13 N Deducciones Autonómicas - Castilla-La Mancha - Por gastos en la adquisición de libros de texto y enseñanza de idiomas (789)
47 526 13 N Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento familiar no rumunerado de menores (790)
48 539 13 N Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento no remunerado de mayores de 65 años y/o discapacitados (791)
49 552 9 An Deducciones Autonómicas - Castilla-La Mancha - Por arrendamiento de vivienda habitual por menores de 36 años. Nif del arrendador (792)
50 561 13 N Deducciones Autonómicas - Castilla-La Mancha - Por arrendamiento de vivienda habitual por menores de 36 años. Importe (804)
51 574 13 N Deducciones Autonómicas - Castilla-La Mancha - Por inversión en adquisición participaciones sociales en Sociedades Cooperativas (805)
52 587 13 N Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (491)
53 600 13 N Deducciones Autonómicas - Castilla y León - Para contribuyentes afectados por discapacidad (806)
54 613 13 N Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales (807)
55 626 13 N Deducciones Autonómicas - Castilla y León - Por donación a Fundaciones de Castilla y León para recuperación patrimonio histórico, cultural y natural (808)
56 639 13 N Deducciones Autonómicas - Castilla y León - Por inversión en patrimonio histórico, cultural y natural (809)
57 652 9 An Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años - Nif arrendador (810)
58 661 13 N Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años - Importe (811)
59 674 13 N Deducciones Autonómicas - Castilla y León - Por inversión instalaciones medioambientales/adaptación vvda.habitual discapacitados (812)
60 687 8 Num Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Fecha visado proyecto (813)
61 695 13 N Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Importe (814)
62 708 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10020>
6633 771177 22 AAnn FFiinn ddee RReeggiissttrroo. CCoonnssttaannttee CCRRLLFF(( HHeexxaaddeecciimmaall 00DD00AA, DDeecciimmaall 11331100))
Total: 718
Página 54

# Pag. 55

Anexo B.3
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "21"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Castilla y León - Deducción para el fomento del autoempleo mujeres, jóvenes y autónomos abandono actividad por crisis. Importes pdtes. aplicación (815)
7 23 13 N Deducciones Autonómicas - Castilla y León - Deducción para el fomento del autoempleo mujeres, jóvenes y autónomos abandono actividad por crisis. Importes pdtes. aplicación (816)
8 36 8 Num Deducciones Autonómicas - Castilla y León - Para el fomento del autoempleo mujeres y jóvenes. Fecha de alta en el censo (817)
9 44 13 N Deducciones Autonómicas - Castilla y León - Para fomento del autoempleo de mujeres y jóvenes - Generado 2013 (818)
10 57 13 N Deducciones Autonómicas - Castilla y León - Para fomento del autoempleo de mujeres y jóvenes (819)
11 70 13 N Deducciones Autonómicas - Castilla y León - Por familia numerosa, nacimiento o adopción, etc. Importes pdtes. aplicación (820)
12 83 13 N Deducciones Autonómicas - Castilla y León - Por familia numerosa, nacimiento o adopción, etc. Importes pdtes. aplicación (821)
13 96 13 N Deducciones Autonómicas - Castilla y León - Por familia numerosa (822)
14 109 13 N Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (823)
15 122 13 N Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas (824)
16 135 13 N Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas en 2011 y/o 2012 (825)
17 148 9 An Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Nif empleada (826)
18 157 13 N Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores (827)
19 170 13 N Deducciones Autonómicas - Castilla y León - Por paternidad (828)
20 183 13 N Deducciones Autonómicas - Castilla y León - Por gastos de adopción (829)
21 196 9 An Deducciones Autonómicas - Castilla y León - Por cuota Seg.Social empleados del hogar - Nif persona empleada (830)
22 205 13 N Deducciones Autonómicas - Castilla y León - Por cuota Seg.Social empleados del hogar - Importe (831)
23 218 13 N Deducciones Autonómicas - Castilla y León - Importe total aplicado (832)
24 231 13 N Deducciones Autonómicas - Castilla y León - Total deducciones autonómicas (491)
25 244 13 N Deducciones Autonómicas - Castilla y León - Deducciones fomento autoempleo mujeres y jóvenes y autónomos - 2011 y 2012 Pendiente de aplicación (833)
26 257 13 N Deducciones Autonómicas - Castilla y León - Deducciones fomento autoempleo mujeres y jóvenes y autónomos - 2013 Pendiente de aplicación (834)
27 270 13 N Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2011 y 2012 Pendiente de aplicación (835)
28 283 13 N Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2013 Pendiente de aplicación (836)
29 296 13 N Deducciones Autonómicas - Cataluña - Por nacimiento o adopción hijos (838)
30 309 13 N Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan el uso lengua catalana (839)
31 322 13 N Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan la investigación científica (840)
32 335 9 An Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - NIF arrendador (841)
33 344 13 N Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - Importe (842)
34 357 13 N Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudios universitarios de master y doctorado (843)
35 370 13 N Deducciones Autonómicas - Cataluña - Para los contribuyentes que queden viudos (844)
36 383 13 N Deducciones Autonómicas - Cataluña - Por rehabilitación vivienda habitual (845)
37 396 13 N Deducciones Autonómicas - Cataluña - Por donaciones en beneficio del medio ambiente (846)
38 409 13 N Deducciones Autonómicas - Cataluña - Por inversión adquisición de acciones o participaciones sociales (847)
39 422 13 N Deducciones Autonómicas - Cataluña - Por inversión en acciones de entidades que cotizan en empresas en expansión (848)
40 435 13 N Deducciones Autonómicas - Cataluña - Total deducciones autonómicas (491)
Página 55

# Pag. 56

Anexo B.3
Nº Posic. Long. Tipo Descripción Validación Contenido
41 448 13 N Deducciones Autonómicas - Extremadura - Por adquisición vivienda habitual para jóvenes y víctimas del terrorismo (851)
42 461 13 N Deducciones Autonómicas - Extremadura - Por trabajo dependiente (852)
43 474 13 N Deducciones Autonómicas - Extremadura - Por cuidado de familiares discapacitados (853)
44 487 13 N Deducciones Autonómicas - Extremadura - Por acogimiento de menores (854)
45 500 13 N Deducciones Autonómicas - Extremadura - Por partos múltiples (857)
46 513 13 N Deducciones Autonómicas - Extremadura - Por compra de material escolar (858)
47 526 13 N Deducciones Autonómicas - Extremadura - Por inversión en la adquisición de acciones o participaciones sociales (859)
48 539 13 N Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (491)
49 552 13 N Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (861)
50 565 13 N Deducciones Autonómicas - Galicia - Por familia numerosa (862)
51 578 13 N Deducciones Autonómicas - Galicia - Por cuidado hijos menores (863)
52 591 13 N Deducciones Autonómicas - Galicia - Por contribuyentes discapacitados = > 65 años que precisan ayuda de terceras personas (864)
53 604 13 N Deducciones Autonómicas - Galicia - Por gastos de nuevas tecnologías en hogares gallegos (865)
54 617 9 An Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - NIF arrendador (866)
55 626 13 N Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - Importe (867)
56 639 13 N Deducciones Autonómicas - Galicia - Por acogimiento familiar de menores (868)
57 652 13 N Deducciones Autonómicas - Galicia - Por creación nuevas empresas o ampliación actividad (869)
58 665 13 N Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación (870)
59 678 13 N Deducciones Autonómicas - Galicia - Por inversión en acciones de entidades empresas en expansión Mercado Alternativo Bursátil (871)
60 691 13 N Deducciones Autonómicas - Galicia - Total deducciones autonómicas (491)
61 704 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10021>
62 713 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 714
Página 56

# Pag. 57

Anexo B.4
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "22"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Madrid - Por nacimiento o adopción de hijos (874)
7 23 13 N Deducciones Autonómicas - Madrid - Por adopción internacional de niños (875)
8 36 13 N Deducciones Autonómicas - Madrid - Por acogimiento familiar de menores (876)
9 49 13 N Deducciones Autonómicas - Madrid - Por acogimiento no remunerado de mayores 65 años y/o discapacitados (877)
10 62 9 An Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - NIF arrendador (878)
11 71 13 N Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - Importe (879)
12 84 13 N Deducciones Autonómicas - Madrid - Por donativos a fundaciones (880)
13 97 13 N Deducciones Autonómicas - Madrid - Por gastos educativos (881)
14 110 13 N Deducciones Autonómicas - Madrid - Para familias con dos o más descendientes e ingresos reducidos (882)
15 123 13 N Deducciones Autonómicas - Madrid - Por inversión en adquisición de acciones y participaciones sociales de nuevas entidades (883)
16 136 13 N Deducciones Autonómicas - Madrid - Para el fomento del autoempleo de jóvenes menores de 35 años (884)
1177 114499 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass - MMaaddrriidd - PPoorr iinnvveerrssiioonneess eenn eennttiiddaaddeess ccoottiizzaaddaass eenn eell MMeerrccaaddoo AAlltteerrnnaattiivvoo BBuurrssááttiill ((888855))
18 162 13 N Deducciones Autonómicas - Madrid - Total deducciones autonómicas (491)
19 175 13 N Deducciones Autonómicas - Murcia - Por inversión vivienda habitual jóvenes edad igual/inferior 35 años (incluido rég. transitorio) (888)
20 188 13 N Deducciones Autonómicas - Murcia - Por donativos para la protección del patrimonio histórico Región Murcia (889)
21 201 13 N Deducciones Autonómicas - Murcia - Por gastos de guardería para hijos menores de 3 años (890)
22 214 13 N Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (891)
23 227 13 N Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (892)
24 240 13 N Deducciones Autonómicas - Murcia - Por inversión en la adquisición de acciones y participaciones sociales (893)
25 253 13 N Deducciones Autonómicas - Murcia - Por inversiones en entidades cotizadas Mercado Alternativo Bursátil (894)
26 266 13 N Deducciones Autonómicas - Murcia - Total deducciones autonómicas (491)
27 279 13 N Deducciones Autonómicas - La Rioja - Por nacimiento y adopción de segundo o ulterior hijo (895)
28 292 13 N Deducciones Autonómicas - La Rioja - Por inversión adquisición/rehabilitación vivienda habitual para jóvenes (896)
29 305 4 Num Deducciones Autonómicas - La Rioja - Por adquisición/rehabilitación 2ª vivienda en el medio rural - Código municipio (897)
30 309 13 N Deducciones Autonómicas - La Rioja - Por adquisición/rehabilitación 2ª vivienda en el medio rural - Importe (898)
31 322 13 N Deducciones Autonómicas - La Rioja - Por inversión rehabilitación vivienda habitual (899)
32 335 13 N Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (491)
33 348 13 N Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento/adopción de hijos (902)
34 361 13 N Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento/adopción múltiples (903)
35 374 13 N Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento/adopción hijos discapacitados (904)
Página 57

# Pag. 58

Anexo B.4
Nº Posic. Long. Tipo Descripción Validación Contenido
36 387 13 N Deducciones Autonómicas - Comunitat Valenciana - Por familia numerosa (905)
37 400 13 N Deducciones Autonómicas - Comunitat Valenciana - Por custodia en guarderías y primer ciclo educación infantil hijos menores de 3 años (906)
38 413 13 N Deducciones Autonómicas - Comunitat Valenciana - Por conciliación del trabajo con la vida familiar (907)
39 426 13 N Deducciones Autonómicas - Comunitat Valenciana - Para contribuyentes con un grado de discapacidad igual o superior al 33 por 100, de edad igual o superior a 65 años (908)
40 439 13 N Deducciones Autonómicas - Comunitat Valenciana - Por ascendientes > 75 años ó > 65 años discapacitados (909)
41 452 13 N Deducciones Autonómicas - Comunitat Valenciana - Por realización de labores no remuneradas en el hogar (910)
42 465 13 N Deducciones Autonómicas - Comunitat Valenciana - Por primera adquisición vivienda habitual para contribuyentes edad igual o inferior 35 años (911)
43 478 13 N Deducciones Autonómicas - Comunitat Valenciana - Por adquisición vivienda habitual por discapacitados (912)
44 491 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades adquisición/rehabilitación vivienda habitual, procedentes ayudas públicas (913)
45 504 9 An Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de vivienda habitual - NIF arrendador (914)
46 513 13 N Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de vivienda habitual - Importe (915)
47 526 9 An Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - NIF arrendador (916)
48 535 13 N Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Importe (917)
49 548 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades inversiones fuentes energía renovables en vivienda habitual (918)
50 561 13 N Deducciones Autonómicas - Comunitat Valenciana - Por donaciones con finalidad ecológica (919)
51 574 13 N Deducciones Autonómicas - Comunitat Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (920)
52 587 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades donadas conservación, reparación y restauración Patrimonio Cultural Valenciano (921)
53 600 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades destinadas titulares conservación, etc. bienes Patrimonio Cultural Valenciano (922)
54 613 13 N Deducciones Autonómicas - Comunitat Valenciana - Por donaciones destinadas al fomento de la lengua valenciana (923)
55 626 13 N Deducciones Autonómicas - Comunitat Valenciana - Por contribuyentes con dos o más descendientes (924)
56 639 13 N Deducciones Autonómicas - Comunitat Valenciana - Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (925)
5577 665522 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass - CCoommuunniittaatt VVaalleenncciiaannaa - PPoorr aaddqquuiissiicciióónn mmaatteerriiaall eessccoollaarr ((992266))
58 665 13 N Deducciones Autonómicas - Comunitat Valenciana - Total deduciones autonómicas (491)
59 678 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10022>
60 687 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 688
Página 58

# Pag. 59

I-D
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2013
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "23"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Liquidación (2) - Resultado a ingresar o a devolver [540]
7 23 1 Num Liquidación (2) - Solicitud de suspensión ingreso cónyuge/Renuncia cobro devolución otro cónyuge. "1" o "0" [7]
8 24 13 N Declaración Complementaria (3) - Resultado de Declaración Complementaria [535]
9 37 1 Num Ingreso (4) - Casilla 540 positiva - NO FRACCIONA el pago [1] "1" o "0"
10 38 1 Num Ingreso (4) - Casilla 540 positiva - SÍ FRACCIONA el pago [6] "1" o "0"
11 39 13 N Ingreso (4) - Casilla 540 positiva - Importe del ingreso [I1]
12 52 1 Num Ingreso (4) - Casilla 540 positiva - Forma de pago -"0" No consta; "1" Efectivo; "2" Adeudo en Cuenta; "3" Domiciliación
13 53 1 Num Opciones de pago 2º plazo (5) - NO DOMICILIA el pago [2] "1" o "0"
14 54 1 Num Opciones de pago 2º plazo (5) - SÍ DOMICILIA el pago [3] "1" o "0"
15 55 13 N Opciones de pago 2º plazo (5) - Importe del 2º plazo [I2]
1166 6688 11 NNuumm DDeevvoolluucciióónn ((66)) -- CCaassiillllaa 554400 nneeggaattiivvaa -- "00" NNoo ccoonnssttaa,, "11" DDeevvoolluucciióónn yy "22" rreennuunncciiaa ddeevvoolluucciióónn
17 69 13 N Devolución (6) - Casilla 540 negativa - Importe [D]
18 82 34 An Número de cuenta IBAN
19 116 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10023>
20 125 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 126
Página 59