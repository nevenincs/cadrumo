# 100-00

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 17 | An | Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "<T100020160A0000>"
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
15 | *** | 18 | An | Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "</T100020160A0000>"
16 | *** | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total |  | Variable
 |  |  |  | (**) A cumplimentar por las entidades desarrolladoras (EEDD)
 |  |  |  | Idioma de la declaración: (E) Castellano, (C) Catalán, (G) Gallego, (V) Valenciano
 |  |  |  | Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
 |  |  |  | NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
 |  |  | Páginas Complementarias
 |  |  | PÁG | APARTADO | OCUR. | HOJAS
 |  |  | 1 | Vivienda habitual | 8 | 1
 |  |  | 3 | Aplicación de la disposición transitoria 4ª | 6 | 3
 |  |  | 4 | Inmuebles no afectos AAEE | 60 | 20
 |  |  | 4 | Inmuebles arrendados por ent.reg.atrib.rentas | 60 | 20
 |  |  | 4 | Inmuebles afectos AAEE | 60 | 20
 |  |  | 5 | (E1) Rtos. AAEE estim. directa | 6 | 2
 |  |  | 6 | (E2) Rtos. AAEE estim. objetiva | 6 | 3
 |  |  | 7 | (E3) Rtos. activ. agricolas | 6 | 3
 |  |  | 8 | (F) Regímenes especiales | 8 | 4
 |  |  | 9 | G2 Aplicación de la disposición transitoria 9ª | 9 | 5
 |  |  | 9 | (G2) G/P Instituciones de inversión colectiva | 60 | 20
 |  |  | 10 | (G2) G/P Acciones y participaciones negociadas | 60 | 20
 |  |  | 10 | (G2) G/P Otros elementos patrimoniales | 40 | 20
 |  |  | 11 | (G2) G/P Imputación a 2015 ejercicios anteriores | 15 | 5
 |  |  | 11 | (G3) G/P Imputación a 2015 diferim. reinversión | 15 | 5
 |  |  | 11 | ( G4) G/P cambio residencia fuera de España | 15 | 5
 |  |  | 12 | (I) Aport. sistemas previsión social | 4 | 2
 |  |  | 13 | (I) Aport. Sistemas previsión social a favor de discapacitados | 4 | 2
 |  |  | 13 | (I)Aport. patrim. proteg. discapacit. | 4 | 2
 |  |  | 13 | (I)Pens. Compens. A favor cónyuge | 4 | 2
 |  |  | 13 | (I)Aport. Deportistas profesionales | 4 | 2
 |  |  | 16 | Ded Descendientes discapacidad | 15 | 15
 |  |  | 16 | Ded Ascendientes discapacidad | 6 | 6
 |  |  | 16 | Ded Familia Numerosa | 3 | 3
 |  |  | 16 | Ded Familia monoparental con dos hijos sin anualidades por alimentos | 2 | 2
 |  |  | 16 | Regularizaciones | 15 | 15

# 100-01 

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 1 | An | Tipo de declaración (Ver Nota)
7 | 14 | 9 | An | Primer Declarante - NIF (01) | OBLIGATORIO
8 | 23 | 80 | A | Primer Declarante - Apellidos y nombre  (02) | OBLIGATORIO
9 | 103 | 4 | Num | Ejercicio | OBLIGATORIO | Constante 2016
10 | 107 | 2 | An | Periodo | OBLIGATORIO | Constante 0A
11 | 109 | 1 | A | Primer Declarante - Sexo "H" Hombre, "M" Mujer (05) | OBLIGATORIO
12 | 110 | 1 | Num | Primer Declarante -Estado Civil. "1" Soltero/a, "2" Casado/a, "3" Viudo/a, "4" Divorciado/a o Separado/a | OBLIGATORIO
13 | 111 | 8 | Num | Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año < 2017 (10) | OBLIGATORIO
14 | 119 | 1 | Num | Primer Declarante - Grado de discapacidad   "0", "1", "2" o "3" (11)
15 | 120 | 1 | Num | Primer Declarante - Cambio de domicilio "1" o cero (13)
16 | 121 | 5 | A | Primer Declarante - Domicilio habitual - Tipo de Vía (15)
17 | 126 | 5 | Num | Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Vía INE
18 | 131 | 50 | An | Primer Declarante - Domicilio habitual - Nombre de la Vía Pública (16)
19 | 181 | 3 | An | Primer Declarante - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
20 | 184 | 5 | Num | Primer Declarante - Domicilio habitual - Número de Casa (18)
21 | 189 | 3 | An | Primer Declarante - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
22 | 192 | 3 | An | Primer Declarante - Domicilio habitual - Bloque (20)
23 | 195 | 3 | An | Primer Declarante - Domicilio habitual - Portal (21)
24 | 198 | 3 | An | Primer Declarante - Domicilio habitual - Escalera (22)
25 | 201 | 3 | An | Primer Declarante - Domicilio habitual - Planta (23)
26 | 204 | 3 | An | Primer Declarante - Domicilio habitual - Puerta (24)
27 | 207 | 40 | An | Primer Declarante - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
28 | 247 | 30 | An | Primer Declarante - Domicilio habitual - Localidad / Población (26)
29 | 277 | 5 | Num | Primer Declarante - Domicilio habitual - Código postal (27)
30 | 282 | 5 | Num | Primer Declarante - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
31 | 287 | 30 | An | Primer Declarante - Domicilio habitual - Nombre del Municipio (28)
32 | 317 | 2 | Num | Primer Declarante - Domicilio habitual - Código provincia. De "01" a "52".
33 | 319 | 20 | An | Primer Declarante - Domicilio habitual - Provincia (29)
34 | 339 | 50 | An | Primer Declarante - Domicilio extranjero - Domicilio/Address (35)
35 | 389 | 40 | An | Primer Declarante - Domicilio extranjero - Datos complementarios del domicilio (36)
36 | 429 | 30 | An | Primer Declarante - Domicilio extranjero - Población / Ciudad (37)
37 | 459 | 10 | An | Primer Declarante - Domicilio extranjero - Código Postal (39)
38 | 469 | 30 | An | Primer Declarante - Domicilio extranjero - Provincia / Región / Estado (40)
39 | 499 | 30 | An | Primer Declarante - Domicilio extranjero - País. (41)
40 | 529 | 2 | An | Primer Declarante - Domicilio extranjero - Código País.  Código país ISO-3166 (alfabético 2 letras). (42)
41 | 531 | 2 | An | Primer Declarante - País de residencia en la UE (44)
42 | 533 | 28 | An | RESERVADO PARA LA AEAT
43 | 561 | 1 | Num | Primer Declarante - Nacionalidad "0" No consta; "1" Española; "2" Otra  (43)
44 | 562 | 1 | Num | Datos adicionales vivienda - Vivienda 1.Titularidad "1", "2", "3" o "4" (50) | OBLIGATORIO
45 | 563 | 5 | Num | Datos adicionales vivienda - Vivienda 1.Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
46 | 568 | 5 | Num | Datos adicionales vivienda - Vivienda 1.Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
47 | 573 | 1 | Num | Datos adicionales vivienda - Vivienda 1.Situación (clave) "1", "2", "3" o "4" (53)
48 | 574 | 20 | An | Datos adicionales vivienda - Vivienda 1.Referencia catastral (54)
49 | 594 | 1 | Num | Datos adicionales vivienda - Vivienda 2.Titularidad "0", "1", "2", "3" o "4" (50)
50 | 595 | 5 | Num | Datos adicionales vivienda - Vivienda 2. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
51 | 600 | 5 | Num | Datos adicionales vivienda - Vivienda 2. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
52 | 605 | 1 | Num | Datos adicionales vivienda - Vivienda 2.Situación (clave) "0", "1", "2", "3" o "4" (53)
53 | 606 | 20 | An | Datos adicionales vivienda - Vivienda 2. Referencia catastral (54)
54 | 626 | 1 | Num | Datos adicionales vivienda - Vivienda 3.Titularidad "0", "1", "2", "3" o "4" (50)
55 | 627 | 5 | Num | Datos adicionales vivienda - Vivienda 3. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
56 | 632 | 5 | Num | Datos adicionales vivienda - Vivienda 3. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
57 | 637 | 1 | Num | Datos adicionales vivienda - Vivienda 3. Situación (clave) "0", "1", "2", "3" o "4" (53)
58 | 638 | 20 | An | Datos adicionales vivienda - Vivienda 3. Referencia catastral (54)
59 | 658 | 1 | Num | Datos adicionales vivienda - Vivienda 4.Titularidad "0", "1", "2", "3" o "4" (50)
60 | 659 | 5 | Num | Datos adicionales vivienda - Vivienda 4. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
61 | 664 | 5 | Num | Datos adicionales vivienda - Vivienda 4. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
62 | 669 | 1 | Num | Datos adicionales vivienda - Vivienda 4. Situación (clave) "0", "1", "2", "3" o "4" (53)
63 | 670 | 20 | An | Datos adicionales vivienda - Vivienda 4. Referencia catastral (54)
64 | 690 | 1 | Num | Datos adicionales vivienda - Vivienda 5.Titularidad "0", "1", "2", "3" o "4" (50)
65 | 691 | 5 | Num | Datos adicionales vivienda - Vivienda 5. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
66 | 696 | 5 | Num | Datos adicionales vivienda - Vivienda 5. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
67 | 701 | 1 | Num | Datos adicionales vivienda - Vivienda 5. Situación (clave) "0", "1", "2", "3" o "4" (53)
68 | 702 | 20 | An | Datos adicionales vivienda - Vivienda 5. Referencia catastral (54)
69 | 722 | 1 | Num | Datos adicionales vivienda - Vivienda 6.Titularidad "0", "1", "2", "3" o "4" (50)
70 | 723 | 5 | Num | Datos adicionales vivienda - Vivienda 6. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
71 | 728 | 5 | Num | Datos adicionales vivienda - Vivienda 6. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
72 | 733 | 1 | Num | Datos adicionales vivienda - Vivienda 6. Situación (clave) "0", "1", "2", "3" o "4" (53)
73 | 734 | 20 | An | Datos adicionales vivienda - Vivienda 6. Referencia catastral (54)
74 | 754 | 1 | Num | Datos adicionales vivienda - Vivienda 7.Titularidad "0", "1", "2", "3" o "4" (50)
75 | 755 | 5 | Num | Datos adicionales vivienda - Vivienda 7. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
76 | 760 | 5 | Num | Datos adicionales vivienda - Vivienda 7. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
77 | 765 | 1 | Num | Datos adicionales vivienda - Vivienda 7. Situación (clave) "0", "1", "2", "3" o "4" (53)
78 | 766 | 20 | An | Datos adicionales vivienda - Vivienda 7. Referencia catastral (54)
79 | 786 | 1 | Num | Datos adicionales vivienda - Vivienda 8.Titularidad "0", "1", "2", "3" o "4" (50)
80 | 787 | 5 | Num | Datos adicionales vivienda - Vivienda 8. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51) | *
81 | 792 | 5 | Num | Datos adicionales vivienda - Vivienda 8. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52) | *
82 | 797 | 1 | Num | Datos adicionales vivienda - Vivienda 8. Situación (clave) "0", "1", "2", "3" o "4" (53)
83 | 798 | 20 | An | Datos adicionales vivienda - Vivienda 8. Referencia catastral (54)
84 | 818 | 9 | An | Datos adicionales vivienda - Nif Arrendador (55)
85 | 827 | 20 | An | Datos adicionales vivienda - Si no tiene NIF. Nº identificación en el país de residencia (56)
86 | 847 | 9 | An | Cónyuge - NIF (57)
87 | 856 | 80 | A | Cónyuge - Apellidos y nombre (58)
88 | 936 | 1 | A | Cónyuge - Sexo "H" Hombre, "M" Mujer (59]
89 | 937 | 8 | Num | Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero. (60)
90 | 945 | 1 | Num | Cónyuge - Grado de discapacidad   "0", "1", "2" o "3" (61)
91 | 946 | 1 | Num | Cónyuge - No residente que no es contribuyente del I.R.P.F. - "1" o cero (62)
92 | 947 | 1 | Num | Cónyuge - Cambio de domicilio "1" o cero (63)
93 | 948 | 5 | A | Cónyuge - Domicilio habitual - Tipo de Vía (15)
94 | 953 | 5 | Num | Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Vía INE
95 | 958 | 50 | An | Cónyuge - Domicilio habitual - Nombre de la Vía Pública (16)
96 | 1008 | 3 | An | Cónyuge - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
97 | 1011 | 5 | Num | Cónyuge - Domicilio habitual - Número de Casa (18)
98 | 1016 | 3 | An | Cónyuge - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
99 | 1019 | 3 | An | Cónyuge - Domicilio habitual - Bloque (20)
100 | 1022 | 3 | An | Cónyuge - Domicilio habitual - Portal (21)
101 | 1025 | 3 | An | Cónyuge - Domicilio habitual - Escalera (22)
102 | 1028 | 3 | An | Cónyuge - Domicilio habitual - Planta (23)
103 | 1031 | 3 | An | Cónyuge - Domicilio habitual - Puerta (24)
104 | 1034 | 40 | An | Cónyuge - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
105 | 1074 | 30 | An | Cónyuge - Domicilio habitual - Localidad / Población (26)
106 | 1104 | 5 | Num | Cónyuge - Domicilio habitual - Código postal (27)
107 | 1109 | 5 | Num | Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
108 | 1114 | 30 | An | Cónyuge - Domicilio habitual - Nombre del Municipio (28)
109 | 1144 | 2 | Num | Cónyuge - Domicilio habitual - Código provincia. De "01" a "52".
110 | 1146 | 20 | An | Cónyuge - Domicilio habitual - Provincia (29)
111 | 1166 | 50 | An | Cónyuge - Domicilio extranjero - Domicilio/Address (35)
112 | 1216 | 40 | An | Cónyuge - Domicilio extranjero - Datos complementarios del domicilio (36)
113 | 1256 | 30 | An | Cónyuge - Domicilio extranjero - Población / Ciudad (37)
114 | 1286 | 10 | An | Cónyuge - Domicilio extranjero - Código Postal (39)
115 | 1296 | 30 | An | Cónyuge - Domicilio extranjero - Provincia / Región / Estado (40)
116 | 1326 | 30 | An | Cónyuge - Domicilio extranjero - País (41)
117 | 1356 | 2 | An | Cónyuge - Domicilio extranjero - Código País (42)
118 | 1358 | 2 | An | Cónyuge - País de residencia en la UE (44)
119 | 1360 | 28 | An | RESERVADO PARA LA AEAT
120 | 1388 | 1 | Num | Cónyuge - Nacionalidad "0" No consta; "1" Española; "2" Otra (43)
121 | 1389 | 12 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
122 | 1401 | 9 | An | Representante -  N.I.F. (65)
123 | 1410 | 32 | An | Representante -  Apellidos y nombre o razón social (66)
124 | 1442 | 8 | Num | Devengo - Fecha de  finalización del período impositivo (fallecimiento 2016)  (DDMMAAAA) o cero (67)
125 | 1450 | 1 | Num | Opción de tributación. "1" Individual, "2" Conjunta.  Campo OBLIGATORIO (68) (69) | OBLIGATORIO
126 | 1451 | 2 | Num | Comunidad/Ciudad autónoma de residencia en 2016 - Clave (70) Incluido en el fichero COMAUTO.TXT | OBLIGATORIO
127 | 1453 | 13 | Num | Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
128 | 1466 | 21 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
129 | 1487 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
130 | 1500 | 600 | An | RESERVADO PARA LA A.E.A.T
131 | 2100 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10001000>
Total |  | 2111
 |  |  | Nota: | El Tipo de declaración puede ser: I (Ingreso), U (Domiciliación),  N (Negativa/Resultado cero), D (Solicitud de devolución) y R (Renuncia a la devolución)

# 100-02

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "02000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 9 | An | Hijos y descendientes - 1º -  N.I.F. (75)
7 | 22 | 60 | A | Hijos y descendientes - 1º -  Apellidos y nombre  (76)
8 | 82 | 8 | Num | Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año < 2017 o cero (77)
9 | 90 | 8 | Num | Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
10 | 98 | 1 | Num | Hijos y descendientes - 1º - Grado discapacidad   "0", "1", "2" o "3" (79)
11 | 99 | 1 | An | Hijos y descendientes - 1º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (80)
12 | 100 | 2 | Num | Hijos y descendientes - 1º - Nº de orden (81)
13 | 102 | 1 | An | Hijos y descendientes - 1º - Otras situaciones  clave:"1","2","3","4" o blanco  (82)
14 | 103 | 9 | An | Hijos y descendientes - 2º - N.I.F. (75)
15 | 112 | 60 | A | Hijos y descendientes - 2º - Apellidos y nombre  (76)
16 | 172 | 8 | Num | Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año < 2017 o cero (77)
17 | 180 | 8 | Num | Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año < 2017 o cero (78)
18 | 188 | 1 | Num | Hijos y descendientes - 2º - Grado discapacidad   "0", "1", "2" o "3"  (79)
19 | 189 | 1 | An | Hijos y descendientes - 2º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
20 | 190 | 2 | Num | Hijos y descendientes - 2º - Nº de orden (81)
21 | 192 | 1 | An | Hijos y descendientes - 2º - Otras situaciones  "1","2","3","4" o blanco  (82)
22 | 193 | 9 | An | Hijos y descendientes - 3º - N.I.F. (75)
23 | 202 | 60 | A | Hijos y descendientes - 3º - Apellidos y nombre  (76)
24 | 262 | 8 | Num | Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
25 | 270 | 8 | Num | Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
26 | 278 | 1 | Num | Hijos y descendientes - 3º - Grado discapacidad   "0", "1", "2" o "3"  (79)
27 | 279 | 1 | An | Hijos y descendientes - 3º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
28 | 280 | 2 | Num | Hijos y descendientes - 3º - Nº de orden (81)
29 | 282 | 1 | An | Hijos y descendientes - 3º - Otras situaciones  "1","2","3","4" o blanco  (82)
30 | 283 | 9 | An | Hijos y descendientes - 4º - N.I.F.  (75)
31 | 292 | 60 | A | Hijos y descendientes - 4º - Apellidos y nombre  (76)
32 | 352 | 8 | Num | Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
33 | 360 | 8 | Num | Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
34 | 368 | 1 | Num | Hijos y descendientes - 4º - Grado discapacidad   "0", "1", "2" o "3"  (79)
35 | 369 | 1 | An | Hijos y descendientes - 4º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
36 | 370 | 2 | Num | Hijos y descendientes - 4º - Nº de orden (81)
37 | 372 | 1 | An | Hijos y descendientes - 4º - Otras situaciones  "1","2","3","4" o blanco  (82)
38 | 373 | 9 | An | Hijos y descendientes - 5º - N.I.F. (75)
39 | 382 | 60 | A | Hijos y descendientes - 5º - Apellidos y nombre  (76)
40 | 442 | 8 | Num | Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
41 | 450 | 8 | Num | Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
42 | 458 | 1 | Num | Hijos y descendientes - 5º - Grado discapacidad   "0", "1", "2" o "3"  (79)
43 | 459 | 1 | An | Hijos y descendientes - 5º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
44 | 460 | 2 | Num | Hijos y descendientes - 5º - Nº de orden (81)
45 | 462 | 1 | An | Hijos y descendientes - 5º - Otras situaciones  "1","2","3","4" o blanco  (82)
46 | 463 | 9 | An | Hijos y descendientes - 6º - N.I.F. (75)
47 | 472 | 60 | A | Hijos y descendientes - 6º - Apellidos y nombre  (76)
48 | 532 | 8 | Num | Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
49 | 540 | 8 | Num | Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
50 | 548 | 1 | Num | Hijos y descendientes - 6º - Grado discapacidad  "0", "1", "2" o "3" (79)
51 | 549 | 1 | An | Hijos y descendientes - 6º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
52 | 550 | 2 | Num | Hijos y descendientes - 6º - Nº de orden (81)
53 | 552 | 1 | An | Hijos y descendientes - 6º - Otras situaciones  "1","2","3","4" o blanco  (82)
54 | 553 | 9 | An | Hijos y descendientes - 7º - N.I.F.  (75)
55 | 562 | 60 | A | Hijos y descendientes - 7º - Apellidos y nombre  (76)
56 | 622 | 8 | Num | Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
57 | 630 | 8 | Num | Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
58 | 638 | 1 | Num | Hijos y descendientes - 7º - Grado discapacidad  "0", "1", "2" o "3" (79)
59 | 639 | 1 | An | Hijos y descendientes - 7º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
60 | 640 | 2 | Num | Hijos y descendientes - 7º - Nº de orden (81)
61 | 642 | 1 | An | Hijos y descendientes - 7º - Otras situaciones  "1","2","3","4" o blanco  (82)
62 | 643 | 9 | An | Hijos y descendientes - 8º - N.I.F. (75)
63 | 652 | 60 | A | Hijos y descendientes - 8º - Apellidos y nombre  (76)
64 | 712 | 8 | Num | Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
65 | 720 | 8 | Num | Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
66 | 728 | 1 | Num | Hijos y descendientes - 8º - Grado discapacidad "0", "1", "2" o "3"  (79)
67 | 729 | 1 | An | Hijos y descendientes - 8º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (80)
68 | 730 | 2 | Num | Hijos y descendientes - 8º - Nº de orden (81)
69 | 732 | 1 | An | Hijos y descendientes - 8º - Otras situaciones  "1","2","3","4" o blanco  (82)
70 | 733 | 9 | An | Hijos y descendientes - 9º - N.I.F. (75)
71 | 742 | 60 | A | Hijos y descendientes - 9º - Apellidos y nombre  (76)
72 | 802 | 8 | Num | Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
73 | 810 | 8 | Num | Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
74 | 818 | 1 | Num | Hijos y descendientes - 9º - Grado discapacidad  "0", "1", "2" o "3"  (79)
75 | 819 | 1 | An | Hijos y descendientes - 9º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
76 | 820 | 2 | Num | Hijos y descendientes - 9º - Nº de orden (81)
77 | 822 | 1 | An | Hijos y descendientes - 9º - Otras situaciones  "1","2","3","4" o blanco  (82)
78 | 823 | 9 | An | Hijos y descendientes - 10º - N.I.F.  (75)
79 | 832 | 60 | A | Hijos y descendientes - 10º - Apellidos y nombre  (76)
80 | 892 | 8 | Num | Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
81 | 900 | 8 | Num | Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
82 | 908 | 1 | Num | Hijos y descendientes - 10º - Grado discapacidad "0", "1", "2" o "3"  (79)
83 | 909 | 1 | An | Hijos y descendientes - 10º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
84 | 910 | 2 | Num | Hijos y descendientes - 10º - Nº de orden (81)
85 | 912 | 1 | An | Hijos y descendientes - 10º - Otras situaciones  "1","2","3","4" o blanco  (82)
86 | 913 | 9 | An | Hijos y descendientes - 11º - N.I.F. (75)
87 | 922 | 60 | A | Hijos y descendientes - 11º - Apellidos y nombre  (76)
88 | 982 | 8 | Num | Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
89 | 990 | 8 | Num | Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
90 | 998 | 1 | Num | Hijos y descendientes - 11º - Grado discapacidad "0", "1", "2" o "3"  (79)
91 | 999 | 1 | An | Hijos y descendientes - 11º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
92 | 1000 | 2 | Num | Hijos y descendientes - 11º - Nº de orden (81)
93 | 1002 | 1 | An | Hijos y descendientes - 11º - Otras situaciones  "1","2","3","4" o blanco  (82)
94 | 1003 | 9 | An | Hijos y descendientes - 12º - N.I.F. (75)
95 | 1012 | 60 | A | Hijos y descendientes - 12º - Apellidos y nombre  (76)
96 | 1072 | 8 | Num | Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (77)
97 | 1080 | 8 | Num | Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2017 o cero (78)
98 | 1088 | 1 | Num | Hijos y descendientes - 12º - Grado discapacidad  "0", "1", "2" o "3"  (79)
99 | 1089 | 1 | An | Hijos y descendientes - 12º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
100 | 1090 | 2 | Num | Hijos y descendientes - 12º - Nº de orden (81)
101 | 1092 | 1 | An | Hijos y descendientes - 12º - Otras situaciones  "1","2","3","4" o blanco  (82)
102 | 1093 | 2 | Num | Hijos y descendientes - Fallecido 2016 - Nº Orden (83)
103 | 1095 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (84)
104 | 1103 | 2 | Num | Hijos y descendientes - Fallecido 2016 - Nº Orden (83)
105 | 1105 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (84)
106 | 1113 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
107 | 1122 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
108 | 1131 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
109 | 1140 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
110 | 1149 | 9 | An | Hijos y descendientes - Otro progenitor 1 - Nif (85)
111 | 1158 | 60 | A | Hijos y descendientes - Otro progenitor 1 - Apellidos y nombre (86)
112 | 1218 | 1 | Num | Hijos y descendientes - Otro progenitor 1 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
113 | 1219 | 9 | An | Hijos y descendientes - Otro progenitor 2 - Nif (85)
114 | 1228 | 60 | A | Hijos y descendientes - Otro progenitor 2 - Apellidos y nombre (86)
115 | 1288 | 1 | Num | Hijos y descendientes - Otro progenitor 2 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
116 | 1289 | 9 | An | Hijos y descendientes - Otro progenitor 3 - Nif (85)
117 | 1298 | 60 | A | Hijos y descendientes - Otro progenitor 3 - Apellidos y nombre (86)
118 | 1358 | 1 | Num | Hijos y descendientes - Otro progenitor 3 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
119 | 1359 | 9 | An | Hijos y descendientes - Otro progenitor 4 - Nif (85)
120 | 1368 | 60 | A | Hijos y descendientes - Otro progenitor 4 - Apellidos y nombre (86)
121 | 1428 | 1 | Num | Hijos y descendientes - Otro progenitor 4 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
122 | 1429 | 24 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
123 | 1453 | 9 | An | Ascendientes mayores 65 años o discapacitados - 1º - N.I.F.  (90)
124 | 1462 | 60 | A | Ascendientes mayores 65 años o discapacitados - 1º - Apellidos y nombre (91)
125 | 1522 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (92)
126 | 1530 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Grado discapacidad  "0", "1", "2" o "3" (93)
127 | 1531 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Vinculación  clave:"1", "2" o blanco (94)
128 | 1532 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Convivencia   "2" a "9" o blanco (95)
129 | 1533 | 9 | An | Ascendientes mayores 65 años o discapacitados - 2º - N.I.F.  (90)
130 | 1542 | 60 | A | Ascendientes mayores 65 años o discapacitados - 2º - Apellidos y nombre (91)
131 | 1602 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (92)
132 | 1610 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Grado discapacidad  "0", "1", "2" o "3"  (93)
133 | 1611 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Vinculación clave:"1", "2" o blanco  (94)
134 | 1612 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Convivencia  "2" a "9" o blanco  (95)
135 | 1613 | 9 | An | Ascendientes mayores 65 años o discapacitados - 3º - N.I.F.  (90)
136 | 1622 | 60 | A | Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
137 | 1682 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año < 2017 o cero (92)
138 | 1690 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Grado discapacidad  "0", "1", "2" o "3"  (93)
139 | 1691 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Vinculación  clave:"1", "2" o blanco  (94)
140 | 1692 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Convivencia   "2" a "9" o blanco  (95)
141 | 1693 | 9 | An | Ascendientes mayores 65 años o discapacitados - 4º - N.I.F.  (90)
142 | 1702 | 60 | A | Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
143 | 1762 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2017 o cero (92)
144 | 1770 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Grado discapacidad  "0", "1", "2" o "3" (93)
145 | 1771 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Vinculación  clave:"1", "2" o blanco  (94)
146 | 1772 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Convivencia  "2" a "9" o blanco  (95)
147 | 1773 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2016 - Nif (96)
148 | 1782 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
149 | 1790 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2016 - Nif (96)
150 | 1799 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
151 | 1807 | 1 | A | Asignación tributaria a la Iglesia Católica. "X" o  blanco. (105)
152 | 1808 | 1 | A | Asignación de cantidades a actividades de interés general consideradas de interés social. "X" o  blanco. (106)
153 | 1809 | 1 | Num | Declaración complementaria - Si es complementaria por atrasos de rendimientos del trabajo, etc.  "1" o cero (121)
154 | 1810 | 1 | Num | Declaración complementaria - Si es complementaria por haberse producido alguna de las circunstancias previstas. "1" o cero (122)
155 | 1811 | 1 | Num | Declaración complementaria - Si es complementaria a devolver. "1" o cero (123)
156 | 1812 | 1 | Num | Declaración complementaria - Si es complementaria por traslado de residencia a otro Estado miembro, "1" o cero (124)
157 | 1813 | 1 | Num | Declaración complementaria - Está motivada por haberse producido las circunstancias previstas en art. 95 bis Ley (125)
158 | 1814 | 1 | Num | Declaración complementaria - Estar motivada por haberse producido la circunstancia previstas en art. 80.4  o 81.3 LIS (126)
159 | 1815 | 1 | Num | Declaración complementaria - Si es complementaria en supuestos distintos "1" o cero (120)
160 | 1816 | 1 | Num | Solicitud rectificación de autoliquidación - Por resultar una cantidad a devolver > a la solicitada o una cantidad a ingresar <. "1" o cero [127]
161 | 1817 | 600 | An | RESERVADO PARA LA A.E.A.T
162 | 2417 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10002000>
Total |  | 2428

# 100-03

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. |  | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "03000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N |  | (A) Rdto. Trabajo - Retribuciones dinerarias. Importe íntegro (001)
7 | 26 | 13 | N |  | Rdto. Trabajo - Retribuciones en especie - Valoracion (002)
8 | 39 | 13 | N |  | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta (003)
9 | 52 | 13 | N |  | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta repercutidos (004)
10 | 65 | 13 | N |  | Rdto. Trabajo - Retribuciones en especie - Importe íntegro (005)
11 | 78 | 13 | N |  | Rdto. Trabajo - Contribuciones Planes Pensiones y Mutualidades Previsión Social  (006)
12 | 91 | 13 | N |  | Rdto. Trabajo - Contribuciones empresariales a seguros colectivos dependencia. Imputado al contribuyente (007)
13 | 104 | 13 | N |  | Rdto. Trabajo - Aportaciones al patrimonio protegido de discapacitados - Importe (008)
14 | 117 | 13 | N |  | Rdto. Trabajo - Reducciones (009)
15 | 130 | 13 | N |  | Rdto. Trabajo - Total ingresos íntegros computables (010)
16 | 143 | 13 | N |  | Rdto. Trabajo - Cotizaciones Seguridad Social/Mutual. grales. funcionarios/cotiz. colegios huerfanos (011)
17 | 156 | 13 | N |  | Rdto. Trabajo - Cuotas satisfechas a sindicatos (012)
18 | 169 | 13 | N |  | Rdto. Trabajo - Cuotas a colegios profesionales (013)
19 | 182 | 13 | N |  | Rdto. Trabajo - Gastos defensa jurídica derivados litigios con empleador (014)
20 | 195 | 13 | N |  | Rdto. Trabajo - Rdto. Neto previo (015)
21 | 208 | 13 | N |  | Rdto. Trabajo - Otros gastos deducibles (016)
22 | 221 | 13 | N |  | Rdto. Trabajo - Incremento contribuyentes desempleados con traslado de residencia  (017)
23 | 234 | 13 | N |  | Rdto. Trabajo - Incremento para trabajadores activos discapacitados (018)
24 | 247 | 13 | N |  | Rdto. Trabajo - Rendimiento neto  (019)
25 | 260 | 13 | N |  | Rdto. Trabajo - Reducción obtención rendimientos de trabajo. Cuantía aplicable con carácter general (020)
26 | 273 | 13 | N |  | Rdto. Trabajo - Rendimiento neto reducido (021)
27 | 286 | 13 | N |  | (B) Rdto.cap.mob.- Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (022)
28 | 299 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro  - Intereses de activos financieros con derecho a bonificación (023)
29 | 312 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (024)
30 | 325 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (025)
31 | 338 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros (026)
32 | 351 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (027)
33 | 364 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Rdtos. procedentes de rentas que tengan por causa la imposición de capitales (028)
34 | 377 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Rdtos. derivados de valores de deuda subordinada o participaciones preferentes. (029)
35 | 390 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Rdtos. procedentes de seguros de vida, depósitos financieros que instrumenten Planes Ahorro (030)
36 | 403 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Total ingresos íntegros (031)
37 | 416 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Gastos fiscalmente deducibles (032)
38 | 429 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto (033)
39 | 442 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (034]
40 | 455 | 13 | N |  | Rdto.cap.mob.- Base imponible ahorro - Rendimiento neto reducido (035)
41 | 468 | 1 | Num |  | Aplicación DT 4 - Número de hojas adicionales que se adjjuntan
42 | 469 | 1 | Tit | C | Aplicación DT 4 - Contribuyente 1  "0" a "9" (036)
43 | 470 | 13 | N | C | Aplicación DT 4 - Contribuyente 1 - Importe total acumulado del capital diferido percibido en 2015 (037)
44 | 483 | 13 | N | C | Aplicación DT 4 - Contribuyente 1 - Importe total de los capitales diferidos correspondientes a seguros de vida (038)
45 | 496 | 1 | Tit | C | Aplicación DT 4 - Contribuyente 2  "0" a "9" (036)
46 | 497 | 13 | N | C | Aplicación DT 4 - Contribuyente 2 - Importe total acumulado del capital diferido percibido en 2015 (037)
47 | 510 | 13 | N | C | Aplicación DT 4 - Contribuyente 2 - Importe total de los capitales diferidos correspondientes a seguros de vida (038)
48 | 523 | 13 | N |  | (B) Rdto.cap.mob.- Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (039)
49 | 536 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (040)
50 | 549 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (041)
51 | 562 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (042)
52 | 575 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (043)
53 | 588 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Total ingresos íntegros (044)
54 | 601 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Gastos fiscalmente deducibles (045)
55 | 614 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Rendimiento neto (046)
56 | 627 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (047)
57 | 640 | 13 | N |  | Rdto.cap.mob.- Base imponible general - Rendimiento neto reducido (048)
58 | 653 | 600 | An |  | RESERVADO PARA LA A.E.A.T
59 | 1253 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10003000>
Total: |  | 1264

# 100-04

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com. | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "04000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | Nº de hojas adicionales que se adjuntan
7 | 15 | 1 | Tit | C | (C) Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Contribuyente "0" a "9" (050)
8 | 16 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (051) | *
9 | 21 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Porcentaje usufructo (3 enteros y 2 decimales) (052) | *
10 | 26 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Naturaleza (053)
11 | 27 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Uso o destino. Clave   (054)
12 | 28 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Situación "0", "1", "2", "3" o "4" (055)
13 | 29 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Referencia catastral (056)
14 | 49 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (057) | *
15 | 54 | 3 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Número de días (058)
16 | 57 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. A disposición. Renta imputada (059)
17 | 70 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Ingresos íntegros computables (060)
18 | 83 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (061)
19 | 96 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Importe (062)
20 | 109 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (063)
21 | 122 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Títulos, recargos y tasas (064)
22 | 135 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Saldos dudoso cobro (065)
23 | 148 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Cantidades devengadas por terceros (066)
24 | 161 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Amortización bienes inmuebles (067)
25 | 174 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Amortización bienes muebles (068)
26 | 187 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Gastos deducibles. Otros gastos fiscalmente deducibles (069)
27 | 200 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto (070)
28 | 213 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (071)
29 | 226 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Reducción rendimientos más de 2 años (072)
30 | 239 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento mínimo computable parentesco (073)
31 | 252 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 1. Arrendado o cedido. Rendimiento neto reducido (074)
32 | 265 | 1 | Tit | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Contribuyente "0" a "9" (050)
33 | 266 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (051) | *
34 | 271 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Porcentaje usufructo (3 enteros y 2 decimales)  (052) | *
35 | 276 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Naturaleza (053)
36 | 277 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Uso o destino. Clave   (054)
37 | 278 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Situación "0", "1", "2", "3" o "4" (055)
38 | 279 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Referencia catastral (056)
39 | 299 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (057) | *
40 | 304 | 3 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Número de días (058)
41 | 307 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. A disposición. Renta imputada (059)
42 | 320 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Ingresos íntegros computables (060)
43 | 333 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (061)
44 | 346 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Importe (062)
45 | 359 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (063)
46 | 372 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Títulos, recargos y tasas (064)
47 | 385 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Saldos dudoso cobro (065)
48 | 398 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Cantidades devengadas por terceros (066)
49 | 411 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Amortización bienes inmuebles (067)
50 | 424 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Amortización bienes muebles (068)
51 | 437 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Gastos deducibles. Otros gastos fiscalmente deducibles (069)
52 | 450 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto (070)
53 | 463 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (071)
54 | 476 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Reducción rendimientos más de 2 años (072)
55 | 489 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento mínimo computable parentesco (073)
56 | 502 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble 2. Arrendado o cedido. Rendimiento neto reducido (074)
57 | 515 | 13 | N |  | Bienes inmuebles no afectos. Rentas totales . Suma de rentas inmobiliarias imputadas (075)
58 | 528 | 13 | N |  | Bienes inmuebles no afectos. Rentas totales . Suma rendimientos netos reducidos del capital inmobiliario (076)
59 | 541 | 3 | Num |  | Número de inmuebles en declaración conjunta (Reservado para la Administración)
60 | 544 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Contribuyente "0" a "9" (077)
61 | 545 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Nº Identificación fiscal entidad (078)
62 | 565 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Porcentaje titularidad (3 enteros y 2 decimales) (079) | *
63 | 570 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Naturaleza (080)
64 | 571 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Situación "0", "1", "2", "3" o "4" (081)
65 | 572 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Referencia catastral (082)
66 | 592 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. No Residente (083)
67 | 593 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Contribuyente "0" a "9" (077)
68 | 594 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Nº Identificación fiscal entidad (078)
69 | 614 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Porcentaje titularidad (3 enteros y 2 decimales) (079) | *
70 | 619 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Naturaleza (080)
71 | 620 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Situación "0", "1", "2", "3" o "4" (081)
72 | 621 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Referencia catastral (082)
73 | 641 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. No Residente (083)
74 | 642 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Contribuyente "0" a "9" (077)
75 | 643 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Nº Identificación fiscal entidad (078)
76 | 663 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Porcentaje titularidad (3 enteros y 2 decimales) (079) | *
77 | 668 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Naturaleza (080)
78 | 669 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Situación "0", "1", "2", "3" o "4" (081)
79 | 670 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Referencia catastral (082)
80 | 690 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. No Residente (083)
81 | 691 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 1. Contribuyente "0" a "9" (084)
82 | 692 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (085) | *
83 | 697 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje usufructo (3 enteros y 2 decimales)  (086) | *
84 | 702 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Naturaleza (clave) (087)
85 | 703 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1.  Situación "0", "1", "2", "3" o "4" (088)
86 | 704 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 1.  Referencia catastral (089)
87 | 724 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 2. Contribuyente "0" a "9" (084)
88 | 725 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (085) | *
89 | 730 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje usufructo (3 enteros y 2 decimales)  (086) | *
90 | 735 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Naturaleza (clave) (087)
91 | 736 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2.  Situación "0", "1", "2", "3" o "4" (088)
92 | 737 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 2.  Referencia catastral (089)
93 | 757 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 3. Contribuyente "0" a "9" (084)
94 | 758 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (085) | *
95 | 763 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje usufructo (3 enteros y 2 decimales)  (086) | *
96 | 768 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Naturaleza (clave) (087)
97 | 769 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3.  Situación "0", "1", "2", "3" o "4" (088)
98 | 770 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 3.  Referencia catastral (089)
99 | 790 | 600 | An |  | RESERVADO PARA LA A.E.A.T
100 | 1390 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10004000>
Total: |  | 1401

# 100-05

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com. | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "05000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | Nº de hojas adicionales si se declaran más de 3 Actividades a las que resulte aplicable un mismo régimen
7 | 14 | 1 | Tit | C | (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Contribuyente  "0" a "9" (090)
8 | 15 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Tipo actividad. Clave (Blanco o de "1" a "5") (091)
9 | 16 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Epígrafe IAE (092) (**)
10 | 21 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Modalidad aplicable "0" no consta "N" 1  o "S" 2 [93]
11 | 22 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Criterio cobros/pagos. "1" o cero. (094)
12 | 23 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Explotación (095)
13 | 36 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Otros ingresos (096)
14 | 49 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Autoconsumo bienes/servicios (097)
15 | 62 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Transmisión elementos patrimoniales: exceso amortización deducida (098)
16 | 75 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Total ingresos computables (099)
17 | 88 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Consumos de explotación (100)
18 | 101 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Sueldos y salarios (101)
19 | 114 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Seguridad Social (102)
20 | 127 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros gastos de personal (103)
21 | 140 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Arrendamientos y cánones (104)
22 | 153 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Reparación y conservación (105)
23 | 166 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Servicios profesionales independientes (106)
24 | 179 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros servicios exteriores (107]
25 | 192 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Tributos fiscalmente deducibles (108)
26 | 205 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Gastos financieros (109)
27 | 218 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Amortizaciones (110)
28 | 231 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Pérdidas por insolvencia de deudores  (111)
29 | 244 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (convenios) (112)
30 | 257 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (gastos) (113)
31 | 270 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros conceptos fiscalmente deducibles (114)
32 | 283 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Suma  (115)
33 | 296 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Normal - Provisiones (116)
34 | 309 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Normal - Total gastos deducibles (117)
35 | 322 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Diferencia (118)
36 | 335 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (119)
37 | 348 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Total gastos deducibles (120)
38 | 361 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Rdto. neto (121)
39 | 374 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Reducciones (122)
40 | 387 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -1- Rdto. neto reducido (123)
41 | 400 | 1 | Tit | C | (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Contribuyente  "0" a "9" (090)
42 | 401 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Tipo actividad. Clave (Blanco o de "1" a "5") (091)
43 | 402 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Epígrafe IAE (092) (**)
44 | 407 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Modalidad aplicable "0" no consta "N" 1  o "S" 2 [93]
45 | 408 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Criterio cobros/pagos. "1" o cero. (094)
46 | 409 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Explotación (095)
47 | 422 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Otros ingresos (096)
48 | 435 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Autoconsumo bienes/servicios (097)
49 | 448 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Transmisión elementos patrimoniales: exceso amortización deducida (098)
50 | 461 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Total ingresos computables (099)
51 | 474 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Consumos de explotación (100)
52 | 487 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Sueldos y salarios (101)
53 | 500 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Seguridad Social (102)
54 | 513 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos de personal (103)
55 | 526 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Arrendamientos y cánones (104)
56 | 539 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Reparación y conservación (105)
57 | 552 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Servicios profesionales independientes (106)
58 | 565 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros servicios exteriores (107]
59 | 578 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Tributos fiscalmente deducibles (108)
60 | 591 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Gastos financieros (109)
61 | 604 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Amortizaciones (110)
62 | 617 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Pérdidas por insolvencia de deudores  (111)
63 | 630 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (convenios) (112)
64 | 643 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (gastos) (113)
65 | 656 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros conceptos fiscalmente deducibles (114)
66 | 669 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Suma  (115)
67 | 682 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Normal - Provisiones (116)
68 | 695 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Normal - Total gastos deducibles (117)
69 | 708 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Diferencia (118)
70 | 721 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (119)
71 | 734 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Total gastos deducibles (120)
72 | 747 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto. neto (121)
73 | 760 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Reducciones (122)
74 | 773 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -2- Rdto. neto reducido (123)
75 | 786 | 1 | Tit | C | (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Contribuyente  "0" a "9" (090)
76 | 787 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Tipo actividad. Clave (Blanco o de "1" a "5") (091)
77 | 788 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Epígrafe IAE (092) (**)
78 | 793 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Modalidad aplicable "0" no consta "N" 1  o "S" 2 [93]
79 | 794 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Criterio cobros/pagos. "1" o cero. (094)
80 | 795 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Explotación (095)
81 | 808 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Otros ingresos (096)
82 | 821 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Autoconsumo bienes/servicios (097)
83 | 834 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Transmisión elementos patrimoniales: exceso amortización deducida (098)
84 | 847 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Total ingresos computables (099)
85 | 860 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Consumos de explotación (100)
86 | 873 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Sueldos y salarios (101)
87 | 886 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Seguridad Social (102)
88 | 899 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos de personal (103)
89 | 912 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Arrendamientos y cánones (104)
90 | 925 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Reparación y conservación (105)
91 | 938 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Servicios profesionales independientes (106)
92 | 951 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros servicios exteriores (107]
93 | 964 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Tributos fiscalmente deducibles (108)
94 | 977 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Gastos financieros (109)
95 | 990 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Amortizaciones (110)
96 | 1003 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Pérdidas por insolvencia de deudores  (111)
97 | 1016 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (convenios) (112)
98 | 1029 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (gastos) (113)
99 | 1042 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros conceptos fiscalmente deducibles (114)
100 | 1055 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Suma  (115)
101 | 1068 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Normal - Provisiones (116)
102 | 1081 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Normal - Total gastos deducibles (117)
103 | 1094 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Diferencia (118)
104 | 1107 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (119)
105 | 1120 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Total gastos deducibles (120)
106 | 1133 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto. neto (121)
107 | 1146 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Reducciones (122)
108 | 1159 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -1- Rdto. neto reducido (123)
109 | 1172 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Suma de rendimientos netos reducidos (126)
110 | 1185 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción ejercicio determinadas actividades (artículo 32.2.1º) (127)
111 | 1198 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción ejercicio determinadas actividades (artículo 32.2.3º) (128)
112 | 1211 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Reducción por inicio de una actividad económica (129)
113 | 1224 | 13 | N |  | Rdto.actv.econ.est.directa - Rdto.neto reducido total en estimación directa - Rendimiento neto reducido total  (130)
114 | 1237 | 600 | An |  | RESERVADO PARA LA A.E.A.T
115 | 1837 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10005000>
Total: |  | 1848
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignarán las tres cifras seguidas de dos blancos.

# 100-06

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "06000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | Nº de hojas adicionales si se declaran más de 2 actividades
7 | 14 | 1 | Tit | C | (E2) Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Contribuyente titular actividad (131)  "0" a "9"
8 | 15 | 5 | An | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Clasificación IAE (132) (**)
9 | 20 | 1 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (133)
10 | 21 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Definición
11 | 45 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales) | *
12 | 54 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales) | *
13 | 65 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Definición
14 | 89 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales) | *
15 | 98 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales) | *
16 | 109 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Definición
17 | 133 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales) | *
18 | 142 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales) | *
19 | 153 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Definición
20 | 177 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales) | *
21 | 186 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales) | *
22 | 197 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Definición
23 | 221 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales) | *
24 | 230 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales) | *
25 | 241 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Definición
26 | 265 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales) | *
27 | 274 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales) | *
28 | 285 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Definición
29 | 309 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales) | *
30 | 318 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales) | *
31 | 329 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma)  (134)
32 | 342 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo  (135)
33 | 355 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (136)
34 | 368 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (137)
35 | 381 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (138) | *
36 | 385 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (139) | *
37 | 389 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (140) | *
38 | 393 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (141) | *
39 | 397 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (142) | *
40 | 401 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto de módulos (143)
41 | 414 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción de carácter general (144)
42 | 427 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (145)
43 | 440 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Gastos extraordinarios circunstancias  excepcionales (146)
44 | 453 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Otras percepciones empresariales (147)
45 | 466 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª -Rendimiento neto actividad (148)
46 | 479 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción rdtos. más de 2 años o forma irregular (149)
47 | 492 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rendimiento neto reducido (150)
48 | 505 | 1 | Tit | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Contribuyente titular actividad (131)  "0" a "9"
49 | 506 | 5 | An | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Clasificación IAE (132) (**)
50 | 511 | 1 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Criterio cobros/pagos: "1" ó "0" (133)
51 | 512 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Definición
52 | 536 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales) | *
53 | 545 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales) | *
54 | 556 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Definición
55 | 580 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales) | *
56 | 589 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales) | *
57 | 600 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Definición
58 | 624 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales) | *
59 | 633 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales) | *
60 | 644 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Definición
61 | 668 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales) | *
62 | 677 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales) | *
63 | 688 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Definición
64 | 712 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales) | *
65 | 721 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales) | *
66 | 732 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Definición
67 | 756 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales) | *
68 | 765 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales) | *
69 | 776 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Definición
70 | 800 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales) | *
71 | 809 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales) | *
72 | 820 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto previo (suma)  (134)
73 | 833 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos al empleo  (135)
74 | 846 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos a la inversion (136)
75 | 859 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto minorado (137)
76 | 872 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector especial (2 enteros y 2 decimales) (138) | *
77 | 876 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (139) | *
78 | 880 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de temporada (2 enteros y 2 decimales) (140) | *
79 | 884 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de exceso (2 enteros y 2 decimales) (141) | *
80 | 888 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (142) | *
81 | 892 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto de módulos (143)
82 | 905 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción de carácter general (144)
83 | 918 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (145)
84 | 931 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Gastos extraordinarios circunstancias  excepcionales (146)
85 | 944 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Otras percepciones empresariales (147)
86 | 957 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª -Rendimiento neto actividad (148)
87 | 970 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción rdtos. más de 2 años o forma irregular (149)
88 | 983 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rendimiento neto reducido (150)
89 | 996 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Suma rendimientos netos reducidos (153)
90 | 1009 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas - Reducción ejercicio determinadas actividades económicas (154)
91 | 1022 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas (155)
92 | 1035 | 600 | An |  | RESERVADO PARA LA A.E.A.T
93 | 1635 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10006000>
Total: |  | 1646
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos blancos.

# 100-07

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "07000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | Nº de hojas adicionales si se declaran más de 2 Actividades
7 | 14 | 1 | Tit | C | (E3) Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Contribuyente titular de actividad: de "0" a "9"  (156)
8 | 15 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Clave actividad: de "0" a "9" (157)
9 | 16 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Criterio cobros/pagos:  "1" ó "0" (158)
10 | 17 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Ingresos íntegros
11 | 28 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Índice
12 | 34 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 1º - Rdto. base producto
13 | 45 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Ingresos íntegros
14 | 56 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Índice
15 | 62 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 2º - Rdto. base producto
16 | 73 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Ingresos íntegros
17 | 84 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Índice
18 | 90 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 3º - Rdto. base producto
19 | 101 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 4º - Ingresos íntegros
20 | 112 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 4º - Índice
21 | 118 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 4º - Rdto. base producto
22 | 129 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Ingresos íntegros
23 | 140 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Índice
24 | 146 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 5º - Rdto. base producto
25 | 157 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Ingresos íntegros
26 | 168 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Índice
27 | 174 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 6º - Rdto. base producto
28 | 185 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Ingresos íntegros
29 | 196 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Índice
30 | 202 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 7º - Rdto. base producto
31 | 213 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Ingresos íntegros
32 | 224 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Índice
33 | 230 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 8º - Rdto. base producto
34 | 241 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Ingresos íntegros
35 | 252 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Índice
36 | 258 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 9º - Rdto. base producto
37 | 269 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Ingresos íntegros
38 | 280 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Índice
39 | 286 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 10º - Rdto. base producto
40 | 297 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Ingresos íntegros
41 | 308 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Índice
42 | 314 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 11º - Rdto. base producto
43 | 325 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Ingresos íntegros
44 | 336 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Índice
45 | 342 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 12º - Rdto. base producto
46 | 353 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Ingresos íntegros
47 | 364 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Índice
48 | 370 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 13º - Rdto. base producto
49 | 381 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 14º - Ingresos íntegros
50 | 392 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 14º - Índice
51 | 398 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 14º - Rdto. base producto
52 | 409 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 15º - Ingresos íntegros
53 | 420 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 15º - Índice
54 | 426 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 15º - Rdto. base producto
55 | 437 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 16º - Ingresos íntegros
56 | 448 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 16º - Índice
57 | 454 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Producto 16º - Rdto. base producto
58 | 465 | 28 | An | C | RESERVADO PARA LA A.E.A.T
59 | 493 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Total  ingresos íntegros (159)
60 | 504 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto previo (suma) (160)
61 | 515 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones (161)
62 | 526 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Amortización inmovilizado (162)
63 | 537 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto minorado  (163)
64 | 548 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Medios de producción ajenos (2 enteros y 2 decimales) [164] | *
65 | 552 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Utilización personal asalariado (2 enteros y 2 decimales) (165) | *
66 | 556 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (166) | *
67 | 560 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (167) Ver NOTA | *
68 | 564 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 2 (167) Ver NOTA | *
69 | 568 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Actividades agricultura ecológica (2 enteros y dos decimales)  (168) | *
70 | 572 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Cultivo en tierras regadío utilice energía electrica ( 2 enteros y 2 decimales) (169) | *
71 | 576 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales)  (170) | *
72 | 580 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Determinadas actividades forestales  (2 enteros y 2 decimales)  (171) | *
73 | 584 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto de módulos (172)
74 | 597 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción carácter general (173)
75 | 610 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Diferencia (174)
76 | 623 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción agricultores jóvenes (175)
77 | 636 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Gastos extraordinarios por circunstancias excepcionales (176]
78 | 649 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto  (177)
79 | 662 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones rendimientos generados más 2 años o forma irregular (178)
80 | 675 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto reducido (179)
81 | 688 | 1 | Tit | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Contribuyente titular de actividad: de "0" a "9"  (156)
82 | 689 | 1 | Num | C | (E3) Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Clave actividad: de "0" a "9" (157)
83 | 690 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Criterio cobros/pagos:  "1" ó "0" (158)
84 | 691 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Ingresos íntegros
85 | 702 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Índice
86 | 708 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Rdto. base producto
87 | 719 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Ingresos íntegros
88 | 730 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Índice
89 | 736 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Rdto. base producto
90 | 747 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Ingresos íntegros
91 | 758 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Índice
92 | 764 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Rdto. base producto
93 | 775 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Ingresos íntegros
94 | 786 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Índice
95 | 792 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Rdto. base producto
96 | 803 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Ingresos íntegros
97 | 814 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Índice
98 | 820 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Rdto. base producto
99 | 831 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Ingresos íntegros
100 | 842 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Índice
101 | 848 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Rdto. base producto
102 | 859 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Ingresos íntegros
103 | 870 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Índice
104 | 876 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Rdto. base producto
105 | 887 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Ingresos íntegros
106 | 898 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Índice
107 | 904 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Rdto. base producto
108 | 915 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Ingresos íntegros
109 | 926 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Índice
110 | 932 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Rdto. base producto
111 | 943 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Ingresos íntegros
112 | 954 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Índice
113 | 960 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Rdto. base producto
114 | 971 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Ingresos íntegros
115 | 982 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Índice
116 | 988 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Rdto. base producto
117 | 999 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Ingresos íntegros
118 | 1010 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Índice
119 | 1016 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Rdto. base producto
120 | 1027 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Ingresos íntegros
121 | 1038 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Índice
122 | 1044 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Rdto. base producto
123 | 1055 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Ingresos íntegros
124 | 1066 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Índice
125 | 1072 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Rdto. base producto
126 | 1083 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Ingresos íntegros
127 | 1094 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Índice
128 | 1100 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Rdto. base producto
129 | 1111 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 16º - Ingresos íntegros
130 | 1122 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 16º - Índice
131 | 1128 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 16º - Rdto. base producto
132 | 1139 | 28 | An | C | RESERVADO PARA LA A.E.A.T
133 | 1167 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Total  ingresos íntegros (159)
134 | 1178 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto previo (suma) (160)
135 | 1189 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones (161)
136 | 1200 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Amortización inmovilizado (162)
137 | 1211 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto minorado  (163)
138 | 1222 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Medios de producción ajenos (2 enteros y 2 decimales) [164] | *
139 | 1226 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Utilización personal asalariado (2 enteros y 2 decimales) (165) | *
140 | 1230 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (166) | *
141 | 1234 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (167) Ver NOTA | *
142 | 1238 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 2 (167) Ver NOTA | *
143 | 1242 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Actividades agricultura ecológica (2 enteros y dos decimales)  (168) | *
144 | 1246 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Cultivo en tierras regadío utilice energía electrica ( 2 enteros y 2 decimales) (169) | *
145 | 1250 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales)  (170) | *
146 | 1254 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Determinadas actividades forestales  (2 enteros y 2 decimales)  (171) | *
147 | 1258 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto de módulos (172)
148 | 1271 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción carácter general (173)
149 | 1284 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Diferencia (174)
150 | 1297 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción agricultores jóvenes (175)
151 | 1310 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Gastos extraordinarios por circunstancias excepcionales (176]
152 | 1323 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto  (177)
153 | 1336 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones rendimientos generados más 2 años o forma irregular (178)
154 | 1349 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto reducido (179)
155 | 1362 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Suma rendimientos netos reducidos (183)
156 | 1375 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Reducción por ejercicio determinadas actividades económicas (184)
157 | 1388 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total actividades agrícolas - Rendimiento neto reducido total  (185)
158 | 1401 | 600 | An |  | RESERVADO PARA LA A.E.A.T
159 | 2001 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10007000>
Total: |  | 2012
 |  |  |  |  | NOTA: Cumplimentar sólo cuando el índice 2 sea distinto al índice 1.

# 100-08

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "08000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | Nº de hojas adicionales si se declaran más de 3 imputaciones
7 | 14 | 1 | Tit | C | (F) Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (186)
8 | 15 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - NIF Entidad (187)
9 | 35 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país (188)
10 | 36 | 4 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Porcentaje participación  (2 enteros y dos decimales) (189) | *
11 | 40 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (190)
12 | 53 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Minoraciones  aplicables (191)
13 | 66 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones aplicables (192)
14 | 79 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto computable (193)
15 | 92 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Neto atribuido por la entidad . Imp. computable (194)
16 | 105 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Derivado valores deuda subordinada o partic. preferentes (195)
17 | 118 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto atribuido (196)
18 | 131 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Minoraciones aplicables (197)
19 | 144 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Reducciones aplicables (198)
20 | 157 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto computable (199)
21 | 170 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Criterio cobros/pagos. "1" o cero (200]
22 | 171 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rendimiento neto (201]
23 | 184 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Minoraciones aplicables (202]
24 | 197 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Provisiones deducibles y gastos difícil justificación (203]
25 | 210 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducción aplicable art.32.1 y DT 25 (204]
26 | 223 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducción aplicable art.32.2.3 (205]
27 | 236 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducción aplicable art.32.3 (206]
28 | 249 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. Neto computable (207)
29 | 262 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas  patrimoniales - No derivadas transmisiones - Ganancias patrimoniales no derivadas de transmisiones, atribuidas por la entidad (208)
30 | 275 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - No derivadas transmisiones - Pérdidas patrimoniales no derivadas de transmisiones, atribuidas por la entidad (209)
31 | 288 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales (210)
32 | 301 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión destinado a constituir renta vitalicia (211)
33 | 314 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión al que resulta aplicable (212)
34 | 327 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas 50 por 100 (sólo determinados inmuebles urbanos) (213)
35 | 340 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas reinversión rentas vitalicias (214)
36 | 353 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancia exenta reinversión en entidades de nueva o reciente creación (215)
37 | 366 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Parte ganancias susceptibles reducción  (216)
38 | 379 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Reducciones aplicables  (217)
39 | 392 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas  (218)
40 | 405 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas imputable 2016  (219)
41 | 418 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad  (220)
42 | 431 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución de retenciones e ingresos a cuenta -  Retenciones e ingresos a cuenta atribuidos por la entidad (221)
43 | 444 | 1 | Tit | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (186)
44 | 445 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - NIF Entidad (187)
45 | 465 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país (188)
46 | 466 | 4 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Porcentaje participación  (2 enteros y dos decimales) (189) | *
47 | 470 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (190)
48 | 483 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Minoraciones  aplicables (191)
49 | 496 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones aplicables (192)
50 | 509 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto computable (193)
51 | 522 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Neto atribuido por la entidad . Imp. computable (194)
52 | 535 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Derivado valores deuda subordinada o partic. preferentes (195)
53 | 548 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto atribuido (196)
54 | 561 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Minoraciones aplicables (197)
55 | 574 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Reducciones aplicables (198)
56 | 587 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto computable (199)
57 | 600 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Criterio cobros/pagos. "1" o cero (200]
58 | 601 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rendimiento neto (201]
59 | 614 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Minoraciones aplicables (202]
60 | 627 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Provisiones deducibles y gastos difícil justificación (203]
61 | 640 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducción aplicable art.32.1 y DT 25 (204]
62 | 653 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducción aplicable art.32.2.3 (205]
63 | 666 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducción aplicable art.32.3 (206]
64 | 679 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. Neto computable (207)
65 | 692 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas  patrimoniales - No derivadas transmisiones - Ganancias patrimoniales no derivadas de transmisiones, atribuidas por la entidad (208)
66 | 705 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - No derivadas transmisiones - Pérdidas patrimoniales no derivadas de transmisiones, atribuidas por la entidad (209)
67 | 718 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales (210)
68 | 731 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión destinado a constituir renta vitalicia (211)
69 | 744 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión al que resulta aplicable (212)
70 | 757 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas 50 por 100 (sólo determinados inmuebles urbanos) (213)
71 | 770 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas reinversión rentas vitalicias (214)
72 | 783 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancia exenta reinversión en entidades de nueva o reciente creación (215)
73 | 796 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Parte ganancias susceptibles reducción  (216)
74 | 809 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Reducciones aplicables  (217)
75 | 822 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas  (218)
76 | 835 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas imputable 2016  (219)
77 | 848 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad  (220)
78 | 861 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución de retenciones e ingresos a cuenta -  Retenciones e ingresos a cuenta atribuidos por la entidad (221)
79 | 874 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos capital mobiliario - A integrar en BI general - Rdto. Neto computable - Total (222)
80 | 887 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos capital mobiliario - A integrar en BI  ahorro - Rdto. Neto atribuido - Importe computable - Total (223)
81 | 900 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos capital mobiliario - A integrar en BI ahorro - Rdto. derivado valores deuda subordinada o participaciones preferentes - Total (224)
82 | 913 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos capital inmobiliario - Rendimiento neto computable - Total (225)
83 | 926 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  rendimientos actividades económicas - Rendimiento neto computable - Total (226)
84 | 939 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  ganancias y pérdidas patrimoniales -  No derivada transmisiones - Ganancias patrimoniales - Total  (227)
85 | 952 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  ganancias y pérdidas patrimoniales -  No derivada transmisiones - Pérdidas patrimoniales - Total  (228)
86 | 965 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  ganancias y pérdidas patrimoniales -  Derivadas  transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias reducidas no exentas imputables a 2016 - Total  (229)
87 | 978 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución  ganancias y pérdidas patrimoniales -  Derivadas  transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad - Total  (230)
88 | 991 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Atribución retenciones e ingresos a cuenta -  Retenciones e ingresos atribuidos por la entidad - Total  (542)
89 | 1004 | 1 | Tit | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1-  Entidades y contribuyentes socios. Contribuyente "0" a "9" (231)
90 | 1005 | 9 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1-  Entidades y contribuyentes socios. N.I.F. Entidad (232)
91 | 1014 | 1 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (233)
92 | 1015 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Base imponible imputada  (234)
93 | 1028 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones inversión empresarial (235)
94 | 1041 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones creación empleo (236)
95 | 1054 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deduccciones rentas Ceuta/Melilla (237)
96 | 1067 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones doble imposición internacional. (238)
97 | 1080 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones retenciones e ingresos a cuenta  - Retenciones e ingresos a cuenta imputados (239)
98 | 1093 | 1 | Tit | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2-  Entidades y contribuyentes socios. Contribuyente "0" a "9" (231)
99 | 1094 | 9 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2-  Entidades y contribuyentes socios. N.I.F. Entidad (232)
100 | 1103 | 1 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (233)
101 | 1104 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Base imponible imputada  (234)
102 | 1117 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Deducciones inversión empresarial (235)
103 | 1130 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Deducciones creación empleo (236)
104 | 1143 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Deduccciones rentas Ceuta/Melilla (237)
105 | 1156 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Deducciones doble imposición internacional. (238)
106 | 1169 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones retenciones e ingresos a cuenta  - Retenciones e ingresos a cuenta imputados (239)
107 | 1182 | 13 | N |  | Regs. especiales - Agrupaciones interés económico y UTES - Total base imponible imputada  (240)
108 | 1195 | 13 | N |  | Regs. especiales - Agrupaciones interés económico y UTES - Total retenciones e ingresos a cuenta imputados (543)
109 | 1208 | 600 | An |  | RESERVADO PARA LA A.E.A.T
110 | 1808 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10008000>
Total: |  | 1819

# 100-09

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "09000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | Nº hojas adicionales que se adjuntan
7 | 15 | 1 | Tit | C | (F) Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Contribuyente  "0" a "9" (241)
8 | 16 | 24 | An | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Denominación entidad no residente (242)
9 | 40 | 13 | N | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Importe imputación  (243)
10 | 53 | 1 | Tit | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 2 - Contribuyente  "0" a "9" (241)
11 | 54 | 24 | An | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 2 - Denominación entidad no residente (242)
12 | 78 | 13 | N | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 2 - Importe imputación  (243)
13 | 91 | 13 | N |  | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Total importe de la imputación  (244)
14 | 104 | 1 | Tit |  | Regs. especiales - Imputación rentas cesión derechos imagen - Contribuyente que debe efectuar la imputacion.  "0" a "9" (245)
15 | 105 | 25 | An |  | Regs. especiales - Imputación rentas cesión derechos imagen - NIF o denominación persona/entidad cesionaria derechos imagen (246)
16 | 130 | 25 | An |  | Regs. especiales - Imputación rentas cesión derechos imagen - NIF o denominación persona/entidad relación laboral (247]
17 | 155 | 13 | N |  | Regs. especiales - Imputación rentas cesión derechos imagen - Cantidad a imputar  (248)
18 | 168 | 1 | Tit | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Contribuyente  "0" a "9" (249)
19 | 169 | 24 | An | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Denominación Institución (250)
20 | 193 | 13 | N | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Importe imputación (251)
21 | 206 | 1 | Tit | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Contribuyente  "0" a "9" (249)
22 | 207 | 24 | An | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Denominación Institución (250)
23 | 231 | 13 | N | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Importe imputación (251)
24 | 244 | 13 | N |  | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - Total  importe de la imputación  (252)
25 | 257 | 13 | N |  | (G1) Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En metálico - Importe (253)
26 | 270 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Valoración (254)
27 | 283 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta (255)
28 | 296 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta repercutidos (256)
29 | 309 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Importe computable (257)
30 | 322 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Pérdidas patrimoniales derivadas de estos juegos (258)
31 | 335 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Ganancias patrimoniales netas (259)
32 | 348 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En metálico - Importe (260)
33 | 361 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Valoración (261)
34 | 374 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta (262)
35 | 387 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta repercutidos (263)
36 | 400 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios concursos o combinaciones aleatorias con fines publicitarios - En especie - Importe computable (264)
37 | 413 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Subvenciones adquisición vivienda (265)
38 | 426 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Otras subvenciones o ayudas (266)
39 | 439 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Ganancias patrimoniales vecinos, aprovechamientos forestales (267)
40 | 452 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Renta básica emancipación (268)
41 | 465 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas -  Importe ganancias (269)
42 | 478 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe pérdidas (270)
43 | 491 | 1 | Tit | C | (G2) Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente 1 "0" a "9" [271]
44 | 492 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente 1 -Valor total acumulado [272]
45 | 505 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente 2 "0" a "9" [271]
46 | 506 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente 2 -Valor total acumulado [272]
47 | 519 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (273)
48 | 520 | 9 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - N.I.F. (274)
49 | 529 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 -  Importe global transmisiones (275)
50 | 542 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Importe global transmisiones -  Valor transmisión para renta vitalicia (276)
51 | 555 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Importe global transmisiones -  Valor transmisión aplicable D.T.9ª (277)
52 | 568 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Importe global adquisiciones (278)
53 | 581 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 1 -Ganancias patrimoniales (279)
54 | 594 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 -Ganancias exentas reinversión rentas vitalicias (280)
55 | 607 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 1 - Parte ganancias suceptible reducción (281)
56 | 620 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 1 - Reducción aplicable (282)
57 | 633 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Ganancias patrimoniales reducidas no exentas (283)
58 | 646 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Pérdidas patrimoniales (284)
59 | 659 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Pérdidas patrimoniales imputables a 2016 (285)
60 | 672 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Inst. inv. colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (273)
61 | 673 | 9 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - N.I.F. (274)
62 | 682 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 -  Importe global transmisiones (275)
63 | 695 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Importe global transmisiones -  Valor transmisión para renta vitalicia (276)
64 | 708 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Importe global transmisiones -  Valor transmisión aplicable D.T.9ª (277)
65 | 721 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Importe global adquisiciones (278)
66 | 734 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 2 -Ganancias patrimoniales (279)
67 | 747 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 -Ganancias exentas reinversión rentas vitalicias (280)
68 | 760 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 2 - Parte ganancias suceptible reducción (281)
69 | 773 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 2 - Reducción aplicable (282)
70 | 786 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Ganancias patrimoniales reducidas no exentas (283)
71 | 799 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Pérdidas patrimoniales (284)
72 | 812 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Pérdidas patrimoniales imputables a 2016 (285)
73 | 825 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (273)
74 | 826 | 9 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (274)
75 | 835 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 -  Importe global transmisiones (275)
76 | 848 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Importe global transmisiones -  Valor transmisión para renta vitalicia (276)
77 | 861 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Importe global transmisiones -  Valor transmisión aplicable D.T.9ª (277)
78 | 874 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Importe global adquisiciones (278)
79 | 887 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 3 -Ganancias patrimoniales (279)
80 | 900 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 -Ganancias exentas reinversión rentas vitalicias (280)
81 | 913 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 3 - Parte ganancias suceptible reducción (281)
82 | 926 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 3 - Reducción aplicable (282)
83 | 939 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Ganancias patrimoniales reducidas no exentas (283)
84 | 952 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Pérdidas patrimoniales (284)
85 | 965 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Pérdidas patrimoniales imputables a 2016 (285)
86 | 978 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. Colectiva - Resultados - Ganancias patrimoniales reducidas no exentas - Total (286)
87 | 991 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. Colectiva - Resultados - Pérdidas patrimoniales imputables 2016 - Total (287)
88 | 1004 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
89 | 1007 | 600 | An |  | RESERVADO PARA LA A.E.A.T
90 | 1607 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10009000>
Total: |  | 1618

# 100-10

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "10000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | Nº hojas adicionales que se adjuntan
7 | 15 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 1 -  Contribuyente valores transmitidos "0" a "9" (288)
8 | 16 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 1 - Denominación valores (289)
9 | 36 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 1 - Importe global efectuadas en 2016 (290)
10 | 49 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 1 - Importe global efectuadas en 2016 - Valor transmisión a constituir en renta vitalicia  (291)
11 | 62 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 1 - Importe global efectuadas en 2016 - Valor transmisión aplicable D.T.9ª (292)
12 | 75 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Valor adquisición global (293)
13 | 88 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados -  Ganancias patrimoniales (294)
14 | 101 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (295)
15 | 114 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (296)
16 | 127 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Reducción aplicable (297)
17 | 140 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Ganancias patrimoniales no exentas (298)
18 | 153 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Pérdidas patrim. Importe obtenido (299)
19 | 166 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Pérdidas patrim. Importe computable (300)
20 | 179 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 2 -  Contribuyente valores transmitidos "0" a "9" (288)
21 | 180 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 2 - Denominación valores (289)
22 | 200 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 2 - Importe global efectuadas en 2016 (290)
23 | 213 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 2 - Importe global efectuadas en 2016 - Valor transmisión a constituir en renta vitalicia  (291)
24 | 226 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 2 - Importe global efectuadas en 2016 - Valor transmisión aplicable D.T.9ª (292)
25 | 239 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Valor adquisición global (293)
26 | 252 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados -  Ganancias patrimoniales (294)
27 | 265 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (295)
28 | 278 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (296)
29 | 291 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Reducción aplicable (297)
30 | 304 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Ganancias patrimoniales no exentas (298)
31 | 317 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Pérdidas patrim. Importe obtenido (299)
32 | 330 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Pérdidas patrim. Importe computable (300)
33 | 343 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 3 -  Contribuyente valores transmitidos "0" a "9" (288)
34 | 344 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 3 - Denominación valores (289)
35 | 364 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 3 - Importe global efectuadas en 2016 (290)
36 | 377 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 3 - Importe global efectuadas en 2016 - Valor transmisión a constituir en renta vitalicia  (291)
37 | 390 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 3 - Importe global efectuadas en 2016 - Valor transmisión aplicable D.T.9ª (292)
38 | 403 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Valor adquisición global (293)
39 | 416 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados -  Ganancias patrimoniales (294)
40 | 429 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (295)
41 | 442 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (296)
42 | 455 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Reducción aplicable (297)
43 | 468 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Ganancias patrimoniales no exentas (298)
44 | 481 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Pérdidas patrim. Importe obtenido (299)
45 | 494 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Pérdidas patrim. Importe computable (300)
46 | 507 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Resultados - Ganancias patrimoniales reducidas no exentas - Totales (301)
47 | 520 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Resultados - Pérdidas patrimoniales Importe computable - Totales (302)
48 | 533 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
49 | 536 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (303)
50 | 537 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (305)
51 | 538 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -  Inmuebles. Situación. Clave "0" a "4" (306)
52 | 539 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -   Inmuebles. Situación. Ref. catastral (307)
53 | 559 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha transmisión (308)
54 | 567 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha adquisición (309)
55 | 575 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión (310)
56 | 588 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Constituir renta vitalicia (311)
57 | 601 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - De la vivienda habitual (312)
58 | 614 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Susceptible de reducción (313)
59 | 627 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor adquisición (314)
60 | 640 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (315)
61 | 653 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable ( (316)
62 | 666 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida ( (317)
63 | 679 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta 50 por 100 ( (318)
64 | 692 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en rentas vitalicias ( (319)
65 | 705 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en vivienda habitual ( (320)
66 | 718 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en entidades de nueva o reciente creación ( (321)
67 | 731 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia no exenta ( (322)
68 | 744 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Parte ganancia susceptible reducción ( (323)
69 | 757 | 4 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Nº años permanencia hasta 31/12/1994 ( (324)
70 | 761 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Reducción aplicable ( (325)
71 | 774 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida ( (326)
72 | 787 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida  imputable 2016( (327)
73 | 800 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Parte ganancia susceptible reducción ( (328)
74 | 813 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Reducción licencia autotaxis ( (329)
75 | 826 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida( (330)
76 | 839 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida imputable 2016( (331)
77 | 852 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (304)
78 | 853 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (303)
79 | 854 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (305)
80 | 855 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -  Inmuebles. Situación. Clave "0" a "4" (306)
81 | 856 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -   Inmuebles. Situación. Ref. catastral (307)
82 | 876 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Fecha transmisión (308)
83 | 884 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Fecha adquisición (309)
84 | 892 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión (310)
85 | 905 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - Constituir renta vitalicia (311)
86 | 918 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - De la vivienda habitual (312)
87 | 931 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - Susceptible de reducción (313)
88 | 944 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor adquisición (314)
89 | 957 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (315)
90 | 970 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable ( (316)
91 | 983 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida ( (317)
92 | 996 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta 50 por 100 ( (318)
93 | 1009 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta reinversión en rentas vitalicias ( (319)
94 | 1022 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta reinversión en vivienda habitual ( (320)
95 | 1035 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta reinversión en entidades de nueva o reciente creación ( (321)
96 | 1048 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia no exenta ( (322)
97 | 1061 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Parte ganancia susceptible reducción ( (323)
98 | 1074 | 4 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Nº años permanencia hasta 31/12/1994 ( (324)
99 | 1078 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Reducción aplicable ( (325)
100 | 1091 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Ganancia patrimonial reducida ( (326)
101 | 1104 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Ganancia patrimonial reducida  imputable 2016( (327)
102 | 1117 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Parte ganancia susceptible reducción ( (328)
103 | 1130 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Reducción licencia autotaxis ( (329)
104 | 1143 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Ganancia patrimonial reducida( (330)
105 | 1156 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Ganancia patrimonial reducida imputable 2016( (331)
106 | 1169 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (304)
107 | 1170 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Diferencia negativa - Pérdida patrimonial imputable 2016  - Total (332)
108 | 1183 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elementos no afectos - Ganancia patrimonial reducida no exenta imputable 2016 - Total  (333)
109 | 1196 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elementos afectos - Ganancia patrimonial reducida no exenta imputable 2016 - Total  (334)
110 | 1209 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
111 | 1212 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales a integrar en la base imponible del ahorro (335)
112 | 1225 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 1 -  Contribuyente "0" a "9" (336)
113 | 1226 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 1 -  Importe a imputar a 2016 -  (337)
114 | 1239 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 2 -  Contribuyente "0" a "9" (336)
115 | 1240 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 2 -  Importe a imputar a 2016 -  (337)
116 | 1253 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 3 -  Contribuyente "0" a "9" (336)
117 | 1254 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 3 -  Importe a imputar a 2016 -  (337)
118 | 1267 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Ganancia 1 -  Importe a imputar a 2016 -  - Total (338)
119 | 1280 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida  1 -  Contribuyente "0" a "9" (339)
120 | 1281 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida  1 -  Importe pérdida imputar a 2016 -  (340)
121 | 1294 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida 2 -  Contribuyente "0" a "9" (339)
122 | 1295 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida 2 -  Importe pérdida imputar a 2016 -  (340)
123 | 1308 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida  3 -  Contribuyente "0" a "9" (339)
124 | 1309 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores - Pérdida  3 -  Importe pérdida imputar a 2016 -  (340)
125 | 1322 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2016 -  Ganancias/pérdidas efectuadas en ejercicios anteriores -  Importe pérdida imputar a 2016 -  - Total  (341)
126 | 1335 | 600 | An |  | RESERVADO PARA LA A.E.A.T
127 | 1935 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10010000>
Total: |  | 1946

# 100-11

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "11000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | Nº hojas adicionales que se adjuntan
7 | 14 | 1 | Tit | C | (G3) Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2016 diferimiento por reinversión - Ganancia 1 - Contribuyente "0" a "9" (342)
8 | 15 | 13 | N | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2016 diferimiento por reinversión - Ganancia 1 - Importe ganancia (343]
9 | 28 | 1 | Tit | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2016 diferimiento por reinversión - Ganancia 2 - Contribuyente "0" a "9" (342)
10 | 29 | 13 | N | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2016 diferimiento por reinversión - Ganancia 2 - Importe ganancia (343)
11 | 42 | 1 | Tit | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2016 diferimiento por reinversión - Ganancia 3 - Contribuyente "0" a "9" (342)
12 | 43 | 13 | N | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2016 diferimiento por reinversión - Ganancia 3 - Importe ganancia (343)
13 | 56 | 13 | N |  | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2016 diferimiento por reinversión - Total ganancia (344)
14 | 69 | 1 | Num | C | (G4) Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Contribuyente que ha transmitido intervivos las acciones "1" o "0" [345]
15 | 70 | 1 | Tit | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Contribuyente titular valores "0" a "9" (346)
16 | 71 | 9 | An | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Nif entidad (347)
17 | 80 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Valor acciones/participaciones (348)
18 | 93 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Valor transmisión acciones (349)
19 | 106 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Valor transmisión acciones - Aplicable D.T.9ª (350)
20 | 119 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Valor adquisición (351)
21 | 132 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Resultados - Ganancias patrimoniales (352)
22 | 145 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Resultados - Ganancias suceptibles reducción (353)
23 | 158 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Resultados - Reducción aplicable (354)
24 | 171 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 1 -  Resultados - Ganancias patrimoniales reducidas (355)
25 | 184 | 1 | Num | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Contribuyente que ha transmitido intervivos las acciones "1" o "0" [345]
26 | 185 | 1 | Tit | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Contribuyente titular valores "0" a "9" (346)
27 | 186 | 9 | An | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Nif entidad (347)
28 | 195 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Valor acciones/participaciones (348)
29 | 208 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Valor transmisión acciones (349)
30 | 221 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Valor transmisión acciones - Aplicable D.T.9ª (350)
31 | 234 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Valor adquisición (351)
32 | 247 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Resultados - Ganancias patrimoniales (352)
33 | 260 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Resultados - Ganancias suceptibles reducción (353)
34 | 273 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Resultados - Reducción aplicable (354)
35 | 286 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 2 -  Resultados - Ganancias patrimoniales reducidas (355)
36 | 299 | 1 | Num | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Contribuyente que ha transmitido intervivos las acciones "1" o "0" [345]
37 | 300 | 1 | Tit | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Contribuyente titular valores "0" a "9" (346)
38 | 301 | 9 | An | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Nif entidad (347)
39 | 310 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Valor acciones/participaciones (348)
40 | 323 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Valor transmisión acciones (349)
41 | 336 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Valor transmisión acciones - Aplicable D.T.9ª (350)
42 | 349 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Valor adquisición (351)
43 | 362 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Resultados - Ganancias patrimoniales (352)
44 | 375 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Resultados - Ganancias suceptibles reducción (353)
45 | 388 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Resultados - Reducción aplicable (354)
46 | 401 | 13 | N | C | Ganancias por cambio residencia fuera territorio español -  Entidad 3 -  Resultados - Ganancias patrimoniales reducidas (355)
47 | 414 | 13 | N |  | Ganancias por cambio residencia fuera territorio español -  Resultados - Ganancias patrimoniales reducidas. Total (356)
48 | 427 | 13 | N |  | (G5) Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe total obtenido susceptible de reinversión (357)
49 | 440 | 13 | N |  | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Ganancia patrimonial obtenida (358)
50 | 453 | 13 | N |  | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe reinvertido hasta 31-12-2016 en adquisición nueva vivienda (359)
51 | 466 | 13 | N |  | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe que se compromete a reinvertir 2 años siguientes (360)
52 | 479 | 13 | N |  | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (361)
53 | 492 | 13 | N |  | (G6) Exención por reinversión en entidades de nueva o reciente creación - Importe total obtenido susceptible de reinversión(362)
54 | 505 | 13 | N |  | Exención por reinversión en entidades de nueva o reciente creación - Ganancia patrimonial obtenida [363]
55 | 518 | 13 | N |  | Exención por reinversión en entidades de nueva o reciente creación - Importe reinvertido hasta 31-12-2016 [364]
56 | 531 | 13 | N |  | Exención por reinversión en entidades de nueva o reciente creación - Importe que se compromete a reinvertir en el año siguiente [365]
57 | 544 | 13 | N |  | Exención por reinversión en entidades de nueva o reciente creación - Ganancia patrimonial exenta por reinversión [366]
58 | 557 | 13 | N |  | (G7) Exención por reinversión en rentas vitalicias - Importe total transmisión elementos patrimoniales (367)
59 | 570 | 13 | N |  | Exención por reinversión en rentas vitalicias - Ganancia patrimonial obtenida (368)
60 | 583 | 13 | N |  | Exención por reinversión en rentas vitalicias - Importe reinvertido hasta 31-12-2016 en rentas vitalicias (369)
61 | 596 | 13 | N |  | Exención por reinversión en rentas vitalicias - Importe que se compromete a reinvertir en 2017 (370]
62 | 609 | 13 | N |  | Exención por reinversión en rentas vitalicias - Importe retención que se compromete a reinvertir en 2016 (371)
63 | 622 | 13 | N |  | Exención por reinversión en rentas vitalicias - Ganancia patrimonial exenta por reinversión (372)
64 | 635 | 1 | Tit |  | (G8) Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (373)
65 | 636 | 2 | Num |  | Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España -  Número de operaciones1 (374)
66 | 638 | 1 | Tit |  | Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente 2   "0" a "9" (375)
67 | 639 | 2 | Num |  | Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones 2 (376)
68 | 641 | 1 | Num |  | Opción régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Si entidades no residentes no han aplicado régimen fiscal similar a éste  (377)
69 | 642 | 13 | N |  | (G9) Integración/compensación ganancias/pérdidas patrimoniales imputables 2016 - A integrar en base imponible general -  Suma ganancias (378)
70 | 655 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2016 - A integrar base imponible general -  Suma pérdidas (379)
71 | 668 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2016 - A integrar base imponible general -  Saldo neto - Diferencia positiva (380)
72 | 681 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2016 - A integrar base imponible general -  Saldo neto - Diferencia negativa (381)
73 | 694 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2016 - A integrar base imponible ahorro - Suma ganancias (382)
74 | 707 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2016 - A integrar base imponible ahorro - Suma pérdidas (383)
75 | 720 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2016 - A integrar base imponible ahorro - Saldo neto negativo ganancias y pérdidas imputables a 2016 - positiva (384)
76 | 733 | 13 | N |  | Integración/compensación ganancias/pérdidas patrimoniales imputables 2016 - A integrar base imponible ahorro - Saldo neto negativo ganancias y pérdidas imputables a 2016 - positiva (385)
77 | 746 | 600 | An |  | RESERVADO PARA LA A.E.A.T
78 | 1346 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10011000>
Total: |  | 1357

# 100-12

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "12000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N | Base imponible general y base imponible ahorro - Integración y compensación rdtos. capital mobiliario (B.I. ahorro) - Saldo neto positivo rdto. capital mobiliario imputable a 2016 (386)
7 | 26 | 13 | N | Base imponible general y base imponible ahorro - Integración y compensación rdtos. capital mobiliario (B.I. ahorro) - Saldo neto negativo rdtos. capital mobiliario imputable a 2016 (387)
8 | 39 | 13 | N | Base imponible general y base imponible ahorro - BI general - Saldo neto positivo ganancias/pérdidas 2016 a integrar base imponible general (380)
9 | 52 | 13 | N | Base imponible general y base imponible ahorro - BI general - Compensación - Saldos netos negativos ganancias/pérdidas 2012-2015  pendientes compensar (388)
10 | 65 | 13 | N | Base imponible general y base imponible ahorro - BI general - Saldos neto rendimientos a integrar en base Imponible general (389)
11 | 78 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Saldo neto negativo ganancias/pérdidas 2016 (390)
12 | 91 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Resto saldos netos negativos ganancias/pérdidas 2012 a 2015 pendientes compensación (391)
13 | 104 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Base imponible general (392)
14 | 117 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas 2016 (384)
15 | 130 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Saldo neto negativo rendimientos capital mobiliario a 2016 (393]
16 | 143 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Saldos netos negativos ganancias/pérdidas no derivadas transmisión de deuda subordinada o preferentes 2012-2015 (394)
17 | 156 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Saldos netos negativos ganancias/pérdidas derivadas transmisión de deuda subordinada o preferentes 2012-2014 (395)
18 | 169 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Saldo neto negativo ganancias/pérdidas 2015 pendientes compensación (396)
19 | 182 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario de deuda subordinada o preferentes 2012-2014 (397)
20 | 195 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas - Compensaciones - Saldo neto negativo rdtos.capital mobiliario 2015 pendiente compensación (398)
21 | 208 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario a integrar en BI ahorro (386)
22 | 221 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro -  Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Saldo neto negativo ganancias/pérdidas 2016 a integrar ena la base imponible del ahorro  (399)
23 | 234 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Saldos netos negativos rdtos capital mobiliario que no derive deuda o participaciones preferentes 2012 a 2014 (400)
24 | 247 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Saldos netos negativos rdtos capital mobiliario que derive deuda o participaciones preferentes 2012 a 2014 (401)
25 | 260 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Saldo neto negativo rdtos capital mobiliario 2015 pendientes compensación (402)
26 | 273 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Resto saldos netos negativos de ganancias/pérdidas deuda o participaciones preferentes 2012 a 2014 (403)
27 | 286 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimiento capital mobiliario - Compensaciones - Saldo neto negativo ganancias/pérdidas 2015 pendientes compensación (404)
28 | 299 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Base imponible del ahorro (405)
29 | 312 | 13 | N | Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo ganancias/pérdidas imputables 2016 a integrar en BI general (406)
30 | 325 | 13 | N | Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo ganancias/pérdidas imputables 2016 a integrar en BI ahorro (407)
31 | 338 | 13 | N | Base imponible general y base imponible ahorro - Importes pendientes compensar 4 ejercicios siguientes - Saldo neto negativo rdtos.capital mobiliario 2016 a integrar en BI ahorro (408)
32 | 351 | 13 | N | (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidades familiares tributación conjunta (409)
33 | 364 | 1 | Tit | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 1 "0" a "9"  1(410)
34 | 365 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2011a 2015 1  (411)
35 | 378 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 y 2015 de contribuciones a seguros colectivos de dependencia 1 (412)
36 | 391 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones del 2016  1 (413)
37 | 404 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones del 2016 a seguros colectivos 1 (414)
38 | 417 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción  1 (415)
39 | 430 | 1 | Tit | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 2 "0" a "9"  2(410)
40 | 431 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2011 a 2015  2  (411)
41 | 444 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 y 2015 de contribuciones a seguros colectivos de dependencia  2 (412)
42 | 457 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones del 2016  2 (413)
43 | 470 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones del 2016 a seguros colectivos  2 (414)
44 | 483 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción  2 (415)
45 | 496 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total derecho reducción (416)
46 | 509 | 13 | N | Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones cónyuge del contribuyente - Total derecho reducción (417)
47 | 522 | 600 | An | RESERVADO PARA LA A.E.A.T
48 | 1122 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10012000>
Total: |  | 1133

# 100-13

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "13000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | Nº hojas adicionales que se adjuntan
7 | 15 | 1 | Tit | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Contribuyente 1 "0" a "9" (418)
8 | 16 | 9 | An | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - NIF persona con discapacidad 1 (419)
9 | 25 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Excesos pendientes reducir 1 (420)
10 | 38 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Aportaciones 2016 propia persona discapacidad 1 (421)
11 | 51 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Aportaciones 2016 parientes o tutores 1 (422)
12 | 64 | 1 | Tit | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Contribuyente 2 "0" a "9" (418)
13 | 65 | 9 | An | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - NIF persona con discapacidad 2 (419)
14 | 74 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Excesos pendientes reducir 2 (420]
15 | 87 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Aportaciones 2016 propia persona discapacidad 2 (421)
16 | 100 | 13 | N | C | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Aportaciones 2016 parientes o tutores 2 (422)
17 | 113 | 13 | N |  | Reducciones base imponible - Aportaciones y contribuciones a favor personas con discapacidad - Total con derecho a reducción (423)
18 | 126 | 1 | Tit |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (424)
19 | 127 | 9 | An |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 1 (425)
20 | 136 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 1 (426)
21 | 149 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2016 1 (427)
22 | 162 | 1 | Tit |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (424)
23 | 163 | 9 | An |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad 2 (425)
24 | 172 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir 2 (426)
25 | 185 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2016 2 (427)
26 | 198 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Total con derecho a reducción (428)
27 | 211 | 1 | Tit |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos -  Contribuyente 1 "0" a "9" (429)
28 | 212 | 20 | An |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 1 (430)
29 | 232 | 1 | Num |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si ha consignado NIF de otro país 1 (431] "1" o "0"
30 | 233 | 13 | N |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 1 (432)
31 | 246 | 1 | Tit |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos -  Contribuyente 2 "0" a "9" (429)
32 | 247 | 20 | An |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad 2 (430)
33 | 267 | 1 | Num |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si ha consignado NIF de otro país 2 (431] "1" o "0"
34 | 268 | 13 | N |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial 2 (432)
35 | 281 | 13 | N |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Total derecho reducción (433)
36 | 294 | 1 | Tit |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 1 "0" a "9" (434)
37 | 295 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales -  Excesos pendientes reducir 2011-2015  1 (435)
38 | 308 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones 2016 1 (436)
39 | 321 | 1 | Tit |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 2 "0" a "9" (434)
40 | 322 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales -  Excesos pendientes reducir 2011-2015  2 (435)
41 | 335 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones 2014 2 (436)
42 | 348 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Total con derecho a reducción (437)
43 | 361 | 13 | N |  | (J) Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base imponible general (392)
44 | 374 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Tributación conjunta (438)
45 | 387 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social (régimen general) (439)
46 | 400 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social cónyuge (440)
47 | 413 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social personas discapacidad (441)
48 | 426 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones patrimonios protegidos personas discapacidad (442)
49 | 439 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Pensiones compensatorias/anualidades alimentos (443)
50 | 452 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones mutualidades prev. soc. deportistas profesionales (444)
51 | 465 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general (445)
52 | 478 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Compensación bases liquidables generales negativas (446)
53 | 491 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general sometida a gravamen (450)
54 | 504 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base imponible ahorro (405)
55 | 517 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción tributación conjunta (451)
56 | 530 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción pensiones comp./anualidades alimentos (452)
57 | 543 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base liquidable del ahorro (455)
58 | 556 | 600 | An |  | RESERVADO PARA LA A.E.A.T
59 | 1156 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10013000>
Total: |  | 1167

# 100-14

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "14000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 1 | Tit | (K) Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 1 "0" a "9" (456)
7 | 14 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2016 1 (457)
8 | 27 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuciones 2016 a seguros colectivos dependencia no aplicadas 1 (458)
9 | 40 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuyente 2 "0" a "9" (456)
10 | 41 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Aportaciones/contribuciones 2016 2 (457)
11 | 54 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión social (régimen general) - Contribuciones 2016 a seguros colectivos dependencia no aplicadas 2 (458)
12 | 67 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 1 "0" a "9" (459)
13 | 68 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2016 no aplicadas 1 (460)
14 | 81 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 2 "0" a "9" (459)
15 | 82 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2016 no aplicadas 2 (460)
16 | 95 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 3 "0" a "9" (459)
17 | 96 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2016 no aplicadas 3 (460)
18 | 109 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 4 "0" a "9" (459)
19 | 110 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2016 no aplicadas 4 (460)
20 | 123 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 5 "0" a "9" (459)
21 | 124 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2016 no aplicadas 4 (460)
22 | 137 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Contribuyente 6 "0" a "9" (459)
23 | 138 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones sistemas previsión a favor personas discapacidad - Aportaciones 2016 no aplicadas 4 (460)
24 | 151 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (461)
25 | 152 | 13 | 6 | Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2016 no aplicadas 1 (462)
26 | 165 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (461)
27 | 166 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2016 no aplicadas 2 (462)
28 | 179 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 1 "0" a "9" (463)
29 | 180 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2016 no aplicadas 1 (464)
30 | 193 | 1 | Tit | Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Contribuyente 2 "0" a "9" (463)
31 | 194 | 13 | N | Reducciones base imponible no aplicadas - Exceso aportaciones mutualidad previsión deportistas profesionales - Aportaciones 2016 no aplicadas 2 (464)
32 | 207 | 13 | N | (L) Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe (465)
33 | 220 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe cálculo gravamen autonómico (466)
34 | 233 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe (467)
35 | 246 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe cálculo gravamen autonómico (468)
36 | 259 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe (469)
37 | 272 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe cálculo gravamen autonómico (470)
38 | 285 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe (471)
39 | 298 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe cálculo gravamen autonómico (472)
40 | 311 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo personal y familiar (473)
41 | 324 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe total cálculo gravamen autonómico (474)
42 | 337 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen estatal  (475)
43 | 350 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen estatal (476)
44 | 363 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general  - gravamen autonómico (477)
45 | 376 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen autonómico (478)
46 | 389 | 13 | N | (M) Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable ahorro (479)
47 | 402 | 13 | N | Datos adicionales - Rentas exentas salvo para determinar gravamen base liquidable general (480)
48 | 415 | 13 | N | Datos adicionales - Anualidades para alimentos a favor de los hijos. Importe (481)
49 | 428 | 600 | An | RESERVADO PARA LA A.E.A.T
50 | 1028 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10014000>
Total: |  | 1039

# 100-15

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "15000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (N) Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla 450 - Parte estatal (482)
7 | 26 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del  Impuesto importe casilla 450 - Parte autonómica (483)
8 | 39 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general del Impuesto importe casilla 475 - Parte estatal (484)
9 | 52 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala autonómica del Impuesto importe casilla 477 - Parte autonómica (485)
10 | 65 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte estatal (486)
11 | 78 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte autonómica (487)
12 | 91 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte estatal (488) | *
13 | 95 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medio gravamen - Parte autonómica (489) | *
14 | 99 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla 455 - Parte estatal (490)
15 | 112 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla 455 - Parte autonómica (491)
16 | 125 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general del lmpuesto importe casilla 476 - Parte estatal (492)
17 | 138 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala autonómica del Impuesto importe casilla 478 - Parte autonómica (493)
18 | 151 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte estatal (494)
19 | 164 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte autonómica  (495)
20 | 177 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medio gravamen - Parte estatal (496)
21 | 181 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medio gravamen - Parte autonómica (497)
22 | 185 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra estatal - Parte estatal (499)
23 | 198 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra autonómica - Parte autonómica (500)
24 | 211 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte estatal (501)
25 | 224 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte autonómica (502)
26 | 237 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión empresas nueva o reciente creación - Parte estatal (503)
27 | 250 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte estatal (504)
28 | 263 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte autonómica (505)
29 | 276 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones- Parte estatal (506)
30 | 289 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones - Parte autonómica (507)
31 | 302 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte estatal (508)
32 | 315 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte autonómica (509)
33 | 328 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte estatal (510)
34 | 341 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte autonómica (511 ]
35 | 354 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte estatal (512)
36 | 367 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte autonómica (513)
37 | 380 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte estatal (514)
38 | 393 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte autonómica (515)
39 | 406 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte estatal (516)
40 | 419 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte autonómica (517)
41 | 432 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras  - Por obras de mejora en la vivienda pendientes deducción - Parte estatal (518)
42 | 445 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - Suma deducciones autonómicas (519)
43 | 458 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida estatal - Parte estatal (520)
44 | 471 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida autonómica - Parte autonómica (521)
45 | 484 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - Parte estatal (522]
46 | 497 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - Parte estatal (523)
47 | 510 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2015 - Importe - Parte estatal (524]
48 | 523 | 1 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2015 - Regularización motivada por DA 45 [453] "1" o "0"
49 | 524 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2015 - Intereses demora -  Parte estatal (525)
50 | 537 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2015 - Importe - Parte autonómica (526)
51 | 550 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2015 - Intereses demora - Parte autonómica (527)
52 | 563 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2015 - Importe - Parte autonómica (528)
53 | 576 | 1 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2015 - Regularización motivada por  DA 45 [454] "1" o "0"
54 | 577 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2015 - Intereses demora - Parte autonómica (529)
55 | 590 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida estatal incrementada - Parte estatal (530)
56 | 603 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida autonómica incrementada - Parte autonómica (531)
57 | 616 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota líquida incrementada total (532)
58 | 629 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones: Por doble imposición internacional, rentas obtenidas y gravadas en el extranjero (533)
59 | 642 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones: Por doble imposición internacional supuestos aplicación régimen transparencia fiscal internacional (534)
60 | 655 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Deducciones: Por doble imposición supuestos aplicación régimen imputación rentas cesión derechos imagen (535)
61 | 668 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Retenciones deducibles a rendimientos bonificados - Importe retenciones no practicadas (536)
62 | 681 | 13 | N | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota resultante autoliquidación (537)
63 | 694 | 600 | An | RESERVADO PARA LA A.E.A.T
64 | 1294 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10015000>
Total: |  | 1305

# 100-16

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo |  | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "16000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N |  | (N) Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos del trabajo (538]
7 | 26 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos del capital mobiliario (539)
8 | 39 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Arrendamientos de inmuebles urbanos (540)
9 | 52 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Rendimientos de actividades económicas (541)
10 | 65 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Atribuidos por entidades en régimen de atribución de rentas (542)
11 | 78 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Imputados por agrupaciones de interés económico y UTE's (543)
12 | 91 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Ingresos a cuenta art. 92.8 Ley del Impuesto (544)
13 | 104 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Ganancias patrimoniales, incluidos premios (545)
14 | 117 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Pagos fraccionados (actividades económicas) (546)
15 | 130 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Cuotas del Impuesto sobre la Renta de no Residentes (547)
16 | 143 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Retenciones art. 11 Directiva 2003/48/CE (548)
17 | 156 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Retenciones y demás pagos a cuenta - Total pagos a cuenta (549)
18 | 169 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Cuota diferencial (550)
19 | 182 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción por maternidad - Importe deducción (551)
20 | 195 | 13 | N |  | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción por maternidad - Importe abono anticipado deducción (552)
21 | 208 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF descendiente (553)
22 | 217 | 15 | A | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - Nombre (554)
23 | 232 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (555)
24 | 240 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (556)
25 | 248 | 2 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - Nº personas derecho mínimo (557)
26 | 250 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - Se ha cedido el derecho deducción (558) |  | "0" - blanco, "1" - Si,    "2" .- No
27 | 251 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF cedente (559)
28 | 260 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - Se ha cedido el derecho deducción (560) |  | "0" - blanco, "1" - Si,    "2" .- No
29 | 261 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF beneficiario (561)
30 | 270 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - Importe deducción (562)
31 | 283 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción descendientes discapacidad - Importe abono anticipado deducción (563)
32 | 296 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF ascendiente (564)
33 | 305 | 15 | A | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Nombre (565)
34 | 320 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (566)
35 | 328 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (567)
36 | 336 | 2 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Nº personas derecho mínimo (568)
37 | 338 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Se ha cedido el derecho deducción (569) |  | "0" - blanco, "1" - Si,    "2" .- No
38 | 339 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad  - NIF cedente 1 (570)
39 | 348 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF cedente 2 (571)
40 | 357 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF cedente 3 (572)
41 | 366 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Se ha cedido el derecho deducción (573) |  | "0" - blanco, "1" - Si,    "2" .- No
42 | 367 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF beneficiario (574)
43 | 376 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Importe deducción (575)
44 | 389 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Importe abono anticipado deducción (576)
45 | 402 | 30 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Nº identificación título familia numerosa (577)
46 | 432 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Categoría familia numerosa - General (578)
47 | 433 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Categoría familia numerosa - Especial (579)
48 | 434 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Fecha inicio título familia numerosa (DDMMAAAA) (580)
49 | 442 | 8 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Fecha finalización título familia numerosa (DDMMAAAA) (581)
50 | 450 | 2 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Nº ascendientes forman parte familia numerosa  (582)
51 | 452 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Se ha cedido el derecho deducción (583) |  | "0" - blanco, "1" - Si,    "2" .- No
52 | 453 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 1 (584)
53 | 462 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 2 (585)
54 | 471 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 3 (586)
55 | 480 | 1 | Num | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Se ha cedido el derecho deducción (587) |  | "0" - blanco, "1" - Si,    "2" .- No
56 | 481 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - NIF beneficiario (588)
57 | 490 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Importe deducción (589)
58 | 503 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción familia numerosa - Importe abono anticipado deducción (590)
59 | 516 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes, separado o sin vinculo matrimonial, dos hijos sin derecho anualidades alimentos - Importe deducción (591)
60 | 529 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Deducción ascendientes, separado o sin vinculo matrimonial, dos hijos sin derecho anualidades alimentos - Importe abono anticipado deducción (592)
61 | 542 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Regularizaciones - Importe cobro anticipado descendientes sin derecho mínimo por descendientes (593)
62 | 555 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Regularizaciones - NIF descendientes deducción se regulariza (594)
63 | 564 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Regularizaciones - Importe cobro anticipado ascendientes sin derecho mínimo por ascendientes (595)
64 | 577 | 9 | An | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Regularizaciones - NIF ascendientes deducción se regulariza (596)
65 | 586 | 13 | N | C | Cálculo impuesto y resultado declaración (continuación) - Cuota diferencial y resultado - Resultado declaración (600)
66 | 599 | 600 | An |  | RESERVADO PARA LA A.E.A.T
67 | 1199 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10016000>
Total: |  | 1210

# 100-17

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "17000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (O) Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2016 - Cuota líquida autonómica incrementada (601)
7 | 26 | 13 | N | Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2016 -  50% deducciones doble imposición (602)
8 | 39 | 13 | N | Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2016 - Importe IRPF Cdad Autónoma residencia contribuyente (605)
9 | 52 | 13 | N | (P) Regularización - Mediante declaración complemetaria (ejercicio 2016) - Resultados a ingresar anteriores autoliquidaciones o liquidaciones administrativas (606)
10 | 65 | 13 | N | Regularización - Mediante declaración complemetaria (ejercicio 2016) - Devoluciones acordadas Agencia Tributaria, tramitación anteriores autoliquidaciones  (607)
11 | 78 | 13 | N | Regularización -Mediante declaración complemetaria (ejercicio 2016) - Resultado declaración complementaria (610)
12 | 91 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Resultados a ingresar de autoliquidaciones o liquidaciones administrativas [611]
13 | 104 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Devoluciones solicitadas a la Agencia Tributaria,  tramitación anteriores autoliquidaciones [612]
14 | 117 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Resultado de la solicitud de rectificación de autoliquidación [615]
15 | 130 | 13 | Num | Regularización - Mediante rectificación de autoliquidación - Número de justificante de la autoliquidación cuya rectificación se solicita [616]
16 | 143 | 1 | Num | RESERVADO PARA LA A.E.A.T
17 | 144 | 34 | An | Número de cuenta IBAN (618)
18 | 178 | 13 | N | Q) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (621)
19 | 191 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (625)
20 | 204 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (622)
21 | 217 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (625)
22 | 230 | 34 | An | Número de cuenta IBAN (626)
23 | 264 | 11 | An | Devolución - Código SWIFT-BIC Rectificación
24 | 275 | 11 | An | Devolución - Código SWIFT-BIC Compensación entre cónyuges
25 | 286 | 578 | An | RESERVADO PARA LA A.E.A.T
26 | 864 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10017000>
Total: |  | 875

# Anexo A.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "18000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Inversión con derecho a deducción (A)
7 | 26 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte estatal (627)
8 | 39 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte autonómica (628)
9 | 52 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Inversión con derecho a deducción (B)
10 | 65 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte estatal (629)
11 | 78 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte autonómica (630)
12 | 91 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Inversión con derecho a deducción (C )
13 | 104 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte estatal (631)
14 | 117 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte autonómica (632)
15 | 130 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Cantidades satisfechas con derecho a deducción (E)
16 | 143 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte estatal (633)
17 | 156 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte autonómica (634)
18 | 169 | 13 | N | Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte estatal (501)
19 | 182 | 13 | N | Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte autonómica (502)
20 | 195 | 13 | N | Deducción por inversión en vivienda habitual - Datos adicionales - Importe de los pagos realizados en el ejercicio al promotor o constructor (635)
21 | 208 | 9 | An | Deducción por inversión en vivienda habitual - Datos adicionales - NIF del promotor o constructor (636)
22 | 217 | 8 | Num | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Fecha adquisición vivienda (DDMMAAAA) (637)
23 | 225 | 20 | An | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Número de identificación del préstamo hipotecario (638)
24 | 245 | 5 | Num | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Porcentaje del préstamo destinado a adquisición (3 enteros y 2 decimales)  (639) | *
25 | 250 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Cantidades suscripción acciones entidades nueva o reciente creación - Importe (640)
26 | 263 | 9 | An | Deducción inversiones en empresas de nueva o reciente creación - Entidad 1 - NIF (641)
27 | 272 | 9 | An | Deducción inversiones en empresas de nueva o reciente creación - Entidad 2 - NIF (642)
28 | 281 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Importe total deducción inversiones empresa nueva o reciente creación - Base deducción (D)
29 | 294 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Importe total deducciones empresa nueva o reciente creación - Importe deducción (503)
30 | 307 | 20 | An | Deducción por alquiler de la vivienda habitual - NIF del arrendador 1 (643)
31 | 327 | 1 | Num | Deducción por alquiler de la vivienda habitual - Si ha consignado NIF de otro país [644] "1" o ·"0"
32 | 328 | 20 | An | Deducción por alquiler de la vivienda habitual - NIF del arrendador 2 (645)
33 | 348 | 1 | Num | Deducción por alquiler de la vivienda habitual - Si ha consignado NIF de otro país [646] 1" o ·"0"
34 | 349 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador (647)
35 | 362 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades satisfechas con derecho a deducción (F)
36 | 375 | 13 | N | Deducción por alquiler de la vivienda habitual - Importe deducción (648)
37 | 388 | 13 | N | Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte estatal (516)
38 | 401 | 13 | N | Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte autonómica (517]
39 | 414 | 600 | An | RESERVADO PARA LA A.E.A.T
40 | 1014 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10018000>
Total: |  | 1025

# Anexo A.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "19000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones por donativos - Aportaciones actividades mecenazgo límite 15 % base liquidable - Importe con derecho a deducción (G)
7 | 26 | 13 | N | Deducciones por donativos - Aportaciones actividades mecenazgo límite 15 % base liquidable - Importe de la deducción (649)
8 | 39 | 13 | N | Deducciones por donativos - Donativos entidades reguladas Ley 49/2002 - Importe con derecho a deducción (H)
9 | 52 | 13 | N | Deducciones por donativos - Donativos entidades reguladas Ley 49/2002 - Importe de la deducción (650)
10 | 65 | 13 | N | Deducciones por donativos - Donativos fundaciones y asociaciones utilidad pública Ley 49/2002 - Importe con derecho a deducción (J)
11 | 78 | 13 | N | Deducciones por donativos - Donativos fundaciones y asociaciones utilidad pública Ley 49/2002 - Importe de la deducción (651)
12 | 91 | 13 | N | Deducciones por donativos - Cuotas afiliación y aportaciones partidos políticos, federaciones, coaliciones o agrupamientos electorales - Importe con derecho a deducción (M)
13 | 104 | 13 | N | Deducciones por donativos - Cuotas afiliación y aportaciones partidos políticos, federaciones, coaliciones o agrupamientos electorales - Importe con derecho a deducción - Importe de la deducción (652)
14 | 117 | 13 | N | Deducciones por donativos - Deducciones por donativos - Parte estatal (506)
15 | 130 | 13 | N | Deducciones por donativos - Deducciones por donativos - Parte autonómica (507)
16 | 143 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe con derecho a deducción (I)
17 | 156 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe de la deducción (653)
18 | 169 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte estatal (504)
19 | 182 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte autonómica (505)
20 | 195 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Importe total de la deducción (654)
21 | 208 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte estatal (514)
22 | 221 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte autonómica (515)
23 | 234 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Cantidades satisfechas (655)
24 | 247 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 -  Base deducción (L)
25 | 260 | 13 | N | Deducción por obras de mejora en vivienda: cantidades pendientes deducción - Ejercicio 2012 - Importe deducción (518)
26 | 273 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Importe dotaciones (656
27 | 286 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (657)
28 | 299 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2013 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (658)
29 | 312 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Importe dotaciones (659)
30 | 325 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (660]
31 | 338 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (661)
32 | 351 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Pendiente de materializar (662)
33 | 364 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Importe dotaciones (663)
34 | 377 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (664)
35 | 390 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (665)
36 | 403 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Pendiente de materializar (666)
37 | 416 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Importe dotaciones (667)
38 | 429 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (668)
39 | 442 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (669)
40 | 455 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Pendiente de materializar (670)
41 | 468 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Importe de la deducción 2016
42 | 481 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2016 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (671)
43 | 494 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2016 - Inversiones prev. letras C y D 2º. a 6º.) artº. 27.4 (672)
44 | 507 | 600 | An | RESERVADO PARA LA A.E.A.T
45 | 1107 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10019000>
Total: |  | 1118

# Anexo A.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "20000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Saldo anterior
7 | 26 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Aplicado declaración (673)
8 | 39 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Pendiente aplicación
9 | 52 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interés público - Saldo anterior
10 | 65 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interés público - Aplicado declaración (674)
11 | 78 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interes público - Pendiente aplicación
12 | 91 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i  - Deducción
13 | 104 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i - Aplicado declaración (675)
14 | 117 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i  - Pendiente aplicación
15 | 130 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos  - Deducción
16 | 143 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos - Aplicado declaración (676)
17 | 156 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos  - Pendiente aplicación
18 | 169 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS - Deducción
19 | 182 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS -  Aplicado declaración (677)
20 | 195 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS - Pendiente aplicación
21 | 208 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Deducción
22 | 221 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Aplicado declaración (678)
23 | 234 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Pendiente aplicación
24 | 247 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Deducción
25 | 260 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Aplicado declaración (679)
26 | 273 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Pendiente aplicación
27 | 286 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016"- Deducción
28 | 299 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016" - Aplicado declaración (680]
29 | 312 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prog. Prep. Depor. Juegos "Río de Janeiro 2016" - Pendiente aplicación
30 | 325 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Deducción
31 | 338 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Aplicado declaración (681)
32 | 351 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Donostia/San Sebastián, Capital Europea de la Cultura 2016" - Pendiente aplicación
33 | 364 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Deducción
34 | 377 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Aplicado declaración (682)
35 | 390 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Expo Milán 2015" - Pendiente aplicación
36 | 403 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Deducción
37 | 416 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Aplicado declaración  (683)
38 | 429 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Universiada Invierno de Granada 2015" - Pendiente aplicación
39 | 442 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Deducción
40 | 455 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Aplicado declaración (684)
41 | 468 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Pendiente aplicación
42 | 481 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Deducción
43 | 494 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Aplicado declaración (685)
44 | 507 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Madrid Horse Week" - Pendiente aplicación
45 | 520 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Deducción
46 | 533 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Aplicado declaración (686)
47 | 546 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario segunda parte de El Quijote" - Pendiente aplicación
48 | 559 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Deducción
49 | 572 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Aplicado declaración (687)
50 | 585 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "World Challenge LFP/85 Aniversario de la Liga" - Pendiente aplicación
51 | 598 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Deducción
52 | 611 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Aplicado declaración (688)
53 | 624 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2017" - Pendiente aplicación
54 | 637 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Deducción
55 | 650 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Aplicado declaración (689)
56 | 663 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Pendiente aplicación
57 | 676 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Deducción
58 | 689 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Aplicado declaración (690]
59 | 702 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Pendiente aplicación
60 | 715 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Deducción
61 | 728 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Aplicado declaración (691)
62 | 741 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Pendiente aplicación
63 | 754 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Deducción
64 | 767 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Aplicado declaración (692)
65 | 780 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Pendiente aplicación
66 | 793 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Deducción
67 | 806 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Aplicado declaración (693)
68 | 819 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Pendiente aplicación
69 | 832 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Deducción
70 | 845 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Aplicado declaración  (694)
71 | 858 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Pendiente aplicación
72 | 871 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Deducción
73 | 884 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Aplicado declaración (695)
74 | 897 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Pendiente aplicación
75 | 910 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME) 2017" - Deducción
76 | 923 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME) 2017" - Aplicado declaración (696)
77 | 936 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME) 2017" - Pendiente aplicación
78 | 949 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan director Recuperación Patrimonio cultural de Lorca- Deducción
79 | 962 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan director Recuperación Patrimonio cultural de Lorca- Aplicado declaración (697)
80 | 975 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan director Recuperación Patrimonio cultural de Lorca - Pendiente aplicación
81 | 988 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Deducción
82 | 1001 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Aplicado declaración (698)
83 | 1014 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Pendiente aplicación
84 | 1027 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Deducción
85 | 1040 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Aplicado declaración (699)
86 | 1053 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Pendiente aplicación
87 | 1066 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Deducción
88 | 1079 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Aplicado declaración (700)
89 | 1092 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Pendiente aplicación
90 | 1105 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Deducción
91 | 1118 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Aplicado declaración (701)
92 | 1131 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Pendiente aplicación
93 | 1144 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Deducción
94 | 1157 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Aplicado declaración (702)
95 | 1170 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Pendiente aplicación
96 | 1183 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Deducción
97 | 1196 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Aplicado declaración (703)
98 | 1209 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Pendiente aplicación
99 | 1222 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XX Aniversario Cuenca Ciudad Patrimonio de la Humanidad- Deducción
100 | 1235 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XX Aniversario Cuenca Ciudad Patrimonio de la Humanidad- Aplicado declaración (704)
101 | 1248 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XX Aniversario Cuenca Ciudad Patrimonio de la Humanidad- Pendiente aplicación
102 | 1261 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Deducción
103 | 1274 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Aplicado declaración (705)
104 | 1287 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Pendiente aplicación
105 | 1300 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Deducción
106 | 1313 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Aplicado declaración (706)
107 | 1326 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Pendiente aplicación
108 | 1339 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Deducción
109 | 1352 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Aplicado declaración (707)
110 | 1365 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Pendiente aplicación
111 | 1378 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Deducción
112 | 1391 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Aplicado declaración (708)
113 | 1404 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Pendiente aplicación
114 | 1417 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2017 Año de la retina en España- Deducción
115 | 1430 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2017 Año de la retina en España- Aplicado declaración (709)
116 | 1443 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2017 Año de la retina en España- Pendiente aplicación
117 | 1456 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Deducción
118 | 1469 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Aplicado declaración (710)
119 | 1482 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Pendiente aplicación
120 | 1495 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Deducción
121 | 1508 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Aplicado declaración (711)
122 | 1521 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Pendiente aplicación
123 | 1534 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2150 Aniversario de Numancia- Deducción
124 | 1547 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2150 Aniversario de Numancia- Aplicado declaración (712)
125 | 1560 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2150 Aniversario de Numancia- Pendiente aplicación
126 | 1573 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V Centenario fallecimiento Fernando el Católico- Deducción
127 | 1586 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V Centenario fallecimiento Fernando el Católico- Aplicado declaración (713)
128 | 1599 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V Centenario fallecimiento Fernando el Católico- Pendiente aplicación
129 | 1612 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 525 Aniversario Descubrimiento América en Palos de la Frontera- Deducción
130 | 1625 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 525 Aniversario Descubrimiento América en Palos de la Frontera- Aplicado declaración (714)
131 | 1638 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 525 Aniversario Descubrimiento América en Palos de la Frontera- Pendiente aplicación
132 | 1651 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Deducción
133 | 1664 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Aplicado declaración (715)
134 | 1677 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Pendiente aplicación
135 | 1690 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Deducción
136 | 1703 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Aplicado declaración (716)
137 | 1716 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Pendiente aplicación
138 | 1729 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Deducción
139 | 1742 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Aplicado declaración (717)
140 | 1755 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Pendiente aplicación
141 | 1768 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. Económicas 2015 (720)
142 | 1781 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (721)
143 | 1794 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (722)
144 | 1807 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. Económicas 2016 (723)
145 | 1820 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (724)
146 | 1833 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (725)
147 | 1846 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Deducción por inversión elementos nuevos  (726)
148 | 1859 | 600 | An | RESERVADO PARA LA A.E.A.T
149 | 2459 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10020000>
Total: |  | 2470

# Anexo A.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "21000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Saldo anterior
7 | 26 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Aplicado declaración (727)
8 | 39 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Pendiente aplicación
9 | 52 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Saldo anterior
10 | 65 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Aplicado declaración (728)
11 | 78 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Pendiente aplicación
12 | 91 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. investigación, desarrollo e innovación tecnológica, artº. 35 LIS - Deducción
13 | 104 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. investigación, desarrollo e innovación tecnológica, artº. 35 LIS - Aplicado declaración (729)
14 | 117 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. investigación, desarrollo e innovación tecnológica, artº. 35 LIS- Pendiente aplicación
15 | 130 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Deducción
16 | 143 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS (730)
17 | 156 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Pendiente aplicación
18 | 169 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Deducción
19 | 182 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Aplicado declaración (731)
20 | 195 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad,  artº. 38 LIS - Pendiente de aplicación
21 | 208 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994  - Deducción
22 | 221 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994 - Aplicado declaración (732)
23 | 234 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994  - Pendiente aplicación
24 | 247 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Deducción
25 | 260 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Aplicado declaración (733)
26 | 273 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Pendiente aplicación
27 | 286 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Importe total de las deducciones (734)
28 | 299 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Deducciones - Parte estatal (508)
29 | 312 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones: importe aplicado - Deducciones - Parte autonómica (509]
30 | 325 | 600 | An | RESERVADO PARA LA A.E.A.T
31 | 925 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10021000>
Total: |  | 936

# Anexo B.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "22000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios de ayudas familiares (735)
7 | 26 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios ayudas viviendas protegidas (736)
8 | 39 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión vivienda habitual protegida/personas jóvenes (737)
9 | 52 | 13 | N | Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler de vivienda habitual (738)
10 | 65 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión en la adquisición de acciones y participaciones  (739)
11 | 78 | 13 | N | Deducciones Autonómicas - Andalucía - Por adopción de hijos ámbito internacional (740)
12 | 91 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con discapacidad (741)
13 | 104 | 13 | N | Deducciones Autonómicas - Andalucía - Para padre/madre de familia monoparental con ascendientes mayores 75 años (742)
14 | 117 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Deducción con carácter general  (743)
15 | 130 | 11 | An | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Cuenta cotización (744)
16 | 141 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Importe (745)
17 | 154 | 11 | An | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Cuenta cotización (746)
18 | 165 | 13 | N | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Importe (747)
19 | 178 | 13 | N | Deducciones Autonómicas - Andalucía - Para trabajadores por gastos de defensa jurídica de la relación laboral (748)
20 | 191 | 13 | N | Deducciones Autonómicas - Andalucía - Por obras en vivienda (Cantidades 2012 pdtes. deducción 4 años exceder en 2012 base deducción) (749)
21 | 204 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con cónyuges o parejas de hecho con discapacidad (750)
22 | 217 | 13 | N | Deducciones Autonómicas - Andalucía - Otras deducciones (751)
23 | 230 | 13 | N | Deducciones Autonómicas - Andalucía - Total deducciones autonómicas (519)
24 | 243 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del tercer hijo o sucesivos (752)
25 | 256 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción de un hijo en atención al grado discapacidad (753)
26 | 269 | 13 | N | Deducciones Autonómicas - Aragón - Por adopción internacional de niños (754)
27 | 282 | 13 | N | Deducciones Autonómicas - Aragón - Por el cuidado de personas dependientes (755)
28 | 295 | 13 | N | Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico (756)
29 | 308 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo  (757)
30 | 321 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en acciones de entidades que cotizan en Mercado Alternativo Bursátil (758)
31 | 334 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en la adquisición de acciones o participaciones sociales (759)
32 | 347 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición o rehabilitación de vivienda habitual en núcleos rurales o análogos (760)
33 | 360 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición libros de texto y material escolar (761)
34 | 373 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual vinculado operaciones dación en pago. Importe  (762)
35 | 386 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda social (deducción arrendador) (763)
36 | 399 | 13 | N | Deducciones Autonómicas - Aragón - Para mayores de 70 años (764)
37 | 412 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en entidades de la economía social (765)
38 | 425 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del primer y/o segundo hijo en poblaciones de menos de 10.000 habitantes (766)
39 | 438 | 13 | N | Deducciones Autonómicas - Aragón - Por gastos de guardería de hijos menores de 3 años (767
40 | 451 | 13 | N | RESERVADO PARA LA A.E.A.T (rellenar a ceros)
41 | 464 | 13 | N | Deducciones Autonómicas - Aragón -  Otras deducciones (769)
42 | 477 | 13 | N | Deducciones Autonómicas - Aragón - Total deducciones autonómicas (519)
43 | 490 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (770)
44 | 503 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes con discapacidad (771)
45 | 516 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes con discapacidad (772)
46 | 529 | 13 | N | Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (773)
47 | 542 | 13 | N | Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual  (774)
48 | 555 | 13 | N | Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (775)
49 | 568 | 13 | N | Deducciones Autonómicas - Asturias - Por adopción internacional de menores (776)
50 | 581 | 13 | N | Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones constituidas en la misma fecha  (777)
51 | 594 | 13 | N | Deducciones Autonómicas - Asturias - Para familias numerosas (778)
52 | 607 | 13 | N | Deducciones Autonómicas - Asturias - Para familias monoparentales (779)
53 | 620 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (780)
54 | 633 | 13 | N | Deducciones Autonómicas - Asturias - Por certificación de gestión forestal sostenible (781)
55 | 646 | 13 | N | Deducciones Autonómicas - Asturias - Por gastos de descendientes en centros de 0 a 3 años (782)
56 | 659 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición de libros de texto y material escolar (783)
57 | 672 | 13 | N | Deducciones Autonómicas - Asturias -  Otras deducciones (784)
58 | 685 | 13 | N | Deducciones Autonómicas - Asturias - Total deducciones autonómicas (519)
59 | 698 | 600 | An | RESERVADO PARA LA A.E.A.T
60 | 1298 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10022000>
Total: |  | 1309

# Anexo B.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "23000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Illes Balears - Por determinadas inversiones de mejora de sostenibilidad vivienda habitual (785)
7 | 26 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos adquisición libros de texto (786)
8 | 39 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos de aprendizaje extraescolar de idiomas extranjeros (787)
9 | 52 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones entidades destinadas investigación, desarrollo científico o tecnológico o innovación  (788)
10 | 65 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones, cesiones uso o contratos comodato y convenios colaboración empresarial  (789)
11 | 78 | 13 | N | Deducciones Autonómicas - Illes Balears - Por inversión en la adquisición de acciones o participaciones sociales de nuevas entidades (790)
12 | 91 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones, cesiones uso o contrato de comodato y convenios colaboración, mecenazgo deportivo (791)
13 | 104 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones a determinadas entidades fomento lengua catalana (792)
14 | 117 | 13 | N | Deducciones Autonómicas - Illes Balears - Para declarentes con discapacidad física, psiquica o sensorial o con descendientes con esta condición  (793]
15 | 130 | 13 | N | Deducciones Autonómicas - Illes Balears - Por arrendamiento de vivienda habitual a favor de determinados colectivos [972]
16 | 143 | 13 | N | Deducciones Autonómicas - Illes Balears -  Otras deducciones (794)
17 | 156 | 13 | N | Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (519)
18 | 169 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones con finalidad ecológica (795)
19 | 182 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones rehabilitación o conservación patrimonio histórico de Canarias (796)
20 | 195 | 13 | N | Deducciones Autonómicas - Canarias - Por cantidades destinadas restauración/rehabilitación/reparación bienes inmuebles declarados de Interés Cultural (797)
21 | 208 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de estudios (798)
22 | 221 | 13 | N | Deducciones Autonómicas - Canarias - Por trasladar residencia a otra isla para realizar actividad laboral cuenta ajena/actividad económica (799)
23 | 234 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones en metálico a descendientes menores 35 años para adquisición/rehabilitación primera vivienda habitual (800)
24 | 247 | 13 | N | Deducciones Autonómicas - Canarias - Por nacimiento o adopción de hijos (801)
25 | 260 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes con discapacidad y mayores de 65 años (802)
26 | 273 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de guardería (803)
27 | 286 | 13 | N | Deducciones Autonómicas - Canarias - Por familia numerosa (804)
28 | 299 | 13 | N | Deducciones Autonómicas - Canarias - Por inversión en vivienda habitual (805)
29 | 312 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de adecuación vivienda habitual por razón discapacidad (806)
30 | 325 | 13 | N | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Importe (807)
31 | 338 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral 1 (808)
32 | 358 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral 1. "1 o cero" (809)
33 | 359 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral 2 (810)
34 | 379 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral 2. "1 o cero" (811)
35 | 380 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes desempleados (812)
36 | 393 | 13 | N | Deducciones Autonómicas - Canarias - Otras deducciones (813)
37 | 406 | 13 | N | Deducciones Autonómicas - Canarias - Total deducciones autonómicas (519)
38 | 419 | 13 | N | Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con  discapacidad - Importe (814)
39 | 432 | 13 | N | Deducciones Autonómicas - Cantabria - Por cuidado de familiares (815)
40 | 445 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora. Importe 2014 y/o 2015 pendiente de aplicación (816)
41 | 458 | 9 | An | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - NIF persona/entidad  obras (817)
42 | 467 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - Importe deducción (818 )
43 | 480 | 13 | N | Deducciones Autonómicas - Cantabria - Por donativos a fundaciones o al Fondo Cantabria Coopera (819)
44 | 493 | 13 | N | Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (820)
45 | 506 | 13 | N | Deducciones Autonómicas - Cantabria - Por inversión adquisición acciones/participaciones sociales nuevas entidades o reciente creación (821)
46 | 519 | 13 | N | Deducciones Autonómicas - Cantabria - Por gastos de enfermedad (822)
47 | 532 | 13 | N | Deducciones Autonómicas - Cantabria - Otras deducciones (823)
48 | 545 | 13 | N | Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (519)
49 | 558 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora generadas en 2016 a deducir en los 2 años siguientes [824]
50 | 571 | 600 | An | RESERVADO PARA LA A.E.A.T
51 | 1171 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10023000>
Total: |  | 1182

# Anexo B.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "24000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (825)
7 | 26 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (826)
8 | 39 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (827)
9 | 52 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (828)
10 | 65 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (829)
11 | 78 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por cantidades para la Cooperación Internacional, lucha contra pobreza y exclusión social  (830)
12 | 91 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por familia numerosa (831)
13 | 104 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por donaciones con finalidad en investigación y desarrollo e innovación empresarial (832)
14 | 117 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por gastos en la adquisición de libros de texto y enseñanza de idiomas (833)
15 | 130 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento familiar no rumunerado de menores (834)
16 | 143 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento no remunerado de mayores de 65 años y/o discapacitados (835)
17 | 156 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha -  Por arrendamiento de vivienda habitual por menores de 36 años  (836)
18 | 169 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Otras deducciones (837)
19 | 182 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (519)
20 | 195 | 13 | N | Deducciones Autonómicas - Castilla y León - Para contribuyentes afectados por discapacidad (838)
21 | 208 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales  (839)
22 | 221 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cantidades donadas a fundaciones (840)
23 | 234 | 13 | N | Deducciones Autonómicas - Castilla y León - Poro cantidades donadas para el fomento de la investigación, desarrollo e innovación (841)
24 | 247 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión en patrimonio histórico, cultural y natural  (842)
25 | 260 | 13 | N | Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años  (843)
26 | 273 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión instalaciones medioambientales/adaptación a personas con discapacidad en vvda.habitual (844)
27 | 286 | 8 | Num | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Fecha visado proyecto (845)
28 | 294 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Importe  (846)
29 | 307 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducción para el fomento de emprendimiento (847)
30 | 320 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones para el fomento del autoempleo mujeres y jóvenes. Importe generado 2013 pdte. aplicación (848)
31 | 333 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones para el fomento del autoempleo mujeres y jóvenes. Importe aplicado en el ejercicio (849)
32 | 346 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2013 pdte. aplicación (850)
33 | 359 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2014 pdte. aplicación (851)
34 | 372 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2015 pdte. aplicación (852)
35 | 385 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe aplicado en el ejercicio (853)
36 | 398 | 13 | N | Deducciones Autonómicas - Castilla y León - Por familia numerosa (854)
37 | 411 | 13 | N | Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (855)
38 | 424 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas (856)
39 | 437 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas en 2014  y/o 2015 (857)
40 | 450 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Nif persona empleada (858)
41 | 459 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Importe (859)
42 | 472 | 13 | N | Deducciones Autonómicas - Castilla y León - Por paternidad  (860)
43 | 485 | 13 | N | Deducciones Autonómicas - Castilla y León - Por gastos de adopción (861)
44 | 498 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuotas Seg.Social empleados del hogar - Nif persona empleada (862)
45 | 507 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuotas Seg.Social empleados del hogar - Importe (863)
46 | 520 | 13 | N | Deducciones Autonómicas - Castilla y León - Importe total aplicado  (864)
47 | 533 | 13 | N | Deducciones Autonómicas - Castilla y León - Otras deducciones (865)
48 | 546 | 13 | N | Deducciones Autonómicas - Castilla y León - Total deducciones autonómicas  (519)
49 | 559 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2014, 2015 y 2016. Importe 2014 pdte. aplicación (866)
50 | 572 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2014, 2015 y 2016. Importe 2015 pdte. aplicación (867)
51 | 585 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2014, 2015 y 2016. Importe 2016 pdte. aplicación  (868)
52 | 598 | 600 | An | RESERVADO PARA LA A.E.A.T
53 | 1198 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10024000>
Total: |  | 1209

# Anexo B.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "25000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Cataluña - Por nacimiento o adopción de un hijo (869)
7 | 26 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan el uso lengua catalana (870)
8 | 39 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan la investigación científica (871)
9 | 52 | 13 | N | Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual  (872)
10 | 65 | 13 | N | Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudios universitarios de master y doctorado (873)
11 | 78 | 13 | N | Deducciones Autonómicas - Cataluña - Para los contribuyentes que queden viudos (874)
12 | 91 | 13 | N | Deducciones Autonómicas - Cataluña - Por rehabilitación vivienda habitual (875)
13 | 104 | 13 | N | Deducciones Autonómicas - Cataluña - Por donaciones entidades en beneficio del medio ambiente (876)
14 | 117 | 13 | N | Deducciones Autonómicas - Cataluña - Por inversión por ángel inversor y por adquisición de acciones entidades nuevas o de creación reciente (877)
15 | 130 | 13 | N | Deducciones Autonómicas - Cataluña - Por inversión en acciones de entidades que cotizan en empresas en expansión (878)
16 | 143 | 13 | N | Deducciones Autonómicas - Cataluña - Otras deducciones (879)
17 | 156 | 13 | N | Deducciones Autonómicas - Cataluña - Total deducciones autonómicas (519)
18 | 169 | 13 | N | Deducciones Autonómicas - Extremadura - Por adquisición o rehabilitación vivienda habitual para jóvenes y víctimas del terrorismo (880)
19 | 182 | 13 | N | Deducciones Autonómicas - Extremadura - Por trabajo dependiente (881)
20 | 195 | 13 | N | Deducciones Autonómicas - Extremadura - Por cuidado de familiares con discapacidad (882)
21 | 208 | 13 | N | Deducciones Autonómicas - Extremadura - Por acogimiento de menores (883)
22 | 221 | 13 | N | Deducciones Autonómicas - Extremadura - Por  partos múltiples (884)
23 | 234 | 13 | N | Deducciones Autonómicas - Extremadura - Por compra de material escolar (885)
24 | 247 | 13 | N | Deducciones Autonómicas - Extremadura - Por inversión en la adquisición de acciones o participaciones sociales (886)
25 | 260 | 13 | N | Deducciones Autonómicas - Extremadura - Por gastos de guardería para hijos menores de 4 años (887)
26 | 273 | 13 | N | Deducciones Autonómicas - Extremadura - Para contribuyentes viudos (888)
27 | 286 | 13 | N | Deducciones Autonómicas - Extremadura - Por arrendamiento vivienda habitual (889)
28 | 299 | 13 | N | Deducciones Autonómicas - Extremadura - Por adquisición o rehabilitación segunda vivienda en el medio rural (890)
29 | 312 | 13 | N | Deducciones Autonómicas - Extremadura -  Otras deducciones (891)
30 | 325 | 13 | N | Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (519)
31 | 338 | 13 | N | Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (892)
32 | 351 | 13 | N | Deducciones Autonómicas - Galicia - Por familia numerosa (893)
33 | 364 | 13 | N | Deducciones Autonómicas - Galicia - Por cuidado hijos menores (894)
34 | 377 | 13 | N | Deducciones Autonómicas - Galicia - Por contribuyentes con discapacidad = > 65 años que precisan ayuda de terceras personas (895)
35 | 390 | 13 | N | Deducciones Autonómicas - Galicia - Por gastos uso nuevas tecnologías en hogares gallegos (896)
36 | 403 | 13 | N | Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual  por contribuyentes de edad igual o inferior a 35 años (897)
37 | 416 | 13 | N | Deducciones Autonómicas - Galicia - Por acogimiento familiar de menores (898)
38 | 429 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación (900)
39 | 442 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación y su financiación (900)
40 | 455 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones de entidades empresas en expansión Mercado Alternativo Bolsista (901)
41 | 468 | 13 | N | Deducciones Autonómicas - Galicia - Por donaciones finalidad en investigacion y desarrollo científico e innovación tecnológica (902)
42 | 481 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables (903)
43 | 494 | 20 | An | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables - Código de instalación (904)
44 | 514 | 13 | N | Deducciones Autonómicas - Galicia - Otras deducciones (905)
45 | 527 | 13 | N | Deducciones Autonómicas - Galicia - Total deducciones autonómicas (519)
46 | 540 | 13 | N | Deducciones Autonómicas - Madrid - Por nacimiento o adopción de hijos (906)
47 | 553 | 13 | N | Deducciones Autonómicas - Madrid - Por adopción internacional de niños (907)
48 | 566 | 13 | N | Deducciones Autonómicas - Madrid - Por acogimiento familiar de menores (908)
49 | 579 | 13 | N | Deducciones Autonómicas - Madrid - Por acogimiento no remunerado de mayores 65 años y/o con discapacidad (909)
50 | 592 | 13 | N | Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años (910)
51 | 605 | 13 | N | Deducciones Autonómicas - Madrid - Por gastos educativos (911)
52 | 618 | 13 | N | Deducciones Autonómicas - Madrid - Para familias con dos o más descendientes e ingresos reducidos (912)
53 | 631 | 13 | N | Deducciones Autonómicas - Madrid - Por inversión en adquisición de acciones y participaciones sociales de nuevas entidades o de reciente creación (913)
54 | 644 | 13 | N | Deducciones Autonómicas - Madrid -  Para el fomento del autoempleo de jóvenes menores de 35 años (914)
55 | 657 | 13 | N | Deducciones Autonómicas - Madrid - Por inversiones en entidades cotizadas en el Mercado Alternativo Bursátil (915)
56 | 670 | 13 | N | Deducciones Autonómicas - Madrid - Otras deducciones (916)
57 | 683 | 13 | N | Deducciones Autonómicas - Madrid - Total deducciones autonómicas (519)
58 | 696 | 600 | An | RESERVADO PARA LA A.E.A.T
59 | 1296 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10025000>
Total: |  | 1307

# Anexo B.5

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "26000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión vivienda habitual jóvenes edad igual/inferior 35 años (incluido rég. transitorio) (917)
7 | 26 | 13 | N | Deducciones Autonómicas - Murcia - Por donativos (918)
8 | 39 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de guardería para hijos menores de 3 años (919)
9 | 52 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (920)
10 | 65 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (921)
11 | 78 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en la adquisición de acciones y participaciones sociales de nuevas entidades (922)
12 | 91 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en entidades cotizadas Mercado Alternativo Bursátil (923)
13 | 104 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de material escolar y libros de texto (924)
14 | 117 | 13 | N | Deducciones Autonómicas - Murcia - Otras deducciones (925)
15 | 130 | 13 | N | Deducciones Autonómicas - Murcia - Total deducciones autonómicas (519)
16 | 143 | 13 | N | Deducciones Autonómicas - La Rioja - Por nacimiento y adopción del segundo o ulterior hijo (926)
17 | 156 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas rehabilitación vivienda habitual (927)
18 | 169 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas adquisición o contrucción vivienda habitual para jóvenes (928)
19 | 182 | 4 | Num | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Código municipio (929)
20 | 186 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Importe  (930)
21 | 199 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas rehabilitación vivienda habitual para personas con discapacidad (931)
22 | 212 | 13 | N | Deducciones Autonómicas - La Rioja - Por fomento del autoempleo (932)
23 | 225 | 13 | N | Deducciones Autonómicas - La Rioja - Otras deducciones (933)
24 | 238 | 13 | N | Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (519)
25 | 251 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento, adopción o acogimiento familiar (934)
26 | 264 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento o adopción múltiples (935)
27 | 277 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento o adopción hijos con discapacidad (936)
28 | 290 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por familia numerosa (937)
29 | 303 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades custodia en guarderías y primer ciclo educación infantil hijos menores de 3 años (938)
30 | 316 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por conciliación del trabajo con la vida familiar (939)
31 | 329 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Para contribuyentes con un grado de discapacidad igual o superior al 33 por 100, de edad igual o superior a 65 años (940)
32 | 342 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por ascendientes > 75 años ó > 65 años que sean personas con discapacidad (941)
33 | 355 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por realización por uno de los cónyuges de labores no remuneradas en el hogar (942)
34 | 368 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por primera adquisición vivienda habitual por contribuyentes edad igual o inferior 35 años (943)
35 | 381 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición vivienda habitual por personas con discapacidad (944)
36 | 394 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades adquisición o rehabilitación vivienda habitual, procedentes ayudas públicas (945)
37 | 407 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de la vivienda habitual (946)
38 | 420 | 20 | An | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - NIF arrendador (947)
39 | 440 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Importe (948)
40 | 453 | 1 | Num | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Si ha consignado NIF de otro país (949) "1 o cero"
41 | 454 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades inversiones fuentes energía renovables en vivienda habitual (950)
42 | 467 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones con finalidad ecológica (951)
43 | 480 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (952)
44 | 493 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades donadas para la conservación, reparación y restauración de bienes (953)
45 | 506 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades destinadas a la conservación, reparación y restauración de bienes (954)
46 | 519 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por donaciones al fomento de la Lengua Valenciana (955)
47 | 532 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por contribuyentes con dos o más descendientes (956)
48 | 545 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (957)
49 | 558 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición material escolar (958)
50 | 571 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual  - NIF persona o entidad (959)
51 | 580 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual - Importe  (960)
52 | 593 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones importes dinerarios a otros fines culturales (961)
53 | 606 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Otras deducciones (962)
54 | 619 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Total deduciones autonómicas (519)
55 | 632 | 20 | An | Información adicional deducción autonómica por arrendamiento - NIF/NIE arrendador 1 [963]
56 | 652 | 1 | Num | Información adicional deducción autonómica por arrendamiento - Si ha consignado NIF de otro país 1 - "1 o cero"  [964]
57 | 653 | 13 | N | Información adicional deducción autonómica por arrendamiento - Importe 1  [965]
58 | 666 | 20 | An | Información adicional deducción autonómica por arrendamiento - NIF/NIE arrendador 2 [966]
59 | 686 | 1 | Num | Información adicional deducción autonómica por arrendamiento - Si ha consignado NIF de otro país 2 - "1 o cero"  [967]
60 | 687 | 13 | N | Información adicional deducción autonómica por arrendamiento - Importe 2  [968]
61 | 700 | 13 | N | Información adicional deducción autonómica por arrendamiento - Importe total satisfecho [969]
62 | 713 | 13 | N | Información adicional deducción autonómica por arrendamiento - Cantidades satisfechas con derecho a deducción  [970]
63 | 726 | 13 | N | Información adicional deducción autonómica por arrendamiento - Importe deducción autonómica por arrendamiento  [971]
64 | 739 | 600 | An | RESERVADO PARA LA A.E.A.T
65 | 1339 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10026000>
Total: |  | 1350

# I-D

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre la Renta de las Personas Físicas 2016
Nº | Posic. | Long. | Tipo | Descripción |  | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. |  | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. |  | OBLIGATORIO | Constante "27000"
4 | 11 | 1 | An | Fin de identificador de modelo. |  | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Resumen declaración (2) - Base liquidable general sometida a gravamen [450]
7 | 26 | 13 | N | Resumen declaración (2) - Base liquidable del ahorro [455]
8 | 39 | 13 | N | Resumen declaración (2) - Cuota íntegra estatal [499]
9 | 52 | 13 | N | Resumen declaración (2) - Cuota íntegra autonómica [500]
10 | 65 | 13 | N | Resumen declaración (2) - Cuota líquida estatal [520]
11 | 78 | 13 | N | Resumen declaración (2) - Cuota líquida autonómica [521]
12 | 91 | 13 | N | Resumen declaración (2) - Resultado a ingresar o a devolver [625]
13 | 104 | 1 | Num | Opción de tributación. "1" Individual, "2" Conjunta.
14 | 105 | 1 | Num | Resumen declaración (2) - Solicitud de suspensión ingreso cónyuge/Renuncia cobro devolución otro cónyuge. "1" o "0" [7]
15 | 106 | 13 | N | Declaración Complementaria (3) - Resultado de Declaración Complementaria [610]
16 | 119 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 610 positiva - NO FRACCIONA el pago [1]  "1" o "0"
17 | 120 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 610 positiva - SÍ FRACCIONA el pago [6] "1" o "0"
18 | 121 | 13 | N | Fraccionamiento del pago e ingreso (4) - Casilla 610 positiva - Importe  [I1]
19 | 134 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 610 positiva - Forma de pago -"0" No consta; "1" Efectivo; "2" Adeudo en Cuenta; "3" Domiciliación
20 | 135 | 1 | Num | Opciones de pago 2º plazo (5) - NO DOMICILIA el pago [2]   "1" o "0"
21 | 136 | 1 | Num | Opciones de pago 2º plazo (5) - SÍ DOMICILIA el pago [3] "1" o "0"
22 | 137 | 13 | N | Opciones de pago 2º plazo (5) - Importe del 2º plazo [I2]
23 | 150 | 1 | Num | Devolución (6) - Casilla 610 negativa - "0" No consta, "1" Devolución y "2" Renuncia devolución
24 | 151 | 13 | N | Devolución (6) - Casilla 610 negativa - Importe [D]
25 | 164 | 34 | An | Cuenta bancaria (7) Número de cuenta IBAN
26 | 198 | 11 | An | Devolución - Código SWIFT-BIC
27 | 209 | 589 | An | RESERVADO PARA LA A.E.A.T
28 | 798 | 12 | An | Identificador de Fin de registro. |  | OBLIGATORIO | Constante </T10027000>
Total: |  | 809