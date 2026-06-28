# Pag. 1

Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
NNº PPoossiicc.. LLoonngg.. TTiippoo DDeessccrriippcciióónn VVaalliiddaacciióónn CCoonntteenniiddoo
1 1 17 An Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "<T100020110A0000>"
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
VVecttor dde páágiinas. PPara su cumplliimenttaciióón se ddebbe iinddiicar dde fforma secuenciiall llas páágiinas que fforman partte dde estta ddecllaraciióón. CCadda páágiina se iinddiicaráá con 33
digitos. Después de la última página se pondrá el identificador "FIN". Por ejemplo, en un fichero que contenga una página 1, una 2, una 3, cuatro páginas 4, una 10,
una 11, una 12, una 13 y una página 19, debería rellenarse el vector con el siguiente contenido: 001002003004004004004010011012013019FIN (y el resto a blancos
12 337 300 An hasta completar las 300 posiciones
13 637 9 An Constante "</VECTOR>"
Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo
14 646Variable An documento
15*** 18 An Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "</T100020110A0000>"
16*** 2An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total Variable
(**) A cumplimentar por las entidades desarrolladoras (EEDD)
Idioma de la declaración: ((E)) Castellano, ((C)) Catalán, ((G)) Galleggo, ((V)) Valenciano
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# Pag. 2

100-01
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "01"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 9 An Primer Declarante - NIF (01) OBLIGATORIO
7 19 15 A Primer Declarante - Primer apellido (02) OBLIGATORIO
8 34 15 A Primer Declarante - Segundo apellido (03)
9 49 15 A Primer Declarante - Nombre (4) OBLIGATORIO
10 64 1 A Primer Declarante - Sexo "H" Hombre, "M" Mujer (05) OBLIGATORIO
11 65 1 Num Primer Declarante -Estado Civil. "1" Soltero/a, "2" Casado/a, "3" Viudo/a, "4" Divorciado/a o Separado/a OBLIGATORIO
12 66 8 Num Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año < 2012 (10) OBLIGATORIO
13 74 1 Num Primer Declarante - Grado de Minusvalía "0", "1", "2" o "3" (11)
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
Página 2

# Pag. 3

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
40 541 10 An Primer Declarante - Domicilio extranjero - Código Postal (39)
41 551 30 An Primer Declarante - Domicilio extranjero - Provincia / Región / Estado (40)
42 581 30 An Primer Declarante - Domicilio extranjero - País. (41)
43 611 2 An Primer Declarante - Domicilio extranjero - Código País. Código país ISO-3166 (alfabético 2 letras). (42)
44 613 15 An Primer Declarante - Domicilio extranjero - Teléfono fijo (43)
45 628 15 An Primer Declarante - Domicilio extranjero - Teléfono móvil (44)
46 643 15 An Primer Declarante - Domicilio extranjero - Núm. De Fax (45)
47 658 1 Num Datos adicionales vivienda - Titularidad "1", "2", "3" o "4" (50) OBLIGATORIO
48 659 5 Num Datos adicionales vivienda - Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
49 664 5 Num Datos adicionales vivienda - Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
50 669 1 Num Datos adicionales vivienda - Situación (clave) "1", "2", "3" o "4" (53)
51 670 20 An Datos adicionales vivienda - Referencia catastral (54)
52 690 1 Num Datos adicionales vivienda - Titularidad "0", "1", "2", "3" o "4" (50)
53 691 5 Num Datos adicionales vivienda - Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
54 696 5 Num Datos adicionales vivienda - Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
55 701 1 Num Datos adicionales vivienda - Situación (clave) "0", "1", "2", "3" o "4" (53)
56 702 20 An Datos adicionales vivienda - Referencia catastral (54)
57 722 1 Num Datos adicionales vivienda - Titularidad "0", "1", "2", "3" o "4" (50)
58 723 5 Num Datos adicionales vivienda - Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
59 728 5 Num Datos adicionales vivienda - Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
60 733 1 Num Datos adicionales vivienda - Situación (clave) "0", "1", "2", "3" o "4" (53)
61 734 20 An Datos adicionales vivienda - Referencia catastral (54)
62 754 1 Num Datos adicionales vivienda - Titularidad "0", "1", "2", "3" o "4" (50)
6633 775555 55 NNuumm DDaattooss aaddiicciioonnaalleess vviivviieennddaa -- PPoorrcceennttaajjee ppaarrttiicciippaacciióónn PPrriimmeerr ddeeccllaarraannttee ((ttrreess eenntteerrooss, ddooss ddeecciimmaalleess)) ((5511))
64 760 5 Num Datos adicionales vivienda - Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
65 765 1 Num Datos adicionales vivienda - Situación (clave) "0", "1", "2", "3" o "4" (53)
66 766 20 An Datos adicionales vivienda - Referencia catastral (54)
67 786 9 An Datos adicionales vivienda - Nif Arrendador (55)
68 795 9 An Cónyuge - NIF (61)
69 804 15 A Cónyuge - Primer apellido (62)
70 819 15 A Cónyuge - Segundo apellido (63)
71 834 15 A Cónyuge - Nombre (64)
72 849 1 A Cónyuge - Sexo "H" Hombre, "M" Mujer (65)
73 850 8 Num Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero. (66)
74 858 1 Num Cónyuge - Grado de Minusvalía "0", "1", "2" o "3" (67)
75 859 1 Num Cónyuge - No residente que no es contribuyente del I.R.P.F. - "1" o cero (68)
76 860 1 Num Cónyuge - Cambio de domicilio "1" o cero (70)
77 861 5 A Cónyuge - Domicilio habitual - Tipo de Vía (15)
78 866 5 Num Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Vía INE
79 871 50 An Cónyuge - Domicilio habitual - Nombre de la Vía Pública (16)
80 921 3 An Cónyuge - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
81 924 5 Num Cónyuge - Domicilio habitual - Número de Casa (18)
82 929 3 An Cónyuge - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
83 932 3 An Cónyuge - Domicilio habitual - Bloque (20)
Página 3

# Pag. 4

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
84 935 3 An Cónyuge - Domicilio habitual - Portal (21)
85 938 3 An Cónyuge - Domicilio habitual - Escalera (22)
86 941 3 An Cónyuge - Domicilio habitual - Planta (23)
87 944 3 An Cónyuge - Domicilio habitual - Puerta (24)
88 947 40 An Cónyuge - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
89 987 30 An Cónyuge - Domicilio habitual - Localidad / Población (26)
90 1017 5 Num Cónyuge - Domicilio habitual - Código postal (27)
91 1022 5 Num Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
92 1027 30 An Cónyuge - Domicilio habitual - Nombre del Municipio (28)
93 1057 2 Num Cónyuge - Domicilio habitual - Código provincia. De "01" a "52".
94 1059 20 An Cónyuge - Domicilio habitual - Provincia (29)
95 1079 9 Num Cónyuge - Domicilio habitual - Teléfono fijo (30)
96 1088 9 Num Cónyuge - Domicilio habitual - Teléfono móvil (31)
97 1097 9 Num Cónyuge - Domicilio habitual - Núm. De Fax (32)
98 1106 50 An Cónyuge - Domicilio extranjero - Domicilio/Address (35)
99 1156 40 An Cónyuge - Domicilio extranjero - Datos complementarios del domicilio (36)
100 1196 30 An Cónyuge - Domicilio extranjero - Población / Ciudad (37)
101 1226 100 An Cónyuge - Domicilio extranjero - e-mail (38)
102 1326 10 An Cónyuge - Domicilio extranjero - Código Postal (39)
103 1336 30 An Cónyuge - Domicilio extranjero - Provincia / Región / Estado (40)
104 1366 30 An Cónyuge - Domicilio extranjero - País (41)
105 1396 2 An Cónyuge - Domicilio extranjero - Código País (42)
106 1398 15 An Cónyuge - Domicilio extranjero - Teléfono fijo (43)
110077 11441133 1155 AAnn CCóónnyyuuggee -- DDoommiicciilliioo eexxttrraannjjeerroo -- TTeellééffoonnoo mmóóvviill ((4444))
108 1428 15 An Cónyuge - Domicilio extranjero - Núm. De Fax (45)
109 1443 1 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
110 1444 9 An Representante - N.I.F. (75)
111 1453 32 An Representante - Apellidos y nombre o razón social (76)
112 1485 20 An Fecha declaración - Lugar
113 1505 2 Num Fecha declaración - Fecha -Día
114 1507 10 A Fecha declaración - Fecha - Mes
115 1517 4 Num Fecha declaración - Fecha - Año
116 1521 4 Num Código cuenta cliente - Entidad
117 1525 4 Num Código cuenta cliente - Sucursal
118 1529 2 Num Código cuenta cliente - DC
119 1531 10 Num Código cuenta cliente - Número de cuenta
120 1541 13 Num Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
121 1554 21 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
122 1575 13 N Resultado de la declaración
123 1588 1 Num Fraccionamiento del pago. "1" o cero
124 1589 1 Num Domiciliación 2º plazo."1" o cero
125 1590 1 Num Renuncia a la devolución. "1" o cero
126 1591 1 Num Compensación entre cónyuges. "1" o cero
127 1592 20An Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
Página 4

# Pag. 5

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
128 1612 13An SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
129 1625 9An Identificador de Fin de registro. OBLIGATORIO Constante </T10001>
130 1634 2An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total 1635
Página 5

# Pag. 6

100-02
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "02"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 9 An Hijos y descendientes - 1º - N.I.F. (80)
7 19 33 A Hijos y descendientes - 1º - Apellidos y nombre (81)
8 52 8 Num Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año < 2012 o cero (82)
9 60 8 Num Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
10 68 1 Num Hijos y descendientes - 1º - Grado minusvalía "0", "1", "2" o "3" (84)
11 69 1 An Hijos y descendientes - 1º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
12 70 1 An Hijos y descendientes - 1º - Otras situaciones clave:"1","2","3","4" o blanco (86)
13 71 9 An Hijos y descendientes - 2º - N.I.F. (80)
14 80 33 A Hijos y descendientes - 2º - Apellidos y nombre (81)
15 113 8 Num Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año < 2012 o cero (82)
16 121 8 Num Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año < 2012 o cero (83)
17 129 1 Num Hijos y descendientes - 2º - Grado minusvalía "0", "1", "2" o "3" (84)
18 130 1 An Hijos y descendientes - 2º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
1199 113311 11 AAnn HHiijjooss yy ddeesscceennddiieenntteess - 22º - OOttrraass ssiittuuaacciioonneess "11",,"22",,"33",,"44" oo bbllaannccoo ((8866))
20 132 9 An Hijos y descendientes - 3º - N.I.F. (80)
21 141 33 A Hijos y descendientes - 3º - Apellidos y nombre (81)
22 174 8 Num Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
23 182 8 Num Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
24 190 1 Num Hijos y descendientes - 3º - Grado minusvalía "0", "1", "2" o "3" (84)
25 191 1 An Hijos y descendientes - 3º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
26 192 1 An Hijos y descendientes - 3º - Otras situaciones "1","2","3","4" o blanco (86)
27 193 9 An Hijos y descendientes - 4º - N.I.F. (80)
28 202 33 A Hijos y descendientes - 4º - Apellidos y nombre (81)
29 235 8 Num Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
30 243 8 Num Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
31 251 1 Num Hijos y descendientes - 4º - Grado minusvalía "0", "1", "2" o "3" (84)
32 252 1 An Hijos y descendientes - 4º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
33 253 1 An Hijos y descendientes - 4º - Otras situaciones "1","2","3","4" o blanco (86)
34 254 9 An Hijos y descendientes - 5º - N.I.F. (80)
35 263 33 A Hijos y descendientes - 5º - Apellidos y nombre (81)
36 296 8 Num Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
37 304 8 Num Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
38 312 1 Num Hijos y descendientes - 5º - Grado minusvalía "0", "1", "2" o "3" (84)
39 313 1 An Hijos y descendientes - 5º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
Página 6

# Pag. 7

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
40 314 1 An Hijos y descendientes - 5º - Otras situaciones "1","2","3","4" o blanco (86)
41 315 9 An Hijos y descendientes - 6º - N.I.F. (80)
42 324 33 A Hijos y descendientes - 6º - Apellidos y nombre (81)
43 357 8 Num Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
44 365 8 Num Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
45 373 1 Num Hijos y descendientes - 6º - Grado minusvalía "0", "1", "2" o "3" (84)
46 374 1 An Hijos y descendientes - 6º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
47 375 1 An Hijos y descendientes - 6º - Otras situaciones "1","2","3","4" o blanco (86)
48 376 9 An Hijos y descendientes - 7º - N.I.F. (80)
49 385 33 A Hijos y descendientes - 7º - Apellidos y nombre (81)
50 418 8 Num Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
51 426 8 Num Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
52 434 1 Num Hijos y descendientes - 7º - Grado minusvalía "0", "1", "2" o "3" (84)
53 435 1 An Hijos y descendientes - 7º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
54 436 1 An Hijos y descendientes - 7º - Otras situaciones "1","2","3","4" o blanco (86)
55 437 9 An Hijos y descendientes - 8º - N.I.F. (80)
56 446 33 A Hijos y descendientes - 8º - Apellidos y nombre (81)
57 479 8 Num Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
58 487 8 Num Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
59 495 1 Num Hijos y descendientes - 8º - Grado minusvalía "0", "1", "2" o "3" (84)
60 496 1 An Hijos y descendientes - 8º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
61 497 1 An Hijos y descendientes - 8º - Otras situaciones "1","2","3","4" o blanco (86)
62 498 9 An Hijos y descendientes - 9º - N.I.F. (80)
6633 550077 3333 AA HHiijjooss yy ddeesscceennddiieenntteess -- 99ºº -- AAppeelllliiddooss yy nnoommbbrree ((8811))
64 540 8 Num Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
65 548 8 Num Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
66 556 1 Num Hijos y descendientes - 9º - Grado minusvalía "0", "1", "2" o "3" (84)
67 557 1 An Hijos y descendientes - 9º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
68 558 1 An Hijos y descendientes - 9º - Otras situaciones "1","2","3","4" o blanco (86)
69 559 9 An Hijos y descendientes - 10º - N.I.F. (80)
70 568 33 A Hijos y descendientes - 10º - Apellidos y nombre (81)
71 601 8 Num Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
72 609 8 Num Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
73 617 1 Num Hijos y descendientes - 10º - Grado minusvalía "0", "1", "2" o "3" (84)
74 618 1 An Hijos y descendientes - 10º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
75 619 1 An Hijos y descendientes - 10º - Otras situaciones "1","2","3","4" o blanco (86)
76 620 9 An Hijos y descendientes - 11º - N.I.F. (80)
77 629 33 A Hijos y descendientes - 11º - Apellidos y nombre (81)
78 662 8 Num Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
79 670 8 Num Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
80 678 1 Num Hijos y descendientes - 11º - Grado minusvalía "0", "1", "2" o "3" (84)
81 679 1 An Hijos y descendientes - 11º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
82 680 1 An Hijos y descendientes - 11º - Otras situaciones "1","2","3","4" o blanco (86)
83 681 9 An Hijos y descendientes - 12º - N.I.F. (80)
Página 7

# Pag. 8

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
84 690 33 A Hijos y descendientes - 12º - Apellidos y nombre (81)
85 723 8 Num Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (82)
86 731 8 Num Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2012 o cero (83)
87 739 1 Num Hijos y descendientes - 12º - Grado minusvalía "0", "1", "2" o "3" (84)
88 740 1 An Hijos y descendientes - 12º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
89 741 1 An Hijos y descendientes - 12º - Otras situaciones "1","2","3","4" o blanco (86)
90 742 2 Num Hijos y descendientes - Fallecido 2011 - Nº Orden (87)
91 744 8 Num Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
92 752 2 Num Hijos y descendientes - Fallecido 2011 - Nº Orden (87)
93 754 8 Num Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
94 762 9 An Hijos y descendientes - Otro progenitor - Nif (56)
95 771 33 A Hijos y descendientes - Otro progenitor - Apellidos y nombre (57)
96 804 9 An Hijos y descendientes - A efectos de la declaración conjunta los hijos 1 y 2 son relacionados con los NIF
97 813 9 An Hijos y descendientes - A efectos de la declaración conjunta los hijos 1 y 2 son relacionados con los NIF
98 822 24 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
99 846 9 An Ascendientes mayores 65 años o discapacitados - 1º - N.I.F. (90)
100 855 33 A Ascendientes mayores 65 años o discapacitados - 1º - Apellidos y nombre (91)
101 888 8 Num Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (92)
102 896 1 Num Ascendientes mayores 65 años o discapacitados - 1º - Grado de Minusvalía "0", "1", "2" o "3" (93)
103 897 1 An Ascendientes mayores 65 años o discapacitados - 1º - Vinculación clave:"1", "2" o blanco (94)
104 898 1 An Ascendientes mayores 65 años o discapacitados - 1º - Convivencia "2" a "9" o blanco (95)
105 899 9 An Ascendientes mayores 65 años o discapacitados - 2º - N.I.F. (90)
106 908 33 A Ascendientes mayores 65 años o discapacitados - 2º - Apellidos y nombre (91)
110077 994411 88 NNuumm AAsscceennddiieenntteess mmaayyoorreess 6655 aaññooss oo ddiissccaappaacciittaaddooss -- 22ºº -- FFeecchhaa ddee nnaacciimmiieennttoo. ((DDDDMMMMAAAAAAAA)) AAññoo << 22001122 oo cceerroo ((9922))
108 949 1 Num Ascendientes mayores 65 años o discapacitados - 2º - Grado de Minusvalía "0", "1", "2" o "3" (93)
109 950 1 An Ascendientes mayores 65 años o discapacitados - 2º - Vinculación clave:"1", "2" o blanco (94)
110 951 1 An Ascendientes mayores 65 años o discapacitados - 2º - Convivencia "2" a "9" o blanco (95)
111 952 9 An Ascendientes mayores 65 años o discapacitados - 3º - N.I.F. (90)
112 961 33 A Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
113 994 8 Num Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año < 2012 o cero (92)
114 1002 1 Num Ascendientes mayores 65 años o discapacitados - 3º - Grado de Minusvalía "0", "1", "2" o "3" (93)
115 1003 1 An Ascendientes mayores 65 años o discapacitados - 3º - Vinculación clave:"1", "2" o blanco (94)
116 1004 1 An Ascendientes mayores 65 años o discapacitados - 3º - Convivencia "2" a "9" o blanco (95)
117 1005 9 An Ascendientes mayores 65 años o discapacitados - 4º - N.I.F. (90)
118 1014 33 A Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
119 1047 8 Num Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2012 o cero (92)
120 1055 1 Num Ascendientes mayores 65 años o discapacitados - 4º - Grado de Minusvalía "0", "1", "2" o "3" (93)
121 1056 1 An Ascendientes mayores 65 años o discapacitados - 4º - Vinculación clave:"1", "2" o blanco (94)
122 1057 1 An Ascendientes mayores 65 años o discapacitados - 4º - Convivencia "2" a "9" o blanco (95)
123 1058 8 Num Devengo - Fecha de finalización del período impositivo (fallecimiento 2011) (DDMMAAAA) o cero (100)
124 1066 1 Num Opción de tributación. "1" Individual, "2" Conjunta. Campo OBLIGATORIO (101) (102) OBLIGATORIO
125 1067 2 Num Comunidad/Ciudad autónoma de residencia en 2011 - Clave (103) Incluido en el fichero COMAUTO.TXT OBLIGATORIO
126 1069 1 A Asignación tributaria a la Iglesia Católica. "X" o blanco. (105)
127 1070 1 A Asignación de cantidades a fines sociales. "X" o blanco. (106)
Página 8

# Pag. 9

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
128 1071 1 Num Borrador Declaración o datos fiscales 2012. Recibir por correo ordinario y no visualizarlo por internet. "1" o cero (110)
129 1072 1 Num Borrador Declaración o datos fiscales 2012. Obtener tributación individual. "1" o cero (111)
130 1073 1 Num Declaración complementaria - Si es complementaria por atrasos de rendimientos del trabajo. "1" o cero (121)
131 1074 1 Num Declaración complementaria - Si es complementaria por haberse producido alguno de los supuestos especiales. "1" o cero (122)
132 1075 1 Num Declaración complementaria - Si es complementaria a devolver. "1" o cero (123)
133 1076 1 Num Declaración complementaria - Si es complementaria por supuestos distintos "1" o cero (120)
134 1077 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10002>
135 1086 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total 1087
Página 9

# Pag. 10

100-03
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
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
12 88 13 N Rdto. Trabajo - Aportaciones al patrimonio protegido de discapacitados - Importe (007)
13 101 13 N Rdto. Trabajo - Reducciones - Importe (008)
14 114 13 N Rdto. Trabajo - Total ingresos íntegros computables (009)
15 127 13 N Rdto. Trabajo - Cotizaciones Seguridad Social/Mutual. grales. funcionarios/cotiz. colegios huerfanos (010)
16 140 13 N Rdto. Trabajo - Cuotas satisfechas a sindicatos (011)
17 153 13 N Rdto. Trabajo - Cuotas a colegios profesionales (012)
18 166 13 N Rdto. Trabajo - Gastos defensa jurídica derivados litigios con empleador (013)
19 179 13 N Rdto. Trabajo - Total gastos deducibles (014)
20 192 13 N Rdto. Trabajo - Rendimiento neto (015)
21 205 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Cuantía aplicable con carácter general (017)
2222 221188 1133 NN RRddttoo. TTrraabbaajjoo -- RReedduucccciióónn oobbtteenncciióónn rreennddiimmiieennttooss ddee ttrraabbaajjoo. IInnccrreemmeennttoo ttrraabbaajjaaddoorreess aaccttiivvooss >> 6655 aaññooss ((001188))
23 231 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Incremento contribuyentes desempleados con traslado de residencia (019)
24 244 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Reducción adicional para trabajadores activos discapacitados (020)
25 257 13 N Rdto. Trabajo - Rendimiento neto reducido (021)
26 270 13 N (B) Rdto.cap.mob.- Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (022)
27 283 13 N Rdto.cap.mob.- Base imponible ahorro - Intereses de activos financieros con derecho a bonificación (023)
28 296 13 N Rdto.cap.mob.- Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (024)
29 309 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (025)
30 322 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros(026)
31 335 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (027)
32 348 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. Procedentes de rentas que tengan por causa la imposición de capitales (028)
33 361 13 N Rdto.cap.mob.- Base imponible ahorro - Total ingresos íntegros (029)
34 374 13 N Rdto.cap.mob.- Base imponible ahorro - Gastos fiscalmente deducibles (030)
35 387 13 N Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto (031)
36 400 13 N Rdto.cap.mob.- Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (032)
37 413 13 N Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto reducido (035)
38 426 13 N (B) Rdto.cap.mob.- Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (040)
39 439 13 N Rdto.cap.mob.- Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (041)
40 452 13 N Rdto.cap.mob.- Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (042)
41 465 13 N Rdto.cap.mob.- Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (043)
42 478 13 N Rdto.cap.mob.- Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (044)
43 491 13 N Rdto.cap.mob.- Base imponible general - Total ingresos íntegros (045)
44 504 13 N Rdto.cap.mob.- Base imponible general - Gastos fiscalmente deducibles (046)
45 517 13 N Rdto.cap.mob.- Base imponible general - Rendimiento neto (047)
Página 10

# Pag. 11

100-03
Nº Posic. Tipo Descripción Validación Contenido
46 530 13 N Rdto.cap.mob.- Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (048)
47 543 13 N Rdto.cap.mob.- Base imponible general - Rendimiento neto reducido (050)
48 556 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10003>
49 565 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 566
Página 11

# Pag. 12

100-04
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "04"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 2 Num Nº de hojas adicionales que se adjuntan
7 12 1 Tit C (C) Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Contribuyente "0" a "9" (060)
8 13 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje titularidad (3 enteros y 2 decimales) (061)
9 18 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Naturaleza (062)
10 19 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Uso o destino. Clave (063)
11 20 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Situación "0", "1", "2", "3" o "4" (064)
12 21 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Referencia catastral (065)
13 41 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (067)
14 46 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Número de días (068)
15 49 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Renta imputada (069)
16 62 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Ingresos íntegros computables (070)
17 75 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (071)
18 88 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Importe (072)
1199 110011 1133 NN CC BBiieenneess iinnmmuueebblleess nnoo aaffeeccttooss. RReellaacciióónn iinnmmuueebblleess yy rreennttaass. IInnmmuueebbllee 11. AArrrreennddaaddoo oo cceeddiiddoo. GGaassttooss ddeedduucciibblleess. IInntteerreesseess. PPeennddiieennttee ddeedduucciirr ((007733))
20 114 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (074)
21 127 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto (075)
22 140 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (076)
23 153 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción rendimientos más de 2 años (077)
24 166 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento mínimo computable caso parentesto (078)
25 179 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto reducido (079)
26 192 1 Tit C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Contribuyente "0" a "9" (060)
27 193 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje titularidad (3 enteros y 2 decimales) (061)
28 198 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Naturaleza (062)
29 199 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Uso o destino. Clave (063)
30 200 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Situación "0", "1", "2", "3" o "4" (064)
31 201 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Referencia catastral (065)
32 221 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (067)
33 226 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Número de días (068)
34 229 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Renta imputada (069)
35 242 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Ingresos íntegros computables (070)
36 255 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (071)
37 268 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe (072)
38 281 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (073)
Página 12

# Pag. 13

100-04
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
39 294 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (074)
40 307 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto (075)
41 320 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (076)
42 333 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción rendimientos más de 2 años (077)
43 346 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento mínimo computable caso parentesto (078)
44 359 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto reducido (079)
45 372 1 Tit C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Contribuyente "0" a "9" (060)
46 373 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Porcentaje titularidad (3 enteros y 2 decimales) (061)
47 378 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Naturaleza (062)
48 379 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Uso o destino. Clave (063)
49 380 1 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Situación "0", "1", "2", "3" o "4" (064)
50 381 20 An C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Referencia catastral (065)
51 401 5 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (067)
52 406 3 Num C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Número de días (068)
53 409 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. A disposición. Renta imputada (069)
54 422 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Ingresos íntegros computables (070)
55 435 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (071)
56 448 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Importe (072)
57 461 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (073)
58 474 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Gastos deducibles. Otros gastos deducibles (074)
59 487 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento neto (075)
60 500 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (076)
61 513 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Reducción rendimientos más de 2 años (077)
6622 552266 1133 NN CC BBiieenneess iinnmmuueebblleess nnoo aaffeeccttooss. RReellaacciióónn iinnmmuueebblleess yy rreennttaass. IInnmmuueebbllee 33. AArrrreennddaaddoo oo cceeddiiddoo. RReennddiimmiieennttoo mmíínniimmoo ccoommppuuttaabbllee ccaassoo ppaarreenntteessttoo ((007788))
63 539 13 N C Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 3. Arrendado o cedido. Rendimiento neto reducido (079)
64 552 13 N Bienes inmuebles no afectos. Rentas totales . Suma de rentas inmobiliarias imputadas (080)
65 565 13 N Bienes inmuebles no afectos. Rentas totales . Suma rendimientos netos reducidos del capital inmobiliario (085)
66 578 3 Num Número de inmuebles en declaración conjunta (Reservado para la Administración)
67 581 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Contribuyente "0" a "9" (094)
68 582 9 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. NIF entidad (095)
69 591 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Porcentaje participación (3 enteros y 2 decimales) (096)
70 596 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Naturaleza (097)
71 597 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Situación "0", "1", "2", "3" o "4" (098)
72 598 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. Referencia catastral (099)
73 618 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Contribuyente "0" a "9" (094)
74 619 9 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. NIF entidad (095)
75 628 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Porcentaje participación (3 enteros y 2 decimales) (096)
76 633 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Naturaleza (097)
77 634 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Situación "0", "1", "2", "3" o "4" (098)
78 635 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. Referencia catastral (099)
79 655 1 Tit C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Contribuyente "0" a "9" (094)
80 656 9 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. NIF entidad (095)
81 665 5 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Porcentaje participación (3 enteros y 2 decimales) (096)
Página 13

# Pag. 14

100-04
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
82 670 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Naturaleza (097)
83 671 1 Num C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Situación "0", "1", "2", "3" o "4" (098)
84 672 20 An C Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. Referencia catastral (099)
85 692 1 Tit C (D) Bienes inmuebles urbanos afectos. Inmueble 1. Contribuyente "0" a "9" (090)
86 693 5 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje titularidad (3 enteros y 2 decimales) (091)
87 698 1 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Naturaleza (clave) (089)
88 699 1 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Situación "0", "1", "2", "3" o "4" (092)
89 700 20 An C Bienes inmuebles urbanos afectos. Inmueble 1. Referencia catastral (093)
90 720 1 Tit C Bienes inmuebles urbanos afectos. Inmueble 2. Contribuyente "0" a "9" (090)
91 721 5 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje titularidad (3 enteros y 2 decimales) (091)
92 726 1 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Naturaleza (clave) (089)
93 727 1 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Situación "0", "1", "2", "3" o "4" (092)
94 728 20 An C Bienes inmuebles urbanos afectos. Inmueble 2. Referencia catastral (093)
95 748 1 Tit C Bienes inmuebles urbanos afectos. Inmueble 3. Contribuyente "0" a "9" (090)
96 749 5 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje titularidad (3 enteros y 2 decimales) (091)
97 754 1 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Naturaleza (clave) (089)
98 755 1 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Situación "0", "1", "2", "3" o "4" (092)
99 756 20 An C Bienes inmuebles urbanos afectos. Inmueble 3. Referencia catastral (093)
100 776 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10004>
101 785 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 786
Página 14

# Pag. 15

100-05
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "05"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 3 Actividades a las que resulte aplicable un mismo régimen
7 11 1 Tit C (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Contribuyente "0" a "9" (100)
8 12 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Tipo actividad. Clave (Blanco o de "1" a "5") (101)
9 13 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Modalidad Normal (103) o Simplificada (104) "0", "1" o "2"
10 14 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Epígrafe IAE (102) (**)
11 19 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Criterio cobros/pagos. "1" o cero. (105)
12 20 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Explotación (106)
13 33 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Otros ingresos (107)
14 46 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Autoconsumo bienes/servicios (108)
15 59 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Total ingresos computables (109)
16 72 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Consumos de explotación (110)
17 85 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Sueldos y salarios (111)
18 98 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Seguridad Social (112)
1199 111111 1133 NN CC RRddttoo.aaccttvv.eeccoonn.eesstt.ddiirreeccttaa - AAccttiivviiddaadd yy rrddttoo. oobbtteenniiddoo - GGaassttooss - AAccttiivviiddaadd 11- OOttrrooss ggaassttooss ddee ppeerrssoonnaall ((111133))
20 124 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Arrendamientos y cánones (114)
21 137 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Reparación y conservación (115)
22 150 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Servicios profesionales independientes (116)
23 163 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros servicios exteriores (117)
24 176 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Tributos fiscalmente deducibles (118)
25 189 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Gastos financieros (119)
26 202 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Amortizaciones (120)
27 215 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Pérdidas por deterioro (121)
28 228 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (convenios) (122)
29 241 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (gastos) (123)
30 254 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros gastos fiscalmente deducibles (124)
31 267 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Suma (125)
32 280 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Normal - Provisiones (126)
33 293 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Normal - Total gastos deducibles (127)
34 306 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Diferencia (128)
35 319 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (129)
36 332 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad Simplificada - Total gastos deducibles (130)
37 345 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Rdto. neto (131)
38 358 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Reducciones (132)
Página 15

# Pag. 16

100-05
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
39 371 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -1- Rto. Neto reduc.(133)
40 384 1 Tit C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Contribuyente "0" a "9" (100)
41 385 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Tipo actividad.Clave (Blanco o de "1" a "5") (101)
42 386 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Modalidad Normal (103) o Simplificada (104) "0", "1" o "2"
43 387 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Epígrafe IAE (102) (**)
44 392 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Criterio cobros/pagos. "1" o cero. (105)
45 393 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Explotación (106)
46 406 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Otros ingresos (107)
47 419 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Autoconsumo bienes/servicios (108)
48 432 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Total ingresos computables (109)
49 445 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Consumos de explotación (110)
50 458 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Sueldos y salarios 111)
51 471 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Seguridad Social (112)
52 484 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos de personal (113)
53 497 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Arrendamientos y cánones (114)
54 510 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Reparación y conservación (115)
55 523 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Servicios profesionales independientes (116)
56 536 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros servicios exteriores (117)
57 549 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Tributos fiscalmente deducibles (118)
58 562 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Gastos financieros (119)
59 575 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Amortizaciones (120)
60 588 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Pérdidas por deterioro (121)
61 601 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (convenios) (122)
6622 661144 1133 NN CC RRddttoo.aaccttvv.eeccoonn.eesstt.ddiirreeccttaa - AAccttiivviiddaadd yy rrddttoo. oobbtteenniiddoo - GGaassttooss - AAccttiivviiddaadd 22- MMeecceennaazzggoo ((ggaassttooss)) ((112233))
63 627 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos fiscalmente deducibles (124)
64 640 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Suma de gastos (125)
65 653 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Normal - Provisiones (126)
66 666 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Normal - Total gastos deducibles (127)
67 679 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Diferencia (128)
68 692 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (129)
69 705 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Total gastos deducibles (130)
70 718 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto. neto (131)
71 731 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Reducciones (132)
72 744 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rto.neto reduc. (133)
73 757 1 Tit C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Contribuyente "0" a "9" (100)
74 758 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Tipo actividad.Clave (Blanco o de "1" a "5") (101)
75 759 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Modalidad Normal (103) o Simplificada (104) "0", "1" o "2"
76 760 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Epígrafe IAE (102) (**)
77 765 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Criterio cobros/pagos. "1" o cero. (105)
78 766 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Explotación (106)
79 779 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Otros ingresos (107)
80 792 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Autoconsumo bienes/servicios (108)
81 805 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Total ingresos computables (109)
Página 16

# Pag. 17

100-05
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
82 818 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Consumos de explotación (110)
83 831 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Sueldos y salarios (111)
84 844 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Seguridad Social (112)
85 857 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos de personal (113)
86 870 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Arrendamientos y cánones (114)
87 883 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Reparación y conservación (115)
88 896 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Servicios profesionales independientes (116)
89 909 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros servicios exteriores (117)
90 922 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Tributos fiscalmente deducibles (118)
91 935 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Gastos financieros (119)
92 948 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Amortizaciones (120)
93 961 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Pérdidas por deterioro (121)
94 974 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (convenios) (122)
95 987 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (gastos) (123)
96 1000 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos fiscalmente deducibles (124)
97 1013 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Suma de gastos (125)
98 1026 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Normal - Provisiones (126)
99 1039 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Normal - Total gastos deducibles (127)
100 1052 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Diferencia (128)
101 1065 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (129)
102 1078 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Total gastos deducibles (130)
103 1091 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto. neto (131)
104 1104 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Reducciones (132)
110055 11111177 1133 NN CC RRddttoo.aaccttvv.eeccoonn.eesstt.ddiirreeccttaa - AAccttiivviiddaadd yy rrddttoo. oobbtteenniiddoo - RRddttoo. nneettoo yy rrddttoo. nneettoo rreedduucc. - AAccttiivviiddaadd 33- RRttoo.nneettoo rreedduucc. ((113333))
106 1130 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Suma de rendimientos netos reducidos (136)
107 1143 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción ejercicio determinadas actividades (137)
108 1156 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción por mantenimiento o creación de empleo (138)
109 1169 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Rendimiento neto reducido total (140)
110 1182 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10005>
111 1191 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1192
(**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignarán las tres cifras seguidas de dos
blancos.
Página 17

# Pag. 18

100-06
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "06"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 2 actividades
7 11 5 An C (E2) Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Clasificación IAE (151) (**)
8 16 1 Tit C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Contribuyente titular actividad (150) "0" a "9"
9 17 1 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (280)
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
31 326 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma) (152)
32 339 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo (153)
33 352 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (154)
34 365 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (155)
35 378 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (156)
36 382 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (157)
37 386 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (158)
38 390 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (159)
39 394 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (160)
Página 18

# Pag. 19

100-06
Nº Posic. Long. Tipo Com Descripción Validación Contenido
40 398 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto de módulos (161)
41 411 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción de carácter general (166)
42 424 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (149)
43 437 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Gastos extraordinarios circunstancias excepcionales (162)
44 450 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Otras percepciones empresariales (163)
45 463 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª -Rendimiento neto actividad (164)
46 476 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción art. 32.1 Ley del Impuesto (165)
47 489 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rendimiento neto reducido (167)
48 502 5 An C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Clasificación IAE (151) (**)
49 507 1 Tit C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Contribuyente titular actividad (150) "0" a "9"
50 508 1 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (280)
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
72 817 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto previo (suma) (152)
73 830 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos al empleo (153)
74 843 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos a la inversion (154)
75 856 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto minorado (155)
76 869 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector especial (2 enteros y 2 decimales) (156)
77 873 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (157)
78 877 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de temporada (2 enteros y 2 decimales) (158)
79 881 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de exceso (2 enteros y 2 decimales) (159)
80 885 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (160)
81 889 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto de módulos (161)
82 902 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción de carácter general (166)
83 915 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (149)
Página 19

# Pag. 20

100-06
Nº Posic. Long. Tipo Com Descripción Validación Contenido
84 928 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Gastos extraordinarios circunstancias excepcionales (162)
85 941 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Otras percepciones empresariales (163)
86 954 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª -Rendimiento neto actividad (164)
87 967 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción art. 32.1 Ley del Impuesto (165)
88 980 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rendimiento neto reducido (167)
89 993 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Suma rendimientos netos reducidos (168)
90 1006 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Reducción por mantenimiento o creación de empleo (169)
91 1019 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas (170)
92 1032 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10006>
93 1041 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
1042
(**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos
blancos.
Página 20

# Pag. 21

100-07
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "07"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 2 Actividades
7 11 1 Num C (E3) Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Clave actividad: de "0" a "9" (172)
8 12 1 Tit C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Contribuyente titular de actividad: de "0" a "9" (171)
9 13 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Criterio cobros/pagos: "1" ó "0" (173)
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
Página 21

# Pag. 22

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
49 378 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Total ingresos íntegros (174)
50 389 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto previo (suma) (175)
51 400 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones (176)
52 411 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Amortización inmovilizado (178)
53 422 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto minorado (179)
54 433 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Medios ajenos (2 enteros y 2 decimales) (180)
55 437 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Utiliz. personal asalariado (2 enteros y 2 decimales) (181)
56 441 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (182)
57 445 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (183)
58 449 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º, >50 % (2 enteros y 2 decimales) Índice 2 (183) Ver NOTA
59 453 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Activ.agricultura ecológica (2 enteros y 2 decimales) (184)
60 457 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Empresa no supera 9447,91 € (2 enteros y 2 decimales) (185)
61 461 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Determin. activ. forestales (2 enteros y 2 decimales) (186)
6622 446655 1133 NN CC RRddttooss. aaggrríícc.ggaannaadd.yy ffoorreesstt. eesstt. oobbjjeettiivvaa --AAcctt. rreeaalliizz.//rrddttooss-- AAccttiivv 11ªª -- RRddttoo. nneettoo ddee mmóódduullooss ((118877))
63 478 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción carácter general (188)
64 491 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Diferencia (189)
65 504 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción agricultores jóvenes (190)
66 517 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Gastos extraordinarios por circunstancias excepcionales (191)
67 530 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto (192)
68 543 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones rendimientos generados más 2 años o forma irregular (193)
69 556 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto reducido (194)
70 569 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Clave actividad: de "0" a "9" (172)
71 570 1 Tit C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Contribuyente titular de actividad: de "0" a "9" (171)
72 571 1 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Criterio cobros/pagos: "1" ó "0" (173)
73 572 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Ingresos íntegros
74 583 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Índice
75 589 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Rdto. base producto
76 600 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Ingresos íntegros
77 611 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Índice
78 617 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Rdto. base producto
79 628 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Ingresos íntegros
80 639 6 An C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Índice
81 645 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Rdto. base producto
Página 22

# Pag. 23

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
112 936 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Total ingresos íntegros (174)
113 947 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto previo (suma) (175)
114 958 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones (176)
115 969 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Amortizacion inmovilizado (178)
116 980 11 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto minorado (179)
117 991 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Medios ajenos (2 enteros y 2 decimales) (180)
118 995 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Utiliz. personal asalariado (2 enteros y 2 decimales) (181)
119 999 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (182)
120 1003 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (183)
121 1007 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º, >50 % (2 enteros y 2 decimales) Índice 2 (183) Ver NOTA
122 1011 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Activ.agricultura ecológica (2 enteros y 2 decimales) (184)
123 1015 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Empresa no supera 9447,91 € (2 enteros y 2 decimales) (185)
124 1019 4 Num C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Determin. activ. forestales (2 enteros y 2 decimales) (186)
Página 23

# Pag. 24

100-07
Nº Posic. Long. Tipo Com Descripción Validación Contenido
125 1023 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto de módulos (187)
126 1036 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción carácter general (188)
127 1049 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Diferencia (189)
128 1062 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción agricultores jóvenes (190)
129 1075 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Gastos extraordinarios por circunstancias excepcionales (191)
130 1088 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto (192)
131 1101 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones rendimientos generados más 2 años o forma irregular (193)
132 1114 13 N C Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto reducido (194)
133 1127 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Suma rendimientos netos reducidos (195)
134 1140 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Reducción por mantenimiento o creación de empleo (196)
135 1153 13 N Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Rendimiento neto reducido total (197)
136 1166 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10007>
137 1175 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1176
NOTA: Cumplimentar sólo cuando el índice 2 sea distinto al índice 1.
Página 24

# Pag. 25

100-08
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "08"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 3 imputaciones
7 11 1 Tit C (F) Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (200)
8 12 9 An C Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - NIF Entidad (201)
9 21 4 Num C Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Porcentaje participación (202)
10 25 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (203)
11 38 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones y minoraciones (204)
12 51 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto computable (205)
13 64 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto (206)
14 77 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto atribuido (209)
15 90 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Reducciones y minoraciones (210)
16 103 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto computable (211)
17 116 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. neto atribuido (212)
18 129 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducciones y minoraciones (213)
1199 114422 1133 NN CC RReeggss. eessppeecciiaalleess -- RRééggiimmeenn aattrriibbuucciióónn rreennttaass -- EEnnttiiddaadd 11 -- RRddttooss. aaccttiivviiddaaddeess eeccoonnóómmiiccaass -- RRddttoo. nneettoo ccoommppuuttaabbllee ((221144))
20 155 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - No derivadas transmisión - Ganancias (215)
21 168 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - No derivadas transmisión - Pérdidas (216)
22 181 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - Derivadas transmisión - Ganancias (217)
23 194 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas - Derivadas transmisión - Pérdidas (218)
24 207 13 N C Regs. especiales - Régimen atribución rentas - Entidad 1 - Retenciones e ingresos a cuenta. - Retenciones e ingresos atribuidos (219)
25 220 1 Tit C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (200)
26 221 9 An C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - NIF Entidad (201)
27 230 4 Num C Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Porcentaje participación (202)
28 234 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (203)
29 247 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones y minoraciones (204)
30 260 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto computable (205)
31 273 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto (206)
32 286 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto atribuido (209)
33 299 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Reducciones y minoraciones (210)
34 312 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto computable (211)
35 325 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. neto atribuido (212)
36 338 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducciones y minoraciones (213)
37 351 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. neto computable (214)
38 364 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - No derivadas transmisión - Ganancias (215)
Página 25

# Pag. 26

100-08
Nº Posic. Long. Tipo Com Descripción Validación Contenido
39 377 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - No derivadas transmisión - Pérdidas (216)
40 390 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - Derivadas transmisión - Ganancias (217)
41 403 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas - Derivadas transmisión - Pérdidas (218)
42 416 13 N C Regs. especiales - Régimen atribución rentas - Entidad 2 - Retenciones e ingresos a cuenta. - Retenciones e ingresos atribuidos (219)
43 429 1 Tit C Regs. especiales - Régimen atribución rentas - Entidad 3 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (200)
44 430 9 An C Regs. especiales - Régimen atribución rentas - Entidad 3 - Entidades y contribuyentes partícipes - NIF Entidad (201)
45 439 4 Num C Regs. especiales - Régimen atribución rentas - Entidad 3 - Entidades y contribuyentes partícipes - Porcentaje participación (202)
46 443 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (203)
47 456 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones y minoraciones (204)
48 469 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto computable (205)
49 482 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto (206)
50 495 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. capital inmobiliario - Rdto. neto atribuido (209)
51 508 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. capital inmobiliario - Reducciones y minoraciones (210)
52 521 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. capital inmobiliario - Rdto. neto computable (211)
53 534 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. actividades económicas - Rdto. neto atribuido (212)
54 547 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. actividades económicas - Reducciones y minoraciones (213)
55 560 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Rdtos. actividades económicas - Rdto. neto computable (214)
56 573 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Atribución ganancias y pérdidas - No derivadas transmisión - Ganancias (215)
57 586 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Atribución ganancias y pérdidas - No derivadas transmisión - Pérdidas (216)
58 599 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Atribución ganancias y pérdidas - Derivadas transmisión - Ganancias (217)
59 612 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Atribución ganancias y pérdidas - Derivadas transmisión - Pérdidas (218)
60 625 13 N C Regs. especiales - Régimen atribución rentas - Entidad 3 - Retenciones e ingresos a cuenta. - Retenciones e ingresos atribuidos (219)
61 638 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. capital mobiliario - Rdto. integrar base imponible general - Total rdto. neto computable (220)
6622 665511 1133 NN RReeggss. eessppeecciiaalleess -- RRééggiimmeenn aattrriibbuucciióónn rreennttaass -- TToottaall -- RRddttooss. ccaappiittaall mmoobbiilliiaarriioo -- RRddttoo. iinntteeggrraarr bbaassee iimmppoonniibbllee aahhoorrrroo -- TToottaall rrddttoo. nneettoo aattrriibbuuiiddoo ((222211))
63 664 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. capital inmobiliario - Total rdto. neto computable (222)
64 677 13 N Regs. especiales - Régimen atribución rentas - Total - Rdtos. actividades económicas - Total rdto. neto computable (223)
65 690 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - No derivadas transmisión - Total ganancias (224)
66 703 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - No derivadas transmisión - Total pérdidas (225)
67 716 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - Derivadas transmisión - Total ganancias (226)
68 729 13 N Regs. especiales - Régimen atribución rentas - Total - Atribución ganancias y pérdidas - Derivadas transmisión - Total pérdidas (227)
69 742 13 N Regs. especiales - Régimen atribución rentas - Total - Retenciones e ingresos a cuenta - Total retenciones e ingresos atribuidos (746)
70 755 1 Tit C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. Contribuyente "0" a "9" (230)
71 756 9 An C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. N.I.F. Entidad (231)
72 765 1 An C Regs. especiales - Agrupac., ute - Entidad 1- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (232)
73 766 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Base imponible imputada (233)
74 779 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. invers. empres. (234)
75 792 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. creación empleo (235)
76 805 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (236)
77 818 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. base impon. y deduc. - Deduc. doble impos. internac. (237)
78 831 13 N C Regs. especiales - Agrupac., ute - Entidad 1- Imput. Ret.e.ingresos cta. - Retenc. e ingresos a cta. imputados (239)
79 844 1 Tit C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. Contribuyente "0" a "9" (230)
80 845 9 An C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. N.I.F. Entidad (231)
81 854 1 An C Regs. especiales - Agrupac., ute - Entidad 2- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (232)
Página 26

# Pag. 27

100-08
Nº Posic. Long. Tipo Com Descripción Validación Contenido
82 855 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Base imponible imputada (233)
83 868 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. invers. empres. (234)
84 881 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. creación empleo (235)
85 894 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (236)
86 907 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. base impon. y deduc. - Deduc. doble impos. internac. (237)
87 920 13 N C Regs. especiales - Agrupac., ute - Entidad 2- Imput. Ret.e.ingresos cta. - Retenc. e ingresos a cta. imputados (239)
88 933 1 Tit C Regs. especiales - Agrupac., ute - Entidad 3- Entidades y contribuyentes socios. Contribuyente "0" a "9" (230)
89 934 9 An C Regs. especiales - Agrupac., ute - Entidad 3- Entidades y contribuyentes socios. N.I.F. Entidad (231)
90 943 1 An C Regs. especiales - Agrupac., ute - Entidad 3- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (232)
91 944 13 N C Regs. especiales - Agrupac., ute - Entidad 3- Imput. base impon. y deduc. - Base imponible imputada (233)
92 957 13 N C Regs. especiales - Agrupac., ute - Entidad 3- Imput. base impon. y deduc. - Deduc. invers. empres. (234)
93 970 13 N C Regs. especiales - Agrupac., ute - Entidad 3- Imput. base impon. y deduc. - Deduc. creación empleo (235)
94 983 13 N C Regs. especiales - Agrupac., ute - Entidad 3- Imput. base impon. y deduc. - Deduc. rentas Ceuta/Melilla (236)
95 996 13 N C Regs. especiales - Agrupac., ute - Entidad 3- Imput. base impon. y deduc. - Deduc. doble impos. internac. (237)
96 1009 13 N C Regs. especiales - Agrupac., ute - Entidad 3- Imput. Ret.e.ingresos cta. - Retenc. e ingresos a cta. imputados (239)
97 1022 13 N Regs. especiales - Agrupac., ute - Total base imponible imputada (245)
98 1035 13 N Regs. especiales - Agrupac., ute - Total Retenciones e ingresos a cta. imputados (747)
99 1048 1 Tit C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Contribuyente "0" a "9" (250)
100 1049 24 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Denominación entidad no residente (251)
101 1073 1 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Criterio imput. temporal. Clave (blanco, "1" ó "2") (252)
102 1074 13 N C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 1 - Importe imputación (253)
103 1087 1 Tit C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Contribuyente "0" a "9" (250)
104 1088 24 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Denominación entidad no residente (251)
110055 11111122 11 AAnn CC RReeggss.. eessppeecciiaalleess -- IImmppuuttaacc.. rreennttaass rreegg.. ttrraannsspp.. ffiissccaall iinntteerrnnaacciioonnaall -- EEnnttiiddaadd 22 -- CCrriitteerriioo iimmppuutt.. tteemmppoorraall.. CCllaavvee ((bbllaannccoo,, "11" óó "22")) ((225522))
106 1113 13 N C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 2 - Importe imputación (253)
107 1126 1 Tit C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 3 - Contribuyente "0" a "9" (250)
108 1127 24 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 3 - Denominación entidad no residente (251)
109 1151 1 An C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 3 - Criterio imput. temporal. Clave (blanco, "1" ó "2") (252)
110 1152 13 N C Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Entidad 3 - Importe imputación (253)
111 1165 13 N Regs. especiales - Imputac. rentas reg. transp. fiscal internacional - Total importe de la imputación (255)
112 1178 1 Tit Regs. especiales - Imputac. rentas derechos imagen - Contribuyente que debe efectuar la imputacion. "0" a "9" (260)
113 1179 25 An Regs. especiales - Imputac. rentas derechos imagen - NIF o denominación persona/entidad cesionaria derechos imagen (261)
114 1204 25 An Regs. especiales - Imputac. rentas derechos imagen - NIF o denominación persona/entidad relación laboral (262)
115 1229 13 N Regs. especiales - Imputac. rentas derechos imagen - Cantidad a imputar (265)
116 1242 1 Tit C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Contribuyente "0" a "9" (270)
117 1243 24 An C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Denominación Institución (271)
118 1267 13 N C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 1 - Importe imputación (272)
119 1280 1 Tit C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Contribuyente "0" a "9" (270)
120 1281 24 An C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Denominación Institución (271)
121 1305 13 N C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 2 - Importe imputación (272)
122 1318 1 Tit C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 3 - Contribuyente "0" a "9" (270)
123 1319 24 An C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 3 - Denominación Institución (271)
124 1343 13 N C Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - I. I. C. 3 - Importe imputación (272)
Página 27

# Pag. 28

100-08
Nº Posic. Long. Tipo Com Descripción Validación Contenido
125 1356 13 N Regs. especiales - Imputac.rentas I. I.Colectiva paraísos fiscales - Total importe de la imputación (275)
126 1369 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10008>
127 1378 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1379
Página 28

# Pag. 29

100-09
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "09"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 10 1 Num Nº hojas adicionales que se adjuntan
7 11 13 N (G1) Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premio en metálico - Importe total (300)
8 24 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premio en especie - Valoración (301)
9 37 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premio en especie - Ingresos a cuenta (302)
10 50 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premio en especie - Ingresos a cuenta repercutidos (303)
11 63 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premios en especie - Importe computable (304)
12 76 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Premios juegos, concursos, rifas - Premios exentos (305)
13 89 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Subvenciones/ayudas adquisión/rehabilitación vivienda habitual (310)
14 102 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Ganancias patrimoniales vecinos, aprovechamientos forestales (311)
15 115 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe ganancias (312)
16 128 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe pérdidas (313)
17 141 13 N Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Renta básica emancipación (314)
18 154 1 Tit C (G2) Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (320)
1199 115555 99 AAnn CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn -- IInnsstt. iinnvv. ccoolleeccttiivvaa -- SSoocciieeddaadd//FFoonnddoo 11 -- NN.II.FF. ((332211))
20 164 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados netos positivos - Ganancias netas (322)
21 177 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados netos negativos - Pérdidas netas (323)
22 190 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (320)
23 191 9 An C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - N.I.F. (321)
24 200 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados netos positivos - Ganancias netas (322)
25 213 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados netos negativos - Pérdidas netas (323)
26 226 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (320)
27 227 9 An C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (321)
28 236 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados netos positivos - Ganancias netas (322)
29 249 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados netos negativos - Pérdidas netas (323)
30 262 13 N Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Totales - Total ganancias netas (329)
31 275 13 N Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Totales - Total pérdidas netas (330)
32 288 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
33 291 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Contribuyente "0" a "9" (340)
34 292 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Denominación valores (341)
35 312 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Importe global (342)
36 325 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Valor adquisición global (343)
37 338 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe obtenido (344)
38 351 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe computable (345)
Página 29

# Pag. 30

100-09
Nº Posic. Long. Tipo Com Descripción Validación Contenido
39 364 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe obtenido (346)
40 377 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe computable (347)
41 390 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Contribuyente "0" a "9" (340)
42 391 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Denominación valores (341)
43 411 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Importe global (342)
44 424 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Valor adquisición global (343)
45 437 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe obtenido (344)
46 450 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe reducido (345)
47 463 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe obtenido (346)
48 476 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe imputable (347)
49 489 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Contribuyente "0" a "9" (340)
50 490 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Denominación valores (341)
51 510 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Importe global (342)
52 523 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Valor adquisición global (343)
53 536 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe obtenido (344)
54 549 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe reducido (345)
55 562 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe obtenido (346)
56 575 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe imputable (347)
57 588 13 N Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Totales - Ganancias. Importe reducido (349)
58 601 13 N Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Totales - Pérdidas. Importe imputable (350)
59 614 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
60 617 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (360)
61 618 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (361)
6622 661199 11 NNuumm CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn -- OOttrrooss eelleemmeennttooss -- EElleemmeennttoo 11 -- IInnmmuueebblleess. SSiittuuaacciióónn. CCllaavvee ""00"" aa ""44"" ((336622))
63 620 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Ref. catastral (363)
64 640 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Fecha transmisión (364)
65 648 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Fecha adquisición (365)
66 656 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Valor transmisión (366)
67 669 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Valor adquisición (367)
68 682 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (368)
69 695 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (369)
70 708 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (370)
71 721 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Parte ganancia susceptible reducción (371)
72 734 4 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Años permanencia hasta 31-12-94 (372)
73 738 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Reducción aplicable (373)
74 751 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida (374)
75 764 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta reinversión viv. habitual (375)
76 777 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida no exenta (376)
77 790 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida no exenta imputable (377)
78 803 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Reducción (licencia autotaxis) (378)
79 816 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia reducida (379)
80 829 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia reducida imputable (380)
81 842 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (381)
Página 30

# Pag. 31

100-09
Nº Posic. Long. Tipo Com Descripción Validación Contenido
82 843 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (360)
83 844 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (361)
84 845 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Clave "0" a "4" (362)
85 846 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Ref. catastral (363)
86 866 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Fecha transmisión (364)
87 874 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Fecha adquisición (365)
88 882 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Valor transmisión (366)
89 895 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Valor adquisición (367)
90 908 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (368)
91 921 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable (369)
92 934 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida (370)
93 947 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Parte ganancia susceptible reducción (371)
94 960 4 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Años permanencia hasta 31-12-94 (372)
95 964 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Reducción aplicable (373)
96 977 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida (374)
97 990 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia exenta reinversión viv. habitual (375)
98 1003 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida no exenta (376)
99 1016 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida no exenta imputable (377)
100 1029 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Reducción (licencia autotaxis) (378)
101 1042 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia reducida (379)
102 1055 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia reducida imputable (380)
103 1068 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (381)
104 1069 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - Total pérdida imputable (383)
110055 11008822 1133 NN GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn -- OOttrrooss eelleemmeennttooss -- TToottaalleess -- NNoo aaffeeccttooss -- TToottaall ggaannaanncciiaa rreedduucciiddaa nnoo eexxeennttaa iimmppuuttaabbllee ((338844))
106 1095 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - Afectos - Total ganancia reducida imputable (385)
107 1108 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
108 1111 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10009>
109 1120 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1121
Página 31

# Pag. 32

100-10
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "10"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº hojas adicionales que se adjuntan
7 11 1 Tit C (G2) Ganancias/pérdidas patrim. deriv. transmisión (continuación) - Imputación 2009 ejercicios anteriores - Ganancia 1 - Contribuyente "0" a "9" (390)
8 12 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Ganancia 1 - Importe ganancia (391)
9 25 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Ganancia 2 - Contribuyente "0" a "9" (390)
10 26 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Ganancia 2 - Importe ganancia (391)
11 39 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Ganancia 3 - Contribuyente "0" a "9" (390)
12 40 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Ganancia 3 - Importe ganancia (391)
13 53 13 N Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Total ganancias (395)
14 66 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Pérdida 1 - Contribuyente "0" a "9" (400)
15 67 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Pérdida 1 - Importe pérdida (401)
16 80 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Pérdida 2 - Contribuyente "0" a "9" (400)
17 81 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Pérdida 2 - Importe pérdida (401)
18 94 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Pérdida 3 - Contribuyente "0" a "9" (400)
19 95 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 ejercicios anteriores - Pérdida 3 - Importe pérdida (401)
2200 110088 1133 NN GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn - IImmppuuttaacciióónn 22001111 eejjeerrcciicciiooss aanntteerriioorreess - TToottaall ppéérrddiiddaass ((440055))
21 121 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 1 - Contribuyente "0" a "9" (410)
22 122 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 1 - Importe ganancia (411)
23 135 1 An C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 1 - Método integración. Clave (Blanco,"1","2" o "3") (412)
24 136 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 2 - Contribuyente "0" a "9" (410)
25 137 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 2 - Importe ganancia (411)
26 150 1 An C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 2 - Método integración. Clave (Blanco,"1","2" o "3") (412)
27 151 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 3 - Contribuyente "0" a "9" (410)
28 152 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 3 - Importe ganancia (411)
29 165 1 An C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Ganancia 3 - Método integración. Clave (Blanco,"1","2" o "3") (412)
30 166 13 N Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2011 diferimiento por reinversión - Total ganancia (415)
31 179 13 N (G3) Exención por reinversión ganancia patrimonial 2011 transmisión vivienda habitual - Importe transmisión susceptible reinversión (420)
32 192 13 N Exención por reinversión ganancia patrimonial 2011 transmisión vivienda habitual - Ganancia patrimonial consecuencia transmisión (421)
33 205 13 N Exención por reinversión ganancia patrimonial 2011 transmisión vivienda habitual - Importe reinvertido hasta 31-12-2011 adquisición nueva vivienda (422)
34 218 13 N Exención por reinversión ganancia patrimonial 2011 transmisión vivienda habitual - Importe se compromete reinvertir 2 años siguientes (423)
35 231 13 N Exención por reinversión ganancia patrimonial 2011 transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (424)
36 244 1 Tit (G4) Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (430)
37 245 2 Num Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones1 (431)
38 247 1 Tit Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente2 "0" a "9" (432)
39 248 2 Num Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones2 (433)
40 250 13 N (G5) Integración/compensación ganancias/pérdidas patrimoniales imputables 2011 - A integrar en base imponible general - Suma ganancias (440)
41 263 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2011 - A integrar en base imponible general - Suma pérdidas (441)
Página 32

# Pag. 33

100-10
Nº Posic. Long. Tipo Com Descripción Validación Contenido
42 276 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2011 - A integrar en base imponible general - Saldo neto - Diferencia positiva (450)
43 289 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2011 - A integrar en base imponible general - Saldo neto - Diferencia negativa (442)
44 302 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2011 - A integrar en base imponible ahorro - Suma ganancias (443)
45 315 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2011 - A integrar en base imponible ahorro - Suma pérdidas (444)
46 328 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2011 - A integrar en base imponible ahorro - Saldo neto - Diferencia positiva (457)
47 341 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2011 - A integrar en base imponible ahorro - Saldo neto - Diferencia negativa (445)
48 354 13 N (H) Base imponible general y base imponible ahorro - Base imponible general - Saldo neto positivo ganancias/pérdidas 2011 a integrar (450)
49 367 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldos netos negativos ganancias/pérdidas 2007-2010 a integrar (451)
50 380 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldo neto rendimientos a integrar en base imponible general/imputaciones renta (452)
51 393 13 N Base imponible general y base imponible ahorro - Base imponible general - Compensaciones - Resto saldos netos negativos 2007-2010 a integrar (453)
52 406 13 N Base imponible general y base imponible ahorro - Base imponible general - Compensaciones - Saldo neto negativo ganancias/pérdidas imputables 2011 a integrar (454)
53 419 13 N Base imponible general y base imponible ahorro - Base imponible general - Total (455)
54 432 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldo neto negativo ganancias/pérdidas 2011: importe pendiente de compensar (456)
55 445 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Saldo neto positivo ganancias/pérdidas 2011 (457)
56 458 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Compensación - Saldos netos negativos ganancias/pérdidas 2007-2010 a integrar (458)
57 471 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Saldo rendimientos capital mobiliario. Saldo negativo (459)
58 484 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Saldo rendimientos capital mobiliario. Saldo positivo (460)
59 497 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Compensación. Saldo neto negativo capital mobiliario (461)
60 510 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Base imponible ahorro (465)
61 523 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10010>
62 532 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 533
Página 33

# Pag. 34

100-11
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "11"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 13 N (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidad familiar tributación conjunta (470)
7 23 1 Tit Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 1 "0" a "9" (480)
8 24 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes 2006-2010 F401 (481)
9 37 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones 2011 (482)
10 50 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción 1 (483)
11 63 1 Tit Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 2 "0" a "9" (480)
12 64 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes 2006-2010 (481)
13 77 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones 2011 (482)
14 90 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción 2 (483)
15 103 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total derecho reducción (500)
16 116 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones cónyuge del contribuyente - Total derecho reducción (505)
17 129 1 Num Nº hojas adicionales que se adjuntan
18 130 1 Tit C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Contribuyente 1 "0" a "9" (510)
19 131 9 An C Reducciones base imponible - Aportaciones a favor personas con discapacidad - NIF persona con discapacidad 1 (511)
20 140 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Excesos pendientes reducir 2006-2010 1 (512)
21 153 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2011 propia persona discapacidad 1 (513)
2222 116666 1133 NN CC RReedduucccciioonneess bbaassee iimmppoonniibbllee -- AAppoorrttaacciioonneess aa ffaavvoorr ppeerrssoonnaass ccoonn ddiissccaappaacciiddaadd -- AAppoorrttaacciioonneess 22001111 ppaarriieenntteess oo ttuuttoorreess 11 ((551144))
23 179 1 Tit C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Contribuyente 2 "0" a "9" (510)
24 180 9 An C Reducciones base imponible - Aportaciones a favor personas con discapacidad - NIF persona con discapacidad 2 (511)
25 189 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Excesos pendientes reducir 2006-2010 (512)
26 202 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2011 propia persona discapacidad 2 (513)
27 215 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2011 parientes o tutores 2 (514)
28 228 13 N Reducciones base imponible - Aportaciones a favor personas con discapacidad - Total con derecho a reducción (530)
29 241 1 Tit Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (540)
30 242 9 An Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 1 (541)
31 251 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 2007-2010 1 (542)
32 264 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2011 1 (543)
33 277 1 Tit Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (540)
34 278 9 An Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 2 (541)
35 287 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 2007-2010 2 (542)
36 300 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2011 2 (543)
37 313 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Total con derecho a reducción (560)
38 326 1 Tit Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Contribuyente 1 "0" a "9" (570)
39 327 9 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 1 (571)
40 336 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 1 (572)
41 349 1 Tit Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Contribuyente 2 "0" a "9" (570)
42 350 9 An Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 2 (571)
43 359 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 2 (572)
44 372 13 N Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Total derecho reducción (585)
45 385 1 Tit Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 1 "0" a "9" (590)
Página 34

# Pag. 35

100-11
Nº Posic. Long. Tipo Com Descripción Validación Contenido
46 386 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Excesos pendientes reducir 2007, 2008, 2009 y 2010 (591)
47 399 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones 2011 (592)
48 412 1 Tit Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 2 "0" a "9" (590)
49 413 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Excesos pendientes reducir ejercicio 2007, 2008, 2009 y 2010 2 (591)
50 426 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones 2011 2 (592)
51 439 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Total con derecho a reducción (600)
52 452 13 N (J) Base liquidable general/base liquidable ahorro - Determinación base general - Base imponible general (455)
53 465 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Tributación conjunta (610)
54 478 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social (régimen general) (611)
55 491 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social cónyuge (612)
56 504 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones previsión social personas discapacidad (613)
57 517 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones patrimonios protegidos personas discapacidad (614)
58 530 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Pensiones compensatorias/anualidades alimentos (615)
59 543 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Cuotas afiliación y demás aportaciones (616)
60 556 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Reducciones base imponible general - Aportaciones mutualidades prev. soc. deportistas profesionales(617)
61 569 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Base liquidable general (618)
62 582 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Compensación (bases liquidables generales negativas) (619)
63 595 13 N Base liquidable general/base liquidable ahorro - Determinación base general - Base liquidable general sometida a gravamen (620)
64 608 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10011>
65 617 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 618
Página 35

# Pag. 36

100-12
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "12"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 13 N Base liquidable general/base liquidable ahorro - Determinación base ahorro - Base imponible ahorro (465)
7 23 13 N Base liquidable general/base liquidable ahorro - Determinación base ahorro - Remanente reducciones no aplicadas - Reducción tributación conjunta (621)
8 36 13 N Base liquidable general/base liquidable ahorro - Determinación base ahorro - Remanente reducciones no aplicadas - Reducción pensiones comp./anualidades alimentos (622)
9 49 13 N Base liquidable general/base liquidable ahorro - Determinación base ahorro - Cuotas de afiliación y demás aportaciones (623)
10 62 13 N Base liquidable general/base liquidable ahorro - Determinación base ahorro - Base liquidable del ahorro (630)
11 75 1 Tit (K) Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 1 "0" a "9" (640)
12 76 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2010 no aplicadas 1 (641)
13 89 1 Tit Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 2 "0" a "9" (640)
14 90 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2010 no aplicadas 2 (641)
15 103 1 Tit Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 1 "0" a "9" (650)
16 104 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2010 no aplicadas 1 (651)
17 117 1 Tit Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 2 "0" a "9" (650)
18 118 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2010 no aplicadas 2 (651)
19 131 1 Tit Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 1 "0" a "9" (650)
20 132 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2010 no aplicadas 3 (651)
21 145 1 Tit Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 2 "0" a "9" (650)
22 146 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2010 no aplicadas 4 (651)
2233 115599 11 TTiitt RRedducciiones bbase iimponiibblle no aplliicaddas 22001100 - EExceso aporttaciiones pattriimoniios prottegiiddos personas ddiiscapaciiddadd - CConttriibbuyentte 11 ""00"" a ""99"" ((666600))
24 160 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2010 no aplicadas 1 (661)
25 173 1 Tit Reducciones base imponible no aplicadas 2010 - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (660)
26 174 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2010 no aplicadas 2 (661)
27 187 1 Tit Reducciones base imponible no aplicadas 2010 - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 1 "0" a "9" (670)
28 188 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2010 no aplicadas 1 (671)
29 201 1 Tit Reducciones base imponible no aplicadas 2010 - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 2 "0" a "9" (670)
30 202 13 N Reducciones base imponible no aplicadas 2010 - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2010 no aplicadas 2 (671)
31 215 13 N (L) Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe (675)
32 228 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe cálculo gravamen autonómico (635)
33 241 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe (676)
34 254 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe cálculo gravamen autonómico (636)
35 267 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe (677)
36 280 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe cálculo gravamen autonómico (637)
37 293 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe (678)
38 306 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe cálculo gravamen autonómico (638)
39 319 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo personal y familiar (679)
40 332 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe total cálculo gravamen autonómico (685)
41 345 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen estatal (680)
42 358 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen estatal (681)
43 371 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen autonómico (683)
44 384 13 N Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen autonómico (684)
45 397 13 N (M) Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable ahorro (686)
46 410 13 N Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable general (687)
Página 36

# Pag. 37

100-12
Nº Posic. Long. Tipo Descripción Validación Contenido
47 423 13 N Datos adicionales - Anualidades para alimentos a favor de los hijos. Importe (688)
48 436 13 N Datos adicionales - Parte de la base liquidable general que corresponda a indemnizaciones de seguros o ayudas (682)
49 449 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10012>
50 458 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 459
Página 37

# Pag. 38

100-13
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "13"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escalas Impuesto importe casilla 620 - Parte estatal (689)
7 23 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escalas Impuesto importe casilla 620 - Parte autonómica (690)
8 36 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general Impuesto importe casilla 680 - Parte estatal (691)
9 49 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala Impuesto importe casilla 683 - Parte autonómica (692)
10 62 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte estatal (693)
11 75 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte autonómica (694)
12 88 4 Num Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte estatal (TME)
13 92 4 Num Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte autonómica (TMA)
14 96 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Base liquidable ahorro sometida gravamen - Parte estatal (695)
15 109 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Base liquidable ahorro sometida gravamen - Parte autonómica (771)
16 122 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte estatal (696)
17 135 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte autonómica (697)
18 148 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Parte estatal (698)
19 161 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Parte autonómica (699)
20 174 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte estatal (700)
21 187 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte autonómica (701)
22 200 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte estatal (702)
23 213 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte autonómica (703)
24 226 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos - Parte estatal (704)
25 239 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos - Parte autonómica (705)
26 252 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Incentivos inversión empresarial - Parte estatal (706)
27 265 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Incentivos inversión empresarial - Parte autonómica (707)
28 278 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Dotaciones Reserva Canarias - Parte estatal (708)
29 291 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Dotaciones Reserva Canarias - Parte autonómica (709)
30 304 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rendimientos venta bienes Canarias - Parte estatal (710)
31 317 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rendimientos venta bienes Canarias - Parte autonómica (711)
32 330 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte estatal (712)
33 343 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte autonómica (713)
34 356 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Cantidades depositadas cuentas ahorro-empresa - Parte estatal (714)
35 369 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Cantidades depositadas cuentas ahorro-empresa - Parte autonómica (715)
36 382 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte estatal (716)
37 395 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte autonómica (772)
38 408 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Obras de mejora en la vivienda habitual - Parte estatal (773)
39 421 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Obras de mejora en la vivienda (733)
40 434 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - (717)
41 447 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota líquida estatal - Parte estatal (720)
42 460 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota líquida autonómica - Parte autonómica (721)
43 473 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - PE (722)
44 486 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - PE (723)
45 499 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2010 - Importe - PE (724)
46 512 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2010 - Intereses demora - PE (725)
Página 38

# Pag. 39

100-13
Nº Posic. Long. Tipo Descripción Validación Contenido
47 525 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2010 - Importe - PA (726)
48 538 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2010 - Intereses demora - PA (727)
49 551 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2010 - Importe - PA (728)
50 564 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2010 - Intereses demora - PA (729)
51 577 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Cuotas líquidas incrementadas - Parte estatal (730)
52 590 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Cuotas líquidas incrementadas - Parte autonómica (731)
53 603 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota líquida incrementada total (732)
54 616 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Rentas obtenidas y gravadas en el extranjero (734)
55 629 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducción obtención rendimientos trabajo o act. económicas (735)
56 642 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Aplicación régimen transparencia fiscal internacional (736)
57 655 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Aplicación régimen imputación rentas cesión derechos imagen (737)
58 668 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Compensaciones fiscales - Deducción por adquisición vivienda habitual adquirida antes 20-01-06 (738)
59 681 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Compensaciones fiscales - Percepción rdtos.capital mobiliario > 2 años (739)
60 694 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Retenciones deducibles rendimientos bonificados - Importe retenciones no practicadas (740)
61 707 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota resultante autoliquidación (741)
62 720 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10013>
63 729 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 730
Página 39

# Pag. 40

100-14
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "14"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Rendimientos del trabajo (742)
7 23 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Rendimientos del capital mobiliario (743)
8 36 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Arrendamientos de inmuebles urbanos (744)
9 49 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Rendimientos de actividades económicas (745)
10 62 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Atribuidos por entidades en régimen de atribución de rentas (746)
11 75 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Imputados por agrupaciones de interés económico y UTE's (747)
12 88 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Ingresos a cuenta art. 92.8 Ley del Impuesto (748)
13 101 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Ganancias patrimoniales, incluidos premios (749)
14 114 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Pagos fraccionados (actividades económicas) (750)
15 127 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Cuotas del Impuesto sobre la Renta de no Residentes (751)
16 140 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Retenciones art. 11 Directiva 2003/48/CE (752)
17 153 13 N Cálculo impuesto y resultado declaración - Retenciones y demás pagos a cuenta - Total pagos a cuenta (754)
18 166 13 N Cálculo impuesto y resultado declaración - Cuota diferencial y resultado declaración - Cuota diferencial (755)
19 179 13 N Cálculo impuesto y resultado declaración - Cuota diferencial y resultado declaración - Deducción por maternidad - Importe de la deducción (756)
20 192 13 N Cálculo impuesto y resultado declaración - Cuota diferencial y resultado declaración - Importe del abono anticipado correspondiente a 2009 (757)
21 205 13 N Cálculo impuesto y resultado declaración - Cuota diferencial y resultado declaración - Resultado de la declaración (760)
22 218 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - Cuota líquida autonómica incrementada (775)
23 231 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% deducciones doble imposición (776)
24 244 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% compensación fiscal adquisición vivienda habitual (777
25 257 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% compensación fiscal percepción rendimientos capital mobiliario (778)
26 270 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - Importe IRPF que corresponde a la Comunidad Autónoma de residencia [779]
27 283 13 N (P) Regularización mediante declaración complementaria (ejercicio 2011) - Resultados a ingresar anteriores autoliquidaciones o liquidaciones administrativas ejercicio 2010 (761)
28 296 13 N Regularización mediante declaración complementaria (ejercicio 2011) - Devoluciones acordadas por la Administración, consecuencia anteriores autoliquidaciones ejercicio 2010 (762)
29 309 13 N Regularización mediante declaración complementaria (ejercicio 2011) - Resultado de la declaración complementaria (765)
30 322 13 N (Q) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (768)
31 335 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (770)
32 348 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (769)
33 361 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (770)
34 374 4 Num Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Código Cuenta Cliente - Entidad
35 378 4 Num Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Código Cuenta Cliente - Oficina
36 382 2 Num Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Código Cuenta Cliente - DC
37 384 10 Num Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Código Cuenta Cliente - Número de Cuenta
38 394 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10014>
39 403 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 404
Página 40

# Pag. 41

Anexo A.1
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "15"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Inversión con derecho a deducción (A)
7 23 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte estatal (780)
8 36 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte autonómica (781)
9 49 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Inversión con derecho a deducción (B)
10 62 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte estatal (782)
11 75 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte autonómica (783)
12 88 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Inversión con derecho a deducción (C)
13 101 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte estatal (608)
14 114 13 N Importe total de la deducción por inversión vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte autonómica (609)
15 127 13 N Importe total de la deducción por inversión vivienda habitual - Cantidades depositadas en cuenta vivienda primera adquisición/rehabilitación - Importe con derecho a deducción (D)
16 140 13 N Importe total de la deducción por inversión vivienda habitual - Cantidades depositadas en cuenta vivienda primera adquisición/rehabilitación - Importe deducción - Parte estatal (784)
17 153 13 N Importe total de la deducción por inversión vivienda habitual - Cantidades depositadas en cuenta vivienda primera adquisición/rehabilitación - Importe deducción - Parte autonómica (785)
18 166 1 Tit Importe total de la deducción por inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 1 - Titular de la cuenta "0" a "9"
19 167 8 Num Importe total de la deducción por inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 1 - Fecha apertura "DDMMAAAA"
Importe total de la deducción por inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 1 - Entidad (4), Oficina (4), DC (2) y Número (10) alineada a la izquierda en caso de cuenta nacional,
20 175 62 An rellenando con blancos por la derecha
21 237 1 Tit Importe total de la deducción por inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 2 - Titular de la cuenta "0" a "9"
22 238 8 Num Importe total de la deducción por inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 2 - Fecha apertura "DDMMAAAA"
Importe total de la deducción por inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 2 - Entidad (4), Oficina (4), DC (2) y Número (10) alineada a la izquierda en caso de cuenta nacional,
23 246 62 An rellenando con blancos por la derecha
24 308 1 Num Importe total de la deducción por inversión vivienda habitual - Cuenta vivienda no se encuentra abierta en cualquier oficina sita en territorio español "1" o "0"
25 309 13 N Importe total de la deducción por inversión vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Cantidades satisfechas con derecho a deducción (E)
26 322 13 N Importe total de la deducción por inversión vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte estatal (786)
27 335 13 N Importe total de la deducción por inversión vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte autonómica (787)
28 348 13 N Importe total de la deducción por inversión vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte estatal (700)
29 361 13 N Importe total de la deducción por inversión vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte autonómica (701)
30 374 13 N Importe total de la deducción por inversión vivienda habitual - Datos adicionales - Importe de los pagos realizados en el ejercicio al promotor o constructor (788)
31 387 9 An Importe total de la deducción por inversión vivienda habitual - Datos adicionales - NIF del promotor o constructor (789)
32 396 8 An Importe total de la deducción por inversión vivienda habitual - Datos adicionales - En caso de deducción - Fecha adquisición vivienda (DDMMAAAA) (790)
33 404 20 An Importe total de la deducción por inversión vivienda habitual - Datos adicionales - En caso de deducción - Número de identificación del préstamo hipotecario (791)
34 424 5 Num Importe total de la deducción por inversión vivienda habitual - Datos adicionales - En caso de deducción - Porcentaje del préstamo destinado a adquisición (792)
35 429 9 An Deducción por alquiler de la vivienda habitual - NIF del arrendador 1 (793)
36 438 13 N Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 1 (582)
37 451 9 An Deducción por alquiler de la vivienda habitual - NIF del arrendador 2 (583)
38 460 13 N Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 2 (584)
39 473 13 N Deducción por alquiler de la vivienda habitual - Cantidades satisfechas con derecho a deducción (F)
Página 41

# Pag. 42

Anexo A.1
Nº Posic. Long. Tipo Descripción Validación Contenido
40 486 13 N Deducción por alquiler de la vivienda habitual - Importe deducción (774)
41 499 13 N Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte estatal (716)
42 512 13 N Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte autonómica (772)
43 525 13 N Deducciones por donativos - Donativos límite 15% base liquidable - Importe con derecho a deducción (G)
44 538 13 N Deducciones por donativos - Donativos límite 15% base liquidable - Importe de la deducción (795)
45 551 13 N Deducciones por donativos - Donativos límite 10% base liquidable - Importe con derecho a deducción (H)
46 564 13 N Deducciones por donativos - Donativos límite 10% base liquidable - Importe de la deducción (796)
47 577 13 N Deducciones por donativos - Deducciones por donativos - Parte estatal (704)
48 590 13 N Deducciones por donativos - Deducciones por donativos - Parte autonómica (705)
49 603 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe con derecho a deducción (I)
50 616 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe de la deducción (797)
51 629 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte estatal (702)
52 642 13 N Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte autonómica (703)
53 655 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Importe total de la deducción (798)
54 668 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte estatal (712)
55 681 13 N Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte autonómica (713)
56 694 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10015>
57 703 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 704
Página 42

# Pag. 43

Anexo A.2
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "16"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Cantidades depositadas (J)
7 23 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Importe total de la deducción (799)
8 36 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Deducción - Parte estatal (714)
9 49 13 N Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Deducción - Parte autonómica (715)
10 62 1 Tit Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Titular
11 63 8 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Fecha de apertura "DDMMAAAA"
12 71 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Entidad
13 75 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Oficina
14 79 2 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - DC
15 81 10 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 1 - Número de cuenta
16 91 1 Tit Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Titular
17 92 8 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Fecha de apertura
18 100 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Entidad
19 104 4 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - Oficina
20 108 2 Num Otras deducciones generales de la cuota íntegra - Deducción por cantidades depositadas en cuenta ahorro-empresa - Identificación cuentas - Cuenta 2 - DC
21 110 10 Num Otras deducciones ggenerales de la cuota ínteggra - Deducción ppor cantidades deppositadas en cuenta ahorro-emppresa - Identificación cuentas - Cuenta 2 - Número de cuenta
22 120 2 Num Indique el número total de viviendas por las que se aplica la deducción (473)
23 122 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 1 - Cantidades satisfechas en 2011 desde el 7 de mayo (436)
24 135 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 1 - Base de la deducción (K)
25 148 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 1 - Importe de la deducción (437)
26 161 5 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 1 - Porcentaje que tiene el titular de la deducción en la titularidad de la vivienda (438)
27 166 5 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 1 - Porcentaje total en la propiedad de la vivienda de todos los titulares con derecho a aplicar la deducción (439)
28 171 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 1 - Exceso de las cantidades satisfechas en el ejercicio 2011 desde el 7 de mayo sobre la base máxima de deducción (446)
29 184 9 An Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 1 - NIF de la persona/entidad que ha efectuado las obras (447)
30 193 20 An Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 1 - Referencia catastral (448)
31 213 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 2 - Cantidades satisfechas en 2011 desde el 7 de mayo (449)
32 226 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 2 - Base de la deducción (L)
33 239 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 2 - Importe de la deducción (462)
34 252 5 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 2 - Porcentaje que tiene el titular de la deducción en la titularidad de la vivienda (463)
35 257 5 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 2 - Porcentaje total en la propiedad de la vivienda de todos los titulares con derecho a aplicar la deducción (464)
36 262 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 2 - Exceso de las cantidades satisfechas en el ejercicio 2011 desde el 7 de mayo sobre la base máxima de deducción (466)
37 275 9 An Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 2 - NIF de la persona/entidad que ha efectuado las obras (467)
38 284 20 An Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 2 - Referencia catastral (468)
39 304 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 3 y siguientes - Cantidades satisfechas en 2011 desde el 7 de mayo (469)
40 317 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 3 y siguientes - Base de la deducción (M)
41 330 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 3 y siguientes - Importe de la deducción (471)
42 343 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Vivienda 3 y siguientes - Exceso cantidades satisfechas ejercicio 2011 desde el 7 de mayo sobre la base máxima de deducción (472)

# Pag. 44

Anexo A.2
Nº Posic. Long. Tipo Descripción Validación Contenido
43 356 13 Num Deducción por obras de mejora en vivienda (desde 07/05/2011) - Importe total de la deducción (733)
44 369 13 Num Deducción por obras de mejora en la vivienda habitual - Cantidades satisfechas ejercicio 2010 pendientes de deducción por exceso base máxima que se aplican en esta declaración (425)
45 382 13 Num Deducción por obras de mejora en la vivienda habitual - En 2010 - Base de la deducción (N)
46 395 13 Num Deducción por obras de mejora en la vivienda habitual - En 2010 - Importe de la deducción (426)
47 408 13 Num Deducción por obras de mejora en la vivienda habitual - Cantidades satisfechas en 2011 antes del 7 de mayo (427)
48 421 13 Num Deducción por obras de mejora en la vivienda habitual - En 2011 antes del 7 de mayo - - Base de la deducción (O)
49 434 13 Num Deducción por obras de mejora en la vivienda habitual - En 2011 antes del 7 de mayo - - Importe de la deducción (428)
50 447 5 Num Deducción por obras de mejora en la vivienda habitual - Porcentaje que tiene el titular de la deducción en la propiedad de la vivienda (429)
51 452 5 Num Deducción por obras de mejora en la vivienda habitual - Porcentaje total en la propiedad de la vivienda de todos los contribuyentes con derecho a aplicar la deducción (434)
52 457 13 Num Deducción por obras de mejora en la vivienda habitual - Importe total de la deducción (773)
53 470 13 Num Deducción por obras de mejora en la vivienda habitual - Exceso de las cantidades satisfechas en el ejercicio 2011 antes del 7 de mayo sobre la base máxima de deducción (435)
54 483 9 An Deducción por obras de mejora en la vivienda habitual - NIF de la persona/entidad que ha efectuado las obras (531)
55 492 20 An Deducción por obras de mejora en la vivienda habitual - Referencia catastral (532)
56 512 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10016>
57 521 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 522

# Pag. 45

Anexo A.3
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "17"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Saldo anterior
7 23 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Aplicado declaración (945)
8 36 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Pendiente aplicación
9 49 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interes público - Saldo anterior
10 62 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interes público - Aplicado declaración (946)
11 75 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - R. e. acontecimientos interes público - Pendiente aplicación
12 88 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Actv. i. d. i. tecnológica - Deducción 2011
13 101 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Actv. i. d. i. tecnológica - Aplicado declaración (947)
14 114 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Actv. i. d. i. tecnológica - Pendiente aplicación
15 127 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Inversiones/gastos art.º 38.1, 2 y 3 - Deducción 2011
16 140 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Inversiones/gastos art.º 38.1, 2 y 3 - Aplicado declaración (950)
17 153 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Inversiones/gastos art.º 38.1, 2 y 3 - Pendiente aplicación
18 166 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Inversiones medioambientales - Deducción 2011
1199 117799 1133 NN DDeedduucccciioonneess iinncceennttiivvooss//eessttíímmuullooss iinnvv. eemmpprreess. -- RRéégg. ggrraall. LLIISS//eessppeecciiaalleess aaccoonntteecciimmiieennttooss iinntteerrééss ppúúbblliiccoo -- 22001111. RR. gg. LLIISS -- IInnvveerrssiioonneess mmeeddiiooaammbbiieennttaalleess -- AApplliiccaaddoo ddeeccllaarraacciióónn ((995511))
20 192 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Inversiones medioambientales - Pendiente aplicación
21 205 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Util. nuevas tecnologías empleados - Deducción 2011
22 218 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Util. nuevas tecnologías empleados - Aplicado declaración (952)
23 231 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Util. nuevas tecnologías empleados - Pendiente aplicación
24 244 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Creación empleo trabajadores minusválidos - Deducción 2011
25 257 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Creación empleo trabajadores minusválidos - Aplicado declaración (953)
26 270 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. g. LIS - Creación empleo trabajadores minusválidos - Pendiente aplicación
27 283 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Alicante 2011" - Deducción 2011
28 296 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Alicante 2011" - Aplicado declaración (955)
29 309 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Alicante 2011" - Pendiente aplicación
30 322 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Barcelona World Race" - Deducción 2011
31 335 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Barcelona World Race" - Aplicado declaración (956)
32 348 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Barcelona World Race" - Pendiente aplicación
33 361 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Guadalquivir Rio Historia" - Deducciones 2011
34 374 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Guadalquivir Rio Historia" - Aplicado declaración (958)
35 387 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Guadalquivir Rio Historia" - Pendiente aplicación
36 400 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Constitución 1812" - Deducciones 2011
37 413 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Constitución 1812" - Aplicado declaración (959)
38 426 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Constitución 1812" - Pendiente aplicación

# Pag. 46

Anexo A.3
Nº Posic. Long. Tipo Descripción Validación Contenido
39 439 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Londres 2012" - Deducción 2011
40 452 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Londres 2012" - Aplicado declaración (960)
41 465 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Londres 2012" - Pendiente aplicación
42 478 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Alzheimer Int. 2011" - Deducción 2011
43 491 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Alzheimer Int. 2011" - Aplicado declaración (964)
44 504 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Alzheimer Int. 2011" - Pendiente aplicación
45 517 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "JMJ 2011" - Deducción 2011
46 530 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "JMJ 2011" - Aplicado declaración (535)
47 543 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "JMJ 2011" - Pendiente aplicación
48 556 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Milenio Reino Granada" - Deducción 2011
49 569 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Milenio Reino Granada" - Aplicado declaración (536)
50 582 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Milenio Reino Granada" - Pendiente aplicación
51 595 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Solar Dec. E. 2010/2012" - Deducciones 2011
52 608 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Solar Dec. E. 2010/2012" - Aplicado declaración (537)
53 621 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Solar Dec. E. 2010/2012" - Pendiente aplicación
54 634 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Google Lunar X Prize" - Deducción 2011
55 647 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Google Lunar X Prize" - Aplicado declaración (538)
56 660 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Google Lunar X Prize" - Pendiente aplicación
57 673 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "2011: Año Orellana" - Deducción 2011
58 686 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "2011: Año Orellana" - Aplicado declaración (948)
59 699 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "2011: Año Orellana" - Pendiente aplicación
60 712 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Mundo Basket 2014" - Deducciones 2011
61 725 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Mundo Basket 2014" - Aplicado declaración (954)
6622 773388 1133 NN DDeedduucccciioonneess iinncceennttiivvooss//eessttíímmuullooss iinnvv. eemmpprreess. -- RRéégg. ggrraall. LLIISS//eessppeecciiaalleess aaccoonntteecciimmiieennttooss iinntteerrééss ppúúbblliiccoo -- 22001111. RR. aaccoonntteecciimmiieennttooss ee. ii. pp. -- ""MMuunnddoo BBaasskkeett 22001144"" -- PPeennddiieennttee aapplliiccaacciióónn
63 751 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "C. M. Balonmano 2013" - Deducciones 2011
64 764 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "C. M. Balonmano 2013" - Aplicado declaración (961)
65 777 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "C. M. Balonmano 2013" - Pendiente aplicación
66 790 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Tricentenario BNE" - Deducción 2011
67 803 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Tricentenario BNE" - Aplicado declaracion (962)
68 816 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "Tricentenario BNE" - Pendiente aplicación
69 829 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "IV Centenario f. El Greco" - Deducción 2011
70 842 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "IV Centenario f. El Greco" - Aplicado declaración (963)
71 855 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "IV Centenario f. El Greco" - Pendiente aplicación
72 868 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "VIII C. Catedral Santiago" - Deducción 2011
73 881 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "VIII C. Catedral Santiago" - Aplicado declaración (965)
74 894 13 N Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - 2011. R. acontecimientos e. i. p. - "VIII C. Catedral Santiago" - Pendiente aplicación
75 907 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Saldo anterior
76 920 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Aplicado declaración (968)
77 933 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Pendiente aplicación
78 946 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Saldo anterior
79 959 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Aplicado declaración (969)
80 972 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Pendiente aplicación
81 985 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Deducción 2011

# Pag. 47

Anexo A.3
Nº Posic. Long. Tipo Descripción Validación Contenido
82 998 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Aplicado declaración (970)
83 1011 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - L.I.S.: Activ. investigación, desarrollo e innovación tecnológica - Pendiente aplicación
84 1024 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Deducción 2011
85 1037 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Aplicado declaración (973)
86 1050 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones y gastos artº. 38.1, 2 y 3 - Pendiente de aplicación
87 1063 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones medioambientales - Deducción 2011
88 1076 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones medioambientales - Aplicado declaración (974)
89 1089 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones medioambientales - Pendiente aplicación
90 1102 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Util. nuevas tecnologías empleados - Deducción 2011
91 1115 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Util. nuevas tecnologías empleados - Aplicado declaración (975)
92 1128 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Util. nuevas tecnologías empleados - Pendiente aplicación
93 1141 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Creación empleo trabajadores minusválidos - Deducción 2011
94 1154 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Creación empleo trabajadores minusválidos - Aplicado declaración (976)
95 1167 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Creación empleo trabajadores minusválidos - Pendiente aplicación
96 1180 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones en la adquisición de activos fijos - Deducción 2011
97 1193 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones en la adquisición de activos fijos - Aplicado declaración (978)
98 1206 13 N Deducciones incentivos/estímulos inv. empres. - Rég. esp. inv. Canarias - Ejercicio 2011. Modalidades LIS - Inversiones en la adquisición de activos fijos - Pendiente aplicación
99 1219 13 N Deducciones por incentivos y estímulos a la inversión empresarias - Deducciones: importe aplicado - Importe total de las deducciones (979)
100 1232 13 N Deducciones por incentivos y estímulos a la inversión empresarias - Deducciones: importe aplicado - Deducciones - Parte estatal (706)
101 1245 13 N Deducciones por incentivos y estímulos a la inversión empresarias - Deducciones: importe aplicado - Deducciones - Parte autonómica (707)
102 1258 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2007 - Importe dotaciones (984)
103 1271 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2007 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (985)
104 1284 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2007 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (986)
110055 11229977 1133 NN RReesseerrvvaa ppaarraa IInnvveerrssiioonneess eenn CCaannaarriiaass ((LLeeyy 1199//11999944)) -- DDoottaacciioonneess, mmaatteerriiaalliizzaacciioonneess ee iinnvveerrssiioonneess aannttiicciippaaddaass -- 22000088 -- IImmppoorrttee ddoottaacciioonneess ((998888))
106 1310 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2008 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (989)
107 1323 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2008 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (990)
108 1336 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2008 - Pendiente de materializar (991)
109 1349 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2009 - Importe dotaciones (992)
110 1362 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2009 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (993)
111 1375 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2009 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (994)
112 1388 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2009 - Pendiente de materializar (995)
113 1401 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Importe dotaciones (539)
114 1414 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (561)
115 1427 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (562)
116 1440 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2010 - Pendiente de materializar (563)
117 1453 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Importe dotaciones (966)
118 1466 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Inversiones previstas letras A, B y D (1º.) artº. 27.4 (967)
119 1479 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (971)
120 1492 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2011 - Pendiente de materializar (972)
121 1505 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Importe de la deducción 2011
122 1518 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2011 - Inversiones prev. letras A, B y D (1º.) artº. 27.4 (996)
123 1531 13 N Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2011 - Inversiones prev. letras C y D 2º. a 6º.) artº. 27.4 (997)
124 1544 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10017>

# Pag. 48

Anexo A.3
Nº Posic. Long. Tipo Descripción Validación Contenido
125 1553 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1554

# Pag. 49

Anexo B.1
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "18"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Andalucía - Para beneficiarios de ayudas familiares (800)
7 23 13 N Deducciones Autonómicas - Andalucía - Para beneficiarios ayudas viviendas protegidas (801)
8 36 13 N Deducciones Autonómicas - Andalucía - Por inversión vivienda habitual protegida/personas jóvenes (802)
9 49 9 An Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - NIF arrendador (943)
10 58 13 N Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler vivienda habitual - Importe (803)
11 71 13 N Deducciones Autonómicas - Andalucía - Para fomento del autoempleo (804)
12 84 13 N Deducciones Autonómicas - Andalucía - Por inversión en la adquisición de acciones y participaciones (805)
13 97 13 N Deducciones Autonómicas - Andalucía - Por adopción de hijos ámbito internacional (806)
14 110 13 N Deducciones Autonómicas - Andalucía - Para contribuyentes con discapacidad (807)
15 123 13 N Deducciones Autonómicas - Andalucía - Para padre/madre de familia monoparental con ascendientes mayores 75 años (808)
16 136 13 N Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Deducción con carácter general (809)
17 149 11 An Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Cuenta cotización (940)
18 160 13 N Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Importe (810)
1199 117733 1111 AAnn DDeedduucccciioonneess AAuuttoonnóómmiiccaass -- AAnnddaalluuccííaa -- PPoorr aayyuuddaa ddoommééssttiiccaa. CCuueennttaa ccoottiizzaacciióónn ((994411))
20 184 13 N Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Importe (811)
21 197 13 N Deducciones Autonómicas - Andalucía - Total deducciones autonómicas (717)
22 210 13 N Deducciones Autonómicas - Aragón - Por nacimiento o adopción tercer hijo o sucesivos o segundo hijo discapacitado (812)
23 223 13 N Deducciones Autonómicas - Aragón - Por adopción internacional de niños (813)
24 236 13 N Deducciones Autonómicas - Aragón - Por el cuidado de personas dependientes (814)
25 249 13 N Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico (815)
26 262 13 N Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo (816)
27 275 13 N Deducciones Autonómicas - Aragón - Por inversión en acciones de entidades que cotizan en Mercado bursátil (306)
28 288 13 N Deducciones Autonómicas - Aragón - Total deducciones autonómicas (717)
29 301 13 N Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (817)
30 314 13 N Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes discapacitados (818)
31 327 13 N Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes discapacitados (819)
32 340 13 N Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (820)
33 353 9 An Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - NIF arrendador (943)
34 362 13 N Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - Importe (821)
35 375 13 N Deducciones Autonómicas - Asturias - Para fomento de autoempleo mujeres y jóvenes emprendedores (822)
36 388 13 N Deducciones Autonómicas - Asturias - Para fomento de autoempleo (823)
37 401 13 N Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (824)
38 414 13 N Deducciones Autonómicas - Asturias - Por adopción internacional de menores (825)
39 427 13 N Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones (826)
Página 49

# Pag. 50

Anexo B.1
Nº Posic. Long. Tipo Descripción Validación Contenido
40 440 13 N Deducciones Autonómicas - Asturias - Para familias numerosas (827)
41 453 13 N Deducciones Autonómicas - Asturias - Para familias monoparentales (828)
42 466 13 N Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (564)
43 479 13 N Deducciones Autonómicas - Asturias - Por gestión forestal sostenible (307)
44 492 13 N Deducciones Autonómicas - Asturias - Total deducciones autonómicas (717)
45 505 13 N Deducciones Autonómicas - Illes Balears - Por gastos adquisición libros de texto (829)
46 518 13 N Deducciones Autonómicas - Illes Balears - Para contribuyentes edad igual o superior a 65 años (830)
47 531 13 N Deducciones Autonómicas - Illes Balears - Por adquisición/rehabilitación vivienda habitual jóvenes (831)
48 544 9 An Deducciones Autonómicas - Illes Balears - Por arrendamiento de vivienda habitual por jóvenes - NIF arrendador (943)
49 553 13 N Deducciones Autonómicas - Illes Balears - Por arrendamiento de vivienda habitual por jóvenes - Importe (832)
50 566 13 N Deducciones Autonómicas - Illes Balears - Para los declarantes con minusvalía física/psíquica o descendientes con esa condición (833)
51 579 13 N Deducciones Autonómicas - Illes Balears - Para los declarantes titulares de fincas o terrrenos suelo rústico protegido (834)
52 592 13 N Deducciones Autonómicas - Illes Balears - Por adopción de hijos (835)
53 605 13 N Deducciones Autonómicas - Illes Balears - Por el impuesto transmisiones y AJD por adquisición vivienda habitual (836)
54 618 13 N Deducciones Autonómicas - Illes Balears - Por el impuesto transmisiones y AJD por adquisición vivienda habitual protegida (837)
55 631 13 N Deducciones Autonómicas - Illes Balears - Para el fomento del autoempleo (838)
56 644 13 N Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (717)
57 657 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10018>
58 666 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 667
Página 50

# Pag. 51

Anexo B.2
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "19"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Canarias - Por donaciones con finalidad ecológica (839)
7 23 13 N Deducciones Autonómicas - Canarias - Por donaciones rehabilitación/conservación patrimonio histórico de Canarias (840)
8 36 13 N Deducciones Autonómicas - Canarias - Por cantidades destinadas restauración/rehabilitación/reparación bienes inmuebles declarados de Interés Cultural (841)
9 49 13 N Deducciones Autonómicas - Canarias - Por gastos de estudios (842)
10 62 13 N Deducciones Autonómicas - Canarias - Por traslado residencia a otra isla para realizar actividad laboral cuenta ajena/actividad económica (843)
11 75 13 N Deducciones Autonómicas - Canarias - Por donaciones en metálico a descendientes menores 35 años para adquisición/rehabilitación primera vivienda habitual (844)
12 88 13 N Deducciones Autonómicas - Canarias - Por nacimiento o adopción de hijos (845)
13 101 13 N Deducciones Autonómicas - Canarias - Por contribuyentes minusválidos y mayores de 65 años (846)
14 114 13 N Deducciones Autonómicas - Canarias - Por gastos de guardería (847)
15 127 13 N Deducciones Autonómicas - Canarias - Por familia numerosa (848)
16 140 13 N Deducciones Autonómicas - Canarias - Por inversión vivienda habitual: con carácter general (849)
17 153 13 N Deducciones Autonómicas - Canarias - Por inversión vivienda habitual:obras adecuación personas con discapacidad (850)
18 166 9 An Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - NIF arrendador (943)
1199 117755 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass -- CCaannaarriiaass -- PPoorr aallqquuiilleerr ddee vviivviieennddaa hhaabbiittuuaall -- IImmppoorrttee ((885511))
20 188 13 N Deducciones Autonómicas - Canarias - Por variación del euribor (852)
21 201 13 N Deducciones Autonómicas - Canarias - Por contribuyentes desempleados (853)
22 214 13 N Deducciones Autonómicas - Canarias - Por obras de rehabilitación o reforma en vivienda (308)
23 227 13 N Deducciones Autonómicas - Canarias - Total deducciones autonómicas (717)
24 240 9 An Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores, discapacitados - NIF arrendador (943)
25 249 13 N Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores, discapacitados - Importe (854)
26 262 13 N Deducciones Autonómicas - Cantabria - Por cuidado de familiares (855)
27 275 5 Num Deducciones Autonómicas - Cantabria - Por adquisición o rehabilitación de vivienda - Código municipio (939)
28 280 13 N Deducciones Autonómicas - Cantabria - Por adquisición o rehabilitación de vivienda - Importe (856)
29 293 13 N Deducciones Autonómicas - Cantabria - Por donativos a fundaciones (857)
30 306 13 N Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (858)
31 319 13 N Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (717)
32 332 13 N Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (859)
33 345 13 N Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (860)
34 358 13 N Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (861)
35 371 13 N Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (862)
36 384 13 N Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (863)
37 397 13 N Deducciones Autonómicas - Castilla-La Mancha - Por cantidades donadas al Fondo Castellano-Manchego de Cooperación (864)
38 410 13 N Deducciones Autonómicas - Castilla-La Mancha - Por cantidades satisfechas adquisición/rehabilitación vivienda habitual (865)
39 423 20 An Deducciones Autonómicas - Castilla-La Mancha - Por cantidades satisfechas adquisición/rehabilitación vivienda habitual - nº identificación préstamo (942)
Página 51

# Pag. 52

Anexo B.2
Nº Posic. Long. Tipo Descripción Validación Contenido
40 443 13 N Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (717)
41 456 13 N Deducciones Autonómicas - Castilla y León - Para contribuyentes afectados con minusvalía (870)
42 469 13 N Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales (871)
43 482 13 N Deducciones Autonómicas - Castilla y León - Por donación a Fundaciones de Castilla y León para recuperación patrimonio histórico, cultural y natural (872)
44 495 13 N Deducciones Autonómicas - Castilla y León - Por inversión en patrimonio histórico, cultural y natural (873)
45 508 9 An Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años - Nif arrendador (943)
46 517 13 N Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años - Importe (874)
47 530 13 N Deducciones Autonómicas - Castilla y León - Por inversión instalaciones medioambientales/adaptación vvda.habitual discapacitados (565)
48 543 9 An Deducciones Autonómicas - Castilla y León - Por cuota Seg.Social empleados del hogar - Nif persona empleada (324)
49 552 13 N Deducciones Autonómicas - Castilla y León - Por cuota Seg.Social empleados del hogar - Importe (309)
50 565 9 An Deducciones Autonómicas - Castilla y León - Por inversión obras adecuación inspeccion técnica - Nif persona o entidad (325)
51 574 13 N Deducciones Autonómicas - Castilla y León - Por inversión obras adecuación inspeccion técnica - Importe (315)
52 587 9 An Deducciones Autonómicas - Castilla y León - Por inversión en obras de mejora en vvda. habitual - Nif persona o entidad (326)
53 596 13 N Deducciones Autonómicas - Castilla y León - Por inversión en obras de mejora en vvda. habitual - Importe (316)
54 609 13 N Deducciones Autonómicas - Castilla y León - Para fomento del autoempleo de mujeres y jovenes - Generado 2011 (331)
55 622 13 N Deducciones Autonómicas - Castilla y León - Para fomento del autoempleo de mujeres y jovenes (875)
56 635 13 N Deducciones Autonómicas - Castilla y León - Por familia numerosa (866)
57 648 13 N Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (867)
58 661 13 N Deducciones Autonómicas - Castilla y León - Por adopción internacional (868)
59 674 9 An Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Nif empleada (327)
60 683 13 N Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores (869)
61 696 13 N Deducciones Autonómicas - Castilla y León - Por paternidad (334)
62 709 13 N Deducciones Autonómicas - Castilla y León - Por gastos de adopción (337)
6633 772222 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass -- CCaassttiillllaa yy LLeeóónn -- IImmppoorrttee ttoottaall ((331177))
64 735 13 N Deducciones Autonómicas - Castilla y León - Total deducciones autonómicas (717)
65 748 13 N Deducciones Autonómicas - Castilla y León - Importe deducciones autonom. No aplicadas en 2011 - Deducciones para fomento del autoempleo (318)
66 761 13 N Deducciones Autonómicas - Castilla y León - Importe deducciones autonom. No aplicadas en 2011 - Deducciones por familia numerosa (319)
67 774 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10019>
68 783 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 784
Página 52

# Pag. 53

Anexo B.3
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "20"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Cataluña - Por nacimiento o adopción hijos (876)
7 23 13 N Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan el uso lengua catalana (877)
8 36 13 N Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan la investigación científica (878)
9 49 9 An Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - NIF arrendador (943)
10 58 13 N Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual - Importe (879)
11 71 13 N Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudios universitarios de master y doctorado (880)
12 84 13 N Deducciones Autonómicas - Cataluña - Para los contribuyentes que queden viudos (881)
13 97 13 N Deducciones Autonómicas - Cataluña - Por rehabilitación vivienda habitual (882)
14 110 13 N Deducciones Autonómicas - Cataluña - Por donaciones en beneficio del medio ambiente (883)
15 123 13 N Deducciones Autonómicas - Cataluña - Por inversión adquisición de acciones o participaciones sociales (566)
16 136 13 N Deducciones Autonómicas - Cataluña - Por inversión en acciones de entidades que cotizan en empresas en expansión (567)
17 149 13 N Deducciones Autonómicas - Cataluña - Total deducciones autonómicas (717)
18 162 13 N Deducciones Autonómicas - Extremadura - Por adquisición vivienda habitual para jóvenes y víctimas del terrorismo (884)
19 175 13 N Deducciones Autonómicas - Extremadura - Por trabajo dependiente (885)
20 188 13 N Deducciones Autonómicas - Extremadura - Por donaciones de bienes integrantes del Patrimonio Histórico y Cultural Extremeño (886)
21 201 13 N Deducciones Autonómicas - Extremadura - Por cantidades destinadas a la conservación, reparación etc. bienes Patrimonio Histórico y Cultural Extremeño (887)
22 214 9 An Deducciones Autonómicas - Extremadura - Por alquiler de vivienda habitual para jóvenes, familias numerosas y minusválidos - NIF arrendador (943)
23 223 13 N Deducciones Autonómicas - Extremadura - Por alquiler de vivienda habitual para jóvenes, familias numerosas y minusválidos - Importe (888)
24 236 13 N Deducciones Autonómicas - Extremadura - Por cuidado de familiares discapacitados (889)
25 249 13 N Deducciones Autonómicas - Extremadura - Por acogimiento de menores (890)
26 262 13 N Deducciones Autonómicas - Extremadura - Por ayuda doméstica (339)
27 275 13 N Deducciones Autonómicas - Extremadura - Para fomento autoempleo de las mujeres emprendedoras (348)
28 288 13 N Deducciones Autonómicas - Extremadura - Para fomento autoempleo de los jovenes emprendedores menores de 36 años (351)
29 301 13 N Deducciones Autonómicas - Extremadura - Por adopción de hijos en el ambito internacional (352)
30 314 13 N Deducciones Autonómicas - Extremadura - Para la madre o el padre de familia monoparental (353)
31 327 13 N Deducciones Autonómicas - Extremadura - Por partos múltiples (354)
32 340 13 N Deducciones Autonómicas - Extremadura - Por obras de mejora en la vivienda habitual (355)
33 353 13 N Deducciones Autonómicas - Extremadura - Por inversión no empresarial en adquisición de ordenadores personales para uso doméstico (356)
34 366 13 N Deducciones Autonómicas - Extremadura - Por donaciones con finalidad ecológica (357)
35 379 13 N Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (717)
36 392 13 N Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (891)
37 405 13 N Deducciones Autonómicas - Galicia - Por familia numerosa (892)
38 418 13 N Deducciones Autonómicas - Galicia - Por cuidado hijos menores (893)
39 431 13 N Deducciones Autonómicas - Galicia - Por contribuyentes minusválidos = > 65 años que precisan ayuda de terceras personas (894)
40 444 13 N Deducciones Autonómicas - Galicia - Por gastos de nuevas tecnologías en hogares gallegos (895)
Página 53

# Pag. 54

Anexo B.3
Nº Posic. Long. Tipo Descripción Validación Contenido
41 457 9 An Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - NIF arrendador (943)
42 466 13 N Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - Importe (896)
43 479 13 N Deducciones Autonómicas - Galicia - Para fomento autoempleo hombres menores 35 años y mujeres cualquier edad (897)
44 492 13 N Deducciones Autonómicas - Galicia - Por acogimiento familiar de menores (358)
45 505 13 N Deducciones Autonómicas - Galicia - Por inversión en acciones y participaciones sociales de nuevas entidades/reciente creación (359)
46 518 13 N Deducciones Autonómicas - Galicia - Por inversiones en entidades cotizadas en el Mercado Bursátil (382)
47 531 13 N Deducciones Autonómicas - Galicia - Total deducciones autonómicas (717)
48 544 13 N Deducciones Autonómicas - Madrid - Por nacimiento o adopción hijos (898)
49 557 13 N Deducciones Autonómicas - Madrid - Por adopción internacional niños (899)
50 570 13 N Deducciones Autonómicas - Madrid - Por acogimiento familiar de menores (900)
51 583 13 N Deducciones Autonómicas - Madrid - Por acogimiento no remunerado de mayores 65 años y/o discapacitados (901)
52 596 9 An Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - NIF arrendador (943)
53 605 13 N Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - Importe (902)
54 618 13 N Deducciones Autonómicas - Madrid - Por donativos a fundaciones (903)
55 631 13 N Deducciones Autonómicas - Madrid - Por incremento costes financiación ajena para inversión en vivienda habitual (904)
56 644 13 N Deducciones Autonómicas - Madrid - Por gastos educativos (905)
57 657 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10020>
58 666 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 667
Página 54

# Pag. 55

Anexo B.4
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "21"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Madrid - Por inversión en vivienda habitual de nueva construcción (906)
7 23 13 N Deducciones Autonómicas - Madrid - Para familias con dos o más descendientes e ingresos reducidos (568)
8 36 13 N Deducciones Autonómicas - Madrid - Por inversión en adquisición de acciones y participaciones sociales de nuevas entidades (569)
9 49 13 N Deducciones Autonómicas - Madrid - Para el fomento del autoempleo de jóvenes menores de 35 años (586)
10 62 13 N Deducciones Autonómicas - Madrid - Por inversiones en entidades cotizadas en el Mercado Alternativo Bursátil (587)
11 75 13 N Deducciones Autonómicas - Madrid - Total deducciones autonómicas (717)
12 88 13 N Deducciones Autonómicas - Murcia - Por inversión vivienda habitual jóvenes edad igual/inferior 35 años (incluido rég. transitorio D.T. segunda Ley 7/2011) (907)
13 101 13 N Deducciones Autonómicas - Murcia - Por donativos para la protección del patrimonio histórico Región Murcia (908)
14 114 13 N Deducciones Autonómicas - Murcia - Por gastos de guardería para hijos menores de 3 años (909)
15 127 13 N Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (910)
16 140 13 N Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (911)
1177 115533 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass - MMuurrcciiaa - TToottaall ddeedduucccciioonneess aauuttoonnóómmiiccaass ((771177))
18 166 13 N Deducciones Autonómicas - La Rioja - Por nacimiento o adopción de segundo o ulterior hijo (912)
19 179 13 N Deducciones Autonómicas - La Rioja - Por inversión adquisición/rehabilitación vivienda habitual para jóvenes (913)
20 192 4 Num Deducciones Autonómicas - La Rioja - Por adquisición/rehabilitación 2ª vivienda en el medio rural. Código municipio (939)
21 196 13 N Deducciones Autonómicas - La Rioja - Por adquisición/rehabilitación 2ª vivienda en el medio rural (914)
22 209 13 N Deducciones Autonómicas - La Rioja - Por inversión rehabilitación vivienda habitual (916)
23 222 13 N Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (717)
24 235 13 N Deducciones Autonómicas - Comunidad Valenciana - Por nacimiento/adopción de hijos (917)
25 248 13 N Deducciones Autonómicas - Comunidad Valenciana - Por nacimiento/adopción múltiples (918)
26 261 13 N Deducciones Autonómicas - Comunidad Valenciana - Por nacimiento/adopción hijos discapacitados (919)
27 274 13 N Deducciones Autonómicas - Comunidad Valenciana - Por familia numerosa (920)
28 287 13 N Deducciones Autonómicas - Comunidad Valenciana - Por custodia en guarderías y primer ciclo educación infantil hijos menores de 3 años (921)
29 300 13 N Deducciones Autonómicas - Comunidad Valenciana - Por conciliación del trabajo con la vida familiar (922)
30 313 13 N Deducciones Autonómicas - Comunidad Valenciana - Para contribuyentes discapacitados de edad igual o superior a 65 años (923)
31 326 13 N Deducciones Autonómicas - Comunidad Valenciana - Por ascendientes > 75 años ó > 65 años discapacitados (924)
32 339 13 N Deducciones Autonómicas - Comunidad Valenciana - Por realización de labores no remuneradas en el hogar (925)
33 352 13 N Deducciones Autonómicas - Comunidad Valenciana - Por adquisición/rehabilitación vivienda con financiación ajena (926)
34 365 13 N Deducciones Autonómicas - Comunidad Valenciana - Por primera adquisición vivienda habitual para contribuyentes edad igual o inferior 35 años (927)
35 378 13 N Deducciones Autonómicas - Comunidad Valenciana - Por adquisición vivienda habitual por discapacitados (928)
Página 55

# Pag. 56

Anexo B.4
Nº Posic. Long. Tipo Descripción Validación Contenido
36 391 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades adquisición/rehabilitación vivienda habitual, procedentes ayudas públicas (929)
37 404 9 An Deducciones Autonómicas - Comunidad Valenciana - Por arrendamiento de vivienda habitual - NIF arrendador (943)
38 413 13 N Deducciones Autonómicas - Comunidad Valenciana - Por arrendamiento de vivienda habitual - Importe (930)
39 426 9 An Deducciones Autonómicas - Comunidad Valenciana - Por arrendamiento vivienda actividades distinto municipio - NIF arrendador (944)
40 435 13 N Deducciones Autonómicas - Comunidad Valenciana - Por arrendamiento vivienda actividades distinto municipio - Importe (931)
41 448 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades inversiones fuentes energía renovables en vivienda habitual (932)
42 461 13 N Deducciones Autonómicas - Comunidad Valenciana - Por donaciones con finalidad ecológica (933)
43 474 13 N Deducciones Autonómicas - Comunidad Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (934)
44 487 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades donadas conservación, reparación y restauración Patrimonio Cultural Valenciano (935)
45 500 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades destinadas titulares conservación, etc. bienes Patrimonio Cultural Valenciano (936)
46 513 13 N Deducciones Autonómicas - Comunidad Valenciana - Por donaciones destinadas al fomento de la lengua valenciana (937)
47 526 13 N Deducciones Autonómicas - Comunidad Valenciana - Por incrementos costes financiación ajena en inversión vivienda habitual (938)
48 539 13 N Deducciones Autonómicas - Comunidad Valenciana - Por contribuyentes con dos o más descendientes (588)
49 552 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (589)
50 565 13 N Deducciones Autonómicas - Comunidad Valenciana - Total deduciones autonómicas (717)
51 578 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10021>
52 587 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 588
Página 56

# Pag. 57

I-D
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2011
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "22"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Liquidación (2) - Resultado a ingresar o a devolver [770]
7 23 1 Num Liquidación (2) - Solicitud de suspensión ingreso cónyuge/Renuncia cobro devolución otro cónyuge. "1" o "0" [7]
8 24 13 N Declaración Complementaria (3) - Resultado de Declaración Complementaria [765]
9 37 1 Num Ingreso (4) - Casilla 770 positiva - NO FRACCIONA el pago [1] "1" o "0"
10 38 1 Num Ingreso (4) - Casilla 770 positiva - SÍ FRACCIONA el pago [6] "1" o "0"
11 39 13 N Ingreso (4) - Casilla 770 positiva - Importe del ingreso [I1]
12 52 1 Num Ingreso (4) - Casilla 770 positiva - Forma de pago -"0" No consta; "1" Efectivo; "2" Adeudo en Cuenta; "3" Domiciliación
13 53 1 Num Opciones de pago 2º plazo (5) - NO DOMICILIA el pago [2] "1" o "0"
14 54 1 Num Opciones de pago 2º plazo (5) - SÍ DOMICILIA el pago [3] "1" o "0"
15 55 13 N Opciones de pago 2º plazo (5) - Importe del 2º plazo [I2]
1166 6688 11 NNuumm DDeevvoolluucciióónn ((66)) -- CCaassiillllaa 777700 nneeggaattiivvaa -- "00" NNoo ccoonnssttaa,, "11" DDeevvoolluucciióónn yy "22" rreennuunncciiaa ddeevvoolluucciióónn
17 69 13 N Devolución (6) - Casilla 770 negativa - Importe [D]
18 82 4 Num Cuenta bancaria (7) - Código cuenta cliente - Entidad
19 86 4 Num Cuenta bancaria (7) - Código cuenta cliente - Sucursal
20 90 2 Num Cuenta bancaria (7) - Código cuenta cliente - DC
21 92 10 Num Cuenta bancaria (7) - Código cuenta cliente - Número de cuenta
22 102 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10022>
23 111 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 112
Página 57