# Pag. 1

Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
NNº PPoossiicc.. LLoonngg.. TTiippoo DDeessccrriippcciióónn VVaalliiddaacciióónn CCoonntteenniiddoo
1 1 17 An Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "<T100020100A0000>"
2 18 5 An Constante "<AUX>"
3 23 70 An Reservado para la Administración. Rellenar con blancos BLANCOS
4 93 4 An Versión del Programa (**)
5 97 4 An Reservado para la Administración. Rellenar con blancos BLANCOS
66 110011 99 AAnn NNIIFF EEmmpprreessaa DDeessaarrrroolllloo ((**))
7 110 213 An Reservado para la Administración. Rellenar con blancos BLANCOS
8 323 6 An Constante "</AUX>"
9 329 8 An Constante "<VECTOR>"
Vector de páginas. Para su cumplimentación se debe indicar de forma secuencial las páginas que forman parte de esta declaración. Cada página se indicará con 3
digitos. Después de la última página se pondrá el identificador "FIN". Por ejemplo, en un fichero que contenga una página 1, una 2, una 3, cuatro páginas 4, una 10,
uunaa 11,, uunaa 12,, uunaa 133 yy uunaa ppáágginaa 199,, ddeebbeeríaa reelleenaarssee eel veeccttoor ccoon eel ssigguuieenttee ccoontteeniddoo: 00001000020000330000400004000040000400100001100120013300199FIN ((yy eel reessttoo aa bblaanccooss
10 337 300 An hasta completar las 300 posiciones
11 637 9 An Constante "</VECTOR>"
Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo
12 646Variable An documento
13*** 18 An Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "</T100020100A0000>"
14*** 2An Fin de Reggistro. Constante CRLF(( Hexadecimal 0D0A, Decimal 1310))
Total Variable
(**) A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# Pag. 2

100-01
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
11 65 1 Num Primer Declarante - Estado Civil. "1" Soltero/a, "2" Casado/a, "3" Viudo/a, "4" Divorciado/a o Separado/a OBLIGATORIO
12 66 8 Num Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 (10) OBLIGATORIO
13 74 1 Num Primer Declarante - Grado de Minusvalía "0", "1", "2" o "3" (11)
14 75 1 Num Primer Declarante - Suscripción servicio mensajes SMS "1" o cero (12)
15 76 1 Num Primer Declarante - Cambio de domicilio "1" o cero
16 77 5 A Primer Declarante - Domicilio habitual - Tipo de Vía (15)
17 82 5 Num Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Vía INE
18 87 50 An Primer Declarante - Domicilio habitual - Nombre de la Vía Pública (16)
1199 113377 33 AAnn PPrriimmeerr DDeeccllaarraannttee - DDoommiicciilliioo hhaabbiittuuaall - TTiippoo ddee nnuummeerraacciióónn. VVaalloorreess:: NNUUMM;;KKMM;;SS//NN;;OOTTRR ((1177))
20 140 5 Num Primer Declarante - Domicilio habitual - Número de Casa (18)
21 145 3 An Primer Declarante - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
22 148 3 An Primer Declarante - Domicilio habitual - Bloque (20)
23 151 3 An Primer Declarante - Domicilio habitual - Portal (21)
24 154 3 An Primer Declarante - Domicilio habitual - Escalera (22)
25 157 3 An Primer Declarante - Domicilio habitual - Planta (23)
26 160 3 An Primer Declarante - Domicilio habitual - Puerta (24)
27 163 40 An Primer Declarante - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
28 203 30 An Primer Declarante - Domicilio habitual - Localidad / Población (26)
29 233 5 Num Primer Declarante - Domicilio habitual - Código postal (27)
30 238 5 Num Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
31 243 30 An Primer Declarante - Domicilio habitual - Nombre del Municipio (28)
32 273 2 Num Primer Declarante - Domicilio habitual - Código provincia. De "01" a "52".
33 275 20 An Primer Declarante - Domicilio habitual - Provincia (29)
34 295 9 Num Primer Declarante - Domicilio habitual - Teléfono fijo (30)
35 304 9 Num Primer Declarante - Domicilio habitual - Teléfono móvil (31)
36 313 9 Num Primer Declarante - Domicilio habitual - Núm. De Fax (32)
37 322 50 An Primer Declarante - Domicilio extranjero - Domicilio/Address (35)
38 372 40 An Primer Declarante - Domicilio extranjero - Datos complementarios del domicilio (36)
39 412 30 An Primer Declarante - Domicilio extranjero - Población / Ciudad (37)
Página 2

# Pag. 3

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
40 442 100 An Primer Declarante - Domicilio extranjero - e-mail (38)
41 542 10 An Primer Declarante - Domicilio extranjero - Código Postal (39)
42 552 30 An Primer Declarante - Domicilio extranjero - Provincia / Región / Estado (40)
43 582 30 An Primer Declarante - Domicilio extranjero - País. (41)
44 612 2 An Primer Declarante - Domicilio extranjero - Código País. Código país ISO-3166 (alfabético 2 letras). (42)
45 614 15 An Primer Declarante - Domicilio extranjero - Teléfono fijo (43)
46 629 15 An Primer Declarante - Domicilio extranjero - Teléfono móvil (44)
47 644 15 An Primer Declarante - Domicilio extranjero - Núm. De Fax (45)
48 659 1 Num Datos adicionales vivienda - Titularidad "1", "2", "3" o "4" (50) OBLIGATORIO
49 660 5 Num Datos adicionales vivienda - Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
50 665 5 Num Datos adicionales vivienda - Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
51 670 1 Num Datos adicionales vivienda - Situación (clave) "1", "2", "3" o "4" (53)
52 671 20 An Datos adicionales vivienda - Referencia catastral (54)
53 691 1 Num Datos adicionales vivienda - Titularidad "0", "1", "2", "3" o "4" (50)
54 692 5 Num Datos adicionales vivienda - Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
55 697 5 Num Datos adicionales vivienda - Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
56 702 1 Num Datos adicionales vivienda - Situación (clave) "0", "1", "2", "3" o "4" (53)
57 703 20 An Datos adicionales vivienda - Referencia catastral (54)
58 723 1 Num Datos adicionales vivienda - Titularidad "0", "1", "2", "3" o "4" (50)
59 724 5 Num Datos adicionales vivienda - Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
60 729 5 Num Datos adicionales vivienda - Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
61 734 1 Num Datos adicionales vivienda - Situación (clave) "0", "1", "2", "3" o "4" (53)
62 735 20 An Datos adicionales vivienda - Referencia catastral (54)
6633 775555 11 NNuumm DDaattooss aaddiicciioonnaalleess vviivviieennddaa -- TTiittuullaarriiddaadd ""00"", ""11"", ""22"", ""33"" oo ""44"" ((5500))
64 756 5 Num Datos adicionales vivienda - Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
65 761 5 Num Datos adicionales vivienda - Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
66 766 1 Num Datos adicionales vivienda - Situación (clave) "0", "1", "2", "3" o "4" (53)
67 767 20 An Datos adicionales vivienda - Referencia catastral (54)
68 787 9 An Cónyuge - NIF (61)
69 796 15 A Cónyuge - Primer apellido (62)
70 811 15 A Cónyuge - Segundo apellido (63)
71 826 15 A Cónyuge - Nombre (64)
72 841 1 A Cónyuge - Sexo "H" Hombre, "M" Mujer (65)
73 842 8 Num Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero. (66)
74 850 1 Num Cónyuge - Grado de Minusvalía "0", "1", "2" o "3" (67)
75 851 1 Num Cónyuge - No residente que no es contribuyente del I.R.P.F. - "1" o cero (68)
76 852 1 Num Cónyuge - Suscripción servicio mensajes SMS "1" o cero (69)
77 853 1 Num Cónyuge - Cambio de domicilio "1" o cero
78 854 5 A Cónyuge - Domicilio habitual - Tipo de Vía (15)
79 859 5 Num Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Vía INE
80 864 50 An Cónyuge - Domicilio habitual - Nombre de la Vía Pública (16)
81 914 3 An Cónyuge - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
82 917 5 Num Cónyuge - Domicilio habitual - Número de Casa (18)
83 922 3 An Cónyuge - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
Página 3

# Pag. 4

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
84 925 3 An Cónyuge - Domicilio habitual - Bloque (20)
85 928 3 An Cónyuge - Domicilio habitual - Portal (21)
86 931 3 An Cónyuge - Domicilio habitual - Escalera (22)
87 934 3 An Cónyuge - Domicilio habitual - Planta (23)
88 937 3 An Cónyuge - Domicilio habitual - Puerta (24)
89 940 40 An Cónyuge - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
90 980 30 An Cónyuge - Domicilio habitual - Localidad / Población (26)
91 1010 5 Num Cónyuge - Domicilio habitual - Código postal (27)
92 1015 5 Num Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
93 1020 30 An Cónyuge - Domicilio habitual - Nombre del Municipio (28)
94 1050 2 Num Cónyuge - Domicilio habitual - Código provincia. De "01" a "52".
95 1052 20 An Cónyuge - Domicilio habitual - Provincia (29)
96 1072 9 Num Cónyuge - Domicilio habitual - Teléfono fijo (30)
97 1081 9 Num Cónyuge - Domicilio habitual - Teléfono móvil (33)
98 1090 9 Num Cónyuge - Domicilio habitual - Núm. De Fax (32)
99 1099 50 An Cónyuge - Domicilio extranjero - Domicilio/Address (35)
100 1149 40 An Cónyuge - Domicilio extranjero - Datos complementarios del domicilio (36)
101 1189 30 An Cónyuge - Domicilio extranjero - Población / Ciudad (37)
102 1219 100 An Cónyuge - Domicilio extranjero - e-mail (38)
103 1319 10 An Cónyuge - Domicilio extranjero - Código Postal (39)
104 1329 30 An Cónyuge - Domicilio extranjero - Provincia / Región / Estado (40)
105 1359 30 An Cónyuge - Domicilio extranjero - País (41)
106 1389 2 An Cónyuge - Domicilio extranjero - Código País (42)
110077 11339911 1155 AAnn CCóónnyyuuggee -- DDoommiicciilliioo eexxttrraannjjeerroo -- TTeellééffoonnoo ffiijjoo ((4433))
108 1406 15 An Cónyuge - Domicilio extranjero - Teléfono móvil (44)
109 1421 15 An Cónyuge - Domicilio extranjero - Núm. De Fax (45)
110 1436 1 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
111 1437 9 An Representante - N.I.F. (75)
112 1446 32 An Representante - Apellidos y nombre o razón social (76)
113 1478 20 An Fecha declaración - Lugar
114 1498 2 Num Fecha declaración - Fecha -Día
115 1500 10 A Fecha declaración - Fecha - Mes
116 1510 4 Num Fecha declaración - Fecha - Año
117 1514 4 Num Código cuenta cliente - Entidad
118 1518 4 Num Código cuenta cliente - Sucursal
119 1522 2 Num Código cuenta cliente - DC
120 1524 10 Num Código cuenta cliente - Número de cuenta
121 1534 13 Num Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
122 1547 21 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
123 1568 13 N Resultado de la declaración
124 1581 1 Num Fraccionamiento del pago. "1" o cero
125 1582 1 Num Domiciliación 2º plazo."1" o cero
126 1583 1 Num Renuncia a la devolución. "1" o cero
127 1584 1 Num Compensación entre cónyuges. "1" o cero
Página 4

# Pag. 5

100-01
Nº Posic. Long. Tipo Descripción Validación Contenido
128 1585 20An Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
129 1605 13An SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
130 1618 9An Identificador de Fin de registro. OBLIGATORIO Constante </T10001>
131 1627 2An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total 1628
Página 5

# Pag. 6

100-02
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "02"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 9 An Hijos y descendientes - 1º - N.I.F. (80)
7 19 33 A Hijos y descendientes - 1º - Apellidos y nombre (81)
8 52 8 Num Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año de 1886 a 2010 o cero (82)
9 60 8 Num Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
10 68 1 Num Hijos y descendientes - 1º - Grado minusvalía "0", "1", "2" o "3" (84)
11 69 1 An Hijos y descendientes - 1º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
12 70 1 An Hijos y descendientes - 1º - Otras situaciones clave:"1","2","3","4" o blanco (86)
13 71 9 An Hijos y descendientes - 2º - N.I.F. (80)
14 80 33 A Hijos y descendientes - 2º - Apellidos y nombre (81)
15 113 8 Num Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año de 1886 a 2010 o cero (82)
16 121 8 Num Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año de 1886 a 2010 o cero (83)
17 129 1 Num Hijos y descendientes - 2º - Grado minusvalía "0", "1", "2" o "3" (84)
18 130 1 An Hijos y descendientes - 2º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
1199 113311 11 AAnn HHiijjooss yy ddeesscceennddiieenntteess - 22º - OOttrraass ssiittuuaacciioonneess "11",,"22",,"33",,"44" oo bbllaannccoo ((8866))
20 132 9 An Hijos y descendientes - 3º - N.I.F. (80)
21 141 33 A Hijos y descendientes - 3º - Apellidos y nombre (81)
22 174 8 Num Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
23 182 8 Num Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
24 190 1 Num Hijos y descendientes - 3º - Grado minusvalía "0", "1", "2" o "3" (84)
25 191 1 An Hijos y descendientes - 3º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
26 192 1 An Hijos y descendientes - 3º - Otras situaciones "1","2","3","4" o blanco (86)
27 193 9 An Hijos y descendientes - 4º - N.I.F. (80)
28 202 33 A Hijos y descendientes - 4º - Apellidos y nombre (81)
29 235 8 Num Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
30 243 8 Num Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
31 251 1 Num Hijos y descendientes - 4º - Grado minusvalía "0", "1", "2" o "3" (84)
32 252 1 An Hijos y descendientes - 4º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
33 253 1 An Hijos y descendientes - 4º - Otras situaciones "1","2","3","4" o blanco (86)
34 254 9 An Hijos y descendientes - 5º - N.I.F. (80)
35 263 33 A Hijos y descendientes - 5º - Apellidos y nombre (81)
36 296 8 Num Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
37 304 8 Num Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
38 312 1 Num Hijos y descendientes - 5º - Grado minusvalía "0", "1", "2" o "3" (84)
39 313 1 An Hijos y descendientes - 5º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
Página 6

# Pag. 7

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
40 314 1 An Hijos y descendientes - 5º - Otras situaciones "1","2","3","4" o blanco (86)
41 315 9 An Hijos y descendientes - 6º - N.I.F. (80)
42 324 33 A Hijos y descendientes - 6º - Apellidos y nombre (81)
43 357 8 Num Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
44 365 8 Num Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
45 373 1 Num Hijos y descendientes - 6º - Grado minusvalía "0", "1", "2" o "3" (84)
46 374 1 An Hijos y descendientes - 6º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
47 375 1 An Hijos y descendientes - 6º - Otras situaciones "1","2","3","4" o blanco (86)
48 376 9 An Hijos y descendientes - 7º - N.I.F. (80)
49 385 33 A Hijos y descendientes - 7º - Apellidos y nombre (81)
50 418 8 Num Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
51 426 8 Num Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
52 434 1 Num Hijos y descendientes - 7º - Grado minusvalía "0", "1", "2" o "3" (84)
53 435 1 An Hijos y descendientes - 7º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
54 436 1 An Hijos y descendientes - 7º - Otras situaciones "1","2","3","4" o blanco (86)
55 437 9 An Hijos y descendientes - 8º - N.I.F. (80)
56 446 33 A Hijos y descendientes - 8º - Apellidos y nombre (81)
57 479 8 Num Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
58 487 8 Num Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
59 495 1 Num Hijos y descendientes - 8º - Grado minusvalía "0", "1", "2" o "3" (84)
60 496 1 An Hijos y descendientes - 8º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
61 497 1 An Hijos y descendientes - 8º - Otras situaciones "1","2","3","4" o blanco (86)
62 498 9 An Hijos y descendientes - 9º - N.I.F. (80)
6633 550077 3333 AA HHiijjooss yy ddeesscceennddiieenntteess -- 99ºº -- AAppeelllliiddooss yy nnoommbbrree ((8811))
64 540 8 Num Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
65 548 8 Num Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
66 556 1 Num Hijos y descendientes - 9º - Grado minusvalía "0", "1", "2" o "3" (84)
67 557 1 An Hijos y descendientes - 9º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
68 558 1 An Hijos y descendientes - 9º - Otras situaciones "1","2","3","4" o blanco (86)
69 559 9 An Hijos y descendientes - 10º - N.I.F. (80)
70 568 33 A Hijos y descendientes - 10º - Apellidos y nombre (81)
71 601 8 Num Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
72 609 8 Num Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
73 617 1 Num Hijos y descendientes - 10º - Grado minusvalía "0", "1", "2" o "3" (84)
74 618 1 An Hijos y descendientes - 10º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
75 619 1 An Hijos y descendientes - 10º - Otras situaciones "1","2","3","4" o blanco (86)
76 620 9 An Hijos y descendientes - 11º - N.I.F. (80)
77 629 33 A Hijos y descendientes - 11º - Apellidos y nombre (81)
78 662 8 Num Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
79 670 8 Num Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
80 678 1 Num Hijos y descendientes - 11º - Grado minusvalía "0", "1", "2" o "3" (84)
81 679 1 An Hijos y descendientes - 11º - Vinculación. clave: "1", "2", "3", "4", o blanco (85)
82 680 1 An Hijos y descendientes - 11º - Otras situaciones "1","2","3","4" o blanco (86)
83 681 9 An Hijos y descendientes - 12º - N.I.F. (80)
Página 7

# Pag. 8

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
84 690 33 A Hijos y descendientes - 12º - Apellidos y nombre (81)
85 723 8 Num Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (82)
86 731 8 Num Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (83)
87 739 1 Num Hijos y descendientes - 12º - Grado minusvalía "0", "1", "2" o "3" (84)
88 740 1 An Hijos y descendientes - 12º - Vinculación. clave:"1", "2", "3", "4", o blanco (85)
89 741 1 An Hijos y descendientes - 12º - Otras situaciones "1","2","3","4" o blanco (86)
90 742 2 Num Hijos y descendientes - Fallecido 2010 - Nº Orden (87)
91 744 8 Num Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
92 752 2 Num Hijos y descendientes - Fallecido 2010 - Nº Orden (87)
93 754 8 Num Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (88)
94 762 9 An A efectos de la declaración conjunta los hijos 1 y 2 son relacionados con los NIF
95 771 9 An A efectos de la declaración conjunta los hijos 1 y 2 son relacionados con los NIF
96 780 24 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
97 804 9 An Ascendientes mayores 65 años o discapacitados - 1º - N.I.F. (90)
98 813 33 A Ascendientes mayores 65 años o discapacitados - 1º - Apellidos y nombre (91)
99 846 8 Num Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (92)
100 854 1 Num Ascendientes mayores 65 años o discapacitados - 1º - Grado de Minusvalía "0", "1", "2" o "3" (93)
101 855 1 An Ascendientes mayores 65 años o discapacitados - 1º - Vinculación clave:"1", "2" o blanco (94)
102 856 1 An Ascendientes mayores 65 años o discapacitados - 1º - Convivencia "2" a "9" o blanco (95)
103 857 9 An Ascendientes mayores 65 años o discapacitados - 2º - N.I.F. (90)
104 866 33 A Ascendientes mayores 65 años o discapacitados - 2º - Apellidos y nombre (91)
105 899 8 Num Ascendientes mayores 65 años o discapacitados - 2º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (92)
106 907 1 Num Ascendientes mayores 65 años o discapacitados - 2º - Grado de Minusvalía "0", "1", "2" o "3" (93)
110077 990088 11 AAnn AAsscceennddiieenntteess mmaayyoorreess 6655 aaññooss oo ddiissccaappaacciittaaddooss -- 22ºº -- VViinnccuullaacciióónn ccllaavvee::""11"", ""22"" oo bbllaannccoo ((9944))
108 909 1 An Ascendientes mayores 65 años o discapacitados - 2º - Convivencia "2" a "9" o blanco (95)
109 910 9 An Ascendientes mayores 65 años o discapacitados - 3º - N.I.F. (90)
110 919 33 A Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
111 952 8 Num Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año de 1886 a 2010 o cero (92)
112 960 1 Num Ascendientes mayores 65 años o discapacitados - 3º - Grado de Minusvalía "0", "1", "2" o "3" (93)
113 961 1 An Ascendientes mayores 65 años o discapacitados - 3º - Vinculación clave:"1", "2" o blanco (94)
114 962 1 An Ascendientes mayores 65 años o discapacitados - 3º - Convivencia "2" a "9" o blanco (95)
115 963 9 An Ascendientes mayores 65 años o discapacitados - 4º - N.I.F. (90)
116 972 33 A Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
117 1005 8 Num Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año de 1886 a 2010 o cero (92)
118 1013 1 Num Ascendientes mayores 65 años o discapacitados - 4º - Grado de Minusvalía "0", "1", "2" o "3" (93)
119 1014 1 An Ascendientes mayores 65 años o discapacitados - 4º - Vinculación clave:"1", "2" o blanco (94)
120 1015 1 An Ascendientes mayores 65 años o discapacitados - 4º - Convivencia "2" a "9" o blanco (95)
121 1016 8 Num Devengo - Fecha de finalización del período impositivo (fallecimiento 2010) (DDMMAAAA) o cero (100)
122 1024 1 Num Opción de tributación. "1" Individual, "2" Conjunta. Campo OBLIGATORIO (101) (102) OBLIGATORIO
123 1025 2 Num Comunidad/Ciudad autónoma de residencia en 2010 - Clave (103) Incluido en el fichero COMAUTO.TXT OBLIGATORIO
124 1027 1 A Asignación tributaria a la Iglesia Católica. "X" o blanco. (105)
125 1028 1 A Asignación de cantidades a fines sociales. "X" o blanco. (106)
126 1029 1 Num Solicitudes. Borrador de la declaración o datos fiscales. "1" o cero (110)
127 1030 1 Num Solicitudes. Envío individualizado borrador. "1" o cero (111)
Página 8

# Pag. 9

100-02
Nº Posic. Long. Tipo Descripción Validación Contenido
128 1031 1 Num Solicitudes. Borrador o datos fiscales del ejercicio 2011 "1" o cero
129 1032 1 Num Declaración complementaria - Si es complementaria por atrasos de rendimientos del trabajo. "1" o cero (121)
130 1033 1 Num Declaración complementaria - Si es complementaria por haberse producido alguno de los supuestos especiales. "1" o cero (122)
131 1034 1 Num Declaración complementaria - Si es complementaria a devolver. "1" o cero (123)
132 1035 1 Num Declaración complementaria - Si es complementaria por supuestos distintos "1" o cero (120)
133 1036 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10002>
134 1045 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total 1046
Página 9

# Pag. 10

100-03
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Descripción Validación Contenido
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
21 205 13 N Rdto. Trabajo - Reducción rég. especial "33.ª Copa del América" (016)
2222 221188 1133 NN RRddttoo. TTrraabbaajjoo -- RReedduucccciióónn oobbtteenncciióónn rreennddiimmiieennttooss ddee ttrraabbaajjoo. CCuuaannttííaa aapplliiccaabbllee ccoonn ccaarráácctteerr ggeenneerraall ((001177))
23 231 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Incremento trabajadores activos > 65 años (018)
24 244 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Incremento contribuyentes desempleados con traslado de residencia (019)
25 257 13 N Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Reducción adicional para trabajadores activos discapacitados (020)
26 270 13 N Rdto. Trabajo - Rendimiento neto reducido (021)
27 283 13 N (B) Rdto.cap.mob.- Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (022)
28 296 13 N Rdto.cap.mob.- Base imponible ahorro - Intereses de activos financieros con derecho a bonificación (023)
29 309 13 N Rdto.cap.mob.- Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (024)
30 322 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (025)
31 335 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros(026)
32 348 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (027)
33 361 13 N Rdto.cap.mob.- Base imponible ahorro - Rdtos. Procedentes de rentas que tengan por causa la imposición de capitales (028)
34 374 13 N Rdto.cap.mob.- Base imponible ahorro - Total ingresos íntegros (029)
35 387 13 N Rdto.cap.mob.- Base imponible ahorro - Gastos fiscalmente deducibles (030)
36 400 13 N Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto (031)
37 413 13 N Rdto.cap.mob.- Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (032)
38 426 13 N Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto reducido (035)
39 439 13 N (B) Rdto.cap.mob.- Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (040)
40 452 13 N Rdto.cap.mob.- Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (041)
41 465 13 N Rdto.cap.mob.- Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (042)
42 478 13 N Rdto.cap.mob.- Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (043)
43 491 13 N Rdto.cap.mob.- Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (044)
44 504 13 N Rdto.cap.mob.- Base imponible general - Total ingresos íntegros (045)
45 517 13 N Rdto.cap.mob.- Base imponible general - Gastos fiscalmente deducibles (046)
Página 10

# Pag. 11

100-03
Nº Posic. Long. Tipo Descripción Validación Contenido
46 530 13 N Rdto.cap.mob.- Base imponible general - Rendimiento neto (047)
47 543 13 N Rdto.cap.mob.- Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (048)
48 556 13 N Rdto.cap.mob.- Base imponible general - Rendimiento neto reducido (050)
49 569 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10003>
50 578 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 579
Página 11

# Pag. 12

100-04
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
87 698 1 Num C Bienes inmuebles urbanos afectos. Inmueble 1. Situación "0", "1", "2", "3" o "4" (092)
88 699 20 An C Bienes inmuebles urbanos afectos. Inmueble 1. Referencia catastral (093)
89 719 1 Tit C Bienes inmuebles urbanos afectos. Inmueble 2. Contribuyente "0" a "9" (090)
90 720 5 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje titularidad (3 enteros y 2 decimales) (091)
91 725 1 Num C Bienes inmuebles urbanos afectos. Inmueble 2. Situación "0", "1", "2", "3" o "4" (092)
92 726 20 An C Bienes inmuebles urbanos afectos. Inmueble 2. Referencia catastral (093)
93 746 1 Tit C Bienes inmuebles urbanos afectos. Inmueble 3. Contribuyente "0" a "9" (090)
94 747 5 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje titularidad (3 enteros y 2 decimales) (091)
95 752 1 Num C Bienes inmuebles urbanos afectos. Inmueble 3. Situación "0", "1", "2", "3" o "4" (092)
96 753 20 An C Bienes inmuebles urbanos afectos. Inmueble 3. Referencia catastral (093)
97 773 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10004>
98 782 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 783
Página 14

# Pag. 15

100-05
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "05"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 3 Actividades a las que resulte aplicable un mismo régimen
7 11 1 Tit C (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Contribuyente "0" a "9" (100)
8 12 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Tipo actividad. Clave (Blanco o de "1" a "6") (101)
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
39 371 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Diferencia (133)
40 384 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Reduc. rdtos. "33.ª Copa del América" (134)
41 397 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Rdto. neto reducido (135)
42 410 1 Tit C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Contribuyente "0" a "9" (100)
43 411 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Tipo actividad.Clave (Blanco o de "1" a "6") (101)
44 412 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Modalidad Normal (103) o Simplificada (104) "0", "1" o "2"
45 413 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Epígrafe IAE (102) (**)
46 418 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Criterio cobros/pagos. "1" o cero. (105)
47 419 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Explotación (106)
48 432 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Otros ingresos (107)
49 445 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Autoconsumo bienes/servicios (108)
50 458 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Total ingresos computables (109)
51 471 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Consumos de explotación (110)
52 484 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Sueldos y salarios 111)
53 497 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Seguridad Social (112)
54 510 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos de personal (113)
55 523 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Arrendamientos y cánones (114)
56 536 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Reparación y conservación (115)
57 549 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Servicios profesionales independientes (116)
58 562 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros servicios exteriores (117)
59 575 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Tributos fiscalmente deducibles (118)
60 588 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Gastos financieros (119)
61 601 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Amortizaciones (120)
6622 661144 1133 NN CC RRddttoo.aaccttvv.eeccoonn.eesstt.ddiirreeccttaa - AAccttiivviiddaadd yy rrddttoo. oobbtteenniiddoo - GGaassttooss - AAccttiivviiddaadd 22- PPéérrddiiddaass ppoorr ddeetteerriioorroo ((112211))
63 627 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (convenios) (122)
64 640 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (gastos) (123)
65 653 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos fiscalmente deducibles (124)
66 666 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Suma de gastos (125)
67 679 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Normal - Provisiones (126)
68 692 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Normal - Total gastos deducibles (127)
69 705 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Diferencia (128)
70 718 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Provisiones deduc./gastos difícil justif. (129)
71 731 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad Simplificada - Total gastos deducibles (130)
72 744 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto. neto (131)
73 757 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Reducciones (132)
74 770 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Diferencia (133)
75 783 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Reduc. rdtos. "33.ª Copa del América" (134)
76 796 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto. neto reducido (135)
77 809 1 Tit C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Contribuyente "0" a "9" (100)
78 810 1 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Tipo actividad.Clave (Blanco o de "1" a "6") (101)
79 811 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Modalidad Normal (103) o Simplificada (104) "0", "1" o "2"
80 812 5 An C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Epígrafe IAE (102) (**)
81 817 1 Num C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Criterio cobros/pagos. "1" o cero. (105)
Página 16

# Pag. 17

100-05
Nº Posic. Long. Tipo Com. Descripción Validación Contenido
82 818 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Explotación (106)
83 831 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Otros ingresos (107)
84 844 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Autoconsumo bienes/servicios (108)
85 857 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Total ingresos computables (109)
86 870 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Consumos de explotación (110)
87 883 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Sueldos y salarios (111)
88 896 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Seguridad Social (112)
89 909 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos de personal (113)
90 922 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Arrendamientos y cánones (114)
91 935 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Reparación y conservación (115)
92 948 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Servicios profesionales independientes (116)
93 961 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros servicios exteriores (117)
94 974 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Tributos fiscalmente deducibles (118)
95 987 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Gastos financieros (119)
96 1000 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Amortizaciones (120)
97 1013 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Pérdidas por deterioro (121)
98 1026 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (convenios) (122)
99 1039 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (gastos) (123)
100 1052 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos fiscalmente deducibles (124)
101 1065 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Suma de gastos (125)
102 1078 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Normal - Provisiones (126)
103 1091 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Normal - Total gastos deducibles (127)
104 1104 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Diferencia (128)
110055 11111177 1133 NN CC RRddttoo.aaccttvv.eeccoonn.eesstt.ddiirreeccttaa - AAccttiivviiddaadd yy rrddttoo. oobbtteenniiddoo - GGaassttooss - AAccttiivviiddaadd 33- MMooddaalliiddaadd SSiimmpplliiffiiccaaddaa - PPrroovviissiioonneess ddeedduucc.//ggaassttooss ddiiffíícciill jjuussttiiff. ((112299))
106 1130 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad Simplificada - Total gastos deducibles (130)
107 1143 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto. neto (131)
108 1156 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Reducciones (132)
109 1169 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Diferencia (133)
110 1182 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Reduc. rdtos. "33.ª Copa del América" (134)
111 1195 13 N C Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto. neto reducido (135)
112 1208 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Suma de rendimientos netos reducidos (136)
113 1221 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción ejercicio determinadas actividades (137)
114 1234 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción por mantenimiento o creación de empleo (138)
115 1247 13 N Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Rendimiento neto reducido total (140)
116 1260 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10005>
117 1269 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1270
(**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignarán las tres cifras seguidas de dos
blancos.
Página 17

# Pag. 18

100-06
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "06"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº de hojas adicionales si se declaran más de 2 actividades
7 11 5 An C (E2) Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Clasificación IAE (151) (**)
8 16 1 Tit C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Contribuyente titular actividad (150) "0" a "9"
9 17 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Definición
10 41 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales)
11 50 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales)
12 61 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Definición
13 85 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales)
14 94 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales)
15 105 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Definición
16 129 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales)
17 138 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales)
18 149 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Definición
1199 117733 99 NN CC RRddttooss..aaccttiivv..eeccoonnóómm..eesstt..oobbjjeettiivvaa - AAcctt.. rreeaalliizz..//rrddttooss.. oobbtteenniiddooss - AAccttiivv.. 11ª - MMóódduulloo 44 - UUnniiddaaddeess ((nnº)) ((77 eenntteerrooss yy 22 ddeecciimmaalleess))
20 182 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales)
21 193 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Definición
22 217 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales)
23 226 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales)
24 237 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Definición
25 261 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales)
26 270 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales)
27 281 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Definición
28 305 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales)
29 314 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales)
30 325 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma) (152)
31 338 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo (153)
32 351 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (154)
33 364 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (155)
34 377 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (156)
35 381 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (157)
36 385 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (158)
37 389 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (159)
38 393 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (160)
39 397 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto de módulos (161)
Página 18

# Pag. 19

100-06
Nº Posic. Long. Tipo Com Descripción Validación Contenido
40 410 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción de carácter general (166)
41 423 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Gastos extraordinarios circunstancias excepcionales (162)
42 436 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Otras percepciones empresariales (163)
43 449 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª -Rendimiento neto actividad (164)
44 462 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción art. 32.1 Ley del Impuesto (165)
45 475 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rendimiento neto reducido (167)
46 488 5 An C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Clasificación IAE (151) (**)
47 493 1 Tit C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Contribuyente titular actividad (150) "0" a "9"
48 494 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Definición
49 518 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales)
50 527 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales)
51 538 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Definición
52 562 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales)
53 571 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales)
54 582 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Definición
55 606 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales)
56 615 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales)
57 626 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Definición
58 650 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales)
59 659 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales)
60 670 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Definición
61 694 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales)
62 703 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales)
6633 771144 2244 AA CC RRddttooss..aaccttiivv..eeccoonnóómm..eesstt..oobbjjeettiivvaa -- AAcctt.. rreeaalliizz..//rrddttooss.. oobbtteenniiddooss -- AAccttiivv.. 22ª -- MMóódduulloo 66 -- DDeeffiinniicciióónn
64 738 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales)
65 747 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales)
66 758 24 A C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Definición
67 782 9 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales)
68 791 11 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales)
69 802 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto previo (suma) (152)
70 815 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos al empleo (153)
71 828 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos a la inversion (154)
72 841 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto minorado (155)
73 854 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector especial (2 enteros y 2 decimales) (156)
74 858 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (157)
75 862 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de temporada (2 enteros y 2 decimales) (158)
76 866 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de exceso (2 enteros y 2 decimales) (159)
77 870 4 Num C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (160)
78 874 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto de módulos (161)
79 887 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción de carácter general (166)
80 900 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Gastos extraordinarios circunstancias excepcionales (162)
81 913 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Otras percepciones empresariales (163)
82 926 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª -Rendimiento neto actividad (164)
83 939 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción art. 32.1 Ley del Impuesto (165)
Página 19

# Pag. 20

100-06
Nº Posic. Long. Tipo Com Descripción Validación Contenido
84 952 13 N C Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rendimiento neto reducido (167)
85 965 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Suma rendimientos netos reducidos (168)
86 978 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Reducción por mantenimiento o creación de empleo (169)
87 991 13 N Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas (170)
88 1004 9 An C Identificador de Fin de registro. OBLIGATORIO Constante </T10006>
89 1013 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
1014
(**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos
blancos.
Página 20

# Pag. 21

100-07
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
17 141 1 Tit C (G2) Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (320)
18 142 9 An C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - N.I.F. (321)
1199 115511 1133 NN CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn -- IInnsstt. iinnvv. ccoolleeccttiivvaa -- SSoocciieeddaadd//FFoonnddoo 11 -- RReessuullttaaddooss nneettooss ppoossiittiivvooss -- GGaannaanncciiaass nneettaass ((332222))
20 164 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 1 - Resultados netos negativos - Pérdidas netas (323)
21 177 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (320)
22 178 9 An C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - N.I.F. (321)
23 187 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados netos positivos - Ganancias netas (322)
24 200 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 2 - Resultados netos negativos - Pérdidas netas (323)
25 213 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (320)
26 214 9 An C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (321)
27 223 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados netos positivos - Ganancias netas (322)
28 236 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Sociedad/Fondo 3 - Resultados netos negativos - Pérdidas netas (323)
29 249 13 N Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Totales - Total ganancias netas (329)
30 262 13 N Ganancias/pérdidas patrim. deriv. transmisión - Inst. inv. colectiva - Totales - Total pérdidas netas (330)
31 275 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
32 278 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Contribuyente "0" a "9" (340)
33 279 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Denominación valores (341)
34 299 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Importe global (342)
35 312 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Valor adquisición global (343)
36 325 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe obtenido (344)
37 338 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Ganancias. Importe computable (345)
38 351 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe obtenido (346)
Página 29

# Pag. 30

100-09
Nº Posic. Long. Tipo Com Descripción Validación Contenido
39 364 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 1 - Resultados - Pérdidas. Importe computable (347)
40 377 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Contribuyente "0" a "9" (340)
41 378 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Denominación valores (341)
42 398 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Importe global (342)
43 411 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Valor adquisición global (343)
44 424 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe obtenido (344)
45 437 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Ganancias. Importe reducido (345)
46 450 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe obtenido (346)
47 463 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 2 - Resultados - Pérdidas. Importe imputable (347)
48 476 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Contribuyente "0" a "9" (340)
49 477 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Denominación valores (341)
50 497 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Importe global (342)
51 510 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Valor adquisición global (343)
52 523 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe obtenido (344)
53 536 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Ganancias. Importe reducido (345)
54 549 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe obtenido (346)
55 562 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Entidad 3 - Resultados - Pérdidas. Importe imputable (347)
56 575 13 N Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Totales - Ganancias. Importe reducido (349)
57 588 13 N Ganancias/pérdidas patrim. deriv. transmisión - Mercados oficiales - Totales - Pérdidas. Importe imputable (350)
58 601 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
59 604 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (360)
60 605 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (361)
61 606 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Inmuebles. Situación. Clave "0" a "4" (362)
6622 660077 2200 AAnn CC GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn -- OOttrrooss eelleemmeennttooss -- EElleemmeennttoo 11 -- IInnmmuueebblleess. SSiittuuaacciióónn. RReeff. ccaattaassttrraall ((336633))
63 627 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Fecha transmisión (364)
64 635 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Fecha adquisición (365)
65 643 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Valor transmisión (366)
66 656 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Valor adquisición (367)
67 669 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (368)
68 682 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (369)
69 695 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (370)
70 708 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Parte ganancia susceptible reducción (371)
71 721 4 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Años permanencia hasta 31-12-94 (372)
72 725 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Reducción aplicable (373)
73 738 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida (374)
74 751 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia exenta reinversión viv. habitual (375)
75 764 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida no exenta (376)
76 777 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - No afectos - Ganancia reducida no exenta imputable (377)
77 790 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Reducción (licencia autotaxis) (378)
78 803 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia reducida (379)
79 816 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 1 - Afectos - Ganancia reducida imputable (380)
80 829 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (360)
81 830 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (361)
Página 30

# Pag. 31

100-09
Nº Posic. Long. Tipo Com Descripción Validación Contenido
82 831 1 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Clave "0" a "4" (362)
83 832 20 An C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Inmuebles. Situación. Ref. catastral (363)
84 852 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Fecha transmisión (364)
85 860 8 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Fecha adquisición (365)
86 868 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Valor transmisión (366)
87 881 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Valor adquisición (367)
88 894 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (368)
89 907 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable (369)
90 920 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida (370)
91 933 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Parte ganancia susceptible reducción (371)
92 946 4 Num C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Años permanencia hasta 31-12-94 (372)
93 950 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Reducción aplicable (373)
94 963 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida (374)
95 976 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia exenta reinversión viv. habitual (375)
96 989 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida no exenta (376)
97 1002 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - No afectos - Ganancia reducida no exenta imputable (377)
98 1015 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Reducción (licencia autotaxis) (378)
99 1028 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia reducida (379)
100 1041 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Elemento 2 - Afectos - Ganancia reducida imputable (380)
101 1054 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - Total pérdida imputable (383)
102 1067 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - No afectos - Total ganancia reducida no exenta imputable (384)
103 1080 13 N Ganancias/pérdidas patrim. deriv. transmisión - Otros elementos - Totales - Afectos - Total ganancia reducida imputable (385)
104 1093 3 Num Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
110055 11009966 99 AAnn CC IIddeennttiiffiiccaaddoorr ddee FFiinn ddee rreeggiissttrroo. OOBBLLIIGGAATTOORRIIOO CCoonnssttaannttee <<//TT1100000099>>
106 1105 2 An C Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1106
Página 31

# Pag. 32

100-10
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "10"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 1 Num Nº hojas adicionales que se adjuntan
7 11 1 Tit C (G2) Ganancias/pérdidas patrim. deriv. transmisión (continuación) - Imputación 2009 ejercicios anteriores - Ganancia 1 - Contribuyente "0" a "9" (390)
8 12 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Ganancia 1 - Importe ganancia (391)
9 25 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Ganancia 2 - Contribuyente "0" a "9" (390)
10 26 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Ganancia 2 - Importe ganancia (391)
11 39 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Ganancia 3 - Contribuyente "0" a "9" (390)
12 40 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Ganancia 3 - Importe ganancia (391)
13 53 13 N Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Total ganancias (395)
14 66 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Pérdida 1 - Contribuyente "0" a "9" (400)
15 67 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Pérdida 1 - Importe pérdida (401)
16 80 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Pérdida 2 - Contribuyente "0" a "9" (400)
17 81 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Pérdida 2 - Importe pérdida (401)
18 94 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Pérdida 3 - Contribuyente "0" a "9" (400)
19 95 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 ejercicios anteriores - Pérdida 3 - Importe pérdida (401)
2200 110088 1133 NN GGaannaanncciiaass//ppéérrddiiddaass ppaattrriimm. ddeerriivv. ttrraannssmmiissiióónn - IImmppuuttaacciióónn 22001100 eejjeerrcciicciiooss aanntteerriioorreess - TToottaall ppéérrddiiddaass ((440055))
21 121 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 1 - Contribuyente "0" a "9" (410)
22 122 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 1 - Importe ganancia (411)
23 135 1 An C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 1 - Método integración. Clave (Blanco,"1","2" o "3") (412)
24 136 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 2 - Contribuyente "0" a "9" (410)
25 137 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 2 - Importe ganancia (411)
26 150 1 An C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 2 - Método integración. Clave (Blanco,"1","2" o "3") (412)
27 151 1 Tit C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 3 - Contribuyente "0" a "9" (410)
28 152 13 N C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 3 - Importe ganancia (411)
29 165 1 An C Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Ganancia 3 - Método integración. Clave (Blanco,"1","2" o "3") (412)
30 166 13 N Ganancias/pérdidas patrim. deriv. transmisión - Imputación 2010 diferimiento por reinversión - Total ganancia (415)
31 179 13 N (G3) Exención por reinversión ganancia patrimonial 2010 transmisión vivienda habitual - Importe transmisión susceptible reinversión (420)
32 192 13 N Exención por reinversión ganancia patrimonial 2010 transmisión vivienda habitual - Ganancia patrimonial consecuencia transmisión (421)
33 205 13 N Exención por reinversión ganancia patrimonial 2010 transmisión vivienda habitual - Importe reinvertido hasta 31-12-2010 adquisición nueva vivienda (422)
34 218 13 N Exención por reinversión ganancia patrimonial 2010 transmisión vivienda habitual - Importe se compromete reinvertir 2 años siguientes (423)
35 231 13 N Exención por reinversión ganancia patrimonial 2010 transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (424)
36 244 1 Tit (G4) Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (430)
37 245 2 Num Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones1 (431)
38 247 1 Tit Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente2 "0" a "9" (432)
39 248 2 Num Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones2 (433)
40 250 13 N (G5) Integración/compensación ganancias/pérdidas patrimoniales imputables 2010 - A integrar en base imponible general - Suma ganancias (440)
41 263 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2010 - A integrar en base imponible general - Suma pérdidas (441)
Página 32

# Pag. 33

100-10
Nº Posic. Long. Tipo Com Descripción Validación Contenido
42 276 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2010 - A integrar en base imponible general - Saldo neto - Diferencia positiva (450)
43 289 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2010 - A integrar en base imponible general - Saldo neto - Diferencia negativa (442)
44 302 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2010 - A integrar en base imponible ahorro - Suma ganancias (443)
45 315 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2010 - A integrar en base imponible ahorro - Suma pérdidas (444)
46 328 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2010 - A integrar en base imponible ahorro - Saldo neto - Diferencia positiva (457)
47 341 13 N Integración/compensación ganancias/pérdidas patrimoniales imputables 2010 - A integrar en base imponible ahorro - Saldo neto - Diferencia negativa (445)
48 354 13 N (H) Base imponible general y base imponible ahorro - Base imponible general - Saldo neto positivo ganancias/pérdidas 2010 a integrar (450)
49 367 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldos netos negativos ganancias/pérdidas 2006-2009 a integrar (451)
50 380 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldo neto rendimientos a integrar en base imponible general/imputaciones renta (452)
51 393 13 N Base imponible general y base imponible ahorro - Base imponible general - Compensaciones - Resto saldos netos negativos 2006-2009 a integrar (453)
52 406 13 N Base imponible general y base imponible ahorro - Base imponible general - Compensaciones - Saldo neto negativo ganancias/pérdidas imputables 2010 a integrar (454)
53 419 13 N Base imponible general y base imponible ahorro - Base imponible general - Total (455)
54 432 13 N Base imponible general y base imponible ahorro - Base imponible general - Saldo neto negativo ganancias/pérdidas 2010: importe pendiente de compensar (456)
55 445 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Saldo neto positivo ganancias/pérdidas 2009 (457)
56 458 13 N Base imponible general y base imponible ahorro - Base imponible ahorro - Compensación - Saldos netos negativos ganancias/pérdidas 2006-2009 a integrar (458)
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
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Com Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "11"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A C Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 10 13 N (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidad familiar tributación conjunta (470)
7 23 1 Tit Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 1 "0" a "9" (480)
8 24 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes 2005-2009 F401 (481)
9 37 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones 2010 1 (482)
10 50 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción 1 (483)
11 63 1 Tit Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 2 "0" a "9" (480)
12 64 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes 2005-2009 2 (481)
13 77 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones 2010 2 (482)
14 90 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción 2 (483)
15 103 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total derecho reducción (500)
16 116 13 N Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones cónyuge del contribuyente - Total derecho reducción (505)
17 129 1 Num Nº hojas adicionales que se adjuntan
18 130 1 Tit C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Contribuyente 1 "0" a "9" (510)
19 131 9 An C Reducciones base imponible - Aportaciones a favor personas con discapacidad - NIF persona con discapacidad 1 (511)
20 140 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Excesos pendientes reducir 2006-2009 1 (512)
21 153 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2010 propia persona discapacidad 1 (513)
2222 116666 1133 NN CC RReedduucccciioonneess bbaassee iimmppoonniibbllee -- AAppoorrttaacciioonneess aa ffaavvoorr ppeerrssoonnaass ccoonn ddiissccaappaacciiddaadd -- AAppoorrttaacciioonneess 22001100 ppaarriieenntteess oo ttuuttoorreess 11 ((551144))
23 179 1 Tit C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Contribuyente 2 "0" a "9" (510)
24 180 9 An C Reducciones base imponible - Aportaciones a favor personas con discapacidad - NIF persona con discapacidad 2 (511)
25 189 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Excesos pendientes reducir 2006-2009 2 (512)
26 202 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2010 propia persona discapacidad 2 (513)
27 215 13 N C Reducciones base imponible - Aportaciones a favor personas con discapacidad - Aportaciones 2010 parientes o tutores 2 (514)
28 228 13 N Reducciones base imponible - Aportaciones a favor personas con discapacidad - Total con derecho a reducción (530)
29 241 1 Tit Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (540)
30 242 9 An Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 1 (541)
31 251 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 2006-2009 1 (542)
32 264 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2010 1 (543)
33 277 1 Tit Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (540)
34 278 9 An Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 2 (541)
35 287 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 2006-2009 2 (542)
36 300 13 N Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2010 2 (543)
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
46 386 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Excesos pendientes reducir 2007, 2008, 2009 1 (591)
47 399 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones 2010 1 (592)
48 412 1 Tit Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 2 "0" a "9" (590)
49 413 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Excesos pendientes reducir ejercicio 2007 2 (591)
50 426 13 N Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones 2009 2 (592)
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
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
39 421 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - (717)
40 434 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota líquida estatal - Parte estatal (720)
41 447 13 N Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuota líquida autonómica - Parte autonómica (721)
42 460 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - PE (722)
43 473 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - PE (723)
44 486 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2009 - Importe - PE (724)
45 499 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2009 - Intereses demora - PE (725)
46 512 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2009 - Importe - PA (726)
Página 38

# Pag. 39

100-13
Nº Posic. Long. Tipo Descripción Validación Contenido
47 525 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2009 - Intereses demora - PA (727)
48 538 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2009 - Importe - PA (728)
49 551 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2009 - Intereses demora - PA (729)
50 564 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Cuotas líquidas incrementadas - Parte estatal (730)
51 577 13 N Cálculo impuesto y resultado declaración - Incremento cuotas líquidas pérdida derecho deducciones - Cuotas líquidas incrementadas - Parte autonómica (731)
52 590 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota líquida incrementada total (732)
53 603 13 N Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones doble imposición - Dividendos pendientes ejercicio 2006 (733)
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
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
21 205 13 N Cálculo impuesto y resultado declaración - Cuota diferencial y resultado declaración - Deducción por nacimiento o adopción - Importe de la deducción (758)
22 218 13 N Cálculo impuesto y resultado declaración - Cuota diferencial y resultado declaración - Importe del abono anticipado (759)
23 231 13 N Cálculo impuesto y resultado declaración - Cuota diferencial y resultado declaración - Resultado de la declaración (760)
24 244 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - Cuota líquida autonómica incrementada (775)
25 257 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% deducciones doble imposición (776)
26 270 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% compensación fiscal adquisición vivienda habitual (777
27 283 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - 50% compensación fiscal percepción rendimientos capital mobiliario (778)
28 296 13 N Importe del IRPF que corresponde a la Comunidad Autónoma de residencia - Importe IRPF que corresponde a la Comunidad Autónoma de residencia [779]
29 309 13 N (P) Regularización mediante declaración complementaria (ejercicio 2010) - Resultados a ingresar anteriores autoliquidaciones o liquidaciones administrativas ejercicio 2010 (761)
30 322 13 N Regularización mediante declaración complementaria (ejercicio 2010) - Devoluciones acordadas por la Administración, consecuencia anteriores autoliquidaciones ejercicio 2010 (762)
31 335 13 N Regularización mediante declaración complementaria (ejercicio 2010) - Resultado de la declaración complementaria (765)
32 348 13 N (Q) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (768)
33 361 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (770)
34 374 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (769)
35 387 13 N Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (770)
36 400 4 Num Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Código Cuenta Cliente - Entidad
37 404 4 Num Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Código Cuenta Cliente - Oficina
38 408 2 Num Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Código Cuenta Cliente - DC
39 410 10 Num Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Código Cuenta Cliente - Número de Cuenta
40 420 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10014>
41 429 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 430
Página 40

# Pag. 41

Anexo A.1
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "15"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Adquisición - Inversión con derecho a deducción (A)
7 23 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Adquisición - Importe deducción - Parte estatal (780)
8 36 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Adquisición - Importe deducción - Parte autonómica (781)
9 49 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Construcción/rehabilitación/ampliación - Inversión con derecho a deducción (B)
10 62 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Construcción/rehabilitación/ampliación - Importe deducción - Parte estatal (782)
11 75 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Construcción/rehabilitación/ampliación - Importe deducción - Parte autonómica (783)
12 88 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Cuentas vivienda 1º adquisición/rehabilitación - Importe con derecho a deducción (C)
13 101 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Cuentas vivienda 1º adquisición/rehabilitación - Importe deducción - Parte estatal (784)
14 114 13 N Deducción inversión vivienda habitual - Adquisición etc y cuenta vivienda - Cuentas vivienda 1º adquisición/rehabilitación - Importe deducción - Parte autonómica (785)
15 127 1 Tit Deducción inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 1 - Titular de la cuenta "0" a "9"
16 128 8 Num Deducción inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 1 - Fecha apertura (DDMMAAAA)
Deducción inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 1 - Entidad (4), Oficina (4), DC (2) y Número (10) alineada a la izquierda en caso de cuenta nacional , rellenando con
17 136 62 An blancos por la derecha
18 198 1 Tit Deducción inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 2 - Titular de la cuenta "0" a "9"
1199 119999 88 Num Deduccióón inversióón vivienda habitual - Identifficacióón cuentas vivienda - CCuenta 22 - Fecha apertura ((DDMMAAAA))
Deducción inversión vivienda habitual - Identificación cuentas vivienda - Cuenta 2 - Entidad (4), Oficina (4), DC (2) y Número (10) alineada a la izquierda en caso de cuenta nacional , rellenando con
20 207 62 An blancos por la derecha
21 269 1 Num Deducción inversión vivienda habitual - Cuenta vivienda no se encuentra abierta en oficina sita en territorio español
22 270 13 N Deducción inversión vivienda habitual - Obras/instalaciones adecuación personas con discapacidad - Cantidades satisfechas (D)
23 283 13 N Deducción inversión vivienda habitual - Obras/instalaciones adecuación personas con discapacidad - Importe deducción - Parte estatal (786)
24 296 13 N Deducción inversión vivienda habitual - Obras/instalaciones adecuación personas con discapacidad - Importe deducción - Parte autonómica (787)
25 309 13 N Deducción inversión vivienda habitual - Deducción inversión vivienda habitual - Parte estatal (700)
26 322 13 N Deducción inversión vivienda habitual - Deducción inversión vivienda habitual - Parte autonómica (701)
27 335 13 N Deducción inversión vivienda habitual - Datos adicionales - Importe pagos promotor/constructor/obras/instalaciones - Importe (788)
28 348 9 An Deducción inversión vivienda habitual - Datos adicionales - Importe pagos promotor/constructor/obras/instalaciones - NIF promotor/constructor (789)
29 357 8 An Deducción inversión vivienda habitual - Datos adicionales - En caso de deducción - Fecha adquisición vivienda (DDMMAAAA) (790). Ver NOTA
30 365 20 An Deducción inversión vivienda habitual - Datos adicionales - En caso de deducción - Número préstamo hipotecario (791)
31 385 5 Num Deducción inversión vivienda habitual - Datos adicionales - En caso de deducción - Porcentaje préstamo (792)
32 390 9 An Deducción por alquiler vivienda habitual - NIF arrendador 1 (793)
33 399 13 N Deducción por alquiler vivienda habitual - Cantidades arrendador 1 (582)
34 412 9 An Deducción por alquiler vivienda habitual - NIF arrendador 2 (583)
35 421 13 N Deducción por alquiler vivienda habitual - Cantidades arrendador 2 (584)
36 434 13 N Deducción por alquiler vivienda habitual - Cantidades satisfechas con derecho a deducción (E)
37 447 13 N Deducción por alquiler vivienda habitual - Importe deducción (774)
38 460 13 N Deducción por alquiler vivienda habitual - Parte estatal (716)
Página 41

# Pag. 42

Anexo A.1
Nº Posic. Long. Tipo Descripción Validación Contenido
39 473 13 N Deducción por alquiler vivienda habitual - Parte autonómica (772)
40 486 13 N Deducciones por donativos - Donativos límite 15% base liquidable - Importe con derecho a deducción (F)
41 499 13 N Deducciones por donativos - Donativos límite 15% base liquidable - Importe de la deducción (795)
42 512 13 N Deducciones por donativos - Donativos límite 10% base liquidable - Importe con derecho a deducción (G)
43 525 13 N Deducciones por donativos - Donativos límite 10% base liquidable - Importe de la deducción (796)
44 538 13 N Deducciones por donativos - Deducciones por donativos - Parte estatal (704)
45 551 13 N Deducciones por donativos - Deducciones por donativos - Parte autonómica (705)
46 564 9 An Deducción por obras de mejora en vivienda habitual - NIF (531)
47 573 13 N Deducción por obras de mejora en vivienda habitual - Base de la deducción (J)
48 586 13 N Deducción por obras de mejora en vivienda habitual - Importe deducción (773)
49 599 13 N Deducción por obras de mejora en vivienda habitual - Exceso de cantidades satisfechas (532)
50 612 13 N Otras deducciones generales - Por inversiones o gastos de interés cultural - Para la protección y difusión del Patrimonio. Importes con derecho a deducción (H)
51 625 13 N Otras deducciones generales - Por inversiones o gastos de interés cultural - Para la protección y difusión del Patrimonio. Importe de la deducción (797)
52 638 13 N Otras deducciones generales - Por inversiones o gastos de interés cultural - Parte estatal (702)
53 651 13 N Otras deducciones generales - Por inversiones o gastos de interés cultural - Parte autonómica (703)
54 664 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10015>
55 673 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 674 NOTA: En caso de más de una fecha consigne la más antigua
Página 42

# Pag. 43

Anexo A.2
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "16"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Otras deducciones generales - Por rentas obtenidas en Ceuta o Melilla - Importe total de la deducción (798)
7 23 13 N Otras deducciones generales - Por rentas obtenidas en Ceuta o Melilla - Parte estatal (712)
8 36 13 N Otras deducciones generales - Por rentas obtenidas en Ceuta o Melilla - Parte autonómica (713)
9 49 13 N Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cantidades depositadas ejercicio con derecho a deducción - (I)
10 62 13 N Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cantidades depositadas ejercicio - Importe de la deducción (799)
11 75 13 N Otras deducciones generales - cantidades depositadas depositadas cuentas ahorro-empresa - por cantidades depositadas - Parte estatal (714)
12 88 13 N Otras deducciones generales - cantidades depositadas depositadas cuentas ahorro-empresa - por cantidades depositadas - Parte autonómica (715)
13 101 1 Tit Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 1 - Titular de la cuenta "0" a "9"
14 102 8 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 1 - Fecha apertura (DDMMAAAA)
15 110 4 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 1 - Entidad
16 114 4 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 1 - Oficina
17 118 2 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 1 - DC
18 120 10 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 1 - Número cuenta
1199 113300 11 TTiitt OOttrraass ddeedduucccciioonneess ggeenneerraalleess -- ccaannttiiddaaddeess ddeeppoossiittaaddaass ccuueennttaass aahhoorrrroo--eemmpprreessaa -- CCuueennttaa 22 -- TTiittuullaarr ddee llaa ccuueennttaa "00" aa "99"
20 131 8 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 2 - Fecha apertura (DDMMAAAA)
21 139 4 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 2 - Entidad
22 143 4 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 2 - Oficina
23 147 2 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 2 - DC
24 149 10 Num Otras deducciones generales - cantidades depositadas cuentas ahorro-empresa - Cuenta 2 - Número cuenta
25 159 13 N Deducciones incentivos/estímulos inv. empres. - Saldos ptes. - Rég. Gral. Ley Impuesto Sociedades - Saldo anterior
26 172 13 N Deducciones incentivos/estímulos inv. empres. - Saldos ptes. - Rég. Gral. Ley Impuesto Sociedades - Aplicado en esta declaración (945)
27 185 13 N Deducciones incentivos/estímulos inv. empres. - Saldos ptes. - Rég. Gral. Ley Impuesto Sociedades - Pendiente de aplicación
28 198 13 N Deducciones incentivos/estímulos inv. empres. - Saldos ptes. - Regímenes especial interés público. - Saldo anterior
29 211 13 N Deducciones incentivos/estímulos inv. empres. - Saldos ptes. - Regímenes especial interés público. - Aplicado en esta declaración (946)
30 224 13 N Deducciones incentivos/estímulos inv. empres. - Saldos ptes. - Regímenes especial interés público. - Pendiente de aplicación
31 237 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Investigación/innovación tecnológ. - Deducción 2010
32 250 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Investigación/innovación tecnológ. - Aplicado en esta declaración (947)
33 263 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Investigación/innovación tecnológ. - Pendiente de aplicación
34 276 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Fomento tecnologías información y comunicación - Deducción 2010
35 289 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Fomento tecnologías información y comunicación - Aplicado en esta declaración (948)
36 302 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Fomento tecnologías información y comunicación - Pendiente de aplicación
37 315 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Actividades exportación - Deducción 2010
38 328 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Actividades exportación - Aplicado en esta declaración (949)

# Pag. 44

Anexo A.2
Nº Posic. Long. Tipo Descripción Validación Contenido
39 341 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Actividades exportación - Pendiente de aplicación
40 354 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: inv. Art. 38 L.I.S. - Deducción 2010
41 367 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: inv. Art. 38 L.I.S. - Aplicado en esta declaración (950)
42 380 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: inv. Art. 38 L.I.S. - Pendiente de aplicación
43 393 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: inv. medioambientales - Deducción 2010
44 406 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: inv. medioambientales - Aplicado en esta declaración (951)
45 419 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: inv. medioambientales - Pendiente de aplicación
46 432 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Gastos formación profesional - Deducción 2010
47 445 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Gastos formación profesional - Aplicado en esta declaración (952)
48 458 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Gastos formación profesional - Pendiente de aplicación
49 471 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Creación empleo trabajadores minusválidos - Deducción 2010
50 484 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Creación empleo trabajadores minusválidos - Aplicado en esta declaración (953)
51 497 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Creación empleo trabajadores minusválidos - Pendiente de aplicación
52 510 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Contribuciones empresariales Art. 43 L.I.S. - Deducción 2010
53 523 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Contribuciones empresariales Art. 43 L.I.S. - Aplicado en esta declaración (954)
54 536 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Rég. Gral.: Contribuciones empresariales Art. 43 L.I.S. - Pendiente de aplicación
55 549 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Alicante 2011. Vuelta al Mundo a Vela" - Deducción 2010
56 562 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Alicante 2011. Vuelta al Mundo a Vela" - Aplicado en esta declaración (955)
57 575 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Alicante 2011. Vuelta al Mundo a Vela" - Pendiente de aplicación
58 588 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Barcelona World Race" - Deducción 2010
59 601 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Barcelona World Race" - Aplicado en esta declaración (956)
60 614 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Barcelona World Race" - Pendiente de aplicación
61 627 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "33 Copa del América" - Deducción 2010
6622 664400 1133 NN DDeedduucccciioonneess iinncceennttiivvooss//eessttíímmuullooss iinnvv. eemmpprreess. -- EEjjeerrcciicciioo 22001100 -- RReeggíímmeenneess aappooyyoo -- ""3333 CCooppaa ddeell AAmméérriiccaa"" -- AApplliiccaaddoo eenn eessttaa ddeeccllaarraacciióónn ((995577))
63 653 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "33 Copa del América" - Pendiente de aplicación
64 666 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Guadalquivir Rio de Historia" - Deducción 2010
65 679 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Guadalquivir Rio de Historia" - Aplicado en esta declaración (958)
66 692 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Guadalquivir Rio de Historia" - Pendiente de aplicación
67 705 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Conmemoración Bicentenario Constitución 1812" - Deducción 2010
68 718 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Conmemoración Bicentenario Constitución 1812" - Aplicado en esta declaración (959)
69 731 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Conmemoración Bicentenario Constitución 1812" - Pendiente de aplicación
70 744 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Londres 2012" - Deducción 2010
71 757 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Londres 2012" - Aplicado en esta declaración (960)
72 770 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Londres 2012" - Pendiente de aplicación
73 783 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Santo Xacobeo 2010" - Deducción 2010
74 796 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Santo Xacobeo 2010" - Aplicado en esta declaración (961)
75 809 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Santo Xacobeo 2010" - Pendiente de aplicación
76 822 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "IX Centenario Sto.Domingo de la Calzada y Año Jubilar Calceatense" - Deducción 2010
77 835 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "IX Centenario Sto.Domingo de la Calzada y Año Jubilar Calceatense" - Aplicado en esta declaración (962)
78 848 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "IX Centenario Sto.Domingo de la Calzada y Año Jubilar Calceatense" - Pendiente de aplicación
79 861 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Caravaca Jubilar 2010" - Deducción 2010
80 874 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Caravaca Jubilar 2010" - Aplicado en esta declaración (963)
81 887 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Caravaca Jubilar 2010" - Pendiente de aplicación

# Pag. 45

Anexo A.2
Nº Posic. Long. Tipo Descripción Validación Contenido
82 900 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Alzheimer Internacional 2011" - Deducción 2010
83 913 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Alzheimer Internacional 2011" - Aplicado en esta declaración (964)
84 926 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Alzheimer Internacional 2011" - Pendiente de aplicación
85 939 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Hernandiano. Orihuela 2010" - Deducción 2010
86 952 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Hernandiano. Orihuela 2010" - Aplicado en esta declaración (965)
87 965 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Hernandiano. Orihuela 2010" - Pendiente de aplicación
88 978 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Centenario de la Costa Brava" - Deducción 2010
89 991 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Centenario de la Costa Brava" - Aplicado en esta declaración (966)
90 1004 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Centenario de la Costa Brava" - Pendiente de aplicación
91 1017 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "90 Aniversario Salón Internacional Automóvil Barcelona 2010" - Deducción 2010
92 1030 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "90 Aniversario Salón Internacional Automóvil Barcelona 2010" - Aplicado en esta declaración (967)
93 1043 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "90 Aniversario Salón Internacional Automóvil Barcelona 2010" - Pendiente de aplicación
94 1056 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Misteri de Elx" - Deducción 2010
95 1069 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Misteri de Elx" - Aplicado en esta declaración (533)
96 1082 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Misteri de Elx" - Pendiente de aplicación
97 1095 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Jubilar Guadalupense" - Deducción 2010
98 1108 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Jubilar Guadalupense" - Aplicado en esta declaración (534)
99 1121 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Año Jubilar Guadalupense" - Pendiente de aplicación
100 1134 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Jornadas Mundiales Juventud 2011" - Deducción 2010
101 1147 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Jornadas Mundiales Juventud 2011" - Aplicado en esta declaración (535)
102 1160 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Jornadas Mundiales Juventud 2011" - Pendiente de aplicación
103 1173 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Conmemoración Milenio fundación Reino de Granada" - Deducción 2010
104 1186 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Conmemoración Milenio fundación Reino de Granada" - Aplicado en esta declaración (536)
110055 11119999 1133 NN DDeedduucccciioonneess iinncceennttiivvooss//eessttíímmuullooss iinnvv. eemmpprreess. -- EEjjeerrcciicciioo 22001100 -- RReeggíímmeenneess aappooyyoo -- ""CCoonnmmeemmoorraacciióónn MMiilleenniioo ffuunnddaacciióónn RReeiinnoo ddee GGrraannaaddaa"" -- PPeennddiieennttee ddee aapplliiccaacciióónn
106 1212 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Solar Decathlon Europe 2010 y 2012" - Deducción 2010
107 1225 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Solar Decathlon Europe 2010 y 2012" - Aplicado en esta declaración (537)
108 1238 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Solar Decathlon Europe 2010 y 2012" - Pendiente de aplicación
109 1251 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Google Lunar X Prize" - Deducción 2010
110 1264 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Google Lunar X Prize" - Aplicado en esta declaración (538)
111 1277 13 N Deducciones incentivos/estímulos inv. empres. - Ejercicio 2010 - Regímenes apoyo - "Google Lunar X Prize" - Pendiente de aplicación
112 1290 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10016>
113 1299 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 1300

# Pag. 46

Anexo A.3
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "17"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante Blanco
6 10 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Saldos ptes. - Inv. adquisición activos fijos -Saldo anterior
7 23 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Saldos ptes. - Inv. adquisición activos fijos - Aplicado en esta declaración (968)
8 36 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Saldos ptes. - Inv. adquisición activos fijos - Pendiente de aplicación
9 49 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Saldos ptes. - Restantes modalidades - Saldo anterior
10 62 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Saldos ptes. - Restantes modalidades - Aplicado en esta declaración (969)
11 75 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Saldos ptes. - Restantes modalidades - Pendiente de aplicación
12 88 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Investigación, desarrollo, innovación tecnológica - Deducción 2010
13 101 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Investigación, desarrollo, innovación tecnológica - Aplicado en esta declaración (970)
14 114 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Investigación, desarrollo, innovación tecnológica - Pendiente de aplicación
15 127 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Fomento tecnologías información y comunicación - Deducción 2010
16 140 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Fomento tecnologías información y comunicación - Aplicado en esta declaración (971)
17 153 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Fomento tecnologías información y comunicación - Pendiente de aplicación
18 166 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Actividades exportación - Deducción 2010
1199 117799 1133 NN DDeedduucccciioonneess iinncceennttiivvooss//eessttíímmuullooss iinnvv. eemmpprreess. -- RRéégg. EEsspp. iinnvv. CCaannaarriiaass -- EEjjeerrcciicciioo 22001100 -- LL.II.SS.:: AAccttiivviiddaaddeess eexxppoorrttaacciióónn -- AApplliiccaaddoo eenn eessttaa ddeeccllaarraacciióónn ((997722))
20 192 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Actividades exportación - Pendiente de aplicación
21 205 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - L.I.S.: Inversiones/gastos art. 38 - Deducción 2010
22 218 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - L.I.S.: Inversiones/gastos art. 38 - Aplicado en esta declaración (973)
23 231 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - L.I.S.: Inversiones/gastos art. 38 - Pendiente de aplicación
24 244 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - L.I.S.: Inversiones medioambientales - Deducción 2010
25 257 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - L.I.S.: Inversiones medioambientales - Aplicado en esta declaración (974)
26 270 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - L.I.S.: Inversiones medioambientales - Pendiente de aplicación
27 283 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Gastos formación profesional - Deducción 2010
28 296 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Gastos formación profesional - Aplicado en esta declaración (975)
29 309 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Gastos formación profesional - Pendiente de aplicación
30 322 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Creación empleo trabajadores minusválidos - Deducción 2010
31 335 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Creación empleo trabajadores minusválidos - Aplicado en esta declaración (976)
32 348 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Creación empleo trabajadores minusválidos - Pendiente de aplicación
33 361 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Contribuciones empresariales y aportaciones art. 43 - Deducción 2010
34 374 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Contribuciones empresariales y aportaciones art. 43 - Aplicado en esta declaración (977)
35 387 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. inv. Canarias - Ejercicio 2010 - L.I.S.: Contribuciones empresariales y aportaciones art. 43 - Pendiente de aplicación
36 400 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - Inversiones en la adquisición de activos fijos - Deducción 2010
37 413 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - Inversiones en la adquisición de activos fijos - Aplicado en esta declaración (978)
38 426 13 N Deducciones incentivos/estímulos inv. empres. - Rég. Esp. Inv. Canarias - Ejercicio 2010 - Inversiones en la adquisición de activos fijos - Pendiente de aplicación

# Pag. 47

Anexo A.3
Nº Posic. Long. Tipo Descripción Validación Contenido
39 439 13 N Deducciones incentivos/estímulos inv. empres. - Importe aplicado declaración - Importe total (979)
40 452 13 N Deducciones por incentivos y estímulos incentivos/estímulos inv. empres. - Importe aplicado declaración - Deducciones por incentivos y estímulos - Parte estatal (706)
41 465 13 N Deducciones por incentivos y estímulos incentivos/estímulos inv. empres. - Importe aplicado declaración - Deducciones por incentivos y estímulos - Parte autonómica (707)
42 478 13 N Reserva inversiones Canarias (Ley 19/1994) - Reserva inversiones Canarias 2006 - Importe dotaciones
43 491 13 N Reserva inversiones Canarias (Ley 19/1994) - Reserva inversiones Canarias 2006 - Materializaciones 2010 (980)
44 504 1 Num Reserva inversiones Canarias (Ley 19/1994) - Reserva inversiones Canarias 2006 - Clave ("0" a "5") (981)
45 505 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2007. Importe dotaciones (984)
46 518 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2007. Inversiones previstas A B y D art.27.4 (985)
47 531 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2007. Inversiones previstas C y D (2º a 6º) art.27.4 (986)
48 544 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2007. Pendiente materializar (987)
49 557 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2008. Dotación y materializaciones. Importe dotación (988)
50 570 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2008. Dotación y materializaciones. Inversiones A B y D (1º) art.27.4 (989)
51 583 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2008. Dotación y materializaciones. Inversiones C y D (2º a 6º) art.27.4 (990)
52 596 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2008. Dotación y materializaciones. Pendiente de materializar. (991)
53 609 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2009. Dotación y materializaciones. Importe dotación (992)
54 622 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2009. Dotación y materializaciones. Inversiones A B y D (1º) art.27.4 (993)
55 635 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2009. Dotación y materializaciones. Inversiones C y D (2º a 6º) art.27.4 (994)
56 648 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2009. Dotación y materializaciones. Pendiente de materializar. (995)
57 661 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2010. Dotación y materializaciones. Importe dotación (539)
58 674 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2010. Dotación y materializaciones. Inversiones A B y D (1º) art.27.4 (561)
59 687 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2010. Dotación y materializaciones. Inversiones C y D (2º a 6º) art.27.4 (562)
60 700 13 N Reserva inversiones Canarias (Ley 19/1994). Reserva inversiones Canarias 2010. Dotación y materializaciones. Pendiente de materializar. (563)
61 713 13 N Reserva inversiones Canarias (Ley 19/1994). - Inversiones anticipadas futuras dotaciones. Inversiones A B y D (1º) art.27.4 (996)
6622 772266 1133 NN RReesseerrvvaa iinnvveerrssiioonneess CCaannaarriiaass ((LLeeyy 1199//11999944)). -- IInnvveerrssiioonneess aannttiicciippaaddaass ffuuttuurraass ddoottaacciioonneess. IInnvveerrssiioonneess CC yy DD ((22ºº aa 66ºº)) aarrtt.2277.44 ((999977))
63 739 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10017>
64 748 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 749

# Pag. 48

Anexo B.1
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
25 249 13 N Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica (815)
26 262 13 N Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo (816)
27 275 13 N Deducciones Autonómicas - Aragón - Total deducciones autonómicas (717)
28 288 13 N Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (817)
29 301 13 N Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes discapacitados (818)
30 314 13 N Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes discapacitados (819)
31 327 13 N Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (820)
32 340 9 An Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - NIF arrendador (943)
33 349 13 N Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual - Importe (821)
34 362 13 N Deducciones Autonómicas - Asturias - Para fomento de autoempleo mujeres y jóvenes emprendedores (822)
35 375 13 N Deducciones Autonómicas - Asturias - Para fomento de autoempleo (823)
36 388 13 N Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (824)
37 401 13 N Deducciones Autonómicas - Asturias - Por adopción internacional de menores (825)
38 414 13 N Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones (826)
39 427 13 N Deducciones Autonómicas - Asturias - Para familias numerosas (827)
Página 48

# Pag. 49

Anexo B.1
Nº Posic. Long. Tipo Descripción Validación Contenido
40 440 13 N Deducciones Autonómicas - Asturias - Para familias monoparentales (828)
41 453 13 N Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (564)
42 466 13 N Deducciones Autonómicas - Asturias - Total deducciones autonómicas (717)
43 479 13 N Deducciones Autonómicas - Illes Balears - Por gastos adquisición libros de texto (829)
44 492 13 N Deducciones Autonómicas - Illes Balears - Para contribuyentes edad igual o superior a 65 años (830)
45 505 13 N Deducciones Autonómicas - Illes Balears - Por adquisición/rehabilitación vivienda habitual jóvenes (831)
46 518 9 An Deducciones Autonómicas - Illes Balears - Por arrendamiento de vivienda habitual por jóvenes - NIF arrendador (943)
47 527 13 N Deducciones Autonómicas - Illes Balears - Por arrendamiento de vivienda habitual por jóvenes - Importe (832)
48 540 13 N Deducciones Autonómicas - Illes Balears - Para los declarantes con minusvalía física/psíquica o descendientes con esa condición (833)
49 553 13 N Deducciones Autonómicas - Illes Balears - Para los declarantes titulares de fincas o terrrenos suelo rústico protegido (834)
50 566 13 N Deducciones Autonómicas - Illes Balears - Por adopción de hijos (835)
51 579 13 N Deducciones Autonómicas - Illes Balears - Por el impuesto transmisiones y AJD por adquisición vivienda habitual (836)
52 592 13 N Deducciones Autonómicas - Illes Balears - Por el impuesto transmisiones y AJD por adquisición vivienda habitual protegida (837)
53 605 13 N Deducciones Autonómicas - Illes Balears - Para el fomento del autoempleo (838)
54 618 13 N Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (717)
55 631 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10018>
56 640 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 641
Página 49

# Pag. 50

Anexo B.2
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
22 214 13 N Deducciones Autonómicas - Canarias - Total deducciones autonómicas (717)
23 227 9 An Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores, discapacitados - NIF arrendador (943)
24 236 13 N Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores, discapacitados - Importe (854)
25 249 13 N Deducciones Autonómicas - Cantabria - Por cuidado de familiares (855)
26 262 13 N Deducciones Autonómicas - Cantabria - Por adquisición o rehabilitación de 2ª vivienda en municipios con problemas de despoblación (856)
27 275 13 N Deducciones Autonómicas - Cantabria - Por donativos a fundaciones (857)
28 288 13 N Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (858)
29 301 13 N Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (717)
30 314 13 N Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (859)
31 327 13 N Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (860)
32 340 13 N Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (861)
33 353 13 N Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (862)
34 366 13 N Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (863)
35 379 13 N Deducciones Autonómicas - Castilla-La Mancha - Por cantidades donadas al Fondo Castellano-Manchego de Cooperación (864)
36 392 13 N Deducciones Autonómicas - Castilla-La Mancha - Por cantidades satisfechas adquisición/rehabilitación vivienda habitual (865)
37 405 20 An Deducciones Autonómicas - Castilla-La Mancha - Por cantidades satisfechas adquisición/rehabilitación vivienda habitual - nº identificación préstamo (942)
38 425 13 N Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (717)
39 438 13 N Deducciones Autonómicas - Castilla y León - Por familia numerosa (866)
Página 50

# Pag. 51

Anexo B.2
Nº Posic. Long. Tipo Descripción Validación Contenido
40 451 13 N Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (867)
41 464 13 N Deducciones Autonómicas - Castilla y León - Por adopción internacional (868)
42 477 13 N Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores (869)
43 490 13 N Deducciones Autonómicas - Castilla y León - Para contribuyentes 65 años o más afectados minusvalía (870)
44 503 13 N Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales (871)
45 516 13 N Deducciones Autonómicas - Castilla y León - Por cantidades donadas recuperación patrimonio histórico, cultural y natural (872)
46 529 13 N Deducciones Autonómicas - Castilla y León - Por cantidades invertidas recuperación patrimonio histórico, cultural y natural (873)
47 542 9 An Deducciones Autonómicas - Castilla y León - Por alquiler de vivienda habitual jóvenes - NIF arrendador (943)
48 551 13 N Deducciones Autonómicas - Castilla y León - Por alquiler de vivienda habitual jóvenes - Importe (874)
49 564 13 N Deducciones Autonómicas - Castilla y León - Para fomento autoempleo mujeres y jóvenes (875)
50 577 13 N Deducciones Autonómicas - Castilla y León - Por inversión instalaciones recursos energéticos renovables y ahorro agua (565)
51 590 13 N Deducciones Autonómicas - Castilla y León - Total deducciones autonómicas (717)
52 603 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10019>
53 612 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 613
Página 51

# Pag. 52

Anexo B.3
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
11 71 13 N Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudio universitarios de tercer ciclo (880)
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
26 262 13 N Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (717)
27 275 13 N Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (891)
28 288 13 N Deducciones Autonómicas - Galicia - Por familia numerosa (892)
29 301 13 N Deducciones Autonómicas - Galicia - Por cuidado hijos menores (893)
30 314 13 N Deducciones Autonómicas - Galicia - Por contribuyentes minusválidos = > 65 años que precisan ayuda de terceras personas (894)
31 327 13 N Deducciones Autonómicas - Galicia - Por gastos de nuevas tecnologías en hogares gallegos (895)
32 340 9 An Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - NIF arrendador (943)
33 349 13 N Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual - Importe (896)
34 362 13 N Deducciones Autonómicas - Galicia - Para fomento autoempleo hombres menores 35 años y mujeres cualquier edad (897)
35 375 13 N Deducciones Autonómicas - Galicia - Total deducciones autonómicas (717)
36 388 13 N Deducciones Autonómicas - Madrid - Por nacimiento o adopción hijos (898)
37 401 13 N Deducciones Autonómicas - Madrid - Por adopción internacional niños (899)
38 414 13 N Deducciones Autonómicas - Madrid - Por acogimiento familiar de menores (900)
39 427 13 N Deducciones Autonómicas - Madrid - Por acogimiento no remunerado de mayores 65 años y/o discapacitados (901)
40 440 9 An Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - NIF arrendador (943)
Página 52

# Pag. 53

Anexo B.3
Nº Posic. Long. Tipo Descripción Validación Contenido
41 449 13 N Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años - Importe (902)
42 462 13 N Deducciones Autonómicas - Madrid - Por donativos a fundaciones (903)
43 475 13 N Deducciones Autonómicas - Madrid - Por incremento costes financiación ajena para inversión en vivienda habitual (904)
44 488 13 N Deducciones Autonómicas - Madrid - Por gastos educativos (905)
45 501 13 N Deducciones Autonómicas - Madrid - Por inversión en vivienda habitual de nueva construcción (906)
46 514 13 N Deducciones Autonómicas - Madrid - Para familias con dos o más descendientes e ingresos reducidos (568)
47 527 13 N Deducciones Autonómicas - Madrid - Por inversión en adquisición de acciones y participaciones sociales de nuevas entidades (569)
48 540 13 N Deducciones Autonómicas - Madrid - Para el fomento del autoempleo de jóvenes menores de 35 años (586)
49 553 13 N Deducciones Autonómicas - Madrid - Por inversiones en entidades cotizadas en el Mercado Alternativo Bursátil (587)
50 566 13 N Deducciones Autonómicas - Madrid - Total deducciones autonómicas (717)
51 579 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10020>
52 588 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 589
Página 53

# Pag. 54

Anexo B.4
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
Nº Posic. Long. Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "100"
3 6 2 Num Página. OBLIGATORIO Constante "21"
4 8 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 9 1 A Indicador de página complementaria. Constante. Blanco
6 10 13 N Deducciones Autonómicas - Murcia - Por inversión en vivienda habitual por jóvenes de edad igual o inferior a 35 años (907)
7 23 13 N Deducciones Autonómicas - Murcia - Por donativos para la protección del patrimonio histórico Región Murcia (908)
8 36 13 N Deducciones Autonómicas - Murcia - Por gastos de guardería para hijos menores de 3 años (909)
9 49 13 N Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (910)
10 62 13 N Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (911)
11 75 13 N Deducciones Autonómicas - Murcia - Total deducciones autonómicas (717)
12 88 13 N Deducciones Autonómicas - La Rioja - Por nacimiento o adopción de segundo o ulterior hijo (912)
13 101 13 N Deducciones Autonómicas - La Rioja - Por inversión adquisición/rehabilitación vivienda habitual para jóvenes (913)
14 114 4 Num Deducciones Autonómicas - La Rioja - Por adquisición/rehabilitación 2ª vivienda en el medio rural. Código municipio (939)
15 118 13 N Deducciones Autonómicas - La Rioja - Por adquisición/rehabilitación 2ª vivienda en el medio rural (914)
16 131 13 N Deducciones Autonómicas - La Rioja - Por inversión no empresarial en adquisición de ordenadores personales (915)
1177 114444 1133 NN DDeedduucccciioonneess AAuuttoonnóómmiiccaass - LLaa RRiioojjaa - PPoorr iinnvveerrssiióónn rreehhaabbiilliittaacciióónn vviivviieennddaa hhaabbiittuuaall ((991166))
18 157 13 N Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (717)
19 170 13 N Deducciones Autonómicas - Comunidad Valenciana - Por nacimiento/adopción de hijos (917)
20 183 13 N Deducciones Autonómicas - Comunidad Valenciana - Por nacimiento/adopción múltiples (918)
21 196 13 N Deducciones Autonómicas - Comunidad Valenciana - Por nacimiento/adopción hijos discapacitados (919)
22 209 13 N Deducciones Autonómicas - Comunidad Valenciana - Por familia numerosa (920)
23 222 13 N Deducciones Autonómicas - Comunidad Valenciana - Por custodia en guarderías y primer ciclo educación infantil hijos menores de 3 años (921)
24 235 13 N Deducciones Autonómicas - Comunidad Valenciana - Por conciliación del trabajo con la vida familiar (922)
25 248 13 N Deducciones Autonómicas - Comunidad Valenciana - Por contribuyentes discapacitados de edad igual o superior a 65 años (923)
26 261 13 N Deducciones Autonómicas - Comunidad Valenciana - Por ascendientes > 75 años ó > 65 años discapacitados (924)
27 274 13 N Deducciones Autonómicas - Comunidad Valenciana - Por realización de labores no remuneradas en el hogar (925)
28 287 13 N Deducciones Autonómicas - Comunidad Valenciana - Por adquisición/rehabilitación vivienda con financiación ajena (926)
29 300 13 N Deducciones Autonómicas - Comunidad Valenciana - Por primera adquisición vivienda habitual para contribuyentes edad igual o inferior 35 años (927)
30 313 13 N Deducciones Autonómicas - Comunidad Valenciana - Por adquisición vivienda habitual discapacitados (928)
31 326 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades adquisición/rehabilitación vivienda habitual, procedentes ayudas públicas (929)
32 339 9 An Deducciones Autonómicas - Comunidad Valenciana - Por arrendamiento de vivienda habitual - NIF arrendador (943)
33 348 13 N Deducciones Autonómicas - Comunidad Valenciana - Por arrendamiento de vivienda habitual - Importe (930)
34 361 9 An Deducciones Autonómicas - Comunidad Valenciana - Por arrendamiento vivienda actividades distinto municipio - NIF arrendador (944)
35 370 13 N Deducciones Autonómicas - Comunidad Valenciana - Por arrendamiento vivienda actividades distinto municipio - Importe (931)
Página 54

# Pag. 55

Anexo B.4
Nº Posic. Long. Tipo Descripción Validación Contenido
36 383 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades inversiones fuentes energía renovables en vivienda habitual (932)
37 396 13 N Deducciones Autonómicas - Comunidad Valenciana - Por donaciones con finalidad ecológica (933)
38 409 13 N Deducciones Autonómicas - Comunidad Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (934)
39 422 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades donadas conservación, reparación y restauración Patrimonio Cultural Valenciano (935)
40 435 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades destinadas titulares conservación, etc. bienes Patrimonio Cultural Valenciano (936)
41 448 13 N Deducciones Autonómicas - Comunidad Valenciana - Por donaciones destinadas al fomento de la lengua valenciana (937)
42 461 13 N Deducciones Autonómicas - Comunidad Valenciana - Por incrementos costes financiación ajena en inversión vivienda habitual (938)
43 474 13 N Deducciones Autonómicas - Comunidad Valenciana - Por contribuyentes con dos o más descendientes (588)
44 487 13 N Deducciones Autonómicas - Comunidad Valenciana - Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (589)
45 500 13 N Deducciones Autonómicas - Comunidad Valenciana - Total deduciones autonómicas (717)
46 513 9 An Identificador de Fin de registro. OBLIGATORIO Constante </T10021>
47 522 2 An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total: 523
Página 55

# Pag. 56

I-D
Agencia Tributaria
Modelo 100 Diseño de registro
vers. 1.0 Impuesto sobre la Renta de las Personas Físicas 2010
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
Página 56