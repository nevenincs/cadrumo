# 100-00

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 17 | An | Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "<T100020170A0000>"
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
15 | *** | 18 | An | Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "</T100020170A0000>"
16 | *** | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total |  | Variable
 |  |  |  | (**) A cumplimentar por las entidades desarrolladoras (EEDD)
 |  |  |  | Idioma de la declaración: (E) Castellano, (C) Catalán, (G) Gallego, (V) Valenciano
 |  |  |  | Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
 |  |  |  | NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
 |  |  | Páginas Complementarias
 |  |  | Pág | APARTADO | Ocurrencias
 |  |  | 1 | Vivienda habitual | 12
 |  |  | 4 | Rendimientos del trabajo | 6
 |  |  | 4 | Rendimientos del capital mobiliario a integrar en la base imponible del ahorro | 6
 |  |  | 4 | Rend.capital mobiliario: Disp. Transitoria 4ª | 6
 |  |  | 5 | Rendimientos del capital mobiliario a integrar en la base imponible general | 6
 |  |  | 5 | Inmuebles no afectos AAEE | 60
 |  |  | 5 | Inmuebles arrendados por ent.reg.atrib.rentas | 60
 |  |  | 5 | Inmuebles afectos AAEE | 60
 |  |  | 6 | (E1) Rtos. aaee estim. directa | 6
 |  |  | 7 | (E2) Rtos. aaee estim. objetiva | 6
 |  |  | 8 | (E3) Rtos. activ. agricolas | 6
 |  |  | 9 | (F) Regímenes especiales | 8
 |  |  | 10 | (F) Imputaciones de agrupaciones de interés económico y uniones temporales de empresas | 8
 |  |  | 10 | (F) Imputaciones de rentas en el régimen de transparencia fiscal internacional | 8
 |  |  | 10 | (F) Imputación de rentas por la cesión de derechos de imagen | 8
 |  |  | 10 | (F) Imputación de rentas por la participación en Instituciones de Inversión Colectiva constituidas en paraísos fiscales | 8
 |  |  | 10 | (G1) Premios obtenidos por la participación en juegos, rifas o combinaciones aleatorias sin fines publicitarios | 6
 |  |  | 10 | (G1) Premios obtenidos por la participación en concursos o combinaciones aleatorias con fines publicitarios | 6
 |  |  | 10 | (G1) Otras ganancias y pérdidas patrimoniales que no derivan de la transmisión de elementos patrimoniales | 6
 |  |  | 11 | (G2) aplicación disp. Transitoria 9ª | 40
 |  |  | 11 | (G2) G/P patrimoniales sometidas a retención o ingreso a cuenta derivadas de transmisiones o reembolsos de acciones o participaciones | 60
 |  |  |  | de instituciones de inversión colectiva
 |  |  | 11 | (G2) G/P patrimoniales derivadas de transmisiones de acciones o participaciones negociadas | 60
 |  |  | 11 | (G2) Ganancias y pérdidas patrimoniales derivadas de transmisiones de derechos de suscripción | 60
 |  |  | 12 | (G2) G/P patrimoniales derivadas de transmisiones de otros elementos patrimoniales | 40
 |  |  | 12 | (G2) Otras ganancias patrimoniales | 15
 |  |  | 12 | (G2) Imputación a 2017 de G/P patrimoniales derivadas de transmisiones efectuadas en ejercicios anteriores (GANANCIAS) | 15
 |  |  | 12 | (G2) Imputación a 2017 de G/P patrimoniales derivadas de transmisiones efectuadas en ejercicios anteriores | 15
 |  |  |  | (PÉRDIDAS)
 |  |  | 13 | (G3) Imputación a 2017 de ganancias patrimoniales acogidas a diferimiento por reinversión | 15
 |  |  | 13 | (G4) Ganancias patrimoniales por cambio de residencia fuera del territorio español | 15
 |  |  | 14 | (I) Reducciones por aportaciones y contribuciones a sistemas de previsión social | 2
 |  |  | 14 | (I) Reducciones por aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad | 4
 |  |  | 15 | (I) Reducciones por aportaciones a patrimonios protegidos de personas con discapacidad | 2
 |  |  | 15 | (I) Reducciones por pensiones compensatorias a favor del cónyuge y anualidades por alimentos, excepto en favor de los hijos | 2
 |  |  | 15 | (I) Reducciones por aportaciones a la mutualidad de previsión social de deportistas profesionales | 2
 |  |  | 17 | (M) Ded. Descendientes discapacidad | 15
 |  |  | 17 | (M) Ded. Ascendientes discapacidad | 6
 |  |  | 17 | (M) Ded. Familia numerosa | 3
 |  |  | 17 | (M) Ded. Ascendiente separado | 2
 |  |  | 17 | (M) Regularizaciones descendientes | 15
 |  |  | 17 | (M) Regularizaciones ascendientes | 6
 |  |  | C1 | Intereses de los capitales invertidos en la adquisición o mejora de inmuebles y gastos de reparación y conservación de los mismos, pendientes de deducir en los ejercicios siguientes. | 60
 |  |  | C1 | Exención por reinversión de la ganancia patrimonial obtenida en 2017 por la transmisión de la vivienda habitual | 6
 |  |  | C1 | Exención por reinversión en entidades de nueva o reciente creación | 6
 |  |  | C1 | Exención por reinversión en rentas vitalicias | 6
 |  |  | C1 | Pérdidas pendientes de compensar en los ejercicios siguientes BIG | 6
 |  |  | C1 | Pérdidas pendientes de compensar en los ejercicios siguientes BIA | 6
 |  |  | C2 | Rendimientos de capital mobiliario negativos pendientes de compensar en los ejercicios siguientes | 6
 |  |  | C2 | Exceso no reducido de las aportaciones y contribuciones a sistemas de previsión social (régimen general) pendientes de compensar en los ejercicios siguientes(excepto los derivados de | 4
 |  |  |  | contribuciones empresariales a seguros colectivos de dependencia)
 |  |  | C2 | Excesos no reducidos derivados de contribuciones empresariales a seguros colectivos de dependencia pendientes de compensar en los ejercicios | 4
 |  |  |  | siguientes
 |  |  | C2 | Exceso no reducido de las aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad | 4
 |  |  |  | pendientes de compensar en los ejercicios siguientes (PARTÍCIPE)
 |  |  | C2 | Exceso no reducido de las aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad | 4
 |  |  |  | pendientes de compensar en los ejercicios siguientes  (PARIENTES)
 |  |  | C2 | Exceso no reducido de las aportaciones a patrimonios protegidos de personas con discapacidad pendientes de compensar en los ejercicios siguientes | 4
 |  |  | C3 | Exceso no reducido de las aportaciones a la mutualidad de previsión social de deportistas profesionales pendientes de compensar en los ejercicios siguientes | 4
 |  |  | C3 | Bases liquidables generales negativas pendientes de compensar en los ejercicios siguientes | 6

# 100-01 

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 1 | An | Tipo de declaración (Ver Nota)
7 | 14 | 9 | An | Primer Declarante - NIF (01) | OBLIGATORIO
8 | 23 | 80 | A | Primer Declarante - Apellidos y nombre  (02) | OBLIGATORIO
9 | 103 | 4 | Num | Ejercicio | OBLIGATORIO | Constante 2017
10 | 107 | 2 | An | Periodo | OBLIGATORIO | Constante 0A
11 | 109 | 1 | A | Primer Declarante - Sexo "H" Hombre, "M" Mujer (05) | OBLIGATORIO
12 | 110 | 1 | Num | Primer Declarante -Estado Civil. "1" Soltero/a, "2" Casado/a, "3" Viudo/a, "4" Divorciado/a o Separado/a | OBLIGATORIO
13 | 111 | 8 | Num | Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año < 2018 (10) | OBLIGATORIO
14 | 119 | 1 | Num | Primer Declarante - Grado de discapacidad   "0", "1", "2" ,"3" o "4" (11)
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
41 | 531 | 2 | An | Primer Declarante - País de residencia en la UE en 2017 (43)
42 | 533 | 1 | Num | Primer Declarante - Nacionalidad "0" No consta; "1" Española; "2" Otra  (44)
43 | 534 | 1 | Num | Datos adicionales vivienda - Vivienda 1.Titularidad "1", "2", "3" o "4" (50) | OBLIGATORIO
44 | 535 | 5 | Num | Datos adicionales vivienda - Vivienda 1.Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
45 | 540 | 5 | Num | Datos adicionales vivienda - Vivienda 1.Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
46 | 545 | 1 | Num | Datos adicionales vivienda - Vivienda 1.Situación (clave) "1", "2", "3" o "4" (53)
47 | 546 | 20 | An | Datos adicionales vivienda - Vivienda 1.Referencia catastral (54)
48 | 566 | 1 | Num | Datos adicionales vivienda - Vivienda 2.Titularidad "0", "1", "2", "3" o "4" (50)
49 | 567 | 5 | Num | Datos adicionales vivienda - Vivienda 2. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
50 | 572 | 5 | Num | Datos adicionales vivienda - Vivienda 2. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
51 | 577 | 1 | Num | Datos adicionales vivienda - Vivienda 2.Situación (clave) "0", "1", "2", "3" o "4" (53)
52 | 578 | 20 | An | Datos adicionales vivienda - Vivienda 2. Referencia catastral (54)
53 | 598 | 1 | Num | Datos adicionales vivienda - Vivienda 3.Titularidad "0", "1", "2", "3" o "4" (50)
54 | 599 | 5 | Num | Datos adicionales vivienda - Vivienda 3. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
55 | 604 | 5 | Num | Datos adicionales vivienda - Vivienda 3. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
56 | 609 | 1 | Num | Datos adicionales vivienda - Vivienda 3. Situación (clave) "0", "1", "2", "3" o "4" (53)
57 | 610 | 20 | An | Datos adicionales vivienda - Vivienda 3. Referencia catastral (54)
58 | 630 | 1 | Num | Datos adicionales vivienda - Vivienda 4.Titularidad "0", "1", "2", "3" o "4" (50)
59 | 631 | 5 | Num | Datos adicionales vivienda - Vivienda 4. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
60 | 636 | 5 | Num | Datos adicionales vivienda - Vivienda 4. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
61 | 641 | 1 | Num | Datos adicionales vivienda - Vivienda 4. Situación (clave) "0", "1", "2", "3" o "4" (53)
62 | 642 | 20 | An | Datos adicionales vivienda - Vivienda 4. Referencia catastral (54)
63 | 662 | 1 | Num | Datos adicionales vivienda - Vivienda 5.Titularidad "0", "1", "2", "3" o "4" (50)
64 | 663 | 5 | Num | Datos adicionales vivienda - Vivienda 5. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
65 | 668 | 5 | Num | Datos adicionales vivienda - Vivienda 5. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
66 | 673 | 1 | Num | Datos adicionales vivienda - Vivienda 5. Situación (clave) "0", "1", "2", "3" o "4" (53)
67 | 674 | 20 | An | Datos adicionales vivienda - Vivienda 5. Referencia catastral (54)
68 | 694 | 1 | Num | Datos adicionales vivienda - Vivienda 6.Titularidad "0", "1", "2", "3" o "4" (50)
69 | 695 | 5 | Num | Datos adicionales vivienda - Vivienda 6. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
70 | 700 | 5 | Num | Datos adicionales vivienda - Vivienda 6. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
71 | 705 | 1 | Num | Datos adicionales vivienda - Vivienda 6. Situación (clave) "0", "1", "2", "3" o "4" (53)
72 | 706 | 20 | An | Datos adicionales vivienda - Vivienda 6. Referencia catastral (54)
73 | 726 | 1 | Num | Datos adicionales vivienda - Vivienda 7.Titularidad "0", "1", "2", "3" o "4" (50)
74 | 727 | 5 | Num | Datos adicionales vivienda - Vivienda 7. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
75 | 732 | 5 | Num | Datos adicionales vivienda - Vivienda 7. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
76 | 737 | 1 | Num | Datos adicionales vivienda - Vivienda 7. Situación (clave) "0", "1", "2", "3" o "4" (53)
77 | 738 | 20 | An | Datos adicionales vivienda - Vivienda 7. Referencia catastral (54)
78 | 758 | 1 | Num | Datos adicionales vivienda - Vivienda 8.Titularidad "0", "1", "2", "3" o "4" (50)
79 | 759 | 5 | Num | Datos adicionales vivienda - Vivienda 8. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
80 | 764 | 5 | Num | Datos adicionales vivienda - Vivienda 8. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
81 | 769 | 1 | Num | Datos adicionales vivienda - Vivienda 8. Situación (clave) "0", "1", "2", "3" o "4" (53)
82 | 770 | 20 | An | Datos adicionales vivienda - Vivienda 8. Referencia catastral (54)
83 | 790 | 9 | An | Datos adicionales vivienda - Nif Arrendador (55)
84 | 799 | 20 | An | Datos adicionales vivienda - Si no tiene NIF. Nº identificación en el país de residencia (56)
85 | 819 | 9 | An | Cónyuge - NIF (57)
86 | 828 | 80 | A | Cónyuge - Apellidos y nombre (58)
87 | 908 | 1 | A | Cónyuge - Sexo "H" Hombre, "M" Mujer (59]
88 | 909 | 8 | Num | Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero. (60)
89 | 917 | 1 | Num | Cónyuge - Grado de discapacidad   "0", "1", "2" ,"3" o "4" (61)
90 | 918 | 1 | Num | Cónyuge - No residente que no es contribuyente del I.R.P.F. - "1" o cero (62)
91 | 919 | 1 | Num | Cónyuge - Cambio de domicilio "1" o cero (63)
92 | 920 | 5 | A | Cónyuge - Domicilio habitual - Tipo de Vía (15)
93 | 925 | 5 | Num | Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Vía INE
94 | 930 | 50 | An | Cónyuge - Domicilio habitual - Nombre de la Vía Pública (16)
95 | 980 | 3 | An | Cónyuge - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
96 | 983 | 5 | Num | Cónyuge - Domicilio habitual - Número de Casa (18)
97 | 988 | 3 | An | Cónyuge - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
98 | 991 | 3 | An | Cónyuge - Domicilio habitual - Bloque (20)
99 | 994 | 3 | An | Cónyuge - Domicilio habitual - Portal (21)
100 | 997 | 3 | An | Cónyuge - Domicilio habitual - Escalera (22)
101 | 1000 | 3 | An | Cónyuge - Domicilio habitual - Planta (23)
102 | 1003 | 3 | An | Cónyuge - Domicilio habitual - Puerta (24)
103 | 1006 | 40 | An | Cónyuge - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
104 | 1046 | 30 | An | Cónyuge - Domicilio habitual - Localidad / Población (26)
105 | 1076 | 5 | Num | Cónyuge - Domicilio habitual - Código postal (27)
106 | 1081 | 5 | Num | Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
107 | 1086 | 30 | An | Cónyuge - Domicilio habitual - Nombre del Municipio (28)
108 | 1116 | 2 | Num | Cónyuge - Domicilio habitual - Código provincia. De "01" a "52".
109 | 1118 | 20 | An | Cónyuge - Domicilio habitual - Provincia (29)
110 | 1138 | 50 | An | Cónyuge - Domicilio extranjero - Domicilio/Address (35)
111 | 1188 | 40 | An | Cónyuge - Domicilio extranjero - Datos complementarios del domicilio (36)
112 | 1228 | 30 | An | Cónyuge - Domicilio extranjero - Población / Ciudad (37)
113 | 1258 | 10 | An | Cónyuge - Domicilio extranjero - Código Postal (39)
114 | 1268 | 30 | An | Cónyuge - Domicilio extranjero - Provincia / Región / Estado (40)
115 | 1298 | 30 | An | Cónyuge - Domicilio extranjero - País (41)
116 | 1328 | 2 | An | Cónyuge - Domicilio extranjero - Código País (42)
117 | 1330 | 2 | An | Cónyuge - País de residencia en la UE en 2017 (43)
118 | 1332 | 1 | Num | Cónyuge - Nacionalidad "0" No consta; "1" Española; "2" Otra (44)
119 | 1333 | 12 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
120 | 1345 | 9 | An | Representante -  N.I.F. (65)
121 | 1354 | 32 | An | Representante -  Apellidos y nombre o razón social (66)
122 | 1386 | 8 | Num | Devengo - Fecha de  finalización del período impositivo (fallecimiento 2017)  (DDMMAAAA) o cero (67)
123 | 1394 | 1 | Num | Opción de tributación. "1" Individual, "2" Conjunta.  Campo OBLIGATORIO (68) (69) | OBLIGATORIO
124 | 1395 | 2 | Num | Comunidad/Ciudad autónoma de residencia en 2017 - Clave (70) Incluido en el fichero COMAUTO.TXT | OBLIGATORIO
125 | 1397 | 13 | Num | Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
126 | 1410 | 21 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
127 | 1431 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
128 | 1444 | 600 | An | RESERVADO PARA LA A.E.A.T
129 | 2044 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10001000>
Total |  | 2055
 |  |  | Nota: | El Tipo de declaración puede ser: I (Ingreso), U (Domiciliación),  N (Negativa/Resultado cero), D (Solicitud de devolución) y R (Renuncia a la devolución)

# 100-02

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "02000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 9 | An | Hijos y descendientes - 1º -  N.I.F. (75)
7 | 22 | 60 | A | Hijos y descendientes - 1º -  Apellidos y nombre  (76)
8 | 82 | 8 | Num | Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año < 2018 o cero (77)
9 | 90 | 8 | Num | Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
10 | 98 | 1 | Num | Hijos y descendientes - 1º - Grado discapacidad   "0", "1", "2", "3" o "4" (79)
11 | 99 | 1 | An | Hijos y descendientes - 1º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (80)
12 | 100 | 2 | Num | Hijos y descendientes - 1º - Nº de orden (81)
13 | 102 | 1 | An | Hijos y descendientes - 1º - Otras situaciones  clave:"1","2","3","4" o blanco  (82)
14 | 103 | 9 | An | Hijos y descendientes - 2º - N.I.F. (75)
15 | 112 | 60 | A | Hijos y descendientes - 2º - Apellidos y nombre  (76)
16 | 172 | 8 | Num | Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año < 2018 o cero (77)
17 | 180 | 8 | Num | Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año < 2018 o cero (78)
18 | 188 | 1 | Num | Hijos y descendientes - 2º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
19 | 189 | 1 | An | Hijos y descendientes - 2º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
20 | 190 | 2 | Num | Hijos y descendientes - 2º - Nº de orden (81)
21 | 192 | 1 | An | Hijos y descendientes - 2º - Otras situaciones  "1","2","3","4" o blanco  (82)
22 | 193 | 9 | An | Hijos y descendientes - 3º - N.I.F. (75)
23 | 202 | 60 | A | Hijos y descendientes - 3º - Apellidos y nombre  (76)
24 | 262 | 8 | Num | Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
25 | 270 | 8 | Num | Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
26 | 278 | 1 | Num | Hijos y descendientes - 3º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
27 | 279 | 1 | An | Hijos y descendientes - 3º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
28 | 280 | 2 | Num | Hijos y descendientes - 3º - Nº de orden (81)
29 | 282 | 1 | An | Hijos y descendientes - 3º - Otras situaciones  "1","2","3","4" o blanco  (82)
30 | 283 | 9 | An | Hijos y descendientes - 4º - N.I.F.  (75)
31 | 292 | 60 | A | Hijos y descendientes - 4º - Apellidos y nombre  (76)
32 | 352 | 8 | Num | Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
33 | 360 | 8 | Num | Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
34 | 368 | 1 | Num | Hijos y descendientes - 4º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
35 | 369 | 1 | An | Hijos y descendientes - 4º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
36 | 370 | 2 | Num | Hijos y descendientes - 4º - Nº de orden (81)
37 | 372 | 1 | An | Hijos y descendientes - 4º - Otras situaciones  "1","2","3","4" o blanco  (82)
38 | 373 | 9 | An | Hijos y descendientes - 5º - N.I.F. (75)
39 | 382 | 60 | A | Hijos y descendientes - 5º - Apellidos y nombre  (76)
40 | 442 | 8 | Num | Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
41 | 450 | 8 | Num | Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
42 | 458 | 1 | Num | Hijos y descendientes - 5º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
43 | 459 | 1 | An | Hijos y descendientes - 5º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
44 | 460 | 2 | Num | Hijos y descendientes - 5º - Nº de orden (81)
45 | 462 | 1 | An | Hijos y descendientes - 5º - Otras situaciones  "1","2","3","4" o blanco  (82)
46 | 463 | 9 | An | Hijos y descendientes - 6º - N.I.F. (75)
47 | 472 | 60 | A | Hijos y descendientes - 6º - Apellidos y nombre  (76)
48 | 532 | 8 | Num | Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
49 | 540 | 8 | Num | Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
50 | 548 | 1 | Num | Hijos y descendientes - 6º - Grado discapacidad  "0", "1", "2", "3" o "4" (79)
51 | 549 | 1 | An | Hijos y descendientes - 6º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
52 | 550 | 2 | Num | Hijos y descendientes - 6º - Nº de orden (81)
53 | 552 | 1 | An | Hijos y descendientes - 6º - Otras situaciones  "1","2","3","4" o blanco  (82)
54 | 553 | 9 | An | Hijos y descendientes - 7º - N.I.F.  (75)
55 | 562 | 60 | A | Hijos y descendientes - 7º - Apellidos y nombre  (76)
56 | 622 | 8 | Num | Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
57 | 630 | 8 | Num | Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
58 | 638 | 1 | Num | Hijos y descendientes - 7º - Grado discapacidad  "0", "1", "2", "3" o "4" (79)
59 | 639 | 1 | An | Hijos y descendientes - 7º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
60 | 640 | 2 | Num | Hijos y descendientes - 7º - Nº de orden (81)
61 | 642 | 1 | An | Hijos y descendientes - 7º - Otras situaciones  "1","2","3","4" o blanco  (82)
62 | 643 | 9 | An | Hijos y descendientes - 8º - N.I.F. (75)
63 | 652 | 60 | A | Hijos y descendientes - 8º - Apellidos y nombre  (76)
64 | 712 | 8 | Num | Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
65 | 720 | 8 | Num | Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
66 | 728 | 1 | Num | Hijos y descendientes - 8º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
67 | 729 | 1 | An | Hijos y descendientes - 8º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (80)
68 | 730 | 2 | Num | Hijos y descendientes - 8º - Nº de orden (81)
69 | 732 | 1 | An | Hijos y descendientes - 8º - Otras situaciones  "1","2","3","4" o blanco  (82)
70 | 733 | 9 | An | Hijos y descendientes - 9º - N.I.F. (75)
71 | 742 | 60 | A | Hijos y descendientes - 9º - Apellidos y nombre  (76)
72 | 802 | 8 | Num | Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
73 | 810 | 8 | Num | Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
74 | 818 | 1 | Num | Hijos y descendientes - 9º - Grado discapacidad  "0", "1", "2", "3" o "4"  (79)
75 | 819 | 1 | An | Hijos y descendientes - 9º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
76 | 820 | 2 | Num | Hijos y descendientes - 9º - Nº de orden (81)
77 | 822 | 1 | An | Hijos y descendientes - 9º - Otras situaciones  "1","2","3","4" o blanco  (82)
78 | 823 | 9 | An | Hijos y descendientes - 10º - N.I.F.  (75)
79 | 832 | 60 | A | Hijos y descendientes - 10º - Apellidos y nombre  (76)
80 | 892 | 8 | Num | Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
81 | 900 | 8 | Num | Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
82 | 908 | 1 | Num | Hijos y descendientes - 10º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
83 | 909 | 1 | An | Hijos y descendientes - 10º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
84 | 910 | 2 | Num | Hijos y descendientes - 10º - Nº de orden (81)
85 | 912 | 1 | An | Hijos y descendientes - 10º - Otras situaciones  "1","2","3","4" o blanco  (82)
86 | 913 | 9 | An | Hijos y descendientes - 11º - N.I.F. (75)
87 | 922 | 60 | A | Hijos y descendientes - 11º - Apellidos y nombre  (76)
88 | 982 | 8 | Num | Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
89 | 990 | 8 | Num | Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
90 | 998 | 1 | Num | Hijos y descendientes - 11º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
91 | 999 | 1 | An | Hijos y descendientes - 11º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
92 | 1000 | 2 | Num | Hijos y descendientes - 11º - Nº de orden (81)
93 | 1002 | 1 | An | Hijos y descendientes - 11º - Otras situaciones  "1","2","3","4" o blanco  (82)
94 | 1003 | 9 | An | Hijos y descendientes - 12º - N.I.F. (75)
95 | 1012 | 60 | A | Hijos y descendientes - 12º - Apellidos y nombre  (76)
96 | 1072 | 8 | Num | Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (77)
97 | 1080 | 8 | Num | Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2018 o cero (78)
98 | 1088 | 1 | Num | Hijos y descendientes - 12º - Grado discapacidad  "0", "1", "2", "3" o "4"  (79)
99 | 1089 | 1 | An | Hijos y descendientes - 12º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
100 | 1090 | 2 | Num | Hijos y descendientes - 12º - Nº de orden (81)
101 | 1092 | 1 | An | Hijos y descendientes - 12º - Otras situaciones  "1","2","3","4" o blanco  (82)
102 | 1093 | 2 | Num | Hijos y descendientes - Fallecido 2017 - Nº Orden (83)
103 | 1095 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (84)
104 | 1103 | 2 | Num | Hijos y descendientes - Fallecido 2017 - Nº Orden (83)
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
125 | 1522 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (92)
126 | 1530 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Grado discapacidad  "0", "1", "2", "3" o "4" (93)
127 | 1531 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Vinculación  clave:"1", "2" o blanco (94)
128 | 1532 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Convivencia   "2" a "9" o blanco (95)
129 | 1533 | 9 | An | Ascendientes mayores 65 años o discapacitados - 2º - N.I.F.  (90)
130 | 1542 | 60 | A | Ascendientes mayores 65 años o discapacitados - 2º - Apellidos y nombre (91)
131 | 1602 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (92)
132 | 1610 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Grado discapacidad  "0", "1", "2", "3" o "4"  (93)
133 | 1611 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Vinculación clave:"1", "2" o blanco  (94)
134 | 1612 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Convivencia  "2" a "9" o blanco  (95)
135 | 1613 | 9 | An | Ascendientes mayores 65 años o discapacitados - 3º - N.I.F.  (90)
136 | 1622 | 60 | A | Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
137 | 1682 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año < 2018 o cero (92)
138 | 1690 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Grado discapacidad  "0", "1", "2", "3" o "4"  (93)
139 | 1691 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Vinculación  clave:"1", "2" o blanco  (94)
140 | 1692 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Convivencia   "2" a "9" o blanco  (95)
141 | 1693 | 9 | An | Ascendientes mayores 65 años o discapacitados - 4º - N.I.F.  (90)
142 | 1702 | 60 | A | Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
143 | 1762 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (92)
144 | 1770 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Grado discapacidad  "0", "1", "2", "3" o "4" (93)
145 | 1771 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Vinculación  clave:"1", "2" o blanco  (94)
146 | 1772 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Convivencia  "2" a "9" o blanco  (95)
147 | 1773 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2017 - Nif (96)
148 | 1782 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
149 | 1790 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2017 - Nif (96)
150 | 1799 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
151 | 1807 | 1 | A | Asignación tributaria a la Iglesia Católica. "X" o  blanco. (105)
152 | 1808 | 1 | A | Asignación de cantidades a actividades de interés general consideradas de interés social. "X" o  blanco. (106)
153 | 1809 | 600 | An | RESERVADO PARA LA A.E.A.T
154 | 2409 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10002000>
Total |  | 2420

# 100-03

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "03000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 1 | Num | Declaración complementaria - Si de la declaración complementaria resulta una cantidad a devolver inferior a la solicitada en la declaración anterior,  "1" o cero (107)
7 | 14 | 1 | Num | Declaración complementaria - Por haber percibido atrasos de rendimientos de trabajo después de la presentación de la declaración anterior. "1" o cero (108)
8 | 15 | 1 | Num | Declaración complementaria - Por la devolución de cantidades derivadas de la cláusula suelo. "1" o cero (109)
9 | 16 | 1 | Num | Declaración complementaria - Por haber perdido la condición de contribuyente por cambio de residencia. "1" o cero (110)
10 | 17 | 1 | Num | Declaración complementaria - Por el traslado de residencia a otro Estado de la Unión Europea. "1" o cero (111)
11 | 18 | 1 | Num | Declaración complementaria - Por pérdida de la condición de contribuyente por cambio de residencia que genere ganancias patrimoniales. "1"  o cero (112)
12 | 19 | 1 | Num | Declaración complementaria - Por pérdida de la condición de residente del socio por aplicación del régimen especial de canje de valores. "1" o cero (113)
13 | 20 | 1 | Num | Declaración complementaria - Por no producir efecto el cambio de residencia a otra Comunidad Autónoma. "1" o cero (114)
14 | 21 | 1 | Num | Declaración complementaria - Por disposición anticipada de derechos consolidados de sistemas de previsión social. "1" o cero (115)
15 | 22 | 1 | Num | Declaración complementaria - Por disposición de bienes o derechos aportados a patrimonios protegidos. "1" o cero (116)
16 | 23 | 1 | Num | Declaración complementaria - Por incumplimiento de las condiciones para aplicar la exención por reinversión en vivienda habitual. "1" o cero (117)
17 | 24 | 1 | Num | Declaración complementaria - Por incumplimiento de las condiciones para aplicar la exención por reinversión en rentas vitalicias. "1" o cero (118)
18 | 25 | 1 | Num | Declaración complementaria - Por incumplimiento del plazo de 3 años de mantenimiento de las acciones entregadas a los trabajadores. "1" o cero (119)
19 | 26 | 1 | Num | Declaración complementaria - Por pérdida de la exención de la indemnización por despido o cese. "1" o cero (120)
20 | 27 | 1 | Num | Declaración complementaria - Por adquisición de elementos patrimoniales, valores o participaciones homogéneos. "1" o cero (121)
21 | 28 | 1 | Num | Declaración complementaria - En supuesto distintos a los anteriores. "1" o cero (122)
22 | 29 | 1 | Num | Solicitud de rectificación - Si inicia procedimiento de rectificación de la autoliquidación por resultar una cantidad a devolver > o una cantidad a ingresar <. "1" o cero (127)
23 | 30 | 600 | An | RESERVADO PARA LA A.E.A.T
24 | 630 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10003000>
Total: |  | 641

# 100-04

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "04000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (A) Rdto. Trabajo - Contribuyente que obtiene los rendimientos . "0" a "9" (0001)
8 | 15 | 13 | N | C | Rdto. Trabajo - Retribuciones dinerarias. Importe íntegro (0002)
9 | 28 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Valoracion (0003)
10 | 41 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta (0004)
11 | 54 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta repercutidos (0005)
12 | 67 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Importe íntegro (0006)
13 | 80 | 13 | N | C | Rdto. Trabajo - Contribuciones empresariales a planes de pensiones, planes de previsión social empresarial  y mutualidades previsión social  (0007)
14 | 93 | 13 | N | C | Rdto. Trabajo - Contribuciones empresariales a seguros colectivos dependencia. Imputado al contribuyente (0008)
15 | 106 | 13 | N | C | Rdto. Trabajo - Aportaciones al patrimonio protegido de discapacitados - Importe (0009)
16 | 119 | 13 | N | C | Rdto. Trabajo - Reducciones (0010)
17 | 132 | 13 | N | C | Rdto. Trabajo - Total ingresos íntegros computables (0011)
18 | 145 | 13 | N | C | Rdto. Trabajo - Cotizaciones Seguridad Social/mutualidades funcionarios, detracciones por derechos pasivos y cotizaciones  colegios huérfanos (0012)
19 | 158 | 13 | N | C | Rdto. Trabajo - Cuotas satisfechas a sindicatos (0013)
20 | 171 | 13 | N | C | Rdto. Trabajo - Cuotas satisfechas a colegios profesionales (0014)
21 | 184 | 13 | N | C | Rdto. Trabajo - Gastos defensa jurídica derivados litigios con empleador (0015)
22 | 197 | 13 | N | C | Rdto. Trabajo - Rendimiento neto previo (0016)
23 | 210 | 13 | N |  | Rdto. Trabajo -Suma de rendimientos netos previos (0017)
24 | 223 | 13 | N |  | Rdto. Trabajo - Otros gastos deducibles (0018)
25 | 236 | 13 | N |  | Rdto. Trabajo - Incremento contribuyentes desempleados con traslado de residencia  (0019)
26 | 249 | 13 | N |  | Rdto. Trabajo - Incremento para trabajadores activos que sean personas con discapacidad  (0020)
27 | 262 | 13 | N |  | Rdto. Trabajo - Rendimiento neto  (0021)
28 | 275 | 13 | N |  | Rdto. Trabajo - Reducción por obtención rendimientos de trabajo. Cuantía aplicable con carácter general (0022)
29 | 288 | 13 | N |  | Rdto. Trabajo - Rendimiento neto reducido (0023)
30 | 301 | 1 | Tit | C | (B) Rdto.capital mobiliario - Base imponible ahorro - Contribuyente que obtiene los rendimientos . "0" a "9" (0024)
31 | 302 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (0025)
32 | 315 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro  - Intereses de activos financieros con derecho a bonificación (0026)
33 | 328 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (0027)
34 | 341 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (0028)
35 | 354 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros (0029)
36 | 367 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (0030)
37 | 380 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. procedentes de rentas que tengan por causa la imposición de capitales (0031)
38 | 393 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. derivados de valores de deuda subordinada o participaciones preferentes. (0032)
39 | 406 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. procedentes de seguros de vida, depósitos financieros que instrumenten Planes Ahorro (0033)
40 | 419 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Total ingresos íntegros (0034)
41 | 432 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Gastos fiscalmente deducibles (0035)
42 | 445 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rendimiento neto (0036)
43 | 458 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (0037]
44 | 471 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rendimiento neto reducido (0038)
45 | 484 | 13 | N |  | Rdto.capital mobiliario -  Base imponible ahorro  - Suma de rendimientos del capital mobiliario base imponible del ahorro (0039)
46 | 497 | 1 | Tit | C | Aplicación DT 4 - Contribuyente 1  "0" a "9" (0040)
47 | 498 | 13 | N | C | Aplicación DT 4 - Contribuyente 1 - Importe total acumulado del capital diferido percibido 2015 y 2016 (0041)
48 | 511 | 13 | N | C | Aplicación DT 4 - Contribuyente 1 - Importe total de los capitales diferidos correspondientes a seguros de vida (0042)
49 | 524 | 1 | Tit | C | Aplicación DT 4 - Contribuyente 2  "0" a "9" (0040)
50 | 525 | 13 | N | C | Aplicación DT 4 - Contribuyente 2 - Importe total acumulado del capital diferido percibido 2015 y 2016 (0041)
51 | 538 | 13 | N | C | Aplicación DT 4 - Contribuyente 2 - Importe total de los capitales diferidos correspondientes a seguros de vida (0042)
52 | 551 | 600 | An |  | RESERVADO PARA LA A.E.A.T
53 | 1151 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10004000>
Total: |  | 1162

# 100-05

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com. | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "05000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 15 | 1 | Tit | C | Rdto.capital mobiliario - Base imponible general - Contribuyente que obtiene los rendimientos . "0" a "9" (0043)
8 | 16 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (0044)
9 | 29 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (0045)
10 | 42 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (0046)
11 | 55 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (0047)
12 | 68 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (0048)
13 | 81 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Total ingresos íntegros (0049)
14 | 94 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Gastos fiscalmente deducibles (0050)
15 | 107 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimiento neto (0051)
16 | 120 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (0052)
17 | 133 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimiento neto reducido (0053)
18 | 146 | 13 | N |  | Rdto.capital mobiliario -  Base imponible general  - Suma de rendimientos del capital mobiliario base imponible general (0054)
19 | 159 | 3 | Num | C | (C) Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Número de orden (0055))
20 | 162 | 1 | Tit | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Contribuyente "0" a "9" (0056)
21 | 163 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Porcentaje propiedad (3 enteros y 2 decimales) (0057)
22 | 168 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Porcentaje usufructo (3 enteros y 2 decimales) (0058)
23 | 173 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Naturaleza (0059)
24 | 174 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Uso o destino. Clave   (0060)
25 | 175 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Situación "0", "1", "2", "3" o "4" (0061)
26 | 176 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Referencia catastral (0062)
27 | 196 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. NIF del excónyuge (0063)
28 | 216 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Si el excónyuge ha consignado NIF de otro país (0064)
29 | 217 | 65 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Dirección (0065)
30 | 282 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (0066)
31 | 287 | 3 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. Número de días (0067)
32 | 290 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. Renta imputada (0068)
33 | 303 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Ingresos íntegros computables (0069)
34 | 316 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (0070)
35 | 329 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Intereses. Importe (0071)
36 | 342 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (0072)
37 | 355 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Títulos, recargos y tasas (0073)
38 | 368 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Saldos dudoso cobro (0074)
39 | 381 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Cantidades devengadas por terceros (0075)
40 | 394 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Amortización bienes inmuebles (0076)
41 | 407 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Amortización bienes muebles (0077)
42 | 420 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Otros gastos fiscalmente deducibles (0078)
43 | 433 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Rendimiento neto (0079)
44 | 446 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (0080)
45 | 459 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Reducción rendimientos más de 2 años (0081)
46 | 472 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Rendimiento mínimo computable parentesco (0082)
47 | 485 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Rendimiento neto reducido (0083)
48 | 498 | 13 | N |  | Bienes inmuebles no afectos. Rentas totales . Suma de rentas inmobiliarias imputadas (0084)
49 | 511 | 13 | N |  | Bienes inmuebles no afectos. Rentas totales . Suma rendimientos netos reducidos del capital inmobiliario (0085)
50 | 524 | 3 | Num |  | Número de inmuebles en declaración conjunta (Reservado para la Administración)
51 | 527 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Contribuyente "0" a "9" (0086)
52 | 528 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Nº Identificación fiscal entidad (0087)
53 | 548 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Porcentaje titularidad (3 enteros y 2 decimales) (0088)
54 | 553 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Naturaleza (0089)
55 | 554 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Situación "0", "1", "2", "3" o "4" (0090)
56 | 555 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Referencia catastral (0091)
57 | 575 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. No Residente (0092)
58 | 576 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Contribuyente "0" a "9" (0086)
59 | 577 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Nº Identificación fiscal entidad (0087)
60 | 597 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Porcentaje titularidad (3 enteros y 2 decimales) (0088)
61 | 602 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Naturaleza (0089)
62 | 603 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Situación "0", "1", "2", "3" o "4" (0090)
63 | 604 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Referencia catastral (0091)
64 | 624 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. No Residente (0092)
65 | 625 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Contribuyente "0" a "9" (0086)
66 | 626 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Nº Identificación fiscal entidad (0087)
67 | 646 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Porcentaje titularidad (3 enteros y 2 decimales) (0088)
68 | 651 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Naturaleza (0089)
69 | 652 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Situación "0", "1", "2", "3" o "4" (0090)
70 | 653 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Referencia catastral (0091)
71 | 673 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. No Residente (0092)
72 | 674 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 1. Contribuyente "0" a "9" (0093)
73 | 675 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (0094)
74 | 680 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje usufructo (3 enteros y 2 decimales)  (0095)
75 | 685 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Naturaleza (clave) (0096)
76 | 686 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1.  Situación "0", "1", "2", "3" o "4" (0097)
77 | 687 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 1.  Referencia catastral (0098)
78 | 707 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 2. Contribuyente "0" a "9" (0093)
79 | 708 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (0094)
80 | 713 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje usufructo (3 enteros y 2 decimales)  (0095)
81 | 718 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Naturaleza (clave) (0096)
82 | 719 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2.  Situación "0", "1", "2", "3" o "4" (0097)
83 | 720 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 2.  Referencia catastral (0098)
84 | 740 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 3. Contribuyente "0" a "9" (0093)
85 | 741 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (0094)
86 | 746 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje usufructo (3 enteros y 2 decimales)  (0095)
87 | 751 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Naturaleza (clave) (0096)
88 | 752 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3.  Situación "0", "1", "2", "3" o "4" (0097)
89 | 753 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 3.  Referencia catastral (0098)
90 | 773 | 600 | An |  | RESERVADO PARA LA A.E.A.T
91 | 1373 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10005000>
Total: |  | 1384

# 100-06

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com. | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "06000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Contribuyente  "0" a "9" (0100)
8 | 15 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Tipo actividad. Clave (Blanco o de "1" a "5") (0101)
9 | 16 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Epígrafe IAE (0102) (**)
10 | 21 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Modalidad aplicable "0" no consta "N" 1  o "S" 2 [0103)
11 | 22 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 1- Criterio cobros/pagos. "1" o cero. (0104)
12 | 23 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Explotación (0105)
13 | 36 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Otros ingresos (0106)
14 | 49 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Autoconsumo bienes/servicios (0107)
15 | 62 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Transmisión elementos patrimoniales: exceso amortización deducida (0108)
16 | 75 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 1- Total ingresos computables (0109)
17 | 88 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Consumos de explotación (0110)
18 | 101 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Sueldos y salarios (0111)
19 | 114 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Seguridad Social (0112)
20 | 127 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros gastos de personal (0113)
21 | 140 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Arrendamientos y cánones (0114)
22 | 153 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Reparación y conservación (0115)
23 | 166 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Servicios profesionales independientes (0116)
24 | 179 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros servicios exteriores (0117]
25 | 192 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Tributos fiscalmente deducibles (0118)
26 | 205 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Gastos financieros (0119)
27 | 218 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Amortizaciones (0120)
28 | 231 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Pérdidas por insolvencia de deudores  (0121)
29 | 244 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (convenios) (0122)
30 | 257 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Mecenazgo (gastos) (0123)
31 | 270 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Otros conceptos fiscalmente deducibles (0124)
32 | 283 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Suma  (0125)
33 | 296 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Normal - Provisiones (0126)
34 | 309 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Normal - Total gastos deducibles (0127)
35 | 322 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Diferencia (0128)
36 | 335 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (0129)
37 | 348 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 1- Modalidad  Simplificada - Total gastos deducibles (0130)
38 | 361 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Rdto. neto (0131)
39 | 374 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 1- Reducciones (0132)
40 | 387 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -1- Rdto. neto reducido (0133)
41 | 400 | 1 | Tit | C | (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Contribuyente  "0" a "9" (0100)
42 | 401 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Tipo actividad. Clave (Blanco o de "1" a "5") (0101)
43 | 402 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Epígrafe IAE (0102) (**)
44 | 407 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Modalidad aplicable "0" no consta "N" 1  o "S" 2 [0103)
45 | 408 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 2- Criterio cobros/pagos. "1" o cero. (0104)
46 | 409 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Explotación (0105)
47 | 422 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Otros ingresos (0106)
48 | 435 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Autoconsumo bienes/servicios (0107)
49 | 448 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Transmisión elementos patrimoniales: exceso amortización deducida (0108)
50 | 461 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 2- Total ingresos computables (0109)
51 | 474 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Consumos de explotación (0110)
52 | 487 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Sueldos y salarios (0111)
53 | 500 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Seguridad Social (0112)
54 | 513 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros gastos de personal (0113)
55 | 526 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Arrendamientos y cánones (0114)
56 | 539 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Reparación y conservación (0115)
57 | 552 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Servicios profesionales independientes (0116)
58 | 565 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros servicios exteriores (0117]
59 | 578 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Tributos fiscalmente deducibles (0118)
60 | 591 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Gastos financieros (0119)
61 | 604 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Amortizaciones (0120)
62 | 617 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Pérdidas por insolvencia de deudores  (0121)
63 | 630 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (convenios) (0122)
64 | 643 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Mecenazgo (gastos) (0123)
65 | 656 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Otros conceptos fiscalmente deducibles (0124)
66 | 669 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Suma  (0125)
67 | 682 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Normal - Provisiones (0126)
68 | 695 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Normal - Total gastos deducibles (0127)
69 | 708 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Diferencia (0128)
70 | 721 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (0129)
71 | 734 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 2- Modalidad  Simplificada - Total gastos deducibles (0130)
72 | 747 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Rdto. neto (0131)
73 | 760 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 2- Reducciones (0132)
74 | 773 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -2- Rdto. neto reducido (0133)
75 | 786 | 1 | Tit | C | (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Contribuyente  "0" a "9" (0100)
76 | 787 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Tipo actividad. Clave (Blanco o de "1" a "5") (0101)
77 | 788 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Epígrafe IAE (0102) (**)
78 | 793 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Modalidad aplicable "0" no consta "N" 1  o "S" 2 [0103)
79 | 794 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad 3- Criterio cobros/pagos. "1" o cero. (0104)
80 | 795 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Explotación (0105)
81 | 808 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Otros ingresos (0106)
82 | 821 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Autoconsumo bienes/servicios (0107)
83 | 834 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Transmisión elementos patrimoniales: exceso amortización deducida (0108)
84 | 847 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad 3- Total ingresos computables (0109)
85 | 860 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Consumos de explotación (0110)
86 | 873 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Sueldos y salarios (0111)
87 | 886 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Seguridad Social (0112)
88 | 899 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros gastos de personal (0113)
89 | 912 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Arrendamientos y cánones (0114)
90 | 925 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Reparación y conservación (0115)
91 | 938 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Servicios profesionales independientes (0116)
92 | 951 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Otros servicios exteriores (0117]
93 | 964 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Tributos fiscalmente deducibles (0118)
94 | 977 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Gastos financieros (0119)
95 | 990 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Amortizaciones (0120)
96 | 1003 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Pérdidas por insolvencia de deudores  (0121)
97 | 1016 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (convenios) (0122)
98 | 1029 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Mecenazgo (gastos) (0123)
99 | 1042 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3 - Otros conceptos fiscalmente deducibles (0124)
100 | 1055 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Suma  (0125)
101 | 1068 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Normal - Provisiones (0126)
102 | 1081 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Normal - Total gastos deducibles (0127)
103 | 1094 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Diferencia (0128)
104 | 1107 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (0129)
105 | 1120 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad 3- Modalidad  Simplificada - Total gastos deducibles (0130)
106 | 1133 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3- Rdto. neto (0131)
107 | 1146 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad 3 - Reducciones (0132)
108 | 1159 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc.- Actividad -3- Rdto. neto reducido (0133)
109 | 1172 | 13 | N |  | Rdto.actv.econ.est.directa - Suma de rendimientos netos reducidos  (0134)
110 | 1185 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción ejercicio determinadas actividades económicas  (artículo 32.2.1º) (0135)
111 | 1198 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción ejercicio determinadas actividades económicas (artículo 32.2.3º) (0136)
112 | 1211 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción por inicio de una actividad económica (0137)
113 | 1224 | 13 | N |  | Rdto.actv.econ.est.directa - Rendimiento neto reducido total actividades económicas en estimación directa (0140)
114 | 1237 | 600 | An |  | RESERVADO PARA LA A.E.A.T
115 | 1837 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10006000>
Total: |  | 1848
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignarán las tres cifras seguidas de dos blancos.

# 100-07

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "07000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (E2) Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Contribuyente titular actividad   "0" a "9" (0141)
8 | 15 | 5 | An | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Clasificación IAE (0142) (**)
9 | 20 | 1 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (0143)
10 | 21 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Definición
11 | 45 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales)
12 | 54 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales)
13 | 65 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Definición
14 | 89 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales)
15 | 98 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales)
16 | 109 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Definición
17 | 133 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales)
18 | 142 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales)
19 | 153 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Definición
20 | 177 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales)
21 | 186 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales)
22 | 197 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Definición
23 | 221 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales)
24 | 230 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales)
25 | 241 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Definición
26 | 265 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales)
27 | 274 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales)
28 | 285 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Definición
29 | 309 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales)
30 | 318 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales)
31 | 329 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma)  (0144)
32 | 342 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo  (0145)
33 | 355 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (0146)
34 | 368 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (0147)
35 | 381 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (0148)
36 | 385 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (0149)
37 | 389 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (0150)
38 | 393 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (0151)
39 | 397 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (0152)
40 | 401 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto de módulos (0153)
41 | 414 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción de carácter general (0154)
42 | 427 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (0155)
43 | 440 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Gastos extraordinarios circunstancias  excepcionales (0156)
44 | 453 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Otras percepciones empresariales (0157)
45 | 466 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª -Rendimiento neto actividad (0158)
46 | 479 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción rdtos. más de 2 años o forma irregular (0159)
47 | 492 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rendimiento neto reducido (0160)
48 | 505 | 1 | Tit | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Contribuyente titular actividad   "0" a "9" (0141)
49 | 506 | 5 | An | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Clasificación IAE (0142) (**)
50 | 511 | 1 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Criterio cobros/pagos: "1" ó "0" (0143)
51 | 512 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Definición
52 | 536 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales)
53 | 545 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales)
54 | 556 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Definición
55 | 580 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales)
56 | 589 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales)
57 | 600 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Definición
58 | 624 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales)
59 | 633 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales)
60 | 644 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Definición
61 | 668 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales)
62 | 677 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales)
63 | 688 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Definición
64 | 712 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales)
65 | 721 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales)
66 | 732 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Definición
67 | 756 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales)
68 | 765 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales)
69 | 776 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Definición
70 | 800 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales)
71 | 809 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales)
72 | 820 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto previo (suma)  (0144)
73 | 833 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos al empleo  (0145)
74 | 846 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Minorizaciones por incentivos a la inversion (0146)
75 | 859 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto minorado (0147)
76 | 872 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector especial (2 enteros y 2 decimales) (0148)
77 | 876 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (0149)
78 | 880 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de temporada (2 enteros y 2 decimales) (0150)
79 | 884 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corrector de exceso (2 enteros y 2 decimales) (0151)
80 | 888 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (0152)
81 | 892 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rdto. neto de módulos (0153)
82 | 905 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción de carácter general (0154)
83 | 918 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (0155)
84 | 931 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Gastos extraordinarios circunstancias  excepcionales (0156)
85 | 944 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Otras percepciones empresariales (0157)
86 | 957 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª -Rendimiento neto actividad (0158)
87 | 970 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Reducción rdtos. más de 2 años o forma irregular (0159)
88 | 983 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 2ª - Rendimiento neto reducido (0160)
89 | 996 | 13 | N |  | Rdtos.activ.económ.est.objetiva -  Suma rendimientos netos reducidos de las actividades económicas (0161)
90 | 1009 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Reducción por el ejercicio determinadas actividades económicas (0162)
91 | 1022 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas (0165)
92 | 1035 | 600 | An |  | RESERVADO PARA LA A.E.A.T
93 | 1635 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10007000>
Total: |  | 1646
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos blancos.

# 100-08

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "08000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (E3) Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Contribuyente titular de actividad: de "0" a "9"  (0166)
8 | 15 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Clave actividad: de "0" a "9" (0167)
9 | 16 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Criterio cobros/pagos:  "1" ó "0" (0168)
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
58 | 465 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Total  ingresos íntegros (0169)
59 | 476 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto previo (suma) (0170)
60 | 487 | 11 | N | C | RESERVADO PARA LA A.E.A.T
61 | 498 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Amortización inmovilizado (0172)
62 | 509 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto minorado  (0173)
63 | 520 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Medios de producción ajenos (2 enteros y 2 decimales) [0174]
64 | 524 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Utilización personal asalariado (2 enteros y 2 decimales) (0175)
65 | 528 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (0176)
66 | 532 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (0177) Ver NOTA
67 | 536 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 2 (0177) Ver NOTA
68 | 540 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Actividades agricultura ecológica (2 enteros y dos decimales)  (0178)
69 | 544 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Cultivo en tierras regadío utilice energía electrica ( 2 enteros y 2 decimales) (0179)
70 | 548 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales)  (0180)
71 | 552 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Determinadas actividades forestales  (2 enteros y 2 decimales)  (0181)
72 | 556 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto de módulos (0182)
73 | 569 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción carácter general (0183)
74 | 582 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Diferencia (0184)
75 | 595 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción agricultores jóvenes (0185)
76 | 608 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Gastos extraordinarios por circunstancias excepcionales (0186]
77 | 621 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto  (0187)
78 | 634 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones rendimientos generados más 2 años o forma irregular (0188)
79 | 647 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto reducido (0189)
80 | 660 | 1 | Tit | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Contribuyente titular de actividad: de "0" a "9"  (0166)
81 | 661 | 1 | Num | C | (E3) Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Clave actividad: de "0" a "9" (0167)
82 | 662 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Criterio cobros/pagos:  "1" ó "0" (0168)
83 | 663 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Ingresos íntegros
84 | 674 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Índice
85 | 680 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 1º - Rdto. base producto
86 | 691 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Ingresos íntegros
87 | 702 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Índice
88 | 708 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 2º - Rdto. base producto
89 | 719 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Ingresos íntegros
90 | 730 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Índice
91 | 736 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 3º - Rdto. base producto
92 | 747 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Ingresos íntegros
93 | 758 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Índice
94 | 764 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 4º - Rdto. base producto
95 | 775 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Ingresos íntegros
96 | 786 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Índice
97 | 792 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 5º - Rdto. base producto
98 | 803 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Ingresos íntegros
99 | 814 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Índice
100 | 820 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 6º - Rdto. base producto
101 | 831 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Ingresos íntegros
102 | 842 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Índice
103 | 848 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 7º - Rdto. base producto
104 | 859 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Ingresos íntegros
105 | 870 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Índice
106 | 876 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 8º - Rdto. base producto
107 | 887 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Ingresos íntegros
108 | 898 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Índice
109 | 904 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 9º - Rdto. base producto
110 | 915 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Ingresos íntegros
111 | 926 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Índice
112 | 932 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 10º - Rdto. base producto
113 | 943 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Ingresos íntegros
114 | 954 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Índice
115 | 960 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 11º - Rdto. base producto
116 | 971 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Ingresos íntegros
117 | 982 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Índice
118 | 988 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 12º - Rdto. base producto
119 | 999 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Ingresos íntegros
120 | 1010 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Índice
121 | 1016 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 13º - Rdto. base producto
122 | 1027 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Ingresos íntegros
123 | 1038 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Índice
124 | 1044 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 14º - Rdto. base producto
125 | 1055 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Ingresos íntegros
126 | 1066 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Índice
127 | 1072 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 15º - Rdto. base producto
128 | 1083 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 16º - Ingresos íntegros
129 | 1094 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 16º - Índice
130 | 1100 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Producto 16º - Rdto. base producto
131 | 1111 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Total  ingresos íntegros (0169)
132 | 1122 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto previo (suma) (0170)
133 | 1133 | 11 | N | C | RESERVADO PARA LA A.E.A.T
134 | 1144 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Amortización inmovilizado (0172)
135 | 1155 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto minorado  (0173)
136 | 1166 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Medios de producción ajenos (2 enteros y 2 decimales) [0174]
137 | 1170 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Utilización personal asalariado (2 enteros y 2 decimales) (0175)
138 | 1174 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (0176)
139 | 1178 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (0177) Ver NOTA
140 | 1182 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 2 (0177) Ver NOTA
141 | 1186 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Actividades agricultura ecológica (2 enteros y dos decimales)  (0178)
142 | 1190 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Cultivo en tierras regadío utilice energía electrica ( 2 enteros y 2 decimales) (0179)
143 | 1194 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales)  (0180)
144 | 1198 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Ind. correct.- Determinadas actividades forestales  (2 enteros y 2 decimales)  (0181)
145 | 1202 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rdto. neto de módulos (0182)
146 | 1215 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción carácter general (0183)
147 | 1228 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Diferencia (0184)
148 | 1241 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducción agricultores jóvenes (0185)
149 | 1254 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Gastos extraordinarios por circunstancias excepcionales (0186]
150 | 1267 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto  (0187)
151 | 1280 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Reducciones rendimientos generados más 2 años o forma irregular (0188)
152 | 1293 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 2ª - Rendimiento neto reducido (0189)
153 | 1306 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Suma rendimientos netos reducidos de las actividades agrícolas, ganaderas y forestales en estimación objetiva  (0190)
154 | 1319 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva -  Reducción por ejercicio determinadas actividades económicas (0191)
155 | 1332 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total de las actividades agrícolas, ganaderas y forestales en estimación objetiva  (0194)
156 | 1345 | 600 | An |  | RESERVADO PARA LA A.E.A.T
157 | 1945 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10008000>
Total: |  | 1956
 |  |  |  |  | NOTA: Cumplimentar sólo cuando el índice 2 sea distinto al índice 1.

# 100-09

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "09000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (F) Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (0195)
8 | 15 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - NIF Entidad (0196)
9 | 35 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país (0197)
10 | 36 | 4 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Entidades y contribuyentes partícipes - Porcentaje participación  (2 enteros y dos decimales) (0198)
11 | 40 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (0199)
12 | 53 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Minoraciones  aplicables (0200)
13 | 66 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones aplicables (0201)
14 | 79 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto computable (0202)
15 | 92 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Neto atribuido por la entidad . Imp. computable (0203)
16 | 105 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Derivado valores deuda subordinada o partic. preferentes (0204)
17 | 118 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto atribuido (0205)
18 | 131 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Minoraciones aplicables (0206)
19 | 144 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Reducciones aplicables 23.2 (0207)
20 | 157 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Reducciones aplicables 23.3 y DT 25 (0208)
21 | 170 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. capital inmobiliario - Rdto. neto computable (0209)
22 | 183 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Criterio cobros/pagos. "1" o cero (0210]
23 | 184 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rendimiento neto (0211]
24 | 197 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Minoraciones aplicables (0212]
25 | 210 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Provisiones deducibles y gastos difícil justificación (0213]
26 | 223 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducción aplicable art.32.1 y DT 25 (0214]
27 | 236 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducción aplicable art.32.2.3 (0215]
28 | 249 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Reducción aplicable art.32.3 (0216]
29 | 262 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Rdtos. actividades económicas - Rdto. Neto computable (0217)
30 | 275 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas  patrimoniales - No derivadas transmisiones - Ganancias patrimoniales no derivadas de transmisiones, atribuidas por la entidad (0218)
31 | 288 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - No derivadas transmisiones - Pérdidas patrimoniales no derivadas de transmisiones, atribuidas por la entidad (0219)
32 | 301 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales (0220)
33 | 314 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión destinado a constituir renta vitalicia (0221)
34 | 327 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión al que resulta aplicable (0222)
35 | 340 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas 50 por 100 (sólo determinados inmuebles urbanos) (0223)
36 | 353 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas reinversión rentas vitalicias (0224)
37 | 366 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancia exenta reinversión en entidades de nueva o reciente creación (0225)
38 | 379 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Parte ganancias susceptibles reducción  (0226)
39 | 392 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Reducciones aplicables  (0227)
40 | 405 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas  (0228)
41 | 418 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas imputable 2017  (0229)
42 | 431 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad  (0230)
43 | 444 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 1 - Atribución de retenciones e ingresos a cuenta -  Retenciones e ingresos a cuenta atribuidos por la entidad (0231)
44 | 457 | 1 | Tit | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (0195)
45 | 458 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - NIF Entidad (0196)
46 | 478 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país (0197)
47 | 479 | 4 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Entidades y contribuyentes partícipes - Porcentaje participación  (2 enteros y dos decimales) (0198)
48 | 483 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (0199)
49 | 496 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Minoraciones  aplicables (0200)
50 | 509 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones aplicables (0201)
51 | 522 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto computable (0202)
52 | 535 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Neto atribuido por la entidad . Imp. computable (0203)
53 | 548 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Derivado valores deuda subordinada o partic. preferentes (0204)
54 | 561 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto atribuido (0205)
55 | 574 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Minoraciones aplicables (0206)
56 | 587 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Reducciones aplicables 23.2 (0207)
57 | 600 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Reducciones aplicables 23.3 y DT 25 (0208)
58 | 613 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. capital inmobiliario - Rdto. neto computable (0209)
59 | 626 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Criterio cobros/pagos. "1" o cero (0210]
60 | 627 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rendimiento neto (0211]
61 | 640 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Minoraciones aplicables (0212]
62 | 653 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Provisiones deducibles y gastos difícil justificación (0213]
63 | 666 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducción aplicable art.32.1 y DT 25 (0214]
64 | 679 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducción aplicable art.32.2.3 (0215]
65 | 692 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Reducción aplicable art.32.3 (0216]
66 | 705 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Rdtos. actividades económicas - Rdto. Neto computable (0217)
67 | 718 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas  patrimoniales - No derivadas transmisiones - Ganancias patrimoniales no derivadas de transmisiones, atribuidas por la entidad (0218)
68 | 731 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - No derivadas transmisiones - Pérdidas patrimoniales no derivadas de transmisiones, atribuidas por la entidad (0219)
69 | 744 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales (0220)
70 | 757 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión destinado a constituir renta vitalicia (0221)
71 | 770 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión al que resulta aplicable (0222)
72 | 783 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas 50 por 100 (sólo determinados inmuebles urbanos) (0223)
73 | 796 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas reinversión rentas vitalicias (0224)
74 | 809 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancia exenta reinversión en entidades de nueva o reciente creación (0225)
75 | 822 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Parte ganancias susceptibles reducción  (0226)
76 | 835 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Reducciones aplicables  (0227)
77 | 848 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas  (0228)
78 | 861 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas imputable 2017  (0229)
79 | 874 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad  (0230)
80 | 887 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad 2 - Atribución de retenciones e ingresos a cuenta -  Retenciones e ingresos a cuenta atribuidos por la entidad (0231)
81 | 900 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos netos de capital mobiliario (a integrar en la BI general) atribuidos (0232)
82 | 913 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos netos de capital mobiliario (a integrar en la BI del ahorrol) atribuidos (0233)
83 | 926 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos derivados de valores de deuda subordinada o participaciones preferentes (BI del ahorro) atribuidos (0234)
84 | 939 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos netos del capital mobiliario atribuidos (0235)
85 | 952 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos netos de actividades económicas atribuidos (0236)
86 | 965 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de ganancias patrimoniales no derivadas de transmisiones (a integrar en la BI general) atribuidas (0237)
87 | 978 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de pérdidas patrimoniales no derivadas de transmisiones (a integrar en la BI general) atribuidas (0238)
88 | 991 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de ganancias patrimoniales derivadas de transmisiones (a integrar en la BI del ahorro) atribuidas (0239)
89 | 1004 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de pérdidas patrimoniales derivadas de transmisiones (a integrar en la BI del ahorro) atribuidas (0240)
90 | 1017 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de retenciones e ingresos atribuidos (562)
91 | 1030 | 600 | An |  | RESERVADO PARA LA A.E.A.T
92 | 1630 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10009000>
Total: |  | 1641

# 100-10

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "10000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (F) Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1-  Entidades y contribuyentes socios. Contribuyente "0" a "9" (0241)
8 | 15 | 9 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1-  Entidades y contribuyentes socios. N.I.F. Entidad (0242)
9 | 24 | 1 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (0243)
10 | 25 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Base imponible imputada  (0244)
11 | 38 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones inversión empresarial (0245)
12 | 51 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones creación empleo (0246)
13 | 64 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deduccciones rentas Ceuta/Melilla (0247)
14 | 77 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones doble imposición internacional. (0248)
15 | 90 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones retenciones e ingresos a cuenta  - Retenciones e ingresos a cuenta imputados (0249)
16 | 103 | 1 | Tit | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2-  Entidades y contribuyentes socios. Contribuyente "0" a "9" (0241)
17 | 104 | 9 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2-  Entidades y contribuyentes socios. N.I.F. Entidad (0242)
18 | 113 | 1 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (0243)
19 | 114 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Base imponible imputada  (0244)
20 | 127 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Deducciones inversión empresarial (0245)
21 | 140 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Deducciones creación empleo (0246)
22 | 153 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Deduccciones rentas Ceuta/Melilla (0247)
23 | 166 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones bases imponibles y deducciones - Deducciones doble imposición internacional. (0248)
24 | 179 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 2- Imputaciones retenciones e ingresos a cuenta  - Retenciones e ingresos a cuenta imputados (0249)
25 | 192 | 13 | N |  | Regs. especiales - Agrupaciones interés económico y UTES - Suma de bases imponibles imputadas  (0250)
26 | 205 | 13 | N |  | Regs. especiales - Agrupaciones interés económico y UTES - Suma de retenciones e ingresos a cuenta imputados (0563)
27 | 218 | 1 | Tit | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Contribuyente  "0" a "9" (0251)
28 | 219 | 24 | An | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Denominación entidad no residente (0252)
29 | 243 | 13 | N | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Importe imputación  (0253)
30 | 256 | 1 | Tit | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 2 - Contribuyente  "0" a "9" (0251)
31 | 257 | 24 | An | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 2 - Denominación entidad no residente (0252)
32 | 281 | 13 | N | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 2 - Importe imputación  (0253)
33 | 294 | 13 | N |  | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Suma imputaciones de rentas transparencia fiscal internacional (255)
34 | 307 | 1 | Tit | C | Regs. especiales - Imputación rentas cesión derechos imagen - Contribuyente que debe efectuar la imputacion.  "0" a "9" (0256)
35 | 308 | 25 | An | C | Regs. especiales - Imputación rentas cesión derechos imagen - NIF o denominación persona/entidad cesionaria derechos imagen (0257)
36 | 333 | 25 | An | C | Regs. especiales - Imputación rentas cesión derechos imagen - NIF o denominación persona/entidad relación laboral (0258]
37 | 358 | 13 | N | C | Regs. especiales - Imputación rentas cesión derechos imagen - Cantidad a imputar  (0259)
38 | 371 | 13 | N |  | Regs. especiales - Imputación rentas cesión derechos imagen - Suma imputaciones de rentas por cesión derechos de imagen (0260)
39 | 384 | 1 | Tit | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Contribuyente  "0" a "9" (0261)
40 | 385 | 24 | An | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Denominación Institución (0262)
41 | 409 | 13 | N | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Importe imputación (0263)
42 | 422 | 1 | Tit | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Contribuyente  "0" a "9" (0261)
43 | 423 | 24 | An | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Denominación Institución (0262)
44 | 447 | 13 | N | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 2 - Importe imputación (0263)
45 | 460 | 13 | N |  | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales -Suma de imputaciones de rentas por participación en IIC (0264)
46 | 473 | 1 | Tit | C | (G1) Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Contribuyente  que obtiene los premios   "0" a "9" (0265)
47 | 474 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En metálico - Importe (0266)
48 | 487 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Valoración (0267)
49 | 500 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta (0268)
50 | 513 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta repercutidos (0269)
51 | 526 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Importe computable (0270)
52 | 539 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Pérdidas patrimoniales derivadas de estos juegos (0271)
53 | 552 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de ganancias patrimoniales derivadas de estos juegos (0272)
54 | 565 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de pérdidas patrimoniales derivadas de estos juegos (0273)
55 | 578 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de ganancias patrimoniales netas derivadas de estos juegos (0274)
56 | 591 | 1 | Tit | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - Contribuyente que obtiene los premios. "0" a "9" (0275)
57 | 592 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En metálico - Importe (0276)
58 | 605 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Valoración (0277)
59 | 618 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta (0278)
60 | 631 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta repercutidos (0279)
61 | 644 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Importe computable (0280)
62 | 657 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - Suma de ganancias patrimoniales derivadas de premios (0281)
63 | 670 | 1 | Tit | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Contribuyente que obtiene otras ganancias/pérdidas. "0" a "9" (0282)
64 | 671 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Subvenciones adquisición vivienda (0283)
65 | 684 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Otras subvenciones o ayudas 0284)
66 | 697 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Ganancias patrimoniales vecinos por aprovechamientos forestales (0285)
67 | 710 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Renta básica emancipación (0286)
68 | 723 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas -  Importe ganancias (0287)
69 | 736 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe pérdidas (0288)
70 | 749 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Suma de otras ganancias que no derivan de la transmisión (0289)
71 | 762 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Suma de otras pérdidas que no derivan de la transmisión (0290)
72 | 775 | 600 | An |  | RESERVADO PARA LA A.E.A.T
73 | 1375 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10010000>
Total: |  | 1386

# 100-11

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "11000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 15 | 1 | Tit | C | (G2) Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente 1 "0" a "9" [0291]
8 | 16 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente 1 -Valor total acumulado [0292]
9 | 29 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente 2 "0" a "9" [0291]
10 | 30 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente 2 -Valor total acumulado [0292]
11 | 43 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Inst. inv. colectiva - Sociedad/Fondo 1 - Contribuyente "0" a "9" (0293)
12 | 44 | 9 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - N.I.F. (0294)
13 | 53 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 -  Importe global transmisiones (0295)
14 | 66 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Importe global transmisiones -  Valor transmisión para renta vitalicia (0296)
15 | 79 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Importe global transmisiones -  Valor transmisión aplicable D.T.9ª (0297)
16 | 92 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 1 - Importe global adquisiciones (0298)
17 | 105 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 1 -Ganancias patrimoniales (0299)
18 | 118 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 -Ganancias exentas reinversión rentas vitalicias (0300)
19 | 131 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 1 - Parte ganancias suceptible reducción (0301)
20 | 144 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 1 - Reducción aplicable (0302)
21 | 157 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Ganancias patrimoniales reducidas no exentas (0303)
22 | 170 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Pérdidas patrimoniales (0304)
23 | 183 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 1 - Pérdidas patrimoniales imputables a 2017 (0305)
24 | 196 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Inst. inv. colectiva - Sociedad/Fondo 2 - Contribuyente "0" a "9" (0293)
25 | 197 | 9 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - N.I.F. (0294)
26 | 206 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 -  Importe global transmisiones (0295)
27 | 219 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Importe global transmisiones -  Valor transmisión para renta vitalicia (0296)
28 | 232 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Importe global transmisiones -  Valor transmisión aplicable D.T.9ª (0297)
29 | 245 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 2 - Importe global adquisiciones (0298)
30 | 258 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 2 -Ganancias patrimoniales (0299)
31 | 271 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 -Ganancias exentas reinversión rentas vitalicias (0300)
32 | 284 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 2 - Parte ganancias suceptible reducción (0301)
33 | 297 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 2 - Reducción aplicable (0302)
34 | 310 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Ganancias patrimoniales reducidas no exentas (0303)
35 | 323 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Pérdidas patrimoniales (0304)
36 | 336 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 2 - Pérdidas patrimoniales imputables a 2017 (0305)
37 | 349 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Inst. inv. colectiva - Sociedad/Fondo 3 - Contribuyente "0" a "9" (0293)
38 | 350 | 9 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - N.I.F. (0294)
39 | 359 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 -  Importe global transmisiones (0295)
40 | 372 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Importe global transmisiones -  Valor transmisión para renta vitalicia (0296)
41 | 385 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Importe global transmisiones -  Valor transmisión aplicable D.T.9ª (0297)
42 | 398 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Sociedad/Fondo 3 - Importe global adquisiciones (0298)
43 | 411 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -  Sociedad/Fondo 3 -Ganancias patrimoniales (0299)
44 | 424 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 -Ganancias exentas reinversión rentas vitalicias (0300)
45 | 437 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados  - Sociedad/Fondo 3 - Parte ganancias suceptible reducción (0301)
46 | 450 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados -Sociedad/Fondo 3 - Reducción aplicable (0302)
47 | 463 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Ganancias patrimoniales reducidas no exentas (0303)
48 | 476 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Pérdidas patrimoniales (0304)
49 | 489 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva - Resultados - Sociedad/Fondo 3 - Pérdidas patrimoniales imputables a 2017 (0305)
50 | 502 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. Colectiva - Suma de ganancias patrimoniales de transmisiones o reembolsos acciones o participaciones Inst.Inv.Colectiva (0306)
51 | 515 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. Colectiva - Suma de pérdidas patrimoniales de transmisiones o reembolsos acciones o participaciones Inst.Inv.Colectiva (0307)
52 | 528 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
53 | 531 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 1 -  Contribuyente valores transmitidos "0" a "9" (0308)
54 | 532 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 1 - Denominación valores (0309)
55 | 552 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 1 - Importe global efectuadas en 2017 (0310)
56 | 565 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 1 - Importe global efectuadas en 2017 - Valor transmisión a constituir en renta vitalicia  (0311)
57 | 578 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 1 - Importe global efectuadas en 2017 - Valor transmisión aplicable D.T.9ª (0312)
58 | 591 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Valor adquisición global (0313)
59 | 604 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados -  Ganancias patrimoniales (0314)
60 | 617 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0315)
61 | 630 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0316)
62 | 643 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Reducción aplicable (0317)
63 | 656 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Ganancias patrimoniales no exentas (0318)
64 | 669 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Pérdidas patrim. Importe obtenido (0319)
65 | 682 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 1 - Resultados  - Pérdidas patrim. Importe computable (0320)
66 | 695 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 2  -  Contribuyente valores transmitidos "0" a "9" (0308)
67 | 696 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 2 - Denominación valores (0309)
68 | 716 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 2 - Importe global efectuadas en 2017 (0310)
69 | 729 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 2 - Importe global efectuadas en 2017 - Valor transmisión a constituir en renta vitalicia  (0311)
70 | 742 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 2 - Importe global efectuadas en 2017 - Valor transmisión aplicable D.T.9ª (0312)
71 | 755 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Valor adquisición global (0313)
72 | 768 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados -  Ganancias patrimoniales (0314)
73 | 781 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0315)
74 | 794 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0316)
75 | 807 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Reducción aplicable (0317)
76 | 820 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Ganancias patrimoniales no exentas (0318)
77 | 833 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Pérdidas patrim. Importe obtenido (0319)
78 | 846 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 2 - Resultados  - Pérdidas patrim. Importe computable (0320)
79 | 859 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 3  -  Contribuyente valores transmitidos "0" a "9" (0308)
80 | 860 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones - Entidad 3 - Denominación valores (0309)
81 | 880 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones/Participaciones  - Entidad 3 - Importe global efectuadas en 2017 (0310)
82 | 893 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 3 - Importe global efectuadas en 2017 - Valor transmisión a constituir en renta vitalicia  (0311)
83 | 906 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones/Participaciones - Entidad 3 - Importe global efectuadas en 2017 - Valor transmisión aplicable D.T.9ª (0312)
84 | 919 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Valor adquisición global (0313)
85 | 932 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados -  Ganancias patrimoniales (0314)
86 | 945 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0315)
87 | 958 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0316)
88 | 971 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Reducción aplicable (0317)
89 | 984 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Ganancias patrimoniales no exentas (0318)
90 | 997 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Pérdidas patrim. Importe obtenido (0319)
91 | 1010 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Entidad 3 - Resultados  - Pérdidas patrim. Importe computable (0320)
92 | 1023 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Suma de ganancias patrimoniales derivadas de transmisiones de acciones o participaciones negociadas (0321)
93 | 1036 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones/Participaciones  - Suma de pérdidas patrimoniales derivadas de transmisiones de acciones o participaciones negociadas (0322)
94 | 1049 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
95 | 1052 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad 1 -  Contribuyente valores transmitidos "0" a "9" (0323)
96 | 1053 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad 1 - Denominación valores (0324)
97 | 1073 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción  - Entidad 1 - Importe global efectuadas en 2017 (0325)
98 | 1086 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad 1 - Importe global efectuadas en 2017 - Valor transmisión a constituir en renta vitalicia  (0326)
99 | 1099 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad 1 - Importe global efectuadas en 2017 - Valor transmisión aplicable D.T.9ª (0327)
100 | 1112 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 1 - Valor adquisición global (0328)
101 | 1125 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 1 - Resultados -  Ganancias patrimoniales (0329)
102 | 1138 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 1 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0330)
103 | 1151 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 1 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0331)
104 | 1164 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 1 - Resultados  - Reducción aplicable (0332)
105 | 1177 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 1 - Resultados  - Ganancias patrimoniales no exentas (0333)
106 | 1190 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 1 - Resultados  - Pérdidas patrim. Importe obtenido (0334)
107 | 1203 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 1 - Resultados  - Pérdidas patrim. Importe computable (0335)
108 | 1216 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad 2  -  Contribuyente valores transmitidos "0" a "9" (0323)
109 | 1217 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad 2 - Denominación valores (0324)
110 | 1237 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción  - Entidad 2 - Importe global efectuadas en 2017 (0325)
111 | 1250 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad 2 - Importe global efectuadas en 2017 - Valor transmisión a constituir en renta vitalicia  (0326)
112 | 1263 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad 2 - Importe global efectuadas en 2017 - Valor transmisión aplicable D.T.9ª (0327)
113 | 1276 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 2 - Valor adquisición global (0328)
114 | 1289 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 2 - Resultados -  Ganancias patrimoniales (0329)
115 | 1302 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 2 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0330)
116 | 1315 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 2 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0331)
117 | 1328 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 2 - Resultados  - Reducción aplicable (0332)
118 | 1341 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 2 - Resultados  - Ganancias patrimoniales no exentas (0333)
119 | 1354 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 2 - Resultados  - Pérdidas patrim. Importe obtenido (0334)
120 | 1367 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 2 - Resultados  - Pérdidas patrim. Importe computable (0335)
121 | 1380 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad 3  -  Contribuyente valores transmitidos "0" a "9" (0323)
122 | 1381 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad 3 - Denominación valores (0324)
123 | 1401 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción  - Entidad 3 - Importe global efectuadas en 2017 (0325)
124 | 1414 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad 3 - Importe global efectuadas en 2017 - Valor transmisión a constituir en renta vitalicia  (0326)
125 | 1427 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad 3 - Importe global efectuadas en 2017 - Valor transmisión aplicable D.T.9ª (0327)
126 | 1440 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 3 - Valor adquisición global (0328)
127 | 1453 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 3 - Resultados -  Ganancias patrimoniales (0329)
128 | 1466 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 3 - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0330)
129 | 1479 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 3 - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0331)
130 | 1492 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 3 - Resultados  - Reducción aplicable (0332)
131 | 1505 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 3 - Resultados  - Ganancias patrimoniales no exentas (0333)
132 | 1518 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 3 - Resultados  - Pérdidas patrim. Importe obtenido (0334)
133 | 1531 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad 3 - Resultados  - Pérdidas patrim. Importe computable (0335)
134 | 1544 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Suma de ganancias patrimoniales derivadas de transmisiones de derechos de suscripción (0336)
135 | 1557 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Suma de pérdidas patrimoniales derivadas de transmisiones de derechos de suscripción (0337)
136 | 1570 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
137 | 1573 | 600 | An |  | RESERVADO PARA LA A.E.A.T
138 | 2173 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10011000>
Total: |  | 2184

# 100-12

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "12000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 15 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (0338)
8 | 16 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (0340)
9 | 17 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -  Inmuebles. Situación. Clave "0" a "4" (0341)
10 | 18 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -   Inmuebles. Situación. Ref. catastral (0342)
11 | 38 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha transmisión (0343)
12 | 46 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha adquisición (0344)
13 | 54 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión (0345)
14 | 67 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Constituir renta vitalicia (0346)
15 | 80 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - De la vivienda habitual (0347)
16 | 93 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Susceptible de reducción (0348)
17 | 106 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor adquisición (0349)
18 | 119 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (0350)
19 | 132 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (0351)
20 | 145 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (0352)
21 | 158 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta 50 por 100 (0353)
22 | 171 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en rentas vitalicias (0354)
23 | 184 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en vivienda habitual (0355)
24 | 197 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en entidades de nueva o reciente creación (0356)
25 | 210 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia no exenta (0357)
26 | 223 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Parte ganancia susceptible reducción  (0358)
27 | 236 | 4 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Nº años permanencia hasta 31/12/1994  (0359)
28 | 240 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Reducción aplicable (0360)
29 | 253 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida (0361)
30 | 266 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida  no exenta  (0362)
31 | 279 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Parte ganancia susceptible reducción  (0363)
32 | 292 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Reducción licencia autotaxis  (0364)
33 | 305 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida( (0365)
34 | 318 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida no exenta  (0366)
35 | 331 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (0339)
36 | 332 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Contribuyente "0" a "9" (0338)
37 | 333 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Tipo elemento. Clave "0" a "7" (0340)
38 | 334 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -  Inmuebles. Situación. Clave "0" a "4" (0341)
39 | 335 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -   Inmuebles. Situación. Ref. catastral (0342)
40 | 355 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Fecha transmisión (0343)
41 | 363 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Fecha adquisición (0344)
42 | 371 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión (0345)
43 | 384 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - Constituir renta vitalicia (0346)
44 | 397 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - De la vivienda habitual (0347)
45 | 410 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor transmisión - Susceptible de reducción (0348)
46 | 423 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 -Valor adquisición (0349)
47 | 436 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida obtenida (0350)
48 | 449 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia negativa - Pérdida imputable (0351)
49 | 462 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia obtenida (0352)
50 | 475 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta 50 por 100 (0353)
51 | 488 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta reinversión en rentas vitalicias (0354)
52 | 501 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta reinversión en vivienda habitual (0355)
53 | 514 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia exenta reinversión en entidades de nueva o reciente creación (0356)
54 | 527 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Diferencia positiva - Ganancia no exenta (0357)
55 | 540 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Parte ganancia susceptible reducción  (0358)
56 | 553 | 4 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Nº años permanencia hasta 31/12/1994  (0359)
57 | 557 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Reducción aplicable (0360)
58 | 570 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Ganancia patrimonial reducida (0361)
59 | 583 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos no afectos - Ganancia patrimonial reducida no exenta (0362)
60 | 596 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Parte ganancia susceptible reducción  (0363)
61 | 609 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Reducción licencia autotaxis  (0364)
62 | 622 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Ganancia patrimonial reducida( (0365)
63 | 635 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Elementos afectos - Ganancia patrimonial reducida no exenta (0366)
64 | 648 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 2 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (0339)
65 | 649 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de pérdidas patrimoniales derivadas de transmisiones de otros elementos patrimoniales (0368)
66 | 662 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de ganancias patrimoniales derivadas de transmisiones de otros elementos patrimoniales no afectos a actividades económicas (0369)
67 | 675 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de ganancias patrimoniales derivadas de transmisiones de otros elementos patrimoniales afectos a actividades económicas (0370)
68 | 688 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
69 | 691 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Contribuyente "0" a "9" (0371)
70 | 692 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Otras ganancias BI ahorro (0372)
71 | 705 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Suma de otras ganancias BI ahorro (0373)
72 | 718 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Ganancia 1 -  Contribuyente "0" a "9" (0374)
73 | 719 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Ganancia 1 -  Importe a imputar a 2017. (0375)
74 | 732 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Ganancia 2 -  Contribuyente "0" a "9" (0374)
75 | 733 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Ganancia 2 -  Importe a imputar a 2017. (0375)
76 | 746 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Ganancia 3 -  Contribuyente "0" a "9" (0374)
77 | 747 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Ganancia 3 -  Importe a imputar a 2017. (0375)
78 | 760 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Ganancia 1 -  Importe a imputar a 2017. - Total (0376)
79 | 773 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Pérdida  1 -  Contribuyente "0" a "9" (0377)
80 | 774 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Pérdida  1 -  Importe pérdida imputar a 2017. (0378)
81 | 787 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Pérdida 2 -  Contribuyente "0" a "9" (0377)
82 | 788 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Pérdida 2 -  Importe pérdida imputar a 2017. (0378)
83 | 801 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Pérdida  3 -  Contribuyente "0" a "9" (0377)
84 | 802 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores - Pérdida  3 -  Importe pérdida imputar a 2017. (0378)
85 | 815 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2017. Ganancias/pérdidas ejercicios anteriores -  Importe pérdida imputar a 2017. - Total  (0379)
86 | 828 | 600 | An |  | RESERVADO PARA LA A.E.A.T
87 | 1428 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10012000>
Total: |  | 1439

# 100-13

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "13000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (G3) Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2017 diferimiento por reinversión - Ganancia 1 - Contribuyente "0" a "9" (0380)
8 | 15 | 13 | N | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2017 diferimiento por reinversión - Ganancia 1 - Importe ganancia (0381]
9 | 28 | 1 | Tit | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2017 diferimiento por reinversión - Ganancia 2 - Contribuyente "0" a "9" (0380)
10 | 29 | 13 | N | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2017 diferimiento por reinversión - Ganancia 2 - Importe ganancia (0381)
11 | 42 | 1 | Tit | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2017 diferimiento por reinversión - Ganancia 3 - Contribuyente "0" a "9" (0380)
12 | 43 | 13 | N | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2017 diferimiento por reinversión - Ganancia 3 - Importe ganancia (0381)
13 | 56 | 13 | N |  | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2017 diferimiento por reinversión - Suma de imputación a 2017 ganancias patrimoniales acogidas a diferimiento por reinversión (0382)
14 | 69 | 1 | Num | C | (G4) Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Contribuyente que ha transmitido intervivos las acciones "1" o "0" [0383]
15 | 70 | 1 | Tit | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Contribuyente titular valores "0" a "9" (0384)
16 | 71 | 9 | An | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Nif sociedad emisora o fondo de inversión (0385)
17 | 80 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Valor de mercado  acciones/participaciones (0386)
18 | 93 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Valor transmisión acciones (0387)
19 | 106 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Valor al que resulta aplicable D.T.9ª (0388)
20 | 119 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Valor adquisición (0389)
21 | 132 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Resultados - Ganancias patrimoniales (0390)
22 | 145 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Resultados - Ganancias suceptibles reducción (0391)
23 | 158 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Resultados - Reducción aplicable (0392)
24 | 171 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 1 -  Resultados - Ganancias patrimoniales reducidas (0393)
25 | 184 | 1 | Num | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Contribuyente que ha transmitido intervivos las acciones "1" o "0" [0383]
26 | 185 | 1 | Tit | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Contribuyente titular valores "0" a "9" (0384)
27 | 186 | 9 | An | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Nif sociedad emisora o fondo de inversión (0385)
28 | 195 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Valor de mercado  acciones/participaciones (0386)
29 | 208 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Valor transmisión acciones (0387)
30 | 221 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Valor al que resulta aplicable D.T.9ª (0388)
31 | 234 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Valor adquisición (0389)
32 | 247 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Resultados - Ganancias patrimoniales (0390)
33 | 260 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Resultados - Ganancias suceptibles reducción (0391)
34 | 273 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Resultados - Reducción aplicable (0392)
35 | 286 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 2 -  Resultados - Ganancias patrimoniales reducidas (0393)
36 | 299 | 1 | Num | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Contribuyente que ha transmitido intervivos las acciones "1" o "0" [0383]
37 | 300 | 1 | Tit | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Contribuyente titular valores "0" a "9" (0384)
38 | 301 | 9 | An | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Nif sociedad emisora o fondo de inversión (0385)
39 | 310 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Valor de mercado  acciones/participaciones (0386)
40 | 323 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Valor transmisión acciones (0387)
41 | 336 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Valor al que resulta aplicable D.T.9ª (0388)
42 | 349 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Valor adquisición (0389)
43 | 362 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Resultados - Ganancias patrimoniales (0390)
44 | 375 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Resultados - Ganancias suceptibles reducción (0391)
45 | 388 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Resultados - Reducción aplicable (0392)
46 | 401 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad 3 -  Resultados - Ganancias patrimoniales reducidas (0393)
47 | 414 | 13 | N |  | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Suma de ganancias patrimoniales por cambio de residencia fuera del territorio español (0394)
48 | 427 | 1 | Tit |  | (G5) Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (0395)
49 | 428 | 2 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España -  Número de operaciones1 (0396)
50 | 430 | 1 | Tit |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente 2   "0" a "9" (0397)
51 | 431 | 2 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones 2 (0398)
52 | 433 | 1 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Si entidades no residentes no han aplicado régimen fiscal similar a éste  (0399)
53 | 434 | 13 | N |  | (G6) Integración y compensación ganancias/pérdidas patrimoniales imputables 2017 - A integrar en base imponible general -  Suma ganancias (0400)
54 | 447 | 13 | N |  | Integración y compensación ganancias/pérdidas patrimoniales imputables 2017 - A integrar base imponible general -  Suma pérdidas (0401)
55 | 460 | 13 | N |  | Integración y compensación ganancias/pérdidas patrimoniales imputables 2017 - A integrar base imponible general -  Saldo neto - Diferencia positiva (0402)
56 | 473 | 13 | N |  | Integración y compensación ganancias/pérdidas patrimoniales imputables 2017 - A integrar base imponible general -  Saldo neto - Diferencia negativa (0403)
57 | 486 | 13 | N |  | Integración y compensación ganancias/pérdidas patrimoniales imputables 2017 - A integrar base imponible ahorro - Suma ganancias (0404)
58 | 499 | 13 | N |  | Integración y compensación ganancias/pérdidas patrimoniales imputables 2017 - A integrar base imponible ahorro - Suma pérdidas (0405)
59 | 512 | 13 | N |  | Integración y compensación ganancias/pérdidas patrimoniales imputables 2017 - A integrar base imponible ahorro - Saldo neto  - Diferencia positiva (0406)
60 | 525 | 13 | N |  | Integración y compensación ganancias/pérdidas patrimoniales imputables 2017 - A integrar base imponible ahorro - Saldo neto - Diferencia negativa (0407)
61 | 538 | 13 | N |  | (H) Base imponible general y base imponible ahorro - Integración y compensación rdtos. capital mobiliario (B.I. ahorro) - Saldo neto positivo rdto. capital mobiliario imputable a 2017 (0409)
62 | 551 | 13 | N |  | Base imponible general y base imponible ahorro - Integración y compensación rdtos. capital mobiliario (B.I. ahorro) - Saldo neto negativo rdto. capital mobiliario imputable a 2017 (0410)
63 | 564 | 13 | N |  | Base imponible general y base imponible ahorro - BI general - Saldo neto positivo ganancias/pérdidas 2017 a integrar base imponible general (0402)
64 | 577 | 13 | N |  | Base imponible general y base imponible ahorro - BI general - Compensación - Saldos netos negativos ganancias/pérdidas 2013 a 2016  pendientes compensasión (0411)
65 | 590 | 13 | N |  | Base imponible general y base imponible ahorro - BI general - Saldos neto rendimientos a integrar en base Imponible general (0412)
66 | 603 | 13 | N |  | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Saldo neto negativo ganancias/pérdidas 2017 (0413)
67 | 616 | 13 | N |  | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Resto saldos netos negativos ganancias/pérdidas 2013 a 2016 pendientes compensación (0414)
68 | 629 | 13 | N |  | Base imponible general y base imponible ahorro - BI general -  Base imponible general (0415)
69 | 642 | 600 | An |  | RESERVADO PARA LA A.E.A.T
70 | 1242 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10013000>
Total: |  | 1253

# 100-14

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "14000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas  (0406)
7 | 26 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro -  Compensaciones - Saldos netos negativos rendimientos capital mobiliario  (0416]
8 | 39 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas no derivadas transmisión de deuda subordinada o preferentes 2013 a 2014 (0417)
9 | 52 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas derivadas transmisión de deuda subordinada o preferentes 2013 a 2014 (0418)
10 | 65 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2015 pendientes compensación (0419)
11 | 78 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2016 pendientes compensación (0420)
12 | 91 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario de deuda subordinada o preferentes 2013 a 2014 (0421)
13 | 104 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2015 pendiente compensación (0422)
14 | 117 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2016 pendiente compensación (0423)
15 | 130 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimientos capital mobiliario a integrar en BI ahorro (0409)
16 | 143 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro -  Compensaciones -  Saldos netos negativos ganancias/pérdidas (0424)
17 | 156 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario que no derive deuda o participaciones preferentes 2013 a 2014 (0425)
18 | 169 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario que derive deuda o participaciones preferentes 2013 a 2014 (0426)
19 | 182 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2015 pendientes compensación (0427)
20 | 195 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2016 pendientes compensación (0428)
21 | 208 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos de ganancias/pérdidas deuda subordinada o participaciones preferentes 2013 a 2014 (0429)
22 | 221 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2015 pendientes compensación (0430)
23 | 234 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2016 pendientes compensación (0431)
24 | 247 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Base imponible del ahorro (0435)
25 | 260 | 13 | N |  | (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidades familiares tributación conjunta (0436)
26 | 273 | 1 | Tit |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 1 "0" a "9"  (0437)
27 | 274 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2012 a 2016 - 1 (438)
28 | 287 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 a 2016 de contribuciones a seguros colectivos de dependencia - 1 (0439)
29 | 300 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones -1 (0440)
30 | 313 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuciones a seguros colectivos de dependencia -1 (0441)
31 | 326 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción  -1 (0442)
32 | 339 | 1 | Tit |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente 2 "0" a "9"  (0437)
33 | 340 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2012 a 2016 - 2 (438)
34 | 353 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 y 2016 de contribuciones a seguros colectivos de dependencia - 2 (0439)
35 | 366 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones -2 (0440)
36 | 379 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuciones a seguros colectivos de dependencia -2 (0441)
37 | 392 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción  -2 (0442)
38 | 405 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total con derecho a reducción (0443)
39 | 418 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones sistemas previsión social cónyuge del contribuyente - Total con derecho a reducción (0444)
40 | 431 | 2 | Num |  | RESERVADO PARA LA A.E.A.T
41 | 433 | 1 | Tit | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Contribuyente 1 "0" a "9" (0445)
42 | 434 | 9 | An | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - NIF persona con discapacidad - 1 (0446)
43 | 443 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones por la persona con discapacidad. Excesos pendientes reducir - 1 (0447)
44 | 456 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones a favor de parientes. Excesos pendientes reducir - 1 (0448)
45 | 469 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones 2017 propia persona con discapacidad  -1 (0449)
46 | 482 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones 2017 parientes o tutores -1 (0450)
47 | 495 | 1 | Tit | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Contribuyente 2 "0" a "9" (0445)
48 | 496 | 9 | An | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - NIF persona con discapacidad - 2 (0446)
49 | 505 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones por la persona con discapacidad. Excesos pendientes reducir - 2 (0447)
50 | 518 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones a favor de parientes. Excesos pendientes reducir - 2 (0448)
51 | 531 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones 2017 propia persona con discapacidad  -2 (0449)
52 | 544 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones 2017 parientes o tutores -2 (0450)
53 | 557 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Total con derecho a reducción (0451)
54 | 570 | 600 | An |  | RESERVADO PARA LA A.E.A.T
55 | 1170 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10014000>
Total: |  | 1181

# 100-15

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "15000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 1 | Tit | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 1 "0" a "9" (0452)
7 | 14 | 9 | An | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad - 1  (0453)
8 | 23 | 13 | N | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir - 1  (0454)
9 | 36 | 13 | N | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2017 -1  (0455)
10 | 49 | 1 | Tit | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente 2 "0" a "9" (0452)
11 | 50 | 9 | An | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad - 2  (0453)
12 | 59 | 13 | N | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir - 2 (0454)
13 | 72 | 13 | N | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones 2017 -2  (0455)
14 | 85 | 13 | N | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Total con derecho a reducción (0456)
15 | 98 | 1 | Tit | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos -  Contribuyente 1 "0" a "9" (0457)
16 | 99 | 20 | An | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad -1  (0458)
17 | 119 | 1 | Num | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si ha consignado NIF de otro país 1 (431]  -1 "1" o "0" (0459)
18 | 120 | 13 | N | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial - 1  (0460)
19 | 133 | 1 | Tit | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos -  Contribuyente 2 "0" a "9" (0457)
20 | 134 | 20 | An | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad -2  (0458)
21 | 154 | 1 | Num | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si ha consignado NIF de otro país 1 (431]  -2 "1" o "0" (0459)
22 | 155 | 13 | N | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial - 2  (0460)
23 | 168 | 13 | N | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Total derecho reducción (0461)
24 | 181 | 1 | Tit | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 1 "0" a "9" (0462)
25 | 182 | 13 | N | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales -  Excesos pendientes reducir   -1  (0463)
26 | 195 | 13 | N | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones -1  (0464)
27 | 208 | 1 | Tit | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente 2 "0" a "9" (0462)
28 | 209 | 13 | N | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales -  Excesos pendientes reducir  -2  (0463)
29 | 222 | 13 | N | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones -2  (0464)
30 | 235 | 13 | N | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Total con derecho a reducción (0465)
31 | 248 | 13 | N | (J) Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base imponible general (0415)
32 | 261 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Tributación conjunta (0466)
33 | 274 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social (régimen general) (0467)
34 | 287 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social cónyuge (0468)
35 | 300 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social personas discapacidad (0469)
36 | 313 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones patrimonios protegidos personas discapacidad (0470)
37 | 326 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Pensiones compensatorias/anualidades alimentos (0471)
38 | 339 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones mutualidades prev. soc. deportistas profesionales (0472)
39 | 352 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general (0473)
40 | 365 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Compensación bases liquidables generales negativas (0474)
41 | 378 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general sometida a gravamen (0475)
42 | 391 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base imponible ahorro (0435)
43 | 404 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción tributación conjunta (0476)
44 | 417 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción pensiones comp./anualidades alimentos (0477)
45 | 430 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base liquidable del ahorro (0480)
46 | 443 | 13 | N | (K) Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe parte estatal (0481)
47 | 456 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe parte autonómica (0482)
48 | 469 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe parte estatal  (0483)
49 | 482 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe parte autonómica (0484)
50 | 495 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe  parte estatal (0485)
51 | 508 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe parte autonómica (0486)
52 | 521 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe parte estatal (0487)
53 | 534 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe parte autonómica (0488)
54 | 547 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo personal y familiar parte estatala (0489)
55 | 560 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe total cálculo gravamen autonómico (0490)
56 | 573 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen estatal  (0491)
57 | 586 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen estatal (0492)
58 | 599 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general  - gravamen autonómico (0493)
59 | 612 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen autonómico (0494)
60 | 625 | 600 | An | RESERVADO PARA LA A.E.A.T
61 | 1225 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10015000>
Total: |  | 1236

# 100-16

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "16000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (L) Datos adicionales - Rentas exentas excepto para determinar gravamen. Base liquidable general (0495)
7 | 26 | 13 | N | Datos adicionales - Rentas exentas excepto para determinar gravamen. Base liquidable ahorro (0496)
8 | 39 | 13 | N | Datos adicionales - Anualidades para alimentos a favor de los hijos. Importe (0497)
9 | 52 | 13 | N | (N) Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla (0475) - Parte estatal (0498)
10 | 65 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del  Impuesto importe casilla (0475) - Parte autonómica (0499)
11 | 78 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general del Impuesto importe casilla (0491) - Parte estatal (0500)
12 | 91 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala autonómica del Impuesto importe casilla (0493) - Parte autonómica (0501)
13 | 104 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte estatal (0502)
14 | 117 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte autonómica (0503)
15 | 130 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medios gravamen - Parte estatal (0504)
16 | 134 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medios gravamen - Parte autonómica (0505)
17 | 138 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla (480) - Parte estatal (0506)
18 | 151 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla (480) - Parte autonómica (0507)
19 | 164 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general del lmpuesto importe casilla (492) - Parte estatal (0508)
20 | 177 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala autonómica del Impuesto importe casilla (494) - Parte autonómica (0509)
21 | 190 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte estatal (0510)
22 | 203 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte autonómica  (0511)
23 | 216 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medios gravamen - Parte estatal (0512)
24 | 220 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medios gravamen - Parte autonómica (0513)
25 | 224 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra estatal - Parte estatal (0514)
26 | 237 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra autonómica - Parte autonómica (0515)
27 | 250 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte estatal (0516)
28 | 263 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte autonómica (0517)
29 | 276 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión empresas nueva o reciente creación - Parte estatal (0518)
30 | 289 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte estatal (0519)
31 | 302 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte autonómica (0520)
32 | 315 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones- Parte estatal (0521)
33 | 328 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones - Parte autonómica (0522)
34 | 341 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte estatal (0523)
35 | 354 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte autonómica (0524)
36 | 367 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte estatal (0525)
37 | 380 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte autonómica (0526]
38 | 393 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte estatal (0527)
39 | 406 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte autonómica (0528)
40 | 419 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte estatal (0529)
41 | 432 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte autonómica (0530)
42 | 445 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte estatal (0531)
43 | 458 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte autonómica (0532)
44 | 471 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - Suma deducciones autonómicas (0534)
45 | 484 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida estatal - Parte estatal (0535)
46 | 497 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida autonómica - Parte autonómica (0536)
47 | 510 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - Parte estatal (0537]
48 | 523 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - Parte estatal (0538)
49 | 536 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2016 - Importe - Parte estatal (0539]
50 | 549 | 1 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2016 - Regularización motivada por DA 45 [0540] "1" o "0"
51 | 550 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2016 - Intereses demora -  Parte estatal (0541)
52 | 563 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2016 - Importe - Parte autonómica (0542)
53 | 576 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2016 - Intereses demora - Parte autonómica (0543)
54 | 589 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2016 - Importe - Parte autonómica (0544)
55 | 602 | 1 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2016 - Regularización motivada por  DA 45 [0545] "1" o "0"
56 | 603 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2016 - Intereses demora - Parte autonómica (0546)
57 | 616 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida estatal incrementada - Parte estatal (0550)
58 | 629 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida autonómica incrementada - Parte autonómica (0551)
59 | 642 | 600 | An | RESERVADO PARA LA A.E.A.T
60 | 1242 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10016000>
Total: |  | 1253

# 100-17

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "17000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N |  | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota líquida incrementada total (0552)
7 | 26 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Deducciones: Por doble imposición internacional, rentas obtenidas y gravadas en el extranjero (0553)
8 | 39 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Deducciones: Por doble imposición internacional supuestos aplicación régimen transparencia fiscal internacional (0554)
9 | 52 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Deducciones: Por doble imposición supuestos aplicación régimen imputación rentas cesión derechos imagen (0555)
10 | 65 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Retenciones deducibles rendimientos bonificados - Importe retenciones no practicadas (0556)
11 | 78 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Cuota resultante autoliquidación (0557)
12 | 91 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Rendimientos del trabajo (0558]
13 | 104 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Rendimientos del capital mobiliario (0559)
14 | 117 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Arrendamientos de inmuebles urbanos (0560)
15 | 130 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Rendimientos de actividades económicas (0561)
16 | 143 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Atribuidos por entidades en régimen de atribución de rentas (0562)
17 | 156 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Imputados por agrupaciones de interés económico y UTE's (0563)
18 | 169 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Ingresos a cuenta art. 92.8 Ley del Impuesto (0564)
19 | 182 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Ganancias patrimoniales, incluidos premios (0565)
20 | 195 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Pagos fraccionados (actividades económicas) (0566)
21 | 208 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Cuotas del Impuesto sobre la Renta de no Residentes (0567)
22 | 221 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Retenciones art. 11  Directiva 2003/48/CE (0568)
23 | 234 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Total pagos a cuenta (0569)
24 | 247 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Cuota diferencial (0570)
25 | 260 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción por maternidad - Importe deducción (0571)
26 | 273 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción por maternidad - Importe abono anticipado deducción (0572)
27 | 286 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF descendiente (0573)
28 | 295 | 15 | A | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Nombre (0574)
29 | 310 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (0575)
30 | 318 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (0576)
31 | 326 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Nº personas derecho mínimo (0577)
32 | 328 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Se ha cedido el derecho deducción (0578) |  | "0" - blanco, "1" - Si,    "2" .- No
33 | 329 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF cedente (0579)
34 | 338 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Se ha cedido el derecho deducción (0580) |  | "0" - blanco, "1" - Si,    "2" .- No
35 | 339 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF beneficiario (0581)
36 | 348 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Importe deducción (0582)
37 | 361 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Importe abono anticipado deducción (0583)
38 | 374 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF ascendiente (0584)
39 | 383 | 15 | A | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Nombre (0585)
40 | 398 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (0586)
41 | 406 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (0587)
42 | 414 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Nº personas derecho mínimo (0588)
43 | 416 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Se ha cedido el derecho deducción (0589) |  | "0" - blanco, "1" - Si,    "2" .- No
44 | 417 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad  - NIF cedente 1 (0590)
45 | 426 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF cedente 2 (0591)
46 | 435 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF cedente 3 (0592)
47 | 444 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Se ha cedido el derecho deducción (0593) |  | "0" - blanco, "1" - Si,    "2" .- No
48 | 445 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF beneficiario (0594)
49 | 454 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Importe deducción (0595)
50 | 467 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Importe abono anticipado deducción (0596)
51 | 480 | 30 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Nº identificación título familia numerosa (0597)
52 | 510 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Categoría familia numerosa - General (0598)
53 | 511 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Categoría familia numerosa - Especial (0599)
54 | 512 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Fecha inicio título familia numerosa (DDMMAAAA) (0600)
55 | 520 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Fecha finalización título familia numerosa (DDMMAAAA) (0601)
56 | 528 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Nº ascendientes forman parte familia numerosa  (0602)
57 | 530 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Se ha cedido el derecho deducción (0603) |  | "0" - blanco, "1" - Si,    "2" .- No
58 | 531 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 1 (0604)
59 | 540 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 2 (0605)
60 | 549 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 3 (0606)
61 | 558 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Se ha cedido el derecho deducción (0607) |  | "0" - blanco, "1" - Si,    "2" .- No
62 | 559 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF beneficiario (0608)
63 | 568 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Importe deducción (0609)
64 | 581 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Importe abono anticipado deducción (0610)
65 | 594 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes, separado o sin vinculo matrimonial, dos hijos sin derecho anualidades alimentos - Importe deducción (0611)
66 | 607 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes, separado o sin vinculo matrimonial, dos hijos sin derecho anualidades alimentos - Importe abono anticipado deducción (0612)
67 | 620 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Regularizaciones - Importe cobro anticipado descendientes sin derecho mínimo por descendientes (0613)
68 | 633 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Regularizaciones - NIF descendientes deducción se regulariza (0614)
69 | 642 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Regularizaciones - Importe cobro anticipado ascendientes sin derecho mínimo por ascendientes (0615)
70 | 655 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Regularizaciones - NIF ascendientes deducción se regulariza (0616)
71 | 664 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Resultado declaración (0620)
72 | 677 | 600 | An |  | RESERVADO PARA LA A.E.A.T
73 | 1277 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10017000>
Total: |  | 1288

# 100-18

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "18000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (N) Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2017 - Cuota líquida autonómica incrementada (0621)
7 | 26 | 13 | N | Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2017 -  50% deducciones doble imposición (0622)
8 | 39 | 13 | N | Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2017 - Importe IRPF Cdad Autónoma residencia contribuyente (0625)
9 | 52 | 13 | N | (O) Regularización - Mediante declaración complemetaria (ejercicio 2017) - Resultados a ingresar anteriores autoliquidaciones o liquidaciones administrativas (0626)
10 | 65 | 13 | N | Regularización - Mediante declaración complemetaria (ejercicio 2017) - Devoluciones acordadas Agencia Tributaria, tramitación anteriores autoliquidaciones  (0627)
11 | 78 | 13 | N | Regularización -Mediante declaración complemetaria (ejercicio 2017) - Resultado declaración complementaria (0630)
12 | 91 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Resultados a ingresar de autoliquidaciones o liquidaciones administrativas [0631]
13 | 104 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Devoluciones solicitadas a la Agencia Tributaria,  tramitación anteriores autoliquidaciones [0632]
14 | 117 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Resultado de la solicitud de rectificación de autoliquidación [0635]
15 | 130 | 13 | Num | Regularización - Mediante rectificación de autoliquidación - Número de justificante de la autoliquidación cuya rectificación se solicita [0636]
16 | 143 | 34 | An | Número de cuenta IBAN (0637)
17 | 177 | 13 | N | P) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (0643)
18 | 190 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (0645)
19 | 203 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (0644)
20 | 216 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (0645)
21 | 229 | 34 | An | Número de cuenta IBAN (0646)
22 | 263 | 11 | An | Devolución - Código SWIFT-BIC Rectificación (638)
23 | 274 | 11 | An | Devolución - Código SWIFT-BIC Compensación entre cónyuges (640)
24 | 285 | 578 | An | RESERVADO PARA LA A.E.A.T
25 | 863 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10018000>
Total: |  | 874

# Anexo A.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "19000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Inversión con derecho a deducción (A)
7 | 26 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte estatal (0647)
8 | 39 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte autonómica (0648)
9 | 52 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Inversión con derecho a deducción (B)
10 | 65 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte estatal (0649)
11 | 78 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte autonómica (0650)
12 | 91 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Inversión con derecho a deducción (C )
13 | 104 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte estatal (0651)
14 | 117 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte autonómica (0652)
15 | 130 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Cantidades satisfechas con derecho a deducción (E)
16 | 143 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte estatal (0653)
17 | 156 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte autonómica (0654)
18 | 169 | 13 | N | Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte estatal (0516)
19 | 182 | 13 | N | Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte autonómica (0517)
20 | 195 | 13 | N | Deducción por inversión en vivienda habitual - Datos adicionales - Importe de los pagos realizados en el ejercicio al promotor o constructor (0655)
21 | 208 | 9 | An | Deducción por inversión en vivienda habitual - Datos adicionales - NIF del promotor o constructor (0656)
22 | 217 | 8 | Num | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Fecha adquisición vivienda (DDMMAAAA) (0657)
23 | 225 | 20 | An | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Número de identificación del préstamo hipotecario (0658)
24 | 245 | 5 | Num | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Porcentaje del préstamo destinado a adquisición (3 enteros y 2 decimales)  (0659)
25 | 250 | 9 | An | Deducción inversiones en empresas de nueva o reciente creación - Entidad 1 - NIF (0660)
26 | 259 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Entidad 1 - Importe con derecho a deducción  (0661)
27 | 272 | 9 | An | Deducción inversiones en empresas de nueva o reciente creación - Entidad 2 - NIF (0662)
28 | 281 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Entidad 2 - Importe con derecho a deducción  (0663)
29 | 294 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Importe total deducción inversiones empresa nueva o reciente creación - Base deducción (D)
30 | 307 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Importe total deducciones empresa nueva o reciente creación - Importe deducción (0518)
31 | 320 | 20 | An | Deducción por alquiler de la vivienda habitual - NIF del arrendador 1 (0664)
32 | 340 | 1 | Num | Deducción por alquiler de la vivienda habitual - Si ha consignado NIF de otro país [0665] "1" o ·"0"
33 | 341 | 20 | An | Deducción por alquiler de la vivienda habitual - NIF del arrendador 2 (0666)
34 | 361 | 1 | Num | Deducción por alquiler de la vivienda habitual - Si ha consignado NIF de otro país [0667] 1" o ·"0"
35 | 362 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 1 (0668)
36 | 375 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 2 (0669)
37 | 388 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades satisfechas con derecho a deducción (F)
38 | 401 | 13 | N | Deducción por alquiler de la vivienda habitual - Importe deducción (0670)
39 | 414 | 13 | N | Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte estatal (0531)
40 | 427 | 13 | N | Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte autonómica (0532]
41 | 440 | 600 | An | RESERVADO PARA LA A.E.A.T
42 | 1040 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10019000>
Total: |  | 1051

# Anexo A.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "20000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones por donativos - Aportaciones actividades mecenazgo límite 15 % base liquidable - Importe con derecho a deducción (G)
7 | 26 | 13 | N | Deducciones por donativos - Aportaciones actividades mecenazgo límite 15 % base liquidable - Importe de la deducción (0671)
8 | 39 | 13 | N | Deducciones por donativos - Donativos entidades reguladas Ley 49/2002 - Importe con derecho a deducción (H)
9 | 52 | 13 | N | Deducciones por donativos - Donativos entidades reguladas Ley 49/2002 - Importe de la deducción (0672)
10 | 65 | 13 | N | Deducciones por donativos - Donativos fundaciones y asociaciones utilidad pública Ley 49/2002 - Importe con derecho a deducción (J)
11 | 78 | 13 | N | Deducciones por donativos - Donativos fundaciones y asociaciones utilidad pública Ley 49/2002 - Importe de la deducción (0673)
12 | 91 | 13 | N | Deducciones por donativos - Cuotas afiliación y aportaciones partidos políticos, federaciones, coaliciones o agrupamientos electorales - Importe con derecho a deducción (M)
13 | 104 | 13 | N | Deducciones por donativos - Cuotas afiliación y aportaciones partidos políticos, federaciones, coaliciones o agrupamientos electorales - Importe con derecho a deducción - Importe de la deducción (0674)
14 | 117 | 13 | N | Deducciones por donativos - Deducciones por donativos - Parte estatal (0521)
15 | 130 | 13 | N | Deducciones por donativos - Deducciones por donativos - Parte autonómica (0522)
16 | 143 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe con derecho a deducción (I)
17 | 156 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe de la deducción (0675)
18 | 169 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte estatal (0519)
19 | 182 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte autonómica (0520)
20 | 195 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Importe total de la deducción (0676)
21 | 208 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte estatal (0529)
22 | 221 | 13 | N | Otras deducciones generales de la cuota íntegra - Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte autonómica (0530)
23 | 234 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Importe dotaciones (0677)
24 | 247 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0678)
25 | 260 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2014 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0679)
26 | 273 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Importe dotaciones (0680)
27 | 286 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0681]
28 | 299 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0682)
29 | 312 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Pendiente de materializar (0683)
30 | 325 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Importe dotaciones (0684)
31 | 338 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0685)
32 | 351 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0686)
33 | 364 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Pendiente de materializar (0687)
34 | 377 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Importe dotaciones (0688)
35 | 390 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0689)
36 | 403 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0690)
37 | 416 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Pendiente de materializar (0691)
38 | 429 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Importe de la deducción 2017
39 | 442 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2017 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0692)
40 | 455 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2017 - Inversiones prev. letras C y D 2º. a 6º.) artº. 27.4 (0693)
41 | 468 | 600 | An | RESERVADO PARA LA A.E.A.T
42 | 1068 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10020000>
Total: |  | 1079

# Anexo A.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "21000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Saldo anterior
7 | 26 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Aplicado declaración (0694)
8 | 39 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Pendiente aplicación
9 | 52 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interés público - Saldo anterior
10 | 65 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interés público - Aplicado declaración (0695)
11 | 78 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interes público - Pendiente aplicación
12 | 91 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i  - Deducción
13 | 104 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i - Aplicado declaración (0696)
14 | 117 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i  - Pendiente aplicación
15 | 130 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos  - Deducción
16 | 143 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos - Aplicado declaración (0697)
17 | 156 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos  - Pendiente aplicación
18 | 169 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS - Deducción
19 | 182 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS -  Aplicado declaración (0698)
20 | 195 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS - Pendiente aplicación
21 | 208 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Deducción
22 | 221 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Aplicado declaración (0699)
23 | 234 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Pendiente aplicación
24 | 247 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Deducción
25 | 260 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Aplicado declaración (0700)
26 | 273 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Pendiente aplicación
27 | 286 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Deducción
28 | 299 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Aplicado declaración (0701)
29 | 312 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Barcelona Mobile World Capital" - Pendiente aplicación
30 | 325 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2018" - Deducción
31 | 338 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2018" - Aplicado declaración (0702)
32 | 351 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2018" - Pendiente aplicación
33 | 364 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Deducción
34 | 377 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Aplicado declaración (0703)
35 | 390 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Pendiente aplicación
36 | 403 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Deducción
37 | 416 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Aplicado declaración (0704]
38 | 429 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "IV Centenario muerte Miguel de Cervantes" - Pendiente aplicación
39 | 442 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Deducción
40 | 455 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Aplicado declaración (0705)
41 | 468 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Pendiente aplicación
42 | 481 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Deducción
43 | 494 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Aplicado declaración (0706)
44 | 507 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Jerez, Capital mundial del Motociclismo" - Pendiente aplicación
45 | 520 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Deducción
46 | 533 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Aplicado declaración (0707)
47 | 546 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Pendiente aplicación
48 | 559 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Deducción
49 | 572 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Aplicado declaración  (0708)
50 | 585 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Pendiente aplicación
51 | 598 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Deducción
52 | 611 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Aplicado declaración (0709)
53 | 624 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "60 Aniversario Fundación Escuela Organización Industrial" - Pendiente aplicación
54 | 637 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME) 2017" - Deducción
55 | 650 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME) 2017" - Aplicado declaración (0710)
56 | 663 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Encuentro Mundial en las Estrellas (EME) 2017" - Pendiente aplicación
57 | 676 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Deducción
58 | 689 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Aplicado declaración (0711)
59 | 702 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Pendiente aplicación
60 | 715 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Deducción
61 | 728 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Aplicado declaración (0712)
62 | 741 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Pendiente aplicación
63 | 754 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Deducción
64 | 767 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Aplicado declaración (0713)
65 | 780 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Pendiente aplicación
66 | 793 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Deducción
67 | 806 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Aplicado declaración (0714)
68 | 819 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Pendiente aplicación
69 | 832 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Deducción
70 | 845 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Aplicado declaración (0715)
71 | 858 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Pendiente aplicación
72 | 871 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Deducción
73 | 884 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Aplicado declaración (0716)
74 | 897 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Pendiente aplicación
75 | 910 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XX Aniversario Cuenca Ciudad Patrimonio de la Humanidad- Deducción
76 | 923 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XX Aniversario Cuenca Ciudad Patrimonio de la Humanidad- Aplicado declaración (0717)
77 | 936 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XX Aniversario Cuenca Ciudad Patrimonio de la Humanidad- Pendiente aplicación
78 | 949 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Deducción
79 | 962 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Aplicado declaración (0718)
80 | 975 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Pendiente aplicación
81 | 988 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Deducción
82 | 1001 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Aplicado declaración (0719)
83 | 1014 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Pendiente aplicación
84 | 1027 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Deducción
85 | 1040 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Aplicado declaración (0720)
86 | 1053 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Pendiente aplicación
87 | 1066 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Deducción
88 | 1079 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Aplicado declaración (0721)
89 | 1092 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Pendiente aplicación
90 | 1105 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2017 Año de la retina en España- Deducción
91 | 1118 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2017 Año de la retina en España- Aplicado declaración (0722)
92 | 1131 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 2017 Año de la retina en España- Pendiente aplicación
93 | 1144 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Deducción
94 | 1157 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Aplicado declaración (0723)
95 | 1170 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Pendiente aplicación
96 | 1183 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Deducción
97 | 1196 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Aplicado declaración (0724)
98 | 1209 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Pendiente aplicación
99 | 1222 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 525 Aniversario Descubrimiento América en Palos de la Frontera- Deducción
100 | 1235 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 525 Aniversario Descubrimiento América en Palos de la Frontera- Aplicado declaración (0725)
101 | 1248 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 525 Aniversario Descubrimiento América en Palos de la Frontera- Pendiente aplicación
102 | 1261 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Deducción
103 | 1274 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Aplicado declaración (0726)
104 | 1287 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Pendiente aplicación
105 | 1300 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Deducción
106 | 1313 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Aplicado declaración (0727)
107 | 1326 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Pendiente aplicación
108 | 1339 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Deducción
109 | 1352 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Aplicado declaración (0728)
110 | 1365 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Pendiente aplicación
111 | 1378 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Deducción
112 | 1391 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Aplicado declaración (0729)
113 | 1404 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Pendiente aplicación
114 | 1417 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Deducción
115 | 1430 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Aplicado declaración (0730)
116 | 1443 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Pendiente aplicación
117 | 1456 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 4ª edición de la Barcelona World Race- Deducción
118 | 1469 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 4ª edición de la Barcelona World Race- Aplicado declaración (0731)
119 | 1482 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 4ª edición de la Barcelona World Race- Pendiente aplicación
120 | 1495 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Deducción
121 | 1508 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Aplicado declaración (0732)
122 | 1521 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Pendiente aplicación
123 | 1534 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Deducción
124 | 1547 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Aplicado declaración (0733)
125 | 1560 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Pendiente aplicación
126 | 1573 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Deducción
127 | 1586 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Aplicado declaración (0734)
128 | 1599 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Pendiente aplicación
129 | 1612 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Deducción
130 | 1625 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Aplicado declaración (0735)
131 | 1638 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Pendiente aplicación
132 | 1651 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Deducción
133 | 1664 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Aplicado declaración (0736)
134 | 1677 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Pendiente aplicación
135 | 1690 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Deducción
136 | 1703 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Aplicado declaración (0737)
137 | 1716 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Pendiente aplicación
138 | 1729 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Deducción
139 | 1742 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Aplicado declaración (0738)
140 | 1755 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Pendiente aplicación
141 | 1768 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Deducción
142 | 1781 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Aplicado declaración (0739)
143 | 1794 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Pendiente aplicación
144 | 1807 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Numancia 2017- Deducción
145 | 1820 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Numancia 2017- Aplicado declaración (0740)
146 | 1833 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Numancia 2017- Pendiente aplicación
147 | 1846 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - PHotoEspaña 20 aniversario- Deducción
148 | 1859 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - PHotoEspaña 20 aniversario- Aplicado declaración (0741)
149 | 1872 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - PHotoEspaña 20 aniversario- Pendiente aplicación
150 | 1885 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Deducción
151 | 1898 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Aplicado declaración (0742)
152 | 1911 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Pendiente aplicación
153 | 1924 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXX Aniversario Declaración Toledo Ciudad Patrimonio de la Humanidad- Deducción
154 | 1937 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXX Aniversario Declaración Toledo Ciudad Patrimonio de la Humanidad- Aplicado declaración (0743)
155 | 1950 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXX Aniversario Declaración Toledo Ciudad Patrimonio de la Humanidad- Pendiente aplicación
156 | 1963 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Deducción
157 | 1976 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Aplicado declaración (0744)
158 | 1989 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Pendiente aplicación
159 | 2002 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Lorca, Aula de la Historia- Deducción
160 | 2015 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Lorca, Aula de la Historia- Aplicado declaración (0745)
161 | 2028 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Lorca, Aula de la Historia- Pendiente aplicación
162 | 2041 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Deducción
163 | 2054 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Aplicado declaración (0746)
164 | 2067 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Pendiente aplicación
165 | 2080 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Deducción
166 | 2093 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Aplicado declaración (0747)
167 | 2106 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Pendiente aplicación
168 | 2119 | 600 | An | RESERVADO PARA LA A.E.A.T
169 | 2719 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10021000>
Total: |  | 2730

# Anexo A.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "22000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario Festival Internacional Teatro Clásico de Almagro- Deducción
7 | 26 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario Festival Internacional Teatro Clásico de Almagro- Aplicado declaración (0750)
8 | 39 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario Festival Internacional Teatro Clásico de Almagro- Pendiente aplicación
9 | 52 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario de la Ley de Parques Nacionales 1916- Deducción
10 | 65 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario de la Ley de Parques Nacionales 1916- Aplicado declaración (0751)
11 | 78 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario de la Ley de Parques Nacionales 1916- Pendiente aplicación
12 | 91 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario de la Escuela Diplomática- Deducción
13 | 104 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario de la Escuela Diplomática- Aplicado declaración (0752)
14 | 117 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario de la Escuela Diplomática- Pendiente aplicación
15 | 130 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Teruel 2017. 800 años de los Amantes- Deducción
16 | 143 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Teruel 2017. 800 años de los Amantes- Aplicado declaración (0753)
17 | 156 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Teruel 2017. 800 años de los Amantes- Pendiente aplicación
18 | 169 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Deducción
19 | 182 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Aplicado declaración (0754)
20 | 195 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Pendiente aplicación
21 | 208 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 aniversario de Sitges-Festival Internacional Cine Fantástico Catalunya- Deducción
22 | 221 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 aniversario de Sitges-Festival Internacional Cine Fantástico Catalunya- Aplicado declaración (0755)
23 | 234 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 aniversario de Sitges-Festival Internacional Cine Fantástico Catalunya- Pendiente aplicación
24 | 247 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Beneficios fiscales aplicables 50 aniversario Universidad Autónoma Madrid- Deducción
25 | 260 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Beneficios fiscales aplicables 50 aniversario Universidad Autónoma Madrid- Aplicado declaración (0756)
26 | 273 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Beneficios fiscales aplicables 50 aniversario Universidad Autónoma Madrid- Pendiente aplicación
27 | 286 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Hernandiano 2017- Deducción
28 | 299 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Hernandiano 2017- Aplicado declaración (0757)
29 | 312 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Hernandiano 2017- Pendiente aplicación
30 | 325 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Deducción
31 | 338 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Aplicado declaración (0758)
32 | 351 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Pendiente aplicación
33 | 364 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. Económicas 2016 (0759)
34 | 377 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (0760)
35 | 390 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (0761)
36 | 403 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. Económicas 2017 (0762)
37 | 416 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (0763)
38 | 429 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (0764)
39 | 442 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Deducción por inversión elementos nuevos  (0765)
40 | 455 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Saldo anterior
41 | 468 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Aplicado declaración (0766)
42 | 481 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Pendiente aplicación
43 | 494 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Saldo anterior
44 | 507 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Aplicado declaración (0767)
45 | 520 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Pendiente aplicación
46 | 533 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS - Deducción
47 | 546 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS - Aplicado declaración (0768)
48 | 559 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS- Pendiente aplicación
49 | 572 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Deducción
50 | 585 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS (0769)
51 | 598 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Pendiente aplicación
52 | 611 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Deducción
53 | 624 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Aplicado declaración (0770)
54 | 637 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad,  artº. 38 LIS - Pendiente de aplicación
55 | 650 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994  - Deducción
56 | 663 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994 - Aplicado declaración (0771)
57 | 676 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental y gastos propaganda, artº.27 bis Ley 19/1994  - Pendiente aplicación
58 | 689 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Deducción
59 | 702 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Aplicado declaración (0772)
60 | 715 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Pendiente aplicación
61 | 728 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Importe total de las deducciones (0773)
62 | 741 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Deducciones - Parte estatal (0523)
63 | 754 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Deducciones - Parte autonómica (0524]
64 | 767 | 600 | An | RESERVADO PARA LA A.E.A.T
65 | 1367 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10022000>
Total: |  | 1378

# Anexo B.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "23000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios de ayudas familiares (0774)
7 | 26 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios ayudas viviendas protegidas (0775)
8 | 39 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión vivienda habitual protegida/personas jóvenes (0776)
9 | 52 | 13 | N | Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler de vivienda habitual (0777)
10 | 65 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión en la adquisición de acciones y participaciones  (0778)
11 | 78 | 13 | N | Deducciones Autonómicas - Andalucía - Por adopción de hijos ámbito internacional (0779)
12 | 91 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con discapacidad (0780)
13 | 104 | 13 | N | Deducciones Autonómicas - Andalucía - Para padre/madre de familia monoparental con ascendientes mayores 75 años (0781)
14 | 117 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Deducción con carácter general  (0782)
15 | 130 | 11 | An | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Cuenta cotización (0783)
16 | 141 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Importe (0784)
17 | 154 | 11 | An | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Cuenta cotización (0785)
18 | 165 | 13 | N | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Importe (0786)
19 | 178 | 13 | N | Deducciones Autonómicas - Andalucía - Para trabajadores por gastos de defensa jurídica de la relación laboral (0787)
20 | 191 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con cónyuges o parejas de hecho con discapacidad (0788)
21 | 204 | 13 | N | Deducciones Autonómicas - Andalucía - Otras deducciones (0789)
22 | 217 | 13 | N | Deducciones Autonómicas - Andalucía - Total deducciones autonómicas (0534)
23 | 230 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del tercer hijo o sucesivos (0790)
24 | 243 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción de un hijo en atención al grado discapacidad (0791)
25 | 256 | 13 | N | Deducciones Autonómicas - Aragón - Por adopción internacional de niños (0792)
26 | 269 | 13 | N | Deducciones Autonómicas - Aragón - Por el cuidado de personas dependientes (0793)
27 | 282 | 13 | N | Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico (0794)
28 | 295 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo  (0795)
29 | 308 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en acciones de entidades que cotizan en Mercado Alternativo Bursátil (0796)
30 | 321 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en la adquisición de acciones o participaciones sociales (0797)
31 | 334 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición o rehabilitación de vivienda habitual en núcleos rurales o análogos (0798)
32 | 347 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición libros de texto y material escolar (0799)
33 | 360 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual vinculado operaciones dación en pago. Importe  (0800)
34 | 373 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda social (deducción arrendador) (0801)
35 | 386 | 13 | N | Deducciones Autonómicas - Aragón - Para mayores de 70 años (0802)
36 | 399 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en entidades de la economía social (0803)
37 | 412 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del primer y/o segundo hijo en poblaciones de menos de 10.000 habitantes (0804)
38 | 425 | 13 | N | Deducciones Autonómicas - Aragón - Por gastos de guardería de hijos menores de 3 años (0805)
39 | 438 | 13 | N | Deducciones Autonómicas - Aragón -  Otras deducciones (0806)
40 | 451 | 13 | N | Deducciones Autonómicas - Aragón - Total deducciones autonómicas (0534)
41 | 464 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (0807)
42 | 477 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes con discapacidad (0808)
43 | 490 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes con discapacidad (0809)
44 | 503 | 13 | N | Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (0810)
45 | 516 | 13 | N | Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual  (0811)
46 | 529 | 13 | N | Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (0812)
47 | 542 | 13 | N | Deducciones Autonómicas - Asturias - Por adopción internacional de menores (0813)
48 | 555 | 13 | N | Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones constituidas en la misma fecha  (0814)
49 | 568 | 13 | N | Deducciones Autonómicas - Asturias - Para familias numerosas (0815)
50 | 581 | 13 | N | Deducciones Autonómicas - Asturias - Para familias monoparentales (0816)
51 | 594 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (0817)
52 | 607 | 13 | N | Deducciones Autonómicas - Asturias - Por certificación de gestión forestal sostenible (0818)
53 | 620 | 13 | N | Deducciones Autonómicas - Asturias - Por gastos de descendientes en centros de 0 a 3 años (0819)
54 | 633 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición de libros de texto y material escolar (0820)
55 | 646 | 13 | N | Deducciones Autonómicas - Asturias -  Otras deducciones (0821)
56 | 659 | 13 | N | Deducciones Autonómicas - Asturias - Total deducciones autonómicas (0534)
57 | 672 | 600 | An | RESERVADO PARA LA A.E.A.T
58 | 1272 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10023000>
Total: |  | 1283

# Anexo B.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "24000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Illes Balears - Por determinadas inversiones de mejora de sostenibilidad vivienda habitual (0822)
7 | 26 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos adquisición libros de texto (0823)
8 | 39 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos de aprendizaje extraescolar de idiomas extranjeros (0824)
9 | 52 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones entidades destinadas investigación, desarrollo científico o tecnológico o innovación  (0825)
10 | 65 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones, cesiones uso o contratos comodato y convenios colaboración empresarial  (0826)
11 | 78 | 13 | N | Deducciones Autonómicas - Illes Balears - Por inversión en la adquisición de acciones o participaciones sociales de nuevas entidades (0827)
12 | 91 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones, cesiones uso o contrato de comodato y convenios colaboración, mecenazgo deportivo (0828)
13 | 104 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones a determinadas entidades fomento lengua catalana (0829)
14 | 117 | 13 | N | Deducciones Autonómicas - Illes Balears - Para declarentes con discapacidad física, psiquica o sensorial o con descendientes con esta condición  (0830]
15 | 130 | 13 | N | Deducciones Autonómicas - Illes Balears - Por arrendamiento de vivienda habitual a favor de determinados colectivos [0831]
16 | 143 | 13 | N | Deducciones Autonómicas - Illes Balears - Para cursar estudios de educación superior fuera de la isla de residencia habitual  (0832)
17 | 156 | 13 | N | Deducciones Autonómicas - Illes Balears - Por arrendamiento de bienes inmuebles Illes Balears destinados a vivienda (0833)
18 | 169 | 13 | N | Deducciones Autonómicas - Illes Balears - Por arrendamiento vivienda en Illes Balears traslado de residencia por motivos laborales (0834)
19 | 182 | 20 | An | Deducciones Autonómicas - Illes Balears - Nif Arrendador (1019)
20 | 202 | 1 | Num | Deducciones Autonómicas - Illes Balears - Marque si ha consignado NIF de otro país.  "1 o cero" (1020)
21 | 203 | 13 | N | Deducciones Autonómicas - Illes Balears -  Otras deducciones (0835)
22 | 216 | 13 | N | Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (0534)
23 | 229 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones con finalidad ecológica (0836)
24 | 242 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones rehabilitación o conservación patrimonio histórico de Canarias (0837)
25 | 255 | 13 | N | Deducciones Autonómicas - Canarias - Por cantidades destinadas restauración/rehabilitación/reparación bienes inmuebles declarados de Interés Cultural (0838)
26 | 268 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de estudios (0839)
27 | 281 | 13 | N | Deducciones Autonómicas - Canarias - Por trasladar residencia a otra isla para realizar actividad laboral cuenta ajena/actividad económica (0840)
28 | 294 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones en metálico a descendientes menores 35 años para adquisición/rehabilitación primera vivienda habitual (0841)
29 | 307 | 13 | N | Deducciones Autonómicas - Canarias - Por nacimiento o adopción de hijos (0842)
30 | 320 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes con discapacidad y mayores de 65 años (0843)
31 | 333 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de guardería (0844)
32 | 346 | 13 | N | Deducciones Autonómicas - Canarias - Por familia numerosa (0845)
33 | 359 | 13 | N | Deducciones Autonómicas - Canarias - Por inversión en vivienda habitual (0846)
34 | 372 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de adecuación vivienda habitual por razón discapacidad (0847)
35 | 385 | 13 | N | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Importe (0848)
36 | 398 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral 1 (0849)
37 | 418 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral 1. "1 o cero" (0850)
38 | 419 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral 2 (0851)
39 | 439 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral 2. "1 o cero" (0852)
40 | 440 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes desempleados (0853)
41 | 453 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones y aportaciones fines culturales, deportivos, investigación o docencia (0854)
42 | 466 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones a entidades sin ánimo de lucro y con finalidad ecológica (0855)
43 | 479 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de estudios en educación infantil, primaria, secundaria obligatoria…. (0856)
44 | 492 | 13 | N | Deducciones Autonómicas - Canarias - Por acogimiento de menores (0857)
45 | 505 | 13 | N | Deducciones Autonómicas - Canarias - Por familias monoparentales (0858)
46 | 518 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de rehabilitación energética y reforma de la vivienda habitual (0859)
47 | 531 | 13 | N | Deducciones Autonómicas - Canarias - Por gasto de enfermedad (0860)
48 | 544 | 13 | N | Deducciones Autonómicas - Canarias - Por familiares dependientes con discapacidad (0861)
49 | 557 | 13 | N | Deducciones Autonómicas - Canarias - Otras deducciones (0862)
50 | 570 | 13 | N | Deducciones Autonómicas - Canarias - Total deducciones autonómicas (0534)
51 | 583 | 13 | N | Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con  discapacidad - Importe (0863)
52 | 596 | 13 | N | Deducciones Autonómicas - Cantabria - Por cuidado de familiares (0864)
53 | 609 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora. Importe 2015 y/o 2016 pendiente de aplicación (0865)
54 | 622 | 9 | An | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - NIF persona/entidad  obras (0866)
55 | 631 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - Importe deducción (0867)
56 | 644 | 13 | N | Deducciones Autonómicas - Cantabria - Por donativos a fundaciones o al Fondo Cantabria Coopera (0868)
57 | 657 | 13 | N | Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (0869)
58 | 670 | 13 | N | Deducciones Autonómicas - Cantabria - Por inversión adquisición acciones/participaciones sociales nuevas entidades o reciente creación (0870)
59 | 683 | 13 | N | Deducciones Autonómicas - Cantabria - Por gastos de enfermedad (0871)
60 | 696 | 13 | N | Deducciones Autonómicas - Cantabria - Otras deducciones (0872)
61 | 709 | 13 | N | Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (0534)
62 | 722 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora generadas en 2017 a deducir en los 2 años siguientes [0873]
63 | 735 | 600 | An | RESERVADO PARA LA A.E.A.T
64 | 1335 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10024000>
Total: |  | 1346

# Anexo B.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "25000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (0874)
7 | 26 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (0875)
8 | 39 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (0876)
9 | 52 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (0877)
10 | 65 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (0878)
11 | 78 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por cantidades para la Cooperación Internacional, lucha contra pobreza y exclusión social  (0879)
12 | 91 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por familia numerosa (0880)
13 | 104 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por donaciones con finalidad en investigación y desarrollo e innovación empresarial (0881)
14 | 117 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por gastos en la adquisición de libros de texto y enseñanza de idiomas (0882)
15 | 130 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento familiar no rumunerado de menores (0883)
16 | 143 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento no remunerado de mayores de 65 años y/o discapacitados (0884)
17 | 156 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha -  Por arrendamiento de vivienda habitual por menores de 36 años  (0885)
18 | 169 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Otras deducciones (0886)
19 | 182 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (0534)
20 | 195 | 13 | N | Deducciones Autonómicas - Castilla y León - Para contribuyentes afectados por discapacidad (0887)
21 | 208 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales  (0888)
22 | 221 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cantidades donadas a fundaciones (0889)
23 | 234 | 13 | N | Deducciones Autonómicas - Castilla y León - Poro cantidades donadas para el fomento de la investigación, desarrollo e innovación (0890)
24 | 247 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cantidades invertidas en la recuperación del patrimonio histórico, cultural y natural  (0891)
25 | 260 | 13 | N | Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años  (0892)
26 | 273 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión instalaciones medioambientales/adaptación a personas con discapacidad en vvda.habitual (0893)
27 | 286 | 8 | Num | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Fecha visado proyecto (0894)
28 | 294 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Importe  (0895)
29 | 307 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducción para el fomento de emprendimiento (0896)
30 | 320 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión en rehabilitación de viviendas destinadas a alquiler en núcleos rurales  (0897)
31 | 333 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2014 pdte. aplicación (0898)
32 | 346 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2015 pdte. aplicación (0899)
33 | 359 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2016 pdte. aplicación (0900)
34 | 372 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe aplicado en el ejercicio (0901)
35 | 385 | 13 | N | Deducciones Autonómicas - Castilla y León - Por familia numerosa (0902)
36 | 398 | 13 | N | Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (0903)
37 | 411 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas (0904)
38 | 424 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas en 2015  y/o 2016 (0905)
39 | 437 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Nif persona empleada (0906)
40 | 446 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Importe (0907)
41 | 459 | 13 | N | Deducciones Autonómicas - Castilla y León - Por paternidad  (0908)
42 | 472 | 13 | N | Deducciones Autonómicas - Castilla y León - Por gastos de adopción (0909)
43 | 485 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuotas Seg.Social empleados del hogar - Nif persona empleada (0910)
44 | 494 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuotas Seg.Social empleados del hogar - Importe (0911)
45 | 507 | 13 | N | Deducciones Autonómicas - Castilla y León - Importe total aplicado  (0912)
46 | 520 | 13 | N | Deducciones Autonómicas - Castilla y León - Otras deducciones (0913)
47 | 533 | 13 | N | Deducciones Autonómicas - Castilla y León - Total deducciones autonómicas  (0534)
48 | 546 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - Ejercicios siguientes. Importe 2015 pdte. aplicación (0914)
49 | 559 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc -  Ejercicios siguientes. Importe 2016 pdte. aplicación (0915)
50 | 572 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - 2014, 2015 y 2016. Importe 2017 pdte. aplicación  (0916)
51 | 585 | 600 | An | RESERVADO PARA LA A.E.A.T
52 | 1185 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10025000>
Total: |  | 1196

# Anexo B.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "26000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Cataluña - Por nacimiento o adopción de un hijo (0917)
7 | 26 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan el uso lengua catalana (0918)
8 | 39 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan la investigación científica (0919)
9 | 52 | 13 | N | Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual  (0920)
10 | 65 | 13 | N | Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudios universitarios de master y doctorado (0921)
11 | 78 | 13 | N | Deducciones Autonómicas - Cataluña - Para los contribuyentes que queden viudos (0922)
12 | 91 | 13 | N | Deducciones Autonómicas - Cataluña - Por rehabilitación vivienda habitual (0923)
13 | 104 | 13 | N | Deducciones Autonómicas - Cataluña - Por donaciones entidades en beneficio del medio ambiente (0924)
14 | 117 | 13 | N | Deducciones Autonómicas - Cataluña - Por inversión por ángel inversor y por adquisición de acciones entidades nuevas o de creación reciente (0925)
15 | 130 | 13 | N | Deducciones Autonómicas - Cataluña - Otras deducciones (0926)
16 | 143 | 13 | N | Deducciones Autonómicas - Cataluña - Total deducciones autonómicas (0534)
17 | 156 | 13 | N | Deducciones Autonómicas - Extremadura - Por adquisición o rehabilitación vivienda habitual para jóvenes y víctimas del terrorismo (0927)
18 | 169 | 13 | N | Deducciones Autonómicas - Extremadura - Por trabajo dependiente (0928)
19 | 182 | 13 | N | Deducciones Autonómicas - Extremadura - Por cuidado de familiares con discapacidad (0929)
20 | 195 | 13 | N | Deducciones Autonómicas - Extremadura - Por acogimiento de menores (0930)
21 | 208 | 13 | N | Deducciones Autonómicas - Extremadura - Por  partos múltiples (0931)
22 | 221 | 13 | N | Deducciones Autonómicas - Extremadura - Por compra de material escolar (0932)
23 | 234 | 13 | N | Deducciones Autonómicas - Extremadura - Por inversión en la adquisición de acciones o participaciones sociales (0933)
24 | 247 | 13 | N | Deducciones Autonómicas - Extremadura - Por gastos de guardería para hijos menores de 4 años (0934)
25 | 260 | 13 | N | Deducciones Autonómicas - Extremadura - Para contribuyentes viudos (0935)
26 | 273 | 13 | N | Deducciones Autonómicas - Extremadura - Por arrendamiento vivienda habitual (0936)
27 | 286 | 13 | N | Deducciones Autonómicas - Extremadura -  Otras deducciones (0937)
28 | 299 | 13 | N | Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (0534)
29 | 312 | 13 | N | Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (0938)
30 | 325 | 13 | N | Deducciones Autonómicas - Galicia - Por familia numerosa (0939)
31 | 338 | 13 | N | Deducciones Autonómicas - Galicia - Por cuidado hijos menores (0940)
32 | 351 | 13 | N | Deducciones Autonómicas - Galicia - Por contribuyentes con discapacidad = > 65 años que precisan ayuda de terceras personas (0941)
33 | 364 | 13 | N | Deducciones Autonómicas - Galicia - Por gastos uso nuevas tecnologías en hogares gallegos (0942)
34 | 377 | 13 | N | Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual  por contribuyentes de edad igual o inferior a 35 años (0943)
35 | 390 | 13 | N | Deducciones Autonómicas - Galicia - Por acogimiento familiar de menores (0944)
36 | 403 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación (0945)
37 | 416 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación y su financiación (0946)
38 | 429 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones de entidades empresas en expansión Mercado Alternativo Bolsista (0947)
39 | 442 | 13 | N | Deducciones Autonómicas - Galicia - Por donaciones finalidad en investigacion y desarrollo científico e innovación tecnológica (0948)
40 | 455 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables (0949)
41 | 468 | 20 | An | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables - Código de instalación (0950)
42 | 488 | 13 | N | Deducciones Autonómicas - Galicia - Otras deducciones (0951)
43 | 501 | 13 | N | Deducciones Autonómicas - Galicia - Total deducciones autonómicas (0534)
44 | 514 | 13 | N | Deducciones Autonómicas - Madrid - Por nacimiento o adopción de hijos (0952)
45 | 527 | 13 | N | Deducciones Autonómicas - Madrid - Por adopción internacional de niños (0953)
46 | 540 | 13 | N | Deducciones Autonómicas - Madrid - Por acogimiento familiar de menores (0954)
47 | 553 | 13 | N | Deducciones Autonómicas - Madrid - Por acogimiento no remunerado de mayores 65 años y/o con discapacidad (0955)
48 | 566 | 13 | N | Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual por menores de 35 años (0956)
49 | 579 | 13 | N | Deducciones Autonómicas - Madrid - Por gastos educativos (0957)
50 | 592 | 13 | N | Deducciones Autonómicas - Madrid - Para familias con dos o más descendientes e ingresos reducidos (0958)
51 | 605 | 13 | N | Deducciones Autonómicas - Madrid - Por inversión en adquisición de acciones y participaciones sociales de nuevas entidades o de reciente creación (0959)
52 | 618 | 13 | N | Deducciones Autonómicas - Madrid -  Para el fomento del autoempleo de jóvenes menores de 35 años (0960)
53 | 631 | 13 | N | Deducciones Autonómicas - Madrid - Por inversiones en entidades cotizadas en el Mercado Alternativo Bursátil (0961)
54 | 644 | 13 | N | Deducciones Autonómicas - Madrid - Otras deducciones (0962)
55 | 657 | 13 | N | Deducciones Autonómicas - Madrid - Total deducciones autonómicas (0534)
56 | 670 | 600 | An | RESERVADO PARA LA A.E.A.T
57 | 1270 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10026000>
Total: |  | 1281

# Anexo B.5

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "27000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión vivienda habitual jóvenes edad igual/inferior 35 años (incluido rég. transitorio) (0963)
7 | 26 | 13 | N | Deducciones Autonómicas - Murcia - Por donativos para la protección del patrimonio cultural  (0964)
8 | 39 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de guardería para hijos menores de 3 años (0965)
9 | 52 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (0966)
10 | 65 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (0967)
11 | 78 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en la adquisición de acciones y participaciones sociales de nuevas entidades (0968)
12 | 91 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en entidades cotizadas Mercado Alternativo Bursátil (0969)
13 | 104 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de material escolar y libros de texto (0970)
14 | 117 | 13 | N | Deducciones Autonómicas - Murcia - Otras deducciones (0971)
15 | 130 | 13 | N | Deducciones Autonómicas - Murcia - Total deducciones autonómicas (0534)
16 | 143 | 13 | N | Deducciones Autonómicas - La Rioja - Por nacimiento y adopción de hijos (0972)
17 | 156 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas rehabilitación vivienda habitual (0973)
18 | 169 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas adquisición o contrucción vivienda habitual para jóvenes (0974)
19 | 182 | 4 | Num | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Código municipio (0975)
20 | 186 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Importe  (0976)
21 | 199 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas en obras de adecuación de vivienda habitual para personas con discapacidad (0977)
22 | 212 | 4 | Num | Deducciones Autonómicas - La Rioja - Por adquisición, construcción y rehabilitación vivienda habitual pequeños municipios. Código municipio (0978)
23 | 216 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición, construcción y rehabilitación vivienda habitual pequeños municipios. Importe (0979)
24 | 229 | 13 | N | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado. Importe (0980)
25 | 242 | 9 | An | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado.NIF (0981)
26 | 251 | 4 | Num | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado.Código municipio (0982)
27 | 255 | 13 | N | Deducciones Autonómicas - La Rioja - Por acogimiento de menores (0983)
28 | 268 | 13 | N | Deducciones Autonómicas - La Rioja - Otras deducciones (0984)
29 | 281 | 13 | N | Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (0534)
30 | 294 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento, adopción o acogimiento familiar (0985)
31 | 307 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento o adopción múltiples (0986)
32 | 320 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento o adopción hijos con discapacidad (0987)
33 | 333 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por familia numerosa o monoparental (0988)
34 | 346 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades custodia en guarderías y primer ciclo educación infantil hijos menores de 3 años (0989)
35 | 359 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por conciliación del trabajo con la vida familiar (0990)
36 | 372 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Para contribuyentes con un grado de discapacidad igual o superior al 33 por 100, de edad igual o superior a 65 años (0991)
37 | 385 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por ascendientes > 75 años ó > 65 años que sean personas con discapacidad (0992)
38 | 398 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por realización por uno de los cónyuges de labores no remuneradas en el hogar (0993)
39 | 411 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por primera adquisición vivienda habitual por contribuyentes edad igual o inferior 35 años (0994)
40 | 424 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición vivienda habitual por personas con discapacidad (0995)
41 | 437 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades adquisición o rehabilitación vivienda habitual, procedentes ayudas públicas (0996)
42 | 450 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de la vivienda habitual (0997)
43 | 463 | 20 | An | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - NIF arrendador (0998)
44 | 483 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Importe (0999)
45 | 496 | 1 | Num | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Si ha consignado NIF de otro país (1000) "1 o cero"
46 | 497 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones con finalidad ecológica (1001)
47 | 510 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (1002)
48 | 523 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades donadas para la conservación, reparación y restauración de bienes (1003)
49 | 536 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades destinadas a la conservación, reparación y restauración de bienes (1004)
50 | 549 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por donaciones al fomento de la Lengua Valenciana (1005)
51 | 562 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por contribuyentes con dos o más descendientes (1006)
52 | 575 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (1007)
53 | 588 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición material escolar (1008)
54 | 601 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual  - NIF persona o entidad (1009)
55 | 610 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual - Importe  (1010)
56 | 623 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual realizadas en el periodo - NIF persona o entidad (1011)
57 | 632 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual realizadas en el periodo - Importe  (1012)
58 | 645 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones importes dinerarios a otros fines culturales (1013)
59 | 658 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades destinadas a abonos culturales (1014)
60 | 671 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. Importe (1015)
61 | 684 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. Cantidades satisfechas 2017 (1016)
62 | 697 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. Importe pendiente aplicación (1017)
63 | 710 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Otras deducciones (1018)
64 | 723 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Total deduciones autonómicas (0534)
65 | 736 | 600 | An | RESERVADO PARA LA A.E.A.T
66 | 1336 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10027000>
Total: |  | 1347

# Anexo B.6

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "28000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 20 | An | Información adicional deducción autonómica por arrendamiento - NIF/NIE arrendador - 1 (1021)
7 | 33 | 1 | Num | Información adicional deducción autonómica por arrendamiento - Si ha consignado NIF de otro país - 1 - "1 o cero"  (1022)
8 | 34 | 13 | N | Información adicional deducción autonómica por arrendamiento - Cantidades satisfechas - 1  (1023)
9 | 47 | 20 | An | Información adicional deducción autonómica por arrendamiento - NIF/NIE arrendador - 2 (1024)
10 | 67 | 1 | Num | Información adicional deducción autonómica por arrendamiento - Si ha consignado NIF de otro país - 2 - "1 o cero"  (1025)
11 | 68 | 13 | N | Información adicional deducción autonómica por arrendamiento - Cantidades satisfechas - 2  (1026)
12 | 81 | 13 | N | Información adicional deducción autonómica por arrendamiento - Importe total satisfecho (1027)
13 | 94 | 13 | N | Información adicional deducción autonómica por arrendamiento - Cantidades satisfechas con derecho a deducción  (1028)
14 | 107 | 13 | N | Información adicional deducción autonómica por arrendamiento - Importe deducción autonómica por arrendamiento  (1029)
15 | 120 | 9 | An | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Nif entidad - 1 (1030)
16 | 129 | 13 | N | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Importe - 1 (1031)
17 | 142 | 9 | An | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Nif entidad - 2 (1032)
18 | 151 | 13 | N | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Importe - 1 (1033)
19 | 164 | 13 | N | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Importe total con derecho a deducción (1034)
20 | 177 | 13 | N | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Importe total deducción (1035)
21 | 190 | 9 | An | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Nif entidad - 1 (1036)
22 | 199 | 13 | N | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Importe inversión - 1 (1037)
23 | 212 | 9 | An | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Nif entidad - 2 (1038)
24 | 221 | 13 | N | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Importe inversión - 2 (1039)
25 | 234 | 13 | N | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Importe total con derecho a deducción  (1040)
26 | 247 | 13 | N | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Importe total deducción (1041)
27 | 260 | 9 | An | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Nif entidad - 1 (1042)
28 | 269 | 13 | N | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Importe inversión - 1 (1043)
29 | 282 | 9 | An | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Nif entidad - 2 (1044)
30 | 291 | 13 | N | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Importe inversión - 2 (1045)
31 | 304 | 13 | N | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Importe total con derecho a deducción (1046)
32 | 317 | 13 | N | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Importe total deducción (1047)
33 | 330 | 600 | An | RESERVADO PARA LA A.E.A.T
34 | 930 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10028000>
Total: |  | 941

# Anexo C.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "29000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 3 | Num | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - Número de orden  (1048)
7 | 16 | 1 | Tit | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - Contribuyente  "0" a "9" (1049)
8 | 17 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2013. Pendiente principio periodo  (1050)
9 | 30 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2013. Aplicado en declaración (1051)
10 | 43 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2014. Pendiente principio periodo  (1052)
11 | 56 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2014. Aplicado en declaración  (1053)
12 | 69 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2014. Pdte. aplicación ejercicios futuros  (1054)
13 | 82 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2015. Pendiente principio periodo  (1055)
14 | 95 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2015. Aplicado en declaración (1056)
15 | 108 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2015. Pdte. aplicación ejercicios futuros  (1057)
16 | 121 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Pendiente principio periodo  (1058)
17 | 134 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Aplicado en declaración  (1059)
18 | 147 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Pdte. aplicación ejercicios futuros  (1060)
19 | 160 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2017. Pdte. aplicación ejercicios futuros  (0072)
20 | 173 | 1 | Tit | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Contribuyente "0" a "9" (1061)
21 | 174 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe total obtenido susceptible de reinversión (1062)
22 | 187 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Ganancia patrimonial obtenida (1063)
23 | 200 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe reinvertido hasta 31-12-2017 en adquisición nueva vivienda (1064)
24 | 213 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe que se compromete a reinvertir 2 años siguientes (1065)
25 | 226 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (1066)
26 | 239 | 1 | Tit | C | Exención por reinversión en entidades de nueva o reciente creación - Contribuyente "0" a "9" (1067)
27 | 240 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe total obtenido susceptible de reinversión(1068)
28 | 253 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Ganancia patrimonial obtenida [1069]
29 | 266 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe reinvertido hasta 31-12-2017 [1070]
30 | 279 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe que se compromete a reinvertir en 2018 [1071]
31 | 292 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Ganancia patrimonial exenta por reinversión [1072]
32 | 305 | 1 | Tit | C | Exención por reinversión en rentas vitalicias -  Contribuyente "0" a "9" (1073)
33 | 306 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe total transmisión elementos patrimoniales (1074)
34 | 319 | 13 | N | C | Exención por reinversión en rentas vitalicias - Ganancia patrimonial obtenida (1075)
35 | 332 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe reinvertido hasta 31-12-2017 en rentas vitalicias (1076)
36 | 345 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe que se compromete a reinvertir en 2018 (1077]
37 | 358 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe retención que se compromete a reinvertir en 2018 (1078)
38 | 371 | 13 | N | C | Exención por reinversión en rentas vitalicias - Ganancia patrimonial exenta por reinversión (1079)
39 | 384 | 1 | Tit | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. Contribuyente "0" a "9" (1080)
40 | 385 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2013. Pendiente principio periodo (1081)
41 | 398 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2013. Aplicado en declaración (1082)
42 | 411 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2014. Pendiente principio periodo (1083)
43 | 424 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2014. Aplicado en declaración (1084)
44 | 437 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2014. Pdte. aplicación ejercicios futuros (1085)
45 | 450 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2015. Pendiente principio periodo (1086)
46 | 463 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2015. Aplicado en declaración (1087)
47 | 476 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2015. Pdte. aplicación ejercicios futuros (1088)
48 | 489 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Pendiente principio periodo (1089)
49 | 502 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Aplicado en declaración (1090)
50 | 515 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Pdte. aplicación ejercicios futuros (1091)
51 | 528 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. Saldo negativo pendiente de compensación (1092)
52 | 541 | 1 | Tit | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. Contribuyente "0" a "9" (1093)
53 | 542 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2013. Pendiente principio periodo (1094)
54 | 555 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2013. Aplicado en declaración (1095)
55 | 568 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2014. Pendiente principio periodo (1096)
56 | 581 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2014. Aplicado en declaración (1097)
57 | 594 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2014. Pdte. aplicación ejercicios futuros (1098)
58 | 607 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2015. Pendiente principio periodo (1099)
59 | 620 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2015. Aplicado en declaración (1100)
60 | 633 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2015. Pdte. aplicación ejercicios futuros (1101)
61 | 646 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Pendiente principio periodo (1102)
62 | 659 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Aplicado en declaración (1103)
63 | 672 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Pdte. aplicación ejercicios futuros (1104)
64 | 685 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. Saldo negativo pendiente de compensación (1105)
65 | 698 | 600 | An |  | RESERVADO PARA LA A.E.A.T
66 | 1298 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10029000>
Total: |  | 1309

# Anexo C.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "30000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. Contribuyente "0" a "9" (1106)
7 | 14 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2013. Pendiente principio periodo (1107)
8 | 27 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2013. Aplicado en declaración (1108)
9 | 40 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2014. Pendiente principio periodo (1109)
10 | 53 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2014. Aplicado en declaración (1110)
11 | 66 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2014. Pdte. aplicación ejercicios futuros (1111)
12 | 79 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2015. Pendiente principio periodo (1112)
13 | 92 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2015. Aplicado en declaración (1113)
14 | 105 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2015. Pdte. aplicación ejercicios futuros (1114)
15 | 118 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Pendiente principio periodo (1115)
16 | 131 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Aplicado en declaración (1116)
17 | 144 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Pdte. aplicación ejercicios futuros (1117)
18 | 157 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. Saldo negativo pendiente de compensación (1118)
19 | 170 | 1 | Tit | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir.  Contribuyente "0" a "9" (1119)
20 | 171 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2012. Pendiente principio periodo (1120)
21 | 184 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2012. Aplicado en declaración (1121)
22 | 197 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2013. Pendiente principio periodo (1122)
23 | 210 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2013. Aplicado en declaración (1123)
24 | 223 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2013. Pdte. aplicación ejercicios futuros (1124)
25 | 236 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2014. Pendiente principio periodo (1125)
26 | 249 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2014. Aplicado en declaración (1126)
27 | 262 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2014. Pdte. aplicación ejercicios futuros (1127)
28 | 275 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Pendiente principio periodo (1128)
29 | 288 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Aplicado en declaración (1129)
30 | 301 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Pdte. aplicación ejercicios futuros (1130)
31 | 314 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Pendiente principio periodo (1131)
32 | 327 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Aplicado en declaración (1132)
33 | 340 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Pdte. aplicación ejercicios futuros (1133)
34 | 353 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. Aportaciones y contribuciones 2017 (1134)
35 | 366 | 1 | Tit | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. Contribuyente "0" a "9" (1135)
36 | 367 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2013. Pendiente principio periodo (1136)
37 | 380 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2013. Aplicado en declaración (1137)
38 | 393 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2013. Pdte. aplicación ejercicios futuros (1138)
39 | 406 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2014. Pendiente principio periodo (1139)
40 | 419 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2014. Aplicado en declaración (1140)
41 | 432 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2014. Pdte. aplicación ejercicios futuros (1141)
42 | 445 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Pendiente principio periodo (1142)
43 | 458 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Aplicado en declaración (1143)
44 | 471 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Pdte. aplicación ejercicios futuros (1144)
45 | 484 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Pendiente principio periodo (1145)
46 | 497 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Aplicado en declaración (1146)
47 | 510 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Pdte. aplicación ejercicios futuros (1147)
48 | 523 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. Contribuciones 2017 (1148)
49 | 536 | 1 | Tit | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad.  Contribuyente "0" a "9" (1149)
50 | 537 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2012. Pendiente principio periodo (1150)
51 | 550 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2012. Aplicado en declaración (1151)
52 | 563 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2013. Pendiente principio periodo (1152)
53 | 576 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2013. Aplicado en declaración (1153)
54 | 589 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2013. Pdte. aplicación ejercicios futuros (1154)
55 | 602 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2014. Pendiente principio periodo (1155)
56 | 615 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2014. Aplicado en declaración (1156)
57 | 628 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2014. Pdte. aplicación ejercicios futuros (1157)
58 | 641 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Pendiente principio periodo (1158)
59 | 654 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Aplicado en declaración (1159)
60 | 667 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Pdte. aplicación ejercicios futuros (1160)
61 | 680 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Pendiente principio periodo (1161)
62 | 693 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Aplicado en declaración (1162)
63 | 706 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Pdte. aplicación ejercicios futuros (1163)
64 | 719 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. Aportaciones y contribuciones 2017 (1164)
65 | 732 | 1 | Tit | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes.  Contribuyente "0" a "9" (1165)
66 | 733 | 9 | An | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. NIF persona con discapacidad (1166)
67 | 742 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2012. Pendiente principio periodo (1167)
68 | 755 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2012. Aplicado en declaración (1168)
69 | 768 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2013. Pendiente principio periodo (1169)
70 | 781 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2013. Aplicado en declaración (1170)
71 | 794 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2013. Pdte. aplicación ejercicios futuros (1171)
72 | 807 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2014. Pendiente principio periodo (1172)
73 | 820 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2014. Aplicado en declaración (1173)
74 | 833 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2014. Pdte. aplicación ejercicios futuros (1174)
75 | 846 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Pendiente principio periodo (1175)
76 | 859 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Aplicado en declaración (1176)
77 | 872 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Pdte. aplicación ejercicios futuros (1177)
78 | 885 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Pendiente principio periodo (1178)
79 | 898 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Aplicado en declaración (1179)
80 | 911 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Pdte. aplicación ejercicios futuros (1180)
81 | 924 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. Aportaciones y contribuciones 2017 (1181)
82 | 937 | 1 | Tit | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.  Contribuyente "0" a "9" (1182)
83 | 938 | 9 | An | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.  NIF persona con discapacidad  (1183)
84 | 947 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2013. Pendiente principio periodo (1184)
85 | 960 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2013. Aplicado en declaración (1185)
86 | 973 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2014. Pendiente principio periodo (1186)
87 | 986 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2014. Aplicado en declaración (1187)
88 | 999 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2014. Pdte. aplicación ejercicios futuros (1188)
89 | 1012 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2015. Pendiente principio periodo (1189)
90 | 1025 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2015. Aplicado en declaración (1190)
91 | 1038 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2015. Pdte. aplicación ejercicios futuros (1191)
92 | 1051 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Pendiente principio periodo (1192)
93 | 1064 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Aplicado en declaración (1193)
94 | 1077 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Pdte. aplicación ejercicios futuros (1194)
95 | 1090 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir. Aportaciones 2017 (1195)
96 | 1103 | 600 | An |  | RESERVADO PARA LA A.E.A.T
97 | 1703 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10030000>
Total: |  | 1714

# Anexo C.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "31000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.  Contribuyente "0" a "9" (1196)
7 | 14 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2012. Pendiente principio periodo (1197)
8 | 27 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2012. Aplicado en declaración (1198)
9 | 40 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2013. Pendiente principio periodo (1199)
10 | 53 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2013. Aplicado en declaración (1200)
11 | 66 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2013. Pdte. aplicación ejercicios futuros (1201)
12 | 79 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2014. Pendiente principio periodo (1202)
13 | 92 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2014. Aplicado en declaración (1203)
14 | 105 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2014. Pdte. aplicación ejercicios futuros (1204)
15 | 118 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Pendiente principio periodo (1205)
16 | 131 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Aplicado en declaración (1206)
17 | 144 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Pdte. aplicación ejercicios futuros (1207)
18 | 157 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Pendiente principio periodo (1208)
19 | 170 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Aplicado en declaración (1209)
20 | 183 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Pdte. aplicación ejercicios futuros (1210)
21 | 196 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir. Aportaciones y contribuciones 2017 (1211)
22 | 209 | 1 | Tit | C | Bases liquidables generales negativas pendientes de compensar.  Contribuyente "0" a "9" (1212)
23 | 210 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2013. Pendiente principio periodo (1213)
24 | 223 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2013. Aplicado en declaración (1214)
25 | 236 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2014. Pendiente principio periodo (1215)
26 | 249 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2014. Aplicado en declaración (1216)
27 | 262 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2014. Pdte. aplicación ejercicios futuros (1217)
28 | 275 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2015. Pendiente principio periodo (1218)
29 | 288 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2015. Aplicado en declaración (1219)
30 | 301 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2015. Pdte. aplicación ejercicios futuros (1220)
31 | 314 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Pendiente principio periodo (1221)
32 | 327 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Aplicado en declaración (1222)
33 | 340 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Pdte. aplicación ejercicios futuros (1223)
34 | 353 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar. 2017 (1224)
35 | 366 | 600 | An |  | RESERVADO PARA LA A.E.A.T
36 | 966 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10031000>
Total: |  | 977

# I-D

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers.1.00 |  | Impuesto sobre la Renta de las Personas Físicas 2017
Nº | Posic. | Long. | Tipo | Descripción |  | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. |  | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. |  | OBLIGATORIO | Constante "32000"
4 | 11 | 1 | An | Fin de identificador de modelo. |  | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Resumen declaración (2) - Base liquidable general sometida a gravamen [0475]
7 | 26 | 13 | N | Resumen declaración (2) - Base liquidable del ahorro [0480]
8 | 39 | 13 | N | Resumen declaración (2) - Cuota íntegra estatal [0514]
9 | 52 | 13 | N | Resumen declaración (2) - Cuota íntegra autonómica [0515]
10 | 65 | 13 | N | Resumen declaración (2) - Cuota líquida estatal [0535]
11 | 78 | 13 | N | Resumen declaración (2) - Cuota líquida autonómica [0536]
12 | 91 | 13 | N | Resumen declaración (2) - Resultado a ingresar o a devolver [0645]
13 | 104 | 1 | Num | Opción de tributación. "1" Individual, "2" Conjunta.
14 | 105 | 1 | Num | Resumen declaración (2) - Solicitud de suspensión ingreso cónyuge/Renuncia cobro devolución otro cónyuge. "1" o "0" [7]
15 | 106 | 13 | N | Declaración Complementaria (3) - Resultado de Declaración Complementaria [0630]
16 | 119 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 645 positiva - NO FRACCIONA el pago [1]  "1" o "0"
17 | 120 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 645 positiva - SÍ FRACCIONA el pago [6] "1" o "0"
18 | 121 | 13 | N | Fraccionamiento del pago e ingreso (4) - Casilla 645 positiva - Importe  [I1]
19 | 134 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 645 positiva - Forma de pago -"0" No consta; "1" Efectivo; "2" Adeudo en Cuenta; "3" Domiciliación
20 | 135 | 1 | Num | Opciones de pago 2º plazo (5) - NO DOMICILIA el pago [2]   "1" o "0"
21 | 136 | 1 | Num | Opciones de pago 2º plazo (5) - SÍ DOMICILIA el pago [3] "1" o "0"
22 | 137 | 13 | N | Opciones de pago 2º plazo (5) - Importe del 2º plazo [I2]
23 | 150 | 1 | Num | Devolución (6) - Casilla 645 negativa - "0" No consta, "1" Devolución y "2" Renuncia devolución
24 | 151 | 13 | N | Devolución (6) - Casilla 645 negativa - Importe [D]
25 | 164 | 34 | An | Cuenta bancaria (7) Número de cuenta IBAN
26 | 198 | 11 | An | Devolución - Código SWIFT-BIC
27 | 209 | 589 | An | RESERVADO PARA LA A.E.A.T
28 | 798 | 12 | An | Identificador de Fin de registro. |  | OBLIGATORIO | Constante </T10032000>
Total: |  | 809