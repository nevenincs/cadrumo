# 100-00

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 17 | An | Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "<T100020180A0000>"
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
12 | *** | 18 | An | Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "</T100020180A0000>"
13 | *** | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
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
 |  |  | 12 | (G2) Imputación a 2018 de G/P patrimoniales derivadas de transmisiones efectuadas en ejercicios anteriores (GANANCIAS) | 15
 |  |  | 12 | (G2) Imputación a 2018 de G/P patrimoniales derivadas de transmisiones efectuadas en ejercicios anteriores | 15
 |  |  |  | (PÉRDIDAS)
 |  |  | 13 | (G3) Imputación a 2018 de ganancias patrimoniales acogidas a diferimiento por reinversión | 15
 |  |  | 13 | (G4) Ganancias patrimoniales por cambio de residencia fuera del territorio español | 15
 |  |  | 14 | (I) Reducciones por aportaciones y contribuciones a sistemas de previsión social | 2
 |  |  | 14 | (I) Reducciones por aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad | 4
 |  |  | 15 | (I) Reducciones por aportaciones a patrimonios protegidos de personas con discapacidad | 2
 |  |  | 15 | (I) Reducciones por pensiones compensatorias a favor del cónyuge y anualidades por alimentos, excepto en favor de los hijos | 2
 |  |  | 15 | (I) Reducciones por aportaciones a la mutualidad de previsión social de deportistas profesionales | 2
 |  |  | 17 | (M) Ded. Descendientes discapacidad | 15
 |  |  | 17 | (M) Ded. Ascendientes discapacidad | 6
 |  |  | 18 | (M) Ded. Familia numerosa | 3
 |  |  | 18 | (M) Ded. Ascendiente separado | 2
 |  |  | 18 | (M) Regularizaciones descendientes | 15
 |  |  | 18 | (M) Regularizaciones ascendientes | 6
 |  |  | C1 | Intereses de los capitales invertidos en la adquisición o mejora de inmuebles y gastos de reparación y conservación de los mismos, pendientes de deducir en los ejercicios siguientes. | 60
 |  |  | C1 | Exención por reinversión de la ganancia patrimonial obtenida en 2018 por la transmisión de la vivienda habitual | 6
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
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 1 | An | Tipo de declaración (Ver Nota)
7 | 14 | 9 | An | Primer Declarante - NIF (01) | OBLIGATORIO
8 | 23 | 80 | A | Primer Declarante - Apellidos y nombre  (02) | OBLIGATORIO
9 | 103 | 4 | Num | Ejercicio | OBLIGATORIO | Constante 2018
10 | 107 | 2 | An | Periodo | OBLIGATORIO | Constante 0A
11 | 109 | 1 | A | Primer Declarante - Sexo "H" Hombre, "M" Mujer (05) | OBLIGATORIO
12 | 110 | 1 | Num | Primer Declarante -Estado Civil. "1" Soltero/a, "2" Casado/a, "3" Viudo/a, "4" Divorciado/a o Separado/a | OBLIGATORIO
13 | 111 | 8 | Num | Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año < 2019 (10) | OBLIGATORIO
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
41 | 531 | 2 | An | Primer Declarante - País de residencia en la UE o EEE en 2018 (43)
42 | 533 | 1 | Num | Primer Declarante - Nacionalidad "0" No consta; "1" Española; "2" Otra  (44)
43 | 534 | 1 | Num | Datos adicionales vivienda - Vivienda 1.Titularidad "1", "2", "3" o "4" (50) | OBLIGATORIO
44 | 535 | 5 | Num | Datos adicionales vivienda - Vivienda 1.Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
45 | 540 | 5 | Num | Datos adicionales vivienda - Vivienda 1.Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
46 | 545 | 1 | Num | Datos adicionales vivienda - Vivienda 1.Situación (clave) "1", "2", "3", "4" o "5" (53)
47 | 546 | 20 | An | Datos adicionales vivienda - Vivienda 1.Referencia catastral (54)
48 | 566 | 1 | Num | Datos adicionales vivienda - Vivienda 2.Titularidad "0", "1", "2", "3" o "4" (50)
49 | 567 | 5 | Num | Datos adicionales vivienda - Vivienda 2. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
50 | 572 | 5 | Num | Datos adicionales vivienda - Vivienda 2. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
51 | 577 | 1 | Num | Datos adicionales vivienda - Vivienda 2.Situación (clave) "1", "2", "3", "4" o "5" (53)
52 | 578 | 20 | An | Datos adicionales vivienda - Vivienda 2. Referencia catastral (54)
53 | 598 | 1 | Num | Datos adicionales vivienda - Vivienda 3.Titularidad "0", "1", "2", "3" o "4" (50)
54 | 599 | 5 | Num | Datos adicionales vivienda - Vivienda 3. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
55 | 604 | 5 | Num | Datos adicionales vivienda - Vivienda 3. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
56 | 609 | 1 | Num | Datos adicionales vivienda - Vivienda 3.Situación (clave) "1", "2", "3", "4" o "5" (53)
57 | 610 | 20 | An | Datos adicionales vivienda - Vivienda 3. Referencia catastral (54)
58 | 630 | 1 | Num | Datos adicionales vivienda - Vivienda 4.Titularidad "0", "1", "2", "3" o "4" (50)
59 | 631 | 5 | Num | Datos adicionales vivienda - Vivienda 4. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
60 | 636 | 5 | Num | Datos adicionales vivienda - Vivienda 4. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
61 | 641 | 1 | Num | Datos adicionales vivienda - Vivienda 4.Situación (clave) "1", "2", "3", "4" o "5" (53)
62 | 642 | 20 | An | Datos adicionales vivienda - Vivienda 4. Referencia catastral (54)
63 | 662 | 1 | Num | Datos adicionales vivienda - Vivienda 5.Titularidad "0", "1", "2", "3" o "4" (50)
64 | 663 | 5 | Num | Datos adicionales vivienda - Vivienda 5. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
65 | 668 | 5 | Num | Datos adicionales vivienda - Vivienda 5. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
66 | 673 | 1 | Num | Datos adicionales vivienda - Vivienda 5.Situación (clave) "1", "2", "3", "4" o "5" (53)
67 | 674 | 20 | An | Datos adicionales vivienda - Vivienda 5. Referencia catastral (54)
68 | 694 | 1 | Num | Datos adicionales vivienda - Vivienda 6.Titularidad "0", "1", "2", "3" o "4" (50)
69 | 695 | 5 | Num | Datos adicionales vivienda - Vivienda 6. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
70 | 700 | 5 | Num | Datos adicionales vivienda - Vivienda 6. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
71 | 705 | 1 | Num | Datos adicionales vivienda - Vivienda 6.Situación (clave) "1", "2", "3", "4" o "5" (53)
72 | 706 | 20 | An | Datos adicionales vivienda - Vivienda 6. Referencia catastral (54)
73 | 726 | 1 | Num | Datos adicionales vivienda - Vivienda 7.Titularidad "0", "1", "2", "3" o "4" (50)
74 | 727 | 5 | Num | Datos adicionales vivienda - Vivienda 7. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
75 | 732 | 5 | Num | Datos adicionales vivienda - Vivienda 7. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
76 | 737 | 1 | Num | Datos adicionales vivienda - Vivienda 7.Situación (clave) "1", "2", "3", "4" o "5" (53)
77 | 738 | 20 | An | Datos adicionales vivienda - Vivienda 7. Referencia catastral (54)
78 | 758 | 1 | Num | Datos adicionales vivienda - Vivienda 8.Titularidad "0", "1", "2", "3" o "4" (50)
79 | 759 | 5 | Num | Datos adicionales vivienda - Vivienda 8. Porcentaje participación Primer declarante (tres enteros, dos decimales) (51)
80 | 764 | 5 | Num | Datos adicionales vivienda - Vivienda 8. Porcentaje participación Cónyuge (tres enteros, dos decimales) (52)
81 | 769 | 1 | Num | Datos adicionales vivienda - Vivienda 8.Situación (clave) "1", "2", "3", "4" o "5" (53)
82 | 770 | 20 | An | Datos adicionales vivienda - Vivienda 8. Referencia catastral (54)
83 | 790 | 9 | An | Datos adicionales vivienda - Nif Arrendador (55)
84 | 799 | 20 | An | Datos adicionales vivienda - Si no tiene NIF. Nº identificación en el país de residencia (56)
85 | 819 | 9 | An | Cónyuge - NIF (57)
86 | 828 | 80 | A | Cónyuge - Apellidos y nombre (58)
87 | 908 | 1 | A | Cónyuge - Sexo "H" Hombre, "M" Mujer (59)
88 | 909 | 8 | Num | Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero. (60)
89 | 917 | 1 | Num | Cónyuge - Grado de discapacidad   "0", "1", "2" ,"3" o "4" (61)
90 | 918 | 1 | Num | Cónyuge - No residente que no es contribuyente del I.R.P.F. - "1" o cero (62)
91 | 919 | 1 | Num | Cónyuge - No residente que reside en un país de la UE o del EEE, y se aplica la deducción por unidades familiares formadas por residentes fiscales en la UE o del EE.- "1" o cero  (64)
92 | 920 | 1 | Num | Cónyuge - Cambio de domicilio "1" o cero (63)
93 | 921 | 5 | A | Cónyuge - Domicilio habitual - Tipo de Vía (15)
94 | 926 | 5 | Num | Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Vía INE
95 | 931 | 50 | An | Cónyuge - Domicilio habitual - Nombre de la Vía Pública (16)
96 | 981 | 3 | An | Cónyuge - Domicilio habitual - Tipo de numeración. Valores: NUM;KM;S/N;OTR (17)
97 | 984 | 5 | Num | Cónyuge - Domicilio habitual - Número de Casa (18)
98 | 989 | 3 | An | Cónyuge - Domicilio habitual - Calificador del número. Valores: BIS;DUP;MOD;ANT;etc/metros si Tipo Num=KM. (19)
99 | 992 | 3 | An | Cónyuge - Domicilio habitual - Bloque (20)
100 | 995 | 3 | An | Cónyuge - Domicilio habitual - Portal (21)
101 | 998 | 3 | An | Cónyuge - Domicilio habitual - Escalera (22)
102 | 1001 | 3 | An | Cónyuge - Domicilio habitual - Planta (23)
103 | 1004 | 3 | An | Cónyuge - Domicilio habitual - Puerta (24)
104 | 1007 | 40 | An | Cónyuge - Domicilio habitual - Datos complementarios del Domicilio habitual (25)
105 | 1047 | 30 | An | Cónyuge - Domicilio habitual - Localidad / Población (26)
106 | 1077 | 5 | Num | Cónyuge - Domicilio habitual - Código postal (27)
107 | 1082 | 5 | Num | Cónyuge - Domicilio habitual - RESERVADO AEAT - Código Municipio INE
108 | 1087 | 30 | An | Cónyuge - Domicilio habitual - Nombre del Municipio (28)
109 | 1117 | 2 | Num | Cónyuge - Domicilio habitual - Código provincia. De "01" a "52".
110 | 1119 | 20 | An | Cónyuge - Domicilio habitual - Provincia (29)
111 | 1139 | 50 | An | Cónyuge - Domicilio extranjero - Domicilio/Address (35)
112 | 1189 | 40 | An | Cónyuge - Domicilio extranjero - Datos complementarios del domicilio (36)
113 | 1229 | 30 | An | Cónyuge - Domicilio extranjero - Población / Ciudad (37)
114 | 1259 | 10 | An | Cónyuge - Domicilio extranjero - Código Postal (39)
115 | 1269 | 30 | An | Cónyuge - Domicilio extranjero - Provincia / Región / Estado (40)
116 | 1299 | 30 | An | Cónyuge - Domicilio extranjero - País (41)
117 | 1329 | 2 | An | Cónyuge - Domicilio extranjero - Código País (42)
118 | 1331 | 2 | An | Cónyuge - País de residencia en la UE en 2018 (43)
119 | 1333 | 1 | Num | Cónyuge - Nacionalidad "0" No consta; "1" Española; "2" Otra (44)
120 | 1334 | 12 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
121 | 1346 | 9 | An | Representante -  N.I.F. (65)
122 | 1355 | 32 | An | Representante -  Apellidos y nombre o razón social (66)
123 | 1387 | 8 | Num | Devengo - Fecha de  finalización del período impositivo (fallecimiento 2018)  (DDMMAAAA) o cero (67)
124 | 1395 | 1 | Num | Opción de tributación. "1" Individual, "2" Conjunta.  Campo OBLIGATORIO (68) (69) | OBLIGATORIO
125 | 1396 | 2 | Num | Comunidad/Ciudad autónoma de residencia en 2018 - Clave (70) Incluido en el fichero COMAUTO.TXT | OBLIGATORIO
126 | 1398 | 13 | Num | Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
127 | 1411 | 21 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
128 | 1432 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
129 | 1445 | 600 | An | RESERVADO PARA LA A.E.A.T
130 | 2045 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10001000>
Total |  | 2056
 |  |  | Nota: | El Tipo de declaración puede ser: I (Ingreso), U (Domiciliación),  N (Negativa/Resultado cero), D (Solicitud de devolución) y R (Renuncia a la devolución)

# 100-02

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "02000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 9 | An | Hijos y descendientes - 1º -  N.I.F. (75)
7 | 22 | 60 | A | Hijos y descendientes - 1º -  Apellidos y nombre  (76)
8 | 82 | 8 | Num | Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año < 2019 o cero (77)
9 | 90 | 8 | Num | Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
10 | 98 | 1 | Num | Hijos y descendientes - 1º - Grado discapacidad   "0", "1", "2", "3" o "4" (79)
11 | 99 | 1 | An | Hijos y descendientes - 1º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (80)
12 | 100 | 2 | Num | Hijos y descendientes - 1º - Nº de orden (81)
13 | 102 | 1 | An | Hijos y descendientes - 1º - Otras situaciones  clave:"1","2","3","4" o blanco  (82)
14 | 103 | 9 | An | Hijos y descendientes - 2º - N.I.F. (75)
15 | 112 | 60 | A | Hijos y descendientes - 2º - Apellidos y nombre  (76)
16 | 172 | 8 | Num | Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año < 2019 o cero (77)
17 | 180 | 8 | Num | Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año < 2019 o cero (78)
18 | 188 | 1 | Num | Hijos y descendientes - 2º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
19 | 189 | 1 | An | Hijos y descendientes - 2º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
20 | 190 | 2 | Num | Hijos y descendientes - 2º - Nº de orden (81)
21 | 192 | 1 | An | Hijos y descendientes - 2º - Otras situaciones  "1","2","3","4" o blanco  (82)
22 | 193 | 9 | An | Hijos y descendientes - 3º - N.I.F. (75)
23 | 202 | 60 | A | Hijos y descendientes - 3º - Apellidos y nombre  (76)
24 | 262 | 8 | Num | Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
25 | 270 | 8 | Num | Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
26 | 278 | 1 | Num | Hijos y descendientes - 3º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
27 | 279 | 1 | An | Hijos y descendientes - 3º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
28 | 280 | 2 | Num | Hijos y descendientes - 3º - Nº de orden (81)
29 | 282 | 1 | An | Hijos y descendientes - 3º - Otras situaciones  "1","2","3","4" o blanco  (82)
30 | 283 | 9 | An | Hijos y descendientes - 4º - N.I.F.  (75)
31 | 292 | 60 | A | Hijos y descendientes - 4º - Apellidos y nombre  (76)
32 | 352 | 8 | Num | Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
33 | 360 | 8 | Num | Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
34 | 368 | 1 | Num | Hijos y descendientes - 4º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
35 | 369 | 1 | An | Hijos y descendientes - 4º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
36 | 370 | 2 | Num | Hijos y descendientes - 4º - Nº de orden (81)
37 | 372 | 1 | An | Hijos y descendientes - 4º - Otras situaciones  "1","2","3","4" o blanco  (82)
38 | 373 | 9 | An | Hijos y descendientes - 5º - N.I.F. (75)
39 | 382 | 60 | A | Hijos y descendientes - 5º - Apellidos y nombre  (76)
40 | 442 | 8 | Num | Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
41 | 450 | 8 | Num | Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
42 | 458 | 1 | Num | Hijos y descendientes - 5º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
43 | 459 | 1 | An | Hijos y descendientes - 5º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
44 | 460 | 2 | Num | Hijos y descendientes - 5º - Nº de orden (81)
45 | 462 | 1 | An | Hijos y descendientes - 5º - Otras situaciones  "1","2","3","4" o blanco  (82)
46 | 463 | 9 | An | Hijos y descendientes - 6º - N.I.F. (75)
47 | 472 | 60 | A | Hijos y descendientes - 6º - Apellidos y nombre  (76)
48 | 532 | 8 | Num | Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
49 | 540 | 8 | Num | Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
50 | 548 | 1 | Num | Hijos y descendientes - 6º - Grado discapacidad  "0", "1", "2", "3" o "4" (79)
51 | 549 | 1 | An | Hijos y descendientes - 6º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
52 | 550 | 2 | Num | Hijos y descendientes - 6º - Nº de orden (81)
53 | 552 | 1 | An | Hijos y descendientes - 6º - Otras situaciones  "1","2","3","4" o blanco  (82)
54 | 553 | 9 | An | Hijos y descendientes - 7º - N.I.F.  (75)
55 | 562 | 60 | A | Hijos y descendientes - 7º - Apellidos y nombre  (76)
56 | 622 | 8 | Num | Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
57 | 630 | 8 | Num | Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
58 | 638 | 1 | Num | Hijos y descendientes - 7º - Grado discapacidad  "0", "1", "2", "3" o "4" (79)
59 | 639 | 1 | An | Hijos y descendientes - 7º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
60 | 640 | 2 | Num | Hijos y descendientes - 7º - Nº de orden (81)
61 | 642 | 1 | An | Hijos y descendientes - 7º - Otras situaciones  "1","2","3","4" o blanco  (82)
62 | 643 | 9 | An | Hijos y descendientes - 8º - N.I.F. (75)
63 | 652 | 60 | A | Hijos y descendientes - 8º - Apellidos y nombre  (76)
64 | 712 | 8 | Num | Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
65 | 720 | 8 | Num | Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
66 | 728 | 1 | Num | Hijos y descendientes - 8º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
67 | 729 | 1 | An | Hijos y descendientes - 8º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (80)
68 | 730 | 2 | Num | Hijos y descendientes - 8º - Nº de orden (81)
69 | 732 | 1 | An | Hijos y descendientes - 8º - Otras situaciones  "1","2","3","4" o blanco  (82)
70 | 733 | 9 | An | Hijos y descendientes - 9º - N.I.F. (75)
71 | 742 | 60 | A | Hijos y descendientes - 9º - Apellidos y nombre  (76)
72 | 802 | 8 | Num | Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
73 | 810 | 8 | Num | Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
74 | 818 | 1 | Num | Hijos y descendientes - 9º - Grado discapacidad  "0", "1", "2", "3" o "4"  (79)
75 | 819 | 1 | An | Hijos y descendientes - 9º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
76 | 820 | 2 | Num | Hijos y descendientes - 9º - Nº de orden (81)
77 | 822 | 1 | An | Hijos y descendientes - 9º - Otras situaciones  "1","2","3","4" o blanco  (82)
78 | 823 | 9 | An | Hijos y descendientes - 10º - N.I.F.  (75)
79 | 832 | 60 | A | Hijos y descendientes - 10º - Apellidos y nombre  (76)
80 | 892 | 8 | Num | Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
81 | 900 | 8 | Num | Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
82 | 908 | 1 | Num | Hijos y descendientes - 10º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
83 | 909 | 1 | An | Hijos y descendientes - 10º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
84 | 910 | 2 | Num | Hijos y descendientes - 10º - Nº de orden (81)
85 | 912 | 1 | An | Hijos y descendientes - 10º - Otras situaciones  "1","2","3","4" o blanco  (82)
86 | 913 | 9 | An | Hijos y descendientes - 11º - N.I.F. (75)
87 | 922 | 60 | A | Hijos y descendientes - 11º - Apellidos y nombre  (76)
88 | 982 | 8 | Num | Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
89 | 990 | 8 | Num | Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
90 | 998 | 1 | Num | Hijos y descendientes - 11º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
91 | 999 | 1 | An | Hijos y descendientes - 11º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
92 | 1000 | 2 | Num | Hijos y descendientes - 11º - Nº de orden (81)
93 | 1002 | 1 | An | Hijos y descendientes - 11º - Otras situaciones  "1","2","3","4" o blanco  (82)
94 | 1003 | 9 | An | Hijos y descendientes - 12º - N.I.F. (75)
95 | 1012 | 60 | A | Hijos y descendientes - 12º - Apellidos y nombre  (76)
96 | 1072 | 8 | Num | Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero (77)
97 | 1080 | 8 | Num | Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2019 o cero (78)
98 | 1088 | 1 | Num | Hijos y descendientes - 12º - Grado discapacidad  "0", "1", "2", "3" o "4"  (79)
99 | 1089 | 1 | An | Hijos y descendientes - 12º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
100 | 1090 | 2 | Num | Hijos y descendientes - 12º - Nº de orden (81)
101 | 1092 | 1 | An | Hijos y descendientes - 12º - Otras situaciones  "1","2","3","4" o blanco  (82)
102 | 1093 | 2 | Num | Hijos y descendientes - Fallecido 2018 - Nº Orden (83)
103 | 1095 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (84)
104 | 1103 | 2 | Num | Hijos y descendientes - Fallecido 2018 - Nº Orden (83)
105 | 1105 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (84)
106 | 1113 | 1 | Num | Si alguno de los hijos o descendientes es no residente, reside en un país de la UE o del EEE, y se aplica la deducción por unidades familiares formadas por residentes fiscales en la UE o del EEE (88) | "1" = SI;       cero = NO
107 | 1114 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
108 | 1123 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
109 | 1132 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
110 | 1141 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
111 | 1150 | 9 | An | Hijos y descendientes - Otro progenitor 1 - Nif (85)
112 | 1159 | 60 | A | Hijos y descendientes - Otro progenitor 1 - Apellidos y nombre (86)
113 | 1219 | 1 | Num | Hijos y descendientes - Otro progenitor 1 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
114 | 1220 | 9 | An | Hijos y descendientes - Otro progenitor 2 - Nif (85)
115 | 1229 | 60 | A | Hijos y descendientes - Otro progenitor 2 - Apellidos y nombre (86)
116 | 1289 | 1 | Num | Hijos y descendientes - Otro progenitor 2 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
117 | 1290 | 9 | An | Hijos y descendientes - Otro progenitor 3 - Nif (85)
118 | 1299 | 60 | A | Hijos y descendientes - Otro progenitor 3 - Apellidos y nombre (86)
119 | 1359 | 1 | Num | Hijos y descendientes - Otro progenitor 3 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
120 | 1360 | 9 | An | Hijos y descendientes - Otro progenitor 4 - Nif (85)
121 | 1369 | 60 | A | Hijos y descendientes - Otro progenitor 4 - Apellidos y nombre (86)
122 | 1429 | 1 | Num | Hijos y descendientes - Otro progenitor 4 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
123 | 1430 | 24 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
124 | 1454 | 9 | An | Ascendientes mayores 65 años o discapacitados - 1º - N.I.F.  (90)
125 | 1463 | 60 | A | Ascendientes mayores 65 años o discapacitados - 1º - Apellidos y nombre (91)
126 | 1523 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (92)
127 | 1531 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Grado discapacidad  "0", "1", "2", "3" o "4" (93)
128 | 1532 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Vinculación  clave:"1", "2" o blanco (94)
129 | 1533 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Convivencia   "2" a "9" o blanco (95)
130 | 1534 | 9 | An | Ascendientes mayores 65 años o discapacitados - 2º - N.I.F.  (90)
131 | 1543 | 60 | A | Ascendientes mayores 65 años o discapacitados - 2º - Apellidos y nombre (91)
132 | 1603 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (92)
133 | 1611 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Grado discapacidad  "0", "1", "2", "3" o "4"  (93)
134 | 1612 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Vinculación clave:"1", "2" o blanco  (94)
135 | 1613 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Convivencia  "2" a "9" o blanco  (95)
136 | 1614 | 9 | An | Ascendientes mayores 65 años o discapacitados - 3º - N.I.F.  (90)
137 | 1623 | 60 | A | Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
138 | 1683 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año < 2018 o cero (92)
139 | 1691 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Grado discapacidad  "0", "1", "2", "3" o "4"  (93)
140 | 1692 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Vinculación  clave:"1", "2" o blanco  (94)
141 | 1693 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Convivencia   "2" a "9" o blanco  (95)
142 | 1694 | 9 | An | Ascendientes mayores 65 años o discapacitados - 4º - N.I.F.  (90)
143 | 1703 | 60 | A | Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
144 | 1763 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2018 o cero (92)
145 | 1771 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Grado discapacidad  "0", "1", "2", "3" o "4" (93)
146 | 1772 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Vinculación  clave:"1", "2" o blanco  (94)
147 | 1773 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Convivencia  "2" a "9" o blanco  (95)
148 | 1774 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2018 - Nif (96)
149 | 1783 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
150 | 1791 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2018 - Nif (96)
151 | 1800 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
152 | 1808 | 1 | A | Asignación tributaria a la Iglesia Católica. "X" o  blanco. (105)
153 | 1809 | 1 | A | Asignación de cantidades a actividades de interés general consideradas de interés social. "X" o  blanco. (106)
154 | 1810 | 600 | An | RESERVADO PARA LA A.E.A.T
155 | 2410 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10002000>
Total |  | 2421

# 100-03

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
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
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "04000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (A) Rdto. Trabajo - Contribuyente que obtiene los rendimientos . "0" a "9" (0001)
8 | 15 | 1 | Num |  | En el caso de los rendimientos derivados de la cesión de la explotación de los derechos de autor, si opta por imputar el anticipo a cuenta de los mismos a medida que vayan devengándose los derechos (0002) | "1" = SI; cero = NO
9 | 16 | 13 | N | C | Rdto. Trabajo - Retribuciones dinerarias (0003)
10 | 29 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Valoracion (0004)
11 | 42 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta (0005)
12 | 55 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta repercutidos (0006)
13 | 68 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Importe íntegro (0007)
14 | 81 | 13 | N | C | Rdto. Trabajo - Contribuciones empresariales a planes de pensiones, planes de previsión social empresarial  y mutualidades previsión social  (0008)
15 | 94 | 13 | N | C | Rdto. Trabajo - Contribuciones empresariales a seguros colectivos dependencia. Imputado al contribuyente (0009)
16 | 107 | 13 | N | C | Rdto. Trabajo - Aportaciones al patrimonio protegido de discapacitados - Importe (0010)
17 | 120 | 13 | N | C | Rdto. Trabajo - Reducciones (0011)
18 | 133 | 13 | N | C | Rdto. Trabajo - Total ingresos íntegros computables (0012)
19 | 146 | 13 | N | C | Rdto. Trabajo - Cotizaciones Seguridad Social/mutualidades funcionarios, detracciones por derechos pasivos y cotizaciones  colegios huérfanos (0013)
20 | 159 | 13 | N | C | Rdto. Trabajo - Cuotas satisfechas a sindicatos (0014)
21 | 172 | 13 | N | C | Rdto. Trabajo - Cuotas satisfechas a colegios profesionales (0015)
22 | 185 | 13 | N | C | Rdto. Trabajo - Gastos defensa jurídica derivados litigios con empleador (0016)
23 | 198 | 13 | N | C | Rdto. Trabajo - Rendimiento neto previo (0017)
24 | 211 | 13 | N |  | Rdto. Trabajo -Suma de rendimientos netos previos (0018)
25 | 224 | 13 | N |  | Rdto. Trabajo - Otros gastos deducibles (0019)
26 | 237 | 13 | N |  | Rdto. Trabajo - Incremento contribuyentes desempleados con traslado de residencia  (0020)
27 | 250 | 13 | N |  | Rdto. Trabajo - Incremento para trabajadores activos que sean personas con discapacidad  (0021)
28 | 263 | 13 | N |  | Rdto. Trabajo - Rendimiento neto  (0022)
29 | 276 | 13 | N |  | Rdto. Trabajo - Reducción por obtención rendimientos de trabajo. Cuantía aplicable con carácter general (0023)
30 | 289 | 13 | N |  | Rdto. Trabajo - Rendimiento neto reducido (0025)
31 | 302 | 1 | Tit | C | (B) Rdto.capital mobiliario - Base imponible ahorro - Contribuyente que obtiene los rendimientos . "0" a "9" (0026)
32 | 303 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (0027)
33 | 316 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro  - Intereses de activos financieros con derecho a bonificación (0028)
34 | 329 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (0029)
35 | 342 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (0030)
36 | 355 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros (0031)
37 | 368 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (0032)
38 | 381 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. procedentes de rentas que tengan por causa la imposición de capitales (0033)
39 | 394 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. derivados de valores de deuda subordinada o participaciones preferentes. (0034)
40 | 407 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. procedentes de seguros de vida, depósitos financieros que instrumenten Planes Ahorro (0035)
41 | 420 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Total ingresos íntegros (0036)
42 | 433 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Gastos fiscalmente deducibles (0037)
43 | 446 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rendimiento neto (0038)
44 | 459 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (0039]
45 | 472 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rendimiento neto reducido (0040)
46 | 485 | 13 | N |  | Rdto.capital mobiliario -  Base imponible ahorro  - Suma de rendimientos del capital mobiliario base imponible del ahorro (0041)
47 | 498 | 1 | Tit | C | Aplicación DT 4 - Contribuyente 1  "0" a "9" (0042)
48 | 499 | 13 | N | C | Aplicación DT 4 - Contribuyente 1 - Importe total acumulado del capital diferido percibido en 2015, 2016 y 2017 (0043)
49 | 512 | 13 | N | C | Aplicación DT 4 - Contribuyente 1 - Importe total de los capitales diferidos correspondientes a seguros de vida (0044)
50 | 525 | 600 | An |  | RESERVADO PARA LA A.E.A.T
51 | 1125 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10004000>
Total: |  | 1136

# 100-05

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com. | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "05000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 15 | 1 | Tit | C | Rdto.capital mobiliario - Base imponible general - Contribuyente que obtiene los rendimientos . "0" a "9" (0045)
8 | 16 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (0046)
9 | 29 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (0047)
10 | 42 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (0048)
11 | 55 | 1 | Num | C | Rdto.capital mobiliario -  Base imponible general -  Rendimientos derivados de la cesión de derechos de autor (0049) | "1" = SI; cero = NO
12 | 56 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (0050)
13 | 69 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (0051)
14 | 82 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Total ingresos íntegros (0052)
15 | 95 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Gastos fiscalmente deducibles (0053)
16 | 108 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimiento neto (0054)
17 | 121 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (0055)
18 | 134 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimiento neto reducido (0056)
19 | 147 | 13 | N |  | Rdto.capital mobiliario -  Base imponible general  - Suma de rendimientos del capital mobiliario base imponible general (0060)
20 | 160 | 3 | Num | C | (C) Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Número de orden (0061)
21 | 163 | 1 | Tit | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Contribuyente "0" a "9" (0062)
22 | 164 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Porcentaje propiedad (3 enteros y 2 decimales) (0063)
23 | 169 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Porcentaje usufructo (3 enteros y 2 decimales) (0064)
24 | 174 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Naturaleza (0065)
25 | 175 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Uso o destino. Clave   (0066)
26 | 176 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Situación "0", "1", "2", "3", "4" o "5" (0067)
27 | 177 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Referencia catastral (0068)
28 | 197 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. NIF del excónyuge (0069)
29 | 217 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Si el excónyuge ha consignado NIF de otro país (0070)
30 | 218 | 65 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Dirección (0071)
31 | 283 | 5 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. Porcentaje disposición (3 enteros y 2 decimales) (0072)
32 | 288 | 3 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. Número de días (0073)
33 | 291 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. Renta imputada (0074)
34 | 304 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. NIF arrendatario 1 (0075)
35 | 324 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. Si ha consignado el NIF 1 de otro país (0076)
36 | 325 | 20 | An | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. NIF arrendatario 2 (0077)
37 | 345 | 1 | Num | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. A disposición. Si ha consignado el NIF 2 de otro país (0078)
38 | 346 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Ingresos íntegros computables (0079)
39 | 359 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Intereses. Importe pendiente (0080)
40 | 372 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Intereses. Importe (0081)
41 | 385 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Intereses. Pendiente deducir (0082)
42 | 398 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Títulos, recargos y tasas (0083)
43 | 411 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Saldos dudoso cobro (0084)
44 | 424 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Cantidades devengadas por terceros (0085)
45 | 437 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Amortización bienes inmuebles (0086)
46 | 450 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Amortización bienes muebles (0087)
47 | 463 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Gastos deducibles. Otros gastos fiscalmente deducibles (0088)
48 | 476 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Rendimiento neto (0089)
49 | 489 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Reducción por arrendamiento destinado a vivienda (0090)
50 | 502 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Reducción rendimientos más de 2 años (0091)
51 | 515 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Rendimiento mínimo computable parentesco (0092)
52 | 528 | 13 | N | C | Bienes inmuebles no afectos. Relación inmuebles y rentas. Inmueble. Arrendado o cedido. Rendimiento neto reducido (0093)
53 | 541 | 13 | N |  | Bienes inmuebles no afectos. Rentas totales . Suma de rentas inmobiliarias imputadas (0094)
54 | 554 | 13 | N |  | Bienes inmuebles no afectos. Rentas totales . Suma rendimientos netos reducidos del capital inmobiliario (0095)
55 | 567 | 3 | Num |  | Número de inmuebles en declaración conjunta (Reservado para la Administración)
56 | 570 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Contribuyente "0" a "9" (0096)
57 | 571 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Nº Identificación fiscal entidad (0097)
58 | 591 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Porcentaje titularidad (3 enteros y 2 decimales) (0098)
59 | 596 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Naturaleza (0099)
60 | 597 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Situación "0", "1", "2", "3", "4" o "5" (0100)
61 | 598 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1.  Referencia catastral (0101)
62 | 618 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 1. No Residente (0102)
63 | 619 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Contribuyente "0" a "9" (0096)
64 | 620 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Nº Identificación fiscal entidad (0097)
65 | 640 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Porcentaje titularidad (3 enteros y 2 decimales) (0098)
66 | 645 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Naturaleza (0099)
67 | 646 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Situación "0", "1", "2", "3", "4" o "5" (0100)
68 | 647 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2.  Referencia catastral (0101)
69 | 667 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 2. No Residente (0102)
70 | 668 | 1 | Tit | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Contribuyente "0" a "9" (0096)
71 | 669 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Nº Identificación fiscal entidad (0097)
72 | 689 | 5 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Porcentaje titularidad (3 enteros y 2 decimales) (0098)
73 | 694 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Naturaleza (0099)
74 | 695 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Situación "0", "1", "2", "3, "4" o "5" (0100)
75 | 696 | 20 | An | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3.  Referencia catastral (0101)
76 | 716 | 1 | Num | C | Bienes inmuebles no afectos. Bienes inmuebles arrendados o cedidos. Inmueble 3. No Residente (0102)
77 | 717 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 1. Contribuyente "0" a "9" (0103)
78 | 718 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje propiedad (3 enteros y 2 decimales) (0104)
79 | 723 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Porcentaje usufructo (3 enteros y 2 decimales)  (0105)
80 | 728 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1. Naturaleza (clave) (0106)
81 | 729 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 1.  Situación "0", "1", "2", "3", "4" o "5" (0107)
82 | 730 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 1.  Referencia catastral (0108)
83 | 750 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 2. Contribuyente "0" a "9" (0103)
84 | 751 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje propiedad (3 enteros y 2 decimales) (0104)
85 | 756 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Porcentaje usufructo (3 enteros y 2 decimales)  (0105)
86 | 761 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2. Naturaleza (clave) (0106)
87 | 762 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 2.  Situación "0", "1", "2", "3", "4" o "5" (0107)
88 | 763 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 2.  Referencia catastral (0108)
89 | 783 | 1 | Tit | C | (D) Bienes inmuebles urbanos afectos. Inmueble 3. Contribuyente "0" a "9" (0103)
90 | 784 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje propiedad (3 enteros y 2 decimales) (0104)
91 | 789 | 5 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Porcentaje usufructo (3 enteros y 2 decimales)  (0105)
92 | 794 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3. Naturaleza (clave) (0106)
93 | 795 | 1 | Num | C | Bienes inmuebles urbanos afectos. Inmueble 3.  Situación "0", "1", "2", "3", "4" o "5" (0107)
94 | 796 | 20 | An | C | Bienes inmuebles urbanos afectos. Inmueble 3.  Referencia catastral (0108)
95 | 816 | 600 | An |  | RESERVADO PARA LA A.E.A.T
96 | 1416 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10005000>
Total: |  | 1427

# 100-06

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com. | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "06000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (E1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Contribuyente  "0" a "9" (0110)
8 | 15 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Tipo actividad. Clave (Blanco o de "1" a "5") (0111)
9 | 16 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Epígrafe IAE (0112) (**)
10 | 21 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Modalidad aplicable "0" no consta "N" 1  o "S" 2 [0113)
11 | 22 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Criterio cobros/pagos. "1" o cero. (0114)
12 | 23 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Cesión derechos de autor. "1" o cero. (0115)
13 | 24 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Explotación (0116)
14 | 37 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Otros ingresos (0117)
15 | 50 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Autoconsumo bienes/servicios (0118)
16 | 63 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Transmisión elementos patrimoniales: exceso amortización deducida (0119)
17 | 76 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Total ingresos computables (0120)
18 | 89 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Consumos de explotación (0121)
19 | 102 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Sueldos y salarios (0122)
20 | 115 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Seguridad Social (0123)
21 | 128 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros gastos de personal (0124)
22 | 141 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Gastos de manutención del contribuyente (0125)
23 | 154 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Arrendamientos y cánones (0126)
24 | 167 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Reparación y conservación (0127)
25 | 180 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Servicios profesionales independientes (0128)
26 | 193 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Suministros (0129)
27 | 206 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros servicios exteriores (0130]
28 | 219 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Tributos fiscalmente deducibles (0131)
29 | 232 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Gastos financieros (0132)
30 | 245 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Amortizaciones (0133)
31 | 258 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Pérdidas por insolvencia de deudores  (0134)
32 | 271 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Mecenazgo (convenios) (0135)
33 | 284 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Mecenazgo (gastos) (0136)
34 | 297 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros conceptos fiscalmente deducibles (0137)
35 | 310 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Suma  (0138)
36 | 323 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Normal - Provisiones (0139)
37 | 336 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Normal - Total gastos deducibles (0140)
38 | 349 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Simplificada - Diferencia (0141)
39 | 362 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (0142)
40 | 375 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Simplificada - Total gastos deducibles (0143)
41 | 388 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad - Rdto. neto (0144)
42 | 401 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad - Reducciones (0145)
43 | 414 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad - Rdto. neto reducido (0146)
44 | 427 | 13 | N |  | Rdto.actv.econ.est.directa - Suma de rendimientos netos reducidos  (0147)
45 | 440 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción ejercicio determinadas actividades económicas  (artículo 32.2.1º) (0148)
46 | 453 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción ejercicio determinadas actividades económicas (artículo 32.2.3º) (0149)
47 | 466 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción por inicio de una actividad económica (0150)
48 | 479 | 13 | N |  | Rdto.actv.econ.est.directa - Rendimiento neto reducido total actividades económicas en estimación directa (0155)
49 | 492 | 600 | An |  | RESERVADO PARA LA A.E.A.T
50 | 1092 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10006000>
Total: |  | 1103
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignarán las tres cifras seguidas de dos blancos.

# 100-07

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "07000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (E2) Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Contribuyente titular actividad   "0" a "9" (0156)
8 | 15 | 5 | An | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Clasificación IAE (0157) (**)
9 | 20 | 1 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (0158)
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
31 | 329 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma)  (0159)
32 | 342 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo  (0160)
33 | 355 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (0161)
34 | 368 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (0162)
35 | 381 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (0163)
36 | 385 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (0164)
37 | 389 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (0165)
38 | 393 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (0166)
39 | 397 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (0167)
40 | 401 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto de módulos (0168)
41 | 414 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción de carácter general (0169)
42 | 427 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (0170)
43 | 440 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Gastos extraordinarios circunstancias  excepcionales (0171)
44 | 453 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Otras percepciones empresariales (0172)
45 | 466 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª -Rendimiento neto actividad (0173)
46 | 479 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción rdtos. más de 2 años o forma irregular (0174)
47 | 492 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rendimiento neto reducido (0175)
48 | 505 | 13 | N |  | Rdtos.activ.económ.est.objetiva -  Suma rendimientos netos reducidos de las actividades económicas (0176)
49 | 518 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Reducción por el ejercicio determinadas actividades económicas (0177)
50 | 531 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas (0180)
51 | 544 | 600 | An |  | RESERVADO PARA LA A.E.A.T
52 | 1144 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10007000>
Total: |  | 1155
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos blancos.

# 100-08

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "08000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (E3) Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Contribuyente titular de actividad: de "0" a "9"  (0181)
8 | 15 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Clave actividad: de "0" a "9" (0182)
9 | 16 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Criterio cobros/pagos:  "1" ó "0" (0183)
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
58 | 465 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Total  ingresos íntegros (0184)
59 | 476 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto previo (suma) (0185)
60 | 487 | 11 | N | C | RESERVADO PARA LA A.E.A.T
61 | 498 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Amortización inmovilizado (0186)
62 | 509 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto minorado  (0187)
63 | 520 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Medios de producción ajenos (2 enteros y 2 decimales) [0188]
64 | 524 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Utilización personal asalariado (2 enteros y 2 decimales) (0189)
65 | 528 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.-Cultivos tierras arrendadas (2 enteros y 2 decimales) (0190)
66 | 532 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (0191) Ver NOTA
67 | 536 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 2 (0191) Ver NOTA
68 | 540 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Actividades agricultura ecológica (2 enteros y dos decimales)  (0192)
69 | 544 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Cultivo en tierras regadío utilice energía electrica ( 2 enteros y 2 decimales) (0193)
70 | 548 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales)  (0194)
71 | 552 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Ind. correct.- Determinadas actividades forestales  (2 enteros y 2 decimales)  (0195)
72 | 556 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rdto. neto de módulos (0196)
73 | 569 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción carácter general (0197)
74 | 582 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Diferencia (0198)
75 | 595 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducción agricultores jóvenes (0199)
76 | 608 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Gastos extraordinarios por circunstancias excepcionales (0200)
77 | 621 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto  (0201)
78 | 634 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Reducciones rendimientos generados más 2 años o forma irregular (0202)
79 | 647 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Activ 1ª - Rendimiento neto reducido (0203)
80 | 660 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Suma rendimientos netos reducidos de las actividades agrícolas, ganaderas y forestales en estimación objetiva  (0204)
81 | 673 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva -  Reducción por ejercicio determinadas actividades económicas (0205)
82 | 686 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total de las actividades agrícolas, ganaderas y forestales en estimación objetiva  (0206)
83 | 699 | 600 | An |  | RESERVADO PARA LA A.E.A.T
84 | 1299 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10008000>
Total: |  | 1310
 |  |  |  |  | NOTA: Cumplimentar sólo cuando el índice 2 sea distinto al índice 1.

# 100-09

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "09000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (F) Regs. especiales - Régimen atribución rentas - Entidad - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (0208)
8 | 15 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Entidad - Entidades y contribuyentes partícipes - NIF Entidad (0209)
9 | 35 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país (0210)
10 | 36 | 4 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad - Entidades y contribuyentes partícipes - Porcentaje participación  (2 enteros y dos decimales) (0211)
11 | 40 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (0212)
12 | 53 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Minoraciones  aplicables (0213)
13 | 66 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones aplicables (0214)
14 | 79 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro . Rdto. neto computable (0215)
15 | 92 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Neto atribuido por la entidad . Imp. computable (0216)
16 | 105 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Derivado valores deuda subordinada o partic. preferentes (0217)
17 | 118 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Rdto. neto atribuido (0218)
18 | 131 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Minoraciones aplicables (0219)
19 | 144 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Reducciones aplicables 23.2 (0220)
20 | 157 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Reducciones aplicables 23.3 y DT 25 (0221)
21 | 170 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Rdto. neto computable (0222)
22 | 183 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Criterio cobros/pagos. "1" o cero (0223)
23 | 184 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Rendimiento neto (0224)
24 | 197 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Minoraciones aplicables (0225)
25 | 210 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Provisiones deducibles y gastos difícil justificación (0226)
26 | 223 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Reducción aplicable art.32.1 y DT 25 (0227)
27 | 236 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Reducción aplicable art.32.2.3 (0228)
28 | 249 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Reducción aplicable art.32.3 (0229)
29 | 262 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Rdto. Neto computable (0230)
30 | 275 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas  patrimoniales - No derivadas transmisiones - Ganancias patrimoniales no derivadas de transmisiones, atribuidas por la entidad (0231)
31 | 288 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - No derivadas transmisiones - Pérdidas patrimoniales no derivadas de transmisiones, atribuidas por la entidad (0232)
32 | 301 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales (0233)
33 | 314 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión destinado a constituir renta vitalicia (0234)
34 | 327 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión al que resulta aplicable (0235)
35 | 340 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas 50 por 100 (sólo determinados inmuebles urbanos) (0236)
36 | 353 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas reinversión rentas vitalicias (0237)
37 | 366 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancia exenta reinversión en entidades de nueva o reciente creación (0238)
38 | 379 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Parte ganancias susceptibles reducción  (0239)
39 | 392 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Reducciones aplicables  (0240)
40 | 405 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas  (0241)
41 | 418 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas imputable 2017  (0242)
42 | 431 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad  (0243)
43 | 444 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución de retenciones e ingresos a cuenta -  Retenciones e ingresos a cuenta atribuidos por la entidad (0244)
44 | 457 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos netos de capital mobiliario (a integrar en la BI general) atribuidos (0245)
45 | 470 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos netos de capital mobiliario (a integrar en la BI del ahorrol) atribuidos (0246)
46 | 483 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos derivados de valores de deuda subordinada o participaciones preferentes (BI del ahorro) atribuidos (0247)
47 | 496 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos netos del capital mobiliario atribuidos (0248)
48 | 509 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de rendimientos netos de actividades económicas atribuidos (0249)
49 | 522 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de ganancias patrimoniales no derivadas de transmisiones (a integrar en la BI general) atribuidas (0250)
50 | 535 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de pérdidas patrimoniales no derivadas de transmisiones (a integrar en la BI general) atribuidas (0251)
51 | 548 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de ganancias patrimoniales derivadas de transmisiones (a integrar en la BI del ahorro) atribuidas (0252)
52 | 561 | 13 | N |  | Regs. especiales - Régimen atribución rentas -  Suma de pérdidas patrimoniales derivadas de transmisiones (a integrar en la BI del ahorro) atribuidas (0253)
53 | 574 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de retenciones e ingresos atribuidos (0600)
54 | 587 | 600 | An |  | RESERVADO PARA LA A.E.A.T
55 | 1187 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10009000>
Total: |  | 1198

# 100-10

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "10000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (F) Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1-  Entidades y contribuyentes socios. Contribuyente "0" a "9" (0256)
8 | 15 | 9 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1-  Entidades y contribuyentes socios. N.I.F. Entidad (0257)
9 | 24 | 1 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (0258)
10 | 25 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Base imponible imputada  (0259)
11 | 38 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones inversión empresarial (0260)
12 | 51 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones creación empleo (0261)
13 | 64 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deduccciones rentas Ceuta/Melilla (0262)
14 | 77 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones doble imposición internacional. (0263)
15 | 90 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones retenciones e ingresos a cuenta  - Retenciones e ingresos a cuenta imputados (0264)
16 | 103 | 13 | N |  | Regs. especiales - Agrupaciones interés económico y UTES - Suma de bases imponibles imputadas  (0265)
17 | 116 | 13 | N |  | Regs. especiales - Agrupaciones interés económico y UTES - Suma de retenciones e ingresos a cuenta imputados (0601)
18 | 129 | 1 | Tit | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Contribuyente  "0" a "9" (0267)
19 | 130 | 24 | An | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Denominación entidad no residente (0268)
20 | 154 | 13 | N | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Importe imputación  (0269)
21 | 167 | 13 | N |  | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Suma imputaciones de rentas transparencia fiscal internacional (0270)
22 | 180 | 1 | Tit | C | Regs. especiales - Imputación rentas cesión derechos imagen - Contribuyente que debe efectuar la imputacion.  "0" a "9" (0271)
23 | 181 | 25 | An | C | Regs. especiales - Imputación rentas cesión derechos imagen - NIF o denominación persona/entidad cesionaria derechos imagen (0272)
24 | 206 | 25 | An | C | Regs. especiales - Imputación rentas cesión derechos imagen - NIF o denominación persona/entidad relación laboral (0273)
25 | 231 | 13 | N | C | Regs. especiales - Imputación rentas cesión derechos imagen - Cantidad a imputar  (0274)
26 | 244 | 13 | N |  | Regs. especiales - Imputación rentas cesión derechos imagen - Suma imputaciones de rentas por cesión derechos de imagen (0275)
27 | 257 | 1 | Tit | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Contribuyente  "0" a "9" (0276)
28 | 258 | 24 | An | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Denominación Institución (0277)
29 | 282 | 13 | N | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Importe imputación (0278)
30 | 295 | 13 | N |  | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales -Suma de imputaciones de rentas por participación en IIC (0280)
31 | 308 | 1 | Tit | C | (G1) Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Contribuyente  que obtiene los premios   "0" a "9" (0281)
32 | 309 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En metálico - Importe (0282)
33 | 322 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Valoración (0283)
34 | 335 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta (0284)
35 | 348 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta repercutidos (0285)
36 | 361 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Importe computable (0286)
37 | 374 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Pérdidas patrimoniales derivadas de estos juegos (0287)
38 | 387 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de ganancias patrimoniales derivadas de estos juegos (0288)
39 | 400 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de pérdidas patrimoniales derivadas de estos juegos (0289)
40 | 413 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de ganancias patrimoniales netas derivadas de estos juegos (0290)
41 | 426 | 1 | Tit | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - Contribuyente que obtiene los premios. "0" a "9" (0291)
42 | 427 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En metálico - Importe (0292)
43 | 440 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Valoración (0293)
44 | 453 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta (0294)
45 | 466 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta repercutidos (0295)
46 | 479 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Importe computable (0296)
47 | 492 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - Suma de ganancias patrimoniales derivadas de premios (0297)
48 | 505 | 1 | Tit | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Contribuyente que obtiene otras ganancias/pérdidas. "0" a "9" (0298)
49 | 506 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Subvenciones adquisición vivienda (0299)
50 | 519 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Otras subvenciones o ayudas (0300)
51 | 532 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Demás ganancias patrimoniales derivadas de ayudas públicas (0301)
52 | 545 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Ganancias patrimoniales vecinos por aprovechamientos forestales (0302)
53 | 558 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Renta básica emancipación (0303)
54 | 571 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas -  Importe ganancias (0304)
55 | 584 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe pérdidas (0305)
56 | 597 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Suma de otras ganancias que no derivan de la transmisión (0306)
57 | 610 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Suma de otras pérdidas que no derivan de la transmisión (0307)
58 | 623 | 600 | An |  | RESERVADO PARA LA A.E.A.T
59 | 1223 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10010000>
Total: |  | 1234

# 100-11

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "11000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 15 | 1 | Tit | C | (G2) Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente "0" a "9" [0308]
8 | 16 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente - Valor total acumulado [0309]
9 | 29 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Inst. inv. Colectiva o SOCIMI- Sociedad/Fondo - Contribuyente "0" a "9" (0310)
10 | 30 | 9 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo - N.I.F. (0311)
11 | 39 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo -  Importe global transmisiones (0312)
12 | 52 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo - Importe global transmisiones -  Valor transmisión para renta vitalicia (0313)
13 | 65 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo - Importe global transmisiones -  Valor transmisión aplicable D.T.9ª (0314)
14 | 78 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo - Importe global adquisiciones (0315)
15 | 91 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados -  Sociedad/Fondo -Ganancias patrimoniales (0316)
16 | 104 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados - Sociedad/Fondo -Ganancias exentas reinversión rentas vitalicias (0317)
17 | 117 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados  - Sociedad/Fondo - Parte ganancias suceptible reducción (0318)
18 | 130 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados -Sociedad/Fondo - Reducción aplicable (0319)
19 | 143 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados - Sociedad/Fondo - Ganancias patrimoniales reducidas no exentas (0320)
20 | 156 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados - Sociedad/Fondo - Pérdidas patrimoniales (0321)
21 | 169 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados - Sociedad/Fondo - Pérdidas patrimoniales imputables a 2017 (0322)
22 | 182 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. Colectiva - Suma de ganancias patrimoniales de transmisiones o reembolsos acciones o participaciones Inst.Inv.Colectiva o SOCIMI (0324)
23 | 195 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. Colectiva - Suma de pérdidas patrimoniales de transmisiones o reembolsos acciones o participaciones Inst.Inv.Colectiva o SOCIMI (0325)
24 | 208 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
25 | 211 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones - Entidad -  Contribuyente valores transmitidos "0" a "9" (0326)
26 | 212 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones - Entidad - Denominación valores (0327)
27 | 232 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones  - Entidad - Importe global efectuadas en 2017 (0328)
28 | 245 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones - Entidad - Importe global efectuadas en 2017 - Valor transmisión a constituir en renta vitalicia  (0329)
29 | 258 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones - Entidad - Importe global efectuadas en 2017 - Valor transmisión aplicable D.T.9ª (0330)
30 | 271 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Valor adquisición global (0331)
31 | 284 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados -  Ganancias patrimoniales (0332)
32 | 297 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0333)
33 | 310 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0334)
34 | 323 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Reducción aplicable (0335)
35 | 336 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Ganancias patrimoniales no exentas (0336)
36 | 349 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Pérdidas patrim. Importe obtenido (0337)
37 | 362 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Pérdidas patrim. Importe computable (0338)
38 | 375 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Suma de ganancias patrimoniales derivadas de transmisiones de acciones  negociadas (0339)
39 | 388 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Suma de pérdidas patrimoniales derivadas de transmisiones de acciones  negociadas (0340)
40 | 401 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
41 | 404 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad - Contribuyente valores transmitidos "0" a "9" (0341)
42 | 405 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad - Denominación valores (0342)
43 | 425 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción  - Entidad - Importe global efectuadas en 2018 (0343)
44 | 438 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad - Importe global efectuadas en 2018 - Valor transmisión a constituir en renta vitalicia  (0344)
45 | 451 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad - Importe global efectuadas en 2018 - Valor transmisión aplicable D.T.9ª (0345)
46 | 464 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Valor adquisición global (0346)
47 | 477 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados -  Ganancias patrimoniales (0347)
48 | 490 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0348)
49 | 503 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0349)
50 | 516 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Reducción aplicable (0350)
51 | 529 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Ganancias patrimoniales no exentas (0351)
52 | 542 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Pérdidas patrim. Importe obtenido (0352)
53 | 555 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Pérdidas patrim. Importe computable (0353)
54 | 568 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Suma de ganancias patrimoniales derivadas de transmisiones de derechos de suscripción (0354)
55 | 581 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Suma de pérdidas patrimoniales derivadas de transmisiones de derechos de suscripción (0355)
56 | 594 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
57 | 597 | 600 | An |  | RESERVADO PARA LA A.E.A.T
58 | 1197 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10011000>
Total: |  | 1208

# 100-12

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "12000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 2 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 15 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (0356)
8 | 16 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (0358)
9 | 17 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -  Inmuebles. Situación. Clave "0" a "5" (0359)
10 | 18 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -   Inmuebles. Situación. Ref. catastral (0360)
11 | 38 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha transmisión (0361)
12 | 46 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha adquisición (0362)
13 | 54 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión (0363)
14 | 67 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Constituir renta vitalicia (0364)
15 | 80 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - De la vivienda habitual (0365)
16 | 93 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Susceptible de reducción (0366)
17 | 106 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor adquisición (0367)
18 | 119 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (0368)
19 | 132 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (0369)
20 | 145 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (0370)
21 | 158 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta 50 por 100 (0371)
22 | 171 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en rentas vitalicias (0372)
23 | 184 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en vivienda habitual (0373)
24 | 197 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en entidades de nueva o reciente creación (0374)
25 | 210 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia no exenta (0375)
26 | 223 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Parte ganancia susceptible reducción  (0376)
27 | 236 | 4 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Nº años permanencia hasta 31/12/1994  (0377)
28 | 240 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Reducción aplicable (0378)
29 | 253 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida (0379)
30 | 266 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida  no exenta  (0380)
31 | 279 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Parte ganancia susceptible reducción  (0381)
32 | 292 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Reducción licencia autotaxis  (0382)
33 | 305 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida (0383)
34 | 318 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida no exenta  (0384)
35 | 331 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (0357)
36 | 332 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de pérdidas patrimoniales derivadas de transmisiones de otros elementos patrimoniales (0385)
37 | 345 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de ganancias patrimoniales derivadas de transmisiones de otros elementos patrimoniales no afectos a actividades económicas (0386)
38 | 358 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de ganancias patrimoniales derivadas de transmisiones de otros elementos patrimoniales afectos a actividades económicas (0387)
39 | 371 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
40 | 374 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Contribuyente "0" a "9" (0388)
41 | 375 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Otras ganancias BI ahorro (0389)
42 | 388 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Suma de otras ganancias BI ahorro (0390)
43 | 401 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2018. Ganancias/pérdidas ejercicios anteriores - Ganancia 1 -  Contribuyente "0" a "9" (0391)
44 | 402 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2018. Ganancias/pérdidas ejercicios anteriores - Ganancia 1 -  Importe a imputar (0392)
45 | 415 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2018. Ganancias/pérdidas ejercicios anteriores - Ganancia 1 -  Importe a imputar  - Total (0393)
46 | 428 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2018. Ganancias/pérdidas ejercicios anteriores - Pérdida  1 -  Contribuyente "0" a "9" (0394)
47 | 429 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2018. Ganancias/pérdidas ejercicios anteriores - Pérdida  1 -  Importe pérdida a imputar (0395)
48 | 442 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2018. Ganancias/pérdidas ejercicios anteriores -  Importe pérdida a imputar - Total  (0396)
49 | 455 | 600 | An |  | RESERVADO PARA LA A.E.A.T
50 | 1055 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10012000>
Total: |  | 1066

# 100-13

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "13000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Num |  | RESERVADO PARA LA A.E.A.T
7 | 14 | 1 | Tit | C | (G3) Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2018 diferimiento por reinversión - Ganancia - Contribuyente "0" a "9" (0398)
8 | 15 | 13 | N | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2018 diferimiento por reinversión - Ganancia - Importe ganancia (0399)
9 | 28 | 13 | N |  | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2018 diferimiento por reinversión - Suma de imputación a 2018 ganancias patrimoniales acogidas a diferimiento por reinversión (0400)
10 | 41 | 1 | Num | C | (G4) Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Contribuyente que ha transmitido intervivos las acciones "1" o "0" (0401)
11 | 42 | 1 | Tit | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Contribuyente titular valores "0" a "9" (0402)
12 | 43 | 9 | An | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Nif sociedad emisora o fondo de inversión (0403)
13 | 52 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Valor de mercado  acciones/participaciones (0404)
14 | 65 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Valor transmisión acciones (0405)
15 | 78 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Valor al que resulta aplicable D.T.9ª (0406)
16 | 91 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Valor adquisición (0407)
17 | 104 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Resultados - Ganancias patrimoniales (0408)
18 | 117 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Resultados - Ganancias suceptibles reducción (0409)
19 | 130 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Resultados - Reducción aplicable (0410)
20 | 143 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Resultados - Ganancias patrimoniales reducidas (0411)
21 | 156 | 13 | N |  | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Suma de ganancias patrimoniales por cambio de residencia fuera del territorio español (0412)
22 | 169 | 1 | Tit |  | (G5) Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (0413)
23 | 170 | 2 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España -  Número de operaciones1 (0414)
24 | 172 | 1 | Tit |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente 2   "0" a "9" (0415)
25 | 173 | 2 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones 2 (0416)
26 | 175 | 1 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Si entidades no residentes no han aplicado régimen fiscal similar a éste  (0417)
27 | 176 | 13 | N |  | (G6) Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2018 - A integrar en base imponible general -  Suma ganancias (0418)
28 | 189 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2018 - A integrar base imponible general -  Suma pérdidas (0419)
29 | 202 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2018 - A integrar base imponible general -  Saldo neto - Diferencia positiva (0420)
30 | 215 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2018 - A integrar base imponible general -  Saldo neto - Diferencia negativa (0421)
31 | 228 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2018 - A integrar base imponible ahorro - Suma ganancias (0422)
32 | 241 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2018 - A integrar base imponible ahorro - Suma pérdidas (0423)
33 | 254 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2018 - A integrar base imponible ahorro - Saldo neto  - Diferencia positiva (0424)
34 | 267 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2018 - A integrar base imponible ahorro - Saldo neto - Diferencia negativa (0425)
35 | 280 | 13 | N |  | Integración y compensación de rentas - Integración y compensación rdtos. capital mobiliario imputables 2018 a integrar B.I. ahorro - Saldo neto positivo rdto. capital mobiliario (0429)
36 | 293 | 13 | N |  | Integración y compensación de rentas - Integración y compensación rdtos. capital mobiliario imputables 2018 a integrar B.I. ahorro - Saldo neto negativo rdto. capital mobiliario (0430)
37 | 306 | 13 | N |  | (H) Base imponible general y base imponible ahorro - BI general - Saldo neto positivo ganancias/pérdidas 2018 a integrar base imponible general (0420)
38 | 319 | 13 | N |  | Base imponible general y base imponible ahorro - BI general - Compensación - Saldos netos negativos ganancias/pérdidas 2014 a 2017  pendientes compensasión (0431)
39 | 332 | 13 | N |  | Base imponible general y base imponible ahorro - BI general - Saldos neto rendimientos a integrar en base Imponible general (0432)
40 | 345 | 13 | N |  | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Saldo neto negativo ganancias/pérdidas 2018 (0433)
41 | 358 | 13 | N |  | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Resto saldos netos negativos ganancias/pérdidas 2014 a 2017 pendientes compensación (0434)
42 | 371 | 13 | N |  | Base imponible general y base imponible ahorro - BI general -  Base imponible general (0435)
43 | 384 | 600 | An |  | RESERVADO PARA LA A.E.A.T
44 | 984 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10013000>
Total: |  | 995

# 100-14

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "14000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas  (0424)
7 | 26 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro -  Compensaciones - Saldos netos negativos rendimientos capital mobiliario  (0436)
8 | 39 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas no derivadas transmisión de deuda subordinada o preferentes 2014 (0437)
9 | 52 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas derivadas transmisión de deuda subordinada o preferentes 2014 (0438)
10 | 65 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2015 pendientes compensación (0439)
11 | 78 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2016 pendientes compensación (0440)
12 | 91 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2017 pendientes compensación (0441)
13 | 104 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario de deuda subordinada o preferentes 2014 (0442)
14 | 117 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2015 pendiente compensación (0443)
15 | 130 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2016 pendiente compensación (0444)
16 | 143 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2017 pendiente compensación (0445)
17 | 156 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimientos capital mobiliario a integrar en BI ahorro (0429)
18 | 169 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro -  Compensaciones -  Saldos netos negativos ganancias/pérdidas (0446)
19 | 182 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario que no derive deuda o participaciones preferentes 2014 (0447)
20 | 195 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario que derive deuda o participaciones preferentes 2014 (0448)
21 | 208 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2015 pendientes compensación (0449)
22 | 221 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2016 pendientes compensación (0450)
23 | 234 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2017 pendientes compensación (0451)
24 | 247 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos de ganancias/pérdidas deuda subordinada o participaciones preferentes 2014 (0452)
25 | 260 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2015 pendientes compensación (0453)
26 | 273 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2016 pendientes compensación (0454)
27 | 286 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2017 pendientes compensación (0455)
28 | 299 | 13 | N |  | Base imponible general y base imponible ahorro - BI ahorro - Base imponible del ahorro (0460)
29 | 312 | 13 | N |  | (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidades familiares tributación conjunta (0461)
30 | 325 | 1 | Tit | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente "0" a "9"  (0462)
31 | 326 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 a 2017 (0463)
32 | 339 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 a 2017 de contribuciones a seguros colectivos de dependencia (0464)
33 | 352 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones (0465)
34 | 365 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuciones a seguros colectivos de dependencia (0466)
35 | 378 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción (0467)
36 | 391 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total con derecho a reducción (0468)
37 | 404 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones sistemas previsión social cónyuge del contribuyente - Total con derecho a reducción (0469)
38 | 417 | 2 | Num |  | RESERVADO PARA LA A.E.A.T
39 | 419 | 1 | Tit | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Contribuyente "0" a "9" (0470)
40 | 420 | 9 | An | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - NIF persona con discapacidad (0471)
41 | 429 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones por la persona con discapacidad. Excesos pendientes reducir (0472)
42 | 442 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones a favor de parientes. Excesos pendientes reducir (0473)
43 | 455 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones 2018 propia persona con discapacidad (0474)
44 | 468 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones 2018 parientes o tutores (0475)
45 | 481 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Total con derecho a reducción (0476)
46 | 494 | 600 | An |  | RESERVADO PARA LA A.E.A.T
47 | 1094 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10014000>
Total: |  | 1105

# 100-15

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "15000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente "0" a "9" (0477)
7 | 14 | 9 | An | C | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad (0478)
8 | 23 | 13 | N | C | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir (0479)
9 | 36 | 13 | N | C | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones (0480)
10 | 49 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Total con derecho a reducción (0481)
11 | 62 | 1 | Tit | C | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos -  Contribuyente "0" a "9" (0482)
12 | 63 | 20 | An | C | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad (0483)
13 | 83 | 1 | Num | C | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si ha consignado NIF de otro país 1 (431) "1" o "0" (0484)
14 | 84 | 13 | N | C | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial (0485)
15 | 97 | 13 | N |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Total derecho reducción (0486)
16 | 110 | 1 | Tit | C | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente "0" a "9" (0487)
17 | 111 | 13 | N | C | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales -  Excesos pendientes reducir (0488)
18 | 124 | 13 | N | C | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones (0489)
19 | 137 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Total con derecho a reducción (0490)
20 | 150 | 13 | N |  | (J) Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base imponible general (0435)
21 | 163 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Tributación conjunta (0491)
22 | 176 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social (régimen general) (0492)
23 | 189 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social cónyuge (0493)
24 | 202 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social personas discapacidad (0494)
25 | 215 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones patrimonios protegidos personas discapacidad (0495)
26 | 228 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Pensiones compensatorias/anualidades alimentos (0496)
27 | 241 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones mutualidades prev. soc. deportistas profesionales (0497)
28 | 254 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general (0500)
29 | 267 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Compensación bases liquidables generales negativas (0501)
30 | 280 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general sometida a gravamen (0505)
31 | 293 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base imponible ahorro (0460)
32 | 306 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción tributación conjunta (0506)
33 | 319 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción pensiones comp./anualidades alimentos (0507)
34 | 332 | 13 | N |  | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base liquidable del ahorro (0510)
35 | 345 | 13 | N |  | (K) Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe parte estatal (0511)
36 | 358 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe parte autonómica (0512)
37 | 371 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe parte estatal  (0513)
38 | 384 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe parte autonómica (0514)
39 | 397 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe  parte estatal (0515)
40 | 410 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe parte autonómica (0516)
41 | 423 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe parte estatal (0517)
42 | 436 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe parte autonómica (0518)
43 | 449 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo personal y familiar parte estatala (0519)
44 | 462 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe total cálculo gravamen autonómico (0520)
45 | 475 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen estatal  (0521)
46 | 488 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen estatal (0522)
47 | 501 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general  - gravamen autonómico (0523)
48 | 514 | 13 | N |  | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen autonómico (0524)
49 | 527 | 13 | An |  | RESERVADO PARA LA A.E.A.T
50 | 540 | 587 | An |  | RESERVADO PARA LA A.E.A.T
51 | 1127 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10015000>
Total: |  | 1138

# 100-16

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "16000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (L) Datos adicionales - Rentas exentas excepto para determinar gravamen. Base liquidable general (0525)
7 | 26 | 13 | N | Datos adicionales - Rentas exentas excepto para determinar gravamen. Base liquidable ahorro (0526)
8 | 39 | 13 | N | Datos adicionales - Anualidades para alimentos a favor de los hijos. Importe (0527)
9 | 52 | 13 | N | (N) Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla (0505) - Parte estatal (0528)
10 | 65 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del  Impuesto importe casilla (0505) - Parte autonómica (0529)
11 | 78 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general del Impuesto importe casilla (0521) - Parte estatal (0530)
12 | 91 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala autonómica del Impuesto importe casilla (0523) - Parte autonómica (0531)
13 | 104 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte estatal (0532)
14 | 117 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte autonómica (0533)
15 | 130 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medios gravamen - Parte estatal (0534)
16 | 134 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medios gravamen - Parte autonómica (0535)
17 | 138 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla (0510) - Parte estatal (0536)
18 | 151 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla (0510) - Parte autonómica (0537)
19 | 164 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general del lmpuesto importe casilla (0522) - Parte estatal (0538)
20 | 177 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala autonómica del Impuesto importe casilla (0524) - Parte autonómica (0539)
21 | 190 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte estatal (0540)
22 | 203 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte autonómica  (0541)
23 | 216 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medios gravamen - Parte estatal (0542)
24 | 220 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medios gravamen - Parte autonómica (0543)
25 | 224 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra estatal - Parte estatal (0545)
26 | 237 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra autonómica - Parte autonómica (0546)
27 | 250 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte estatal (0547)
28 | 263 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte autonómica (0548)
29 | 276 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión empresas nueva o reciente creación - Parte estatal (0549)
30 | 289 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte estatal (0550)
31 | 302 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte autonómica (0551)
32 | 315 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones- Parte estatal (0552)
33 | 328 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones - Parte autonómica (0553)
34 | 341 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte estatal (0554)
35 | 354 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte autonómica (0555)
36 | 367 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte estatal (0556)
37 | 380 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte autonómica (0557)
38 | 393 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte estatal (0558)
39 | 406 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte autonómica (0559)
40 | 419 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte estatal (0560)
41 | 432 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte autonómica (0561)
42 | 445 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte estatal (0562)
43 | 458 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte autonómica (0563)
44 | 471 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - Suma deducciones autonómicas (0564)
45 | 484 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducción  por unidades familiares formadas por residentes en la UE. Parte estatal (0565)
46 | 497 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducción  por unidades familiares formadas por residentes en la UE - Parte autonómica (0566)
47 | 510 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida estatal - Parte estatal (0570)
48 | 523 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida autonómica - Parte autonómica (0571)
49 | 536 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - Parte estatal (0572]
50 | 549 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - Parte estatal (0573)
51 | 562 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2017 - Importe - Parte estatal (0574)
52 | 575 | 1 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2017 - Regularización motivada por DA 45. "1" o "0" (0575)
53 | 576 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2017 - Intereses demora -  Parte estatal (0576)
54 | 589 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2017 - Importe - Parte autonómica (0577)
55 | 602 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2017 - Intereses demora - Parte autonómica (0578)
56 | 615 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2017 - Importe - Parte autonómica (0579)
57 | 628 | 1 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2017 - Regularización motivada por  DA 45. "1" o "0" (0580)
58 | 629 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2017 - Intereses demora - Parte autonómica (0581)
59 | 642 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida estatal incrementada - Parte estatal (0585)
60 | 655 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida autonómica incrementada - Parte autonómica (0586)
61 | 668 | 600 | An | RESERVADO PARA LA A.E.A.T
62 | 1268 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10016000>
Total: |  | 1279

# 100-17

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "17000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N |  | Cálculo impuesto y resultado declaración - Cuota resultante autoliquidación - Cuota líquida incrementada total (0587)
7 | 26 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Deducciones: Por doble imposición internacional, rentas obtenidas y gravadas en el extranjero (0588)
8 | 39 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Deducciones: Por doble imposición internacional supuestos aplicación régimen transparencia fiscal internacional (0589)
9 | 52 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Deducciones: Por doble imposición supuestos aplicación régimen imputación rentas cesión derechos imagen (0590)
10 | 65 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Retenciones deducibles rendimientos bonificados - Importe retenciones no practicadas (0591)
11 | 78 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota resultante autoliquidación - Cuota resultante autoliquidación (0595)
12 | 91 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Rendimientos del trabajo (0596)
13 | 104 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Rendimientos del capital mobiliario (0597)
14 | 117 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Arrendamientos de inmuebles urbanos (0598)
15 | 130 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Rendimientos de actividades económicas (0599)
16 | 143 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Atribuidos por entidades en régimen de atribución de rentas (0600)
17 | 156 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Imputados por agrupaciones de interés económico y UTE's (0601)
18 | 169 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Ingresos a cuenta art. 92.8 Ley del Impuesto (0602)
19 | 182 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Ganancias patrimoniales, incluidos premios (0603)
20 | 195 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Pagos fraccionados (actividades económicas) (0604)
21 | 208 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Cuotas del Impuesto sobre la Renta de no Residentes (0605)
22 | 221 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Retenciones art. 11  Directiva 2003/48/CE (0606)
23 | 234 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Total pagos a cuenta (0609)
24 | 247 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Cuota diferencial (0610)
25 | 260 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción por maternidad - Importe deducción (0611)
26 | 273 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción por maternidad - Importe abono anticipado deducción (0612)
27 | 286 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción por maternidad - Incremento por gastos de guarderías  (0613)
28 | 299 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF descendiente (0614)
29 | 308 | 15 | A | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Nombre (0615)
30 | 323 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (0616)
31 | 331 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (0617)
32 | 339 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Nº personas derecho mínimo (0618)
33 | 341 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Se ha cedido el derecho deducción (0619) |  | "0" - blanco, "1" - Si,    "2" .- No
34 | 342 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF cedente (0620)
35 | 351 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Se ha cedido el derecho deducción (0621) |  | "0" - blanco, "1" - Si,    "2" .- No
36 | 352 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF beneficiario (0622)
37 | 361 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Importe deducción (0623)
38 | 374 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Importe abono anticipado deducción (0624)
39 | 387 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF ascendiente (0625)
40 | 396 | 15 | A | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Nombre (0626)
41 | 411 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (0627)
42 | 419 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (0628)
43 | 427 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Nº personas derecho mínimo (0629)
44 | 429 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Se ha cedido el derecho deducción (0630) |  | "0" - blanco, "1" - Si,    "2" .- No
45 | 430 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad  - NIF cedente 1 (0631)
46 | 439 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF cedente 2 (0632)
47 | 448 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF cedente 3 (0633)
48 | 457 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Se ha cedido el derecho deducción (0634) |  | "0" - blanco, "1" - Si,    "2" .- No
49 | 458 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF beneficiario (0635)
50 | 467 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Importe deducción (0636)
51 | 480 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Importe abono anticipado deducción (0637)
52 | 493 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - NIF del cónyuge  (0638)
53 | 502 | 15 | A | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Nombre del cónyuge  (0639)
54 | 517 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Fecha inicio discapacidad (DDMMAAAA)(0640)
55 | 525 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Fecha fin discapacidad  (DDMMAAAA)(0641)
56 | 533 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Matrimonio vigente todo el año (0642) |  | "0" - blanco, "1" - Si,    "2" .- No
57 | 534 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Primer mes vigencia matrimonio (0643)
58 | 536 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Último mes vigencia matrimonio  (0644)
59 | 538 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado -  Importe de la deducción (0645)
60 | 551 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Importe del abono anticipado  (0646)
61 | 564 | 600 | An |  | RESERVADO PARA LA A.E.A.T
62 | 1164 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10017000>
Total: |  | 1175

# 100-18

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "18000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 30 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Nº identificación título familia numerosa (0647)
7 | 43 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Categoría familia numerosa - General (0648)
8 | 44 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Categoría familia numerosa - Especial (0649)
9 | 45 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Fecha inicio título familia numerosa (DDMMAAAA) (0650)
10 | 53 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Fecha finalización título familia numerosa (DDMMAAAA) (0651)
11 | 61 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Nº ascendientes forman parte familia numerosa  (0652)
12 | 63 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Se ha cedido el derecho deducción (0653) |  | "0" - blanco, "1" - Si,    "2" .- No
13 | 64 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 1 (0654)
14 | 73 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 2 (0655)
15 | 82 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 3 (0656)
16 | 91 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Se ha cedido el derecho deducción (0657) |  | "0" - blanco, "1" - Si,    "2" .- No
17 | 92 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF beneficiario (0658)
18 | 101 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa -Si a partir de 01/08 los hijos que forman la familia numerosa exceden del mínimo (0659) |  | "0" - No "1" - Si
19 | 102 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Importe deducción (0660)
20 | 115 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Importe abono anticipado deducción (0661)
21 | 128 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes, separado o sin vinculo matrimonial, dos hijos sin derecho anualidades alimentos - Importe deducción (0662)
22 | 141 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes, separado o sin vinculo matrimonial, dos hijos sin derecho anualidades alimentos - Importe abono anticipado deducción (0663)
23 | 154 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Regularizaciones - Importe cobro anticipado descendientes sin derecho mínimo por descendientes (0664)
24 | 167 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Regularizaciones - NIF descendientes deducción se regulariza (0665)
25 | 176 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Regularizaciones - Importe cobro anticipado ascendientes sin derecho mínimo por ascendientes (0666)
26 | 189 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Regularizaciones - NIF ascendientes deducción se regulariza (0667)
27 | 198 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Resultado declaración (0670)
28 | 211 | 13 | N |  | (N) Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2018 - Cuota líquida autonómica incrementada (0671)
29 | 224 | 13 | N |  | Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2018 -  50% deducciones doble imposición (0672)
30 | 237 | 13 | N |  | Importe  IRPF Comunidad Autónoma de residencia del contribuyente 2018 - Importe IRPF Cdad Autónoma residencia contribuyente (0675)
31 | 250 | 600 | An |  | RESERVADO PARA LA A.E.A.T
32 | 850 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10018000>
Total: |  | 861

# 100-19

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "19000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (O) Regularización - Mediante declaración complemetaria - Resultados a ingresar anteriores autoliquidaciones o liquidaciones administrativas (0676)
7 | 26 | 13 | N | Regularización - Mediante declaración complemetaria - Devoluciones acordadas Agencia Tributaria, tramitación anteriores autoliquidaciones  (0677)
8 | 39 | 13 | N | Regularización -Mediante declaración complemetaria - Resultado declaración complementaria (0680)
9 | 52 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Resultados a ingresar de autoliquidaciones o liquidaciones administrativas (0681)
10 | 65 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Devoluciones solicitadas a la Agencia Tributaria,  tramitación anteriores autoliquidaciones (0682)
11 | 78 | 13 | N | Regularización - Mediante rectificación de autoliquidación - Resultado de la solicitud de rectificación de autoliquidación (0685)
12 | 91 | 13 | Num | Regularización - Mediante rectificación de autoliquidación - Número de justificante de la autoliquidación cuya rectificación se solicita (0686)
13 | 104 | 34 | An | Número de cuenta IBAN (0687)
14 | 138 | 13 | N | P) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (0693)
15 | 151 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (0695)
16 | 164 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (0694)
17 | 177 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (0695)
18 | 190 | 34 | An | Número de cuenta IBAN (0696)
19 | 224 | 11 | An | Devolución - Código SWIFT-BIC Rectificación (0688)
20 | 235 | 11 | An | Devolución - Código SWIFT-BIC Compensación entre cónyuges (0697)
21 | 246 | 600 | An | RESERVADO PARA LA A.E.A.T
22 | 846 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10019000>
Total: |  | 857

# Anexo A.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "20000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Inversión con derecho a deducción (A)
7 | 26 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte estatal (0698)
8 | 39 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Adquisición - Importe deducción - Parte autonómica (0699)
9 | 52 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Inversión con derecho a deducción (B)
10 | 65 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte estatal (0700)
11 | 78 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Construcción - Importe deducción - Parte autonómica (0701)
12 | 91 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Inversión con derecho a deducción (C )
13 | 104 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte estatal (0702)
14 | 117 | 13 | N | Deducción por inversión en vivienda habitual - Adquisición, construcción, rehabilitación o ampliación vivienda - Rehabilitación - Importe deducción - Parte autonómica (0703)
15 | 130 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Cantidades satisfechas con derecho a deducción (E)
16 | 143 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte estatal (0704)
17 | 156 | 13 | N | Deducción por inversión en vivienda habitual - Obras e instalaciones de adecuación personas con discapacidad - Importe deducción - Parte autonómica (0705)
18 | 169 | 13 | N | Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte estatal (0547)
19 | 182 | 13 | N | Deducción por inversión en vivienda habitual - Importe total de la deducción por inversión en vivienda habitual - Parte autonómica (0548)
20 | 195 | 13 | N | Deducción por inversión en vivienda habitual - Datos adicionales - Importe de los pagos realizados en el ejercicio al promotor o constructor (0706)
21 | 208 | 9 | An | Deducción por inversión en vivienda habitual - Datos adicionales - NIF del promotor o constructor (0707)
22 | 217 | 8 | Num | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Fecha adquisición vivienda (DDMMAAAA) (0708)
23 | 225 | 20 | An | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Número de identificación del préstamo hipotecario (0709)
24 | 245 | 5 | Num | Deducción por inversión en vivienda habitual - Datos adicionales - En caso de deducción - Porcentaje del préstamo destinado a adquisición (3 enteros y 2 decimales)  (0710)
25 | 250 | 9 | An | Deducción inversiones en empresas de nueva o reciente creación - Entidad 1 - NIF (0711)
26 | 259 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Entidad 1 - Importe con derecho a deducción  (0712)
27 | 272 | 9 | An | Deducción inversiones en empresas de nueva o reciente creación - Entidad 2 - NIF (0713)
28 | 281 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Entidad 2 - Importe con derecho a deducción  (0714)
29 | 294 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Importe total deducción inversiones empresa nueva o reciente creación - Base deducción (D)
30 | 307 | 13 | N | Deducción inversiones en empresas de nueva o reciente creación - Importe total deducciones empresa nueva o reciente creación - Importe deducción (0549)
31 | 320 | 20 | An | Deducción por alquiler de la vivienda habitual - NIF del arrendador 1 (0715)
32 | 340 | 1 | Num | Deducción por alquiler de la vivienda habitual - Si ha consignado NIF de otro país (0716) "1" o ·"0"
33 | 341 | 20 | An | Deducción por alquiler de la vivienda habitual - NIF del arrendador 2 (0717)
34 | 361 | 1 | Num | Deducción por alquiler de la vivienda habitual - Si ha consignado NIF de otro país (0718) 1" o ·"0"
35 | 362 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 1 (0719)
36 | 375 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades totales satisfechas al arrendador 2 (0720)
37 | 388 | 13 | N | Deducción por alquiler de la vivienda habitual - Cantidades satisfechas con derecho a deducción (F)
38 | 401 | 13 | N | Deducción por alquiler de la vivienda habitual - Importe deducción (0721)
39 | 414 | 13 | N | Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte estatal (0562)
40 | 427 | 13 | N | Deducción por alquiler de la vivienda habitual - Deducción por alquiler - Parte autonómica (0563)
41 | 440 | 600 | An | RESERVADO PARA LA A.E.A.T
42 | 1040 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10020000>
Total: |  | 1051

# Anexo A.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "21000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones por donativos - Aportaciones actividades mecenazgo límite 15 % base liquidable - Importe con derecho a deducción (G)
7 | 26 | 13 | N | Deducciones por donativos - Aportaciones actividades mecenazgo límite 15 % base liquidable - Importe de la deducción (0722)
8 | 39 | 13 | N | Deducciones por donativos - Donativos entidades reguladas Ley 49/2002 - Importe con derecho a deducción (H)
9 | 52 | 13 | N | Deducciones por donativos - Donativos entidades reguladas Ley 49/2002 - Importe de la deducción (0723)
10 | 65 | 13 | N | Deducciones por donativos - Donativos fundaciones y asociaciones utilidad pública Ley 49/2002 - Importe con derecho a deducción (J)
11 | 78 | 13 | N | Deducciones por donativos - Donativos fundaciones y asociaciones utilidad pública Ley 49/2002 - Importe de la deducción (0724)
12 | 91 | 13 | N | Deducciones por donativos - Cuotas afiliación y aportaciones partidos políticos, federaciones, coaliciones o agrupamientos electorales - Importe con derecho a deducción (M)
13 | 104 | 13 | N | Deducciones por donativos - Cuotas afiliación y aportaciones partidos políticos, federaciones, coaliciones o agrupamientos electorales - Importe con derecho a deducción - Importe de la deducción (0725)
14 | 117 | 13 | N | Deducciones por donativos - Deducciones por donativos - Parte estatal (0552)
15 | 130 | 13 | N | Deducciones por donativos - Deducciones por donativos - Parte autonómica (0553)
16 | 143 | 13 | N | Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe con derecho a deducción (I)
17 | 156 | 13 | N | Deducción por inversiones o gastos de interés cultural - Patrimonio Histórico Español y UNESCO en España - Importe de la deducción (0726)
18 | 169 | 13 | N | Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte estatal (0550)
19 | 182 | 13 | N | Deducción por inversiones o gastos de interés cultural - Deducciones por inversiones - Parte autonómica (0551)
20 | 195 | 13 | N | Deducción por rentas obtenidas en Ceuta o Melilla - Importe total de la deducción (0727)
21 | 208 | 13 | N | Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte estatal (0560)
22 | 221 | 13 | N | Deducción por rentas obtenidas en Ceuta o Melilla - Deducción - Parte autonómica (0561)
23 | 234 | 13 | N | Deducción aplicable a las unidades familiares formadas por residentes en E.M.U.E. o E.E.E. - Cuota líquida estatal y autonómica (0728)
24 | 247 | 13 | N | Deducción aplicable a las unidades familiares formadas por residentes en E.M.U.E. o E.E.E. - Cuotas del Impuesto de la Renta de no Residentes (0729)
25 | 260 | 13 | N | Deducción aplicable a las unidades familiares formadas por residentes en E.M.U.E. o E.E.E. - Cuota líquida total (0730)
26 | 273 | 13 | N | Deducción aplicable a las unidades familiares formadas por residentes en E.M.U.E. o E.E.E. - Diferencia [0728] + [0729] - [0730] (0731)
27 | 286 | 13 | N | Deducción aplicable a las unidades familiares formadas por residentes en E.M.U.E. o E.E.E. - Deducción que corresponde al contribuyente (0732)
28 | 299 | 13 | N | Deducción aplicable a las unidades familiares formadas por residentes en E.M.U.E. o E.E.E. - Deducción - Parte estatal (0565)
29 | 312 | 13 | N | Deducción aplicable a las unidades familiares formadas por residentes en E.M.U.E. o E.E.E. -  - Deducción - Parte autonómica (0566)
30 | 325 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Importe dotaciones (0735)
31 | 338 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0736)
32 | 351 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0737)
33 | 364 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Importe dotaciones (0738)
34 | 377 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0739)
35 | 390 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0740)
36 | 403 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Pendiente de materializar (0741)
37 | 416 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Importe dotaciones (0742)
38 | 429 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0743)
39 | 442 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0744)
40 | 455 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Pendiente de materializar (0745)
41 | 468 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Importe dotaciones (0746)
42 | 481 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0747)
43 | 494 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0748)
44 | 507 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Pendiente de materializar (0749)
45 | 520 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Importe de la deducción 2018
46 | 533 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2018 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0750)
47 | 546 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2018 - Inversiones prev. letras C y D 2º. a 6º.) artº. 27.4 (0751)
48 | 559 | 600 | An | RESERVADO PARA LA A.E.A.T
49 | 1159 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10021000>
Total: |  | 1170

# Anexo A.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "22000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Saldo anterior
7 | 26 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Aplicado declaración (0752)
8 | 39 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - Deducciones rég. Gral. LIS - Pendiente aplicación
9 | 52 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interés público - Saldo anterior
10 | 65 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interés público - Aplicado declaración (0753)
11 | 78 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Ejercicios anteriores - acontecimientos interes público - Pendiente aplicación
12 | 91 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i  - Deducción
13 | 104 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i - Aplicado declaración (0754)
14 | 117 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Actv. I+D+i  - Pendiente aplicación
15 | 130 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos  - Deducción
16 | 143 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos - Aplicado declaración (0755)
17 | 156 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversiones cinematográficas, series audiovisuales y espectáculos  - Pendiente aplicación
18 | 169 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS - Deducción
19 | 182 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS -  Aplicado declaración (0756)
20 | 195 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo trabajadores con discapacidad art.º 38 LIS - Pendiente aplicación
21 | 208 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Deducción
22 | 221 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Aplicado declaración (0757)
23 | 234 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Creación empleo art.º 37 LIS - Pendiente aplicación
24 | 247 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Deducción
25 | 260 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Aplicado declaración (0758)
26 | 273 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Inversión en beneficios artº.37 TRLIS D.T. 24ª LIS - Pendiente aplicación
27 | 286 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2018" - Deducción
28 | 299 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2018" - Aplicado declaración (0759)
29 | 312 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Juegos del Mediterráneo de 2018" - Pendiente aplicación
30 | 325 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Deducción
31 | 338 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Aplicado declaración (0760)
32 | 351 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Pendiente aplicación
33 | 364 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Deducción
34 | 377 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Aplicado declaración (0761)
35 | 390 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Pendiente aplicación
36 | 403 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Deducción
37 | 416 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Aplicado declaración (0762)
38 | 429 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Cantabria 2017, Liébana Año Jubilar" - Pendiente aplicación
39 | 442 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Deducción
40 | 455 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Aplicado declaración  (0763)
41 | 468 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Programa Universo Mujer" - Pendiente aplicación
42 | 481 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Deducción
43 | 494 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Aplicado declaración (0764)
44 | 507 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge- Pendiente aplicación
45 | 520 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Deducción
46 | 533 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Aplicado declaración (0765)
47 | 546 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "Women's Hockey World league Round 3 Events 2015" - Pendiente aplicación
48 | 559 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Deducción
49 | 572 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Aplicado declaración (0766)
50 | 585 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Pendiente aplicación
51 | 598 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Deducción
52 | 611 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Aplicado declaración (0767)
53 | 624 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Pendiente aplicación
54 | 637 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Deducción
55 | 650 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Aplicado declaración (0768)
56 | 663 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Foro Iberoamericano de Ciudades- Pendiente aplicación
57 | 676 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Deducción
58 | 689 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Aplicado declaración (0769)
59 | 702 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Málaga Cultura Innovadora 2025- Pendiente aplicación
60 | 715 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Deducción
61 | 728 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Aplicado declaración (0770)
62 | 741 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos Mundo Freestyle y Snowboard Sierra Nevada 2017- Pendiente aplicación
63 | 754 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Deducción
64 | 767 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Aplicado declaración (0771)
65 | 780 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinto Aniversario Museo Thyssen-Bornemisza- Pendiente aplicación
66 | 793 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Deducción
67 | 806 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Aplicado declaración (0772)
68 | 819 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Europa Waterpolo Barcelona 2018- Pendiente aplicación
69 | 832 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Deducción
70 | 845 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Aplicado declaración (0773)
71 | 858 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario nacimiento Camilo José Cela- Pendiente aplicación
72 | 871 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Deducción
73 | 884 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Aplicado declaración (0774)
74 | 897 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Caravaca de la Cruz 2017. Año Jubilar- Pendiente aplicación
75 | 910 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Deducción
76 | 923 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Aplicado declaración (0775)
77 | 936 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo al Deporte de Base- Pendiente aplicación
78 | 949 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Deducción
79 | 962 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Aplicado declaración (0776)
80 | 975 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Pendiente aplicación
81 | 988 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Deducción
82 | 1001 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Aplicado declaración (0777)
83 | 1014 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75 Aniversario William Martin. El legado inglés- Pendiente aplicación
84 | 1027 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Deducción
85 | 1040 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Aplicado declaración (0778)
86 | 1053 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Evento Salida vuelta al mundo a vela Alicante 2017- Pendiente aplicación
87 | 1066 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Deducción
88 | 1079 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Aplicado declaración (0779)
89 | 1092 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Pendiente aplicación
90 | 1105 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Deducción
91 | 1118 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Aplicado declaración (0780)
92 | 1131 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Pendiente aplicación
93 | 1144 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Deducción
94 | 1157 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Aplicado declaración (0781)
95 | 1170 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Pendiente aplicación
96 | 1183 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Deducción
97 | 1196 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Aplicado declaración (0782)
98 | 1209 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Pendiente aplicación
99 | 1222 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Deducción
100 | 1235 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Aplicado declaración (0783)
101 | 1248 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Pendiente aplicación
102 | 1261 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Deducción
103 | 1274 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Aplicado declaración (0784)
104 | 1287 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Pendiente aplicación
105 | 1300 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Deducción
106 | 1313 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Aplicado declaración (0785)
107 | 1326 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Pendiente aplicación
108 | 1339 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Deducción
109 | 1352 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Aplicado declaración (0786)
110 | 1365 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Pendiente aplicación
111 | 1378 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Deducción
112 | 1391 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Aplicado declaración (0787)
113 | 1404 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Pendiente aplicación
114 | 1417 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Deducción
115 | 1430 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Aplicado declaración (0788)
116 | 1443 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Pendiente aplicación
117 | 1456 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Numancia 2017- Deducción
118 | 1469 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Numancia 2017- Aplicado declaración (0789)
119 | 1482 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Numancia 2017- Pendiente aplicación
120 | 1495 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - PHotoEspaña 20 aniversario- Deducción
121 | 1508 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - PHotoEspaña 20 aniversario- Aplicado declaración (0790)
122 | 1521 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - PHotoEspaña 20 aniversario- Pendiente aplicación
123 | 1534 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Deducción
124 | 1547 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Aplicado declaración (0791)
125 | 1560 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Pendiente aplicación
126 | 1573 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXX Aniversario Declaración Toledo Ciudad Patrimonio de la Humanidad- Deducción
127 | 1586 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXX Aniversario Declaración Toledo Ciudad Patrimonio de la Humanidad- Aplicado declaración (0792)
128 | 1599 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXX Aniversario Declaración Toledo Ciudad Patrimonio de la Humanidad- Pendiente aplicación
129 | 1612 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Deducción
130 | 1625 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Aplicado declaración (0793)
131 | 1638 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Pendiente aplicación
132 | 1651 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Lorca, Aula de la Historia- Deducción
133 | 1664 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Lorca, Aula de la Historia- Aplicado declaración (0794)
134 | 1677 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Lorca, Aula de la Historia- Pendiente aplicación
135 | 1690 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Deducción
136 | 1703 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Aplicado declaración (0795)
137 | 1716 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Pendiente aplicación
138 | 1729 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Deducción
139 | 1742 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Aplicado declaración (0796)
140 | 1755 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Pendiente aplicación
141 | 1768 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro- Deducción
142 | 1781 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro- Aplicado declaración (0797)
143 | 1794 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro- Pendiente aplicación
144 | 1807 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75º Aniversario de la Escuela Diplomática- Deducción
145 | 1820 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75º Aniversario de la Escuela Diplomática- Aplicado declaración (0798)
146 | 1833 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75º Aniversario de la Escuela Diplomática- Pendiente aplicación
147 | 1846 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Teruel 2017. 800 Años de los Amantes- Deducción
148 | 1859 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Teruel 2017. 800 Años de los Amantes- Aplicado declaración (0799)
149 | 1872 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Teruel 2017. 800 Años de los Amantes- Pendiente aplicación
150 | 1885 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Deducción
151 | 1898 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Aplicado declaración (0800)
152 | 1911 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Pendiente aplicación
153 | 1924 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50° aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya- Deducción
154 | 1937 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50° aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya- Aplicado declaración (0801)
155 | 1950 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50° aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya- Pendiente aplicación
156 | 1963 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Beneficios fiscales aplicables al 50 aniversario de la Universidad Autónoma de Madrid- Deducción
157 | 1976 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Beneficios fiscales aplicables al 50 aniversario de la Universidad Autónoma de Madrid- Aplicado declaración (0802)
158 | 1989 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Beneficios fiscales aplicables al 50 aniversario de la Universidad Autónoma de Madrid- Pendiente aplicación
159 | 2002 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Hernandiano 2017- Deducción
160 | 2015 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Hernandiano 2017- Aplicado declaración (0803)
161 | 2028 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Hernandiano 2017- Pendiente aplicación
162 | 2041 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Deducción
163 | 2054 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Aplicado declaración (0804)
164 | 2067 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Pendiente aplicación
165 | 2080 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de Ordesa y Monte Perdido- Deducción
166 | 2093 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de Ordesa y Monte Perdido- Aplicado declaración (0805)
167 | 2106 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de Ordesa y Monte Perdido- Pendiente aplicación
168 | 2119 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de los Picos de Europa- Deducción
169 | 2132 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de los Picos de Europa- Aplicado declaración (0806)
170 | 2145 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de los Picos de Europa- Pendiente aplicación
171 | 2158 | 600 | An | RESERVADO PARA LA A.E.A.T
172 | 2758 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10022000>
Total: |  | 2769

# Anexo A.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "23000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 Edición del Festival Internacional de Jazz de Barcelona- Deducción
7 | 26 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 Edición del Festival Internacional de Jazz de Barcelona- Aplicado declaración (0807)
8 | 39 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 Edición del Festival Internacional de Jazz de Barcelona- Pendiente aplicación
9 | 52 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenarios del Real Sitio de Covadonga- Deducción
10 | 65 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenarios del Real Sitio de Covadonga- Aplicado declaración (0808)
11 | 78 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenarios del Real Sitio de Covadonga- Pendiente aplicación
12 | 91 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Junior Balonmano Masculino 2019- Deducción
13 | 104 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Junior Balonmano Masculino 2019- Aplicado declaración (0809)
14 | 117 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Junior Balonmano Masculino 2019- Pendiente aplicación
15 | 130 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Andalucía Valderrama Masters- Deducción
16 | 143 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Andalucía Valderrama Masters- Aplicado declaración (0810)
17 | 156 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Andalucía Valderrama Masters- Pendiente aplicación
18 | 169 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Transición: 40 años de Libertad de Expresión- Deducción
19 | 182 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Transición: 40 años de Libertad de Expresión- Aplicado declaración (0811)
20 | 195 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Transición: 40 años de Libertad de Expresión- Pendiente aplicación
21 | 208 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Mobile World Capital- Deducción
22 | 221 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Mobile World Capital- Aplicado declaración (0812)
23 | 234 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Mobile World Capital- Pendiente aplicación
24 | 247 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Ceuta y la Legión, 100 años de unión- Deducción
25 | 260 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Ceuta y la Legión, 100 años de unión- Aplicado declaración (0813)
26 | 273 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Ceuta y la Legión, 100 años de unión- Pendiente aplicación
27 | 286 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019- Deducción
28 | 299 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019- Aplicado declaración (0814)
29 | 312 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019- Pendiente aplicación
30 | 325 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Bádminton World Tour- Deducción
31 | 338 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Bádminton World Tour- Aplicado declaración (0815)
32 | 351 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Bádminton World Tour- Pendiente aplicación
33 | 364 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Nuevas Metas- Deducción
34 | 377 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Nuevas Metas- Aplicado declaración (0816)
35 | 390 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Nuevas Metas- Pendiente aplicación
36 | 403 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Logroño 2021, nuestro V Centenario- Deducción
37 | 416 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Logroño 2021, nuestro V Centenario- Aplicado declaración (0817)
38 | 429 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Logroño 2021, nuestro V Centenario- Pendiente aplicación
39 | 442 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Santo Jacobeo 2021- Deducción
40 | 455 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Santo Jacobeo 2021- Aplicado declaración (0818)
41 | 468 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Santo Jacobeo 2021- Pendiente aplicación
42 | 481 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VIII Centenario de la Catedral de Burgos 2021- Deducción
43 | 494 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VIII Centenario de la Catedral de Burgos 2021- Aplicado declaración (0819)
44 | 507 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VIII Centenario de la Catedral de Burgos 2021- Pendiente aplicación
45 | 520 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Deporte Inclusivo- Deducción
46 | 533 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Deporte Inclusivo- Aplicado declaración (0820)
47 | 546 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Deporte Inclusivo- Pendiente aplicación
48 | 559 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - España, Capital del Talento Joven- Deducción
49 | 572 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - España, Capital del Talento Joven- Aplicado declaración (0821)
50 | 585 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - España, Capital del Talento Joven- Pendiente aplicación
51 | 598 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Conmemoración del Centenario de la Coronación de Nuestra Señora del Rocío (1919-2019)- Deducción
52 | 611 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Conmemoración del Centenario de la Coronación de Nuestra Señora del Rocío (1919-2019)- Aplicado declaración (0822)
53 | 624 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Conmemoración del Centenario de la Coronación de Nuestra Señora del Rocío (1919-2019)- Pendiente aplicación
54 | 637 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Traslado de la Imagen de Nuestra Señora del Rocío desde la Aldea al Pueblo de Almonte- Deducción
55 | 650 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Traslado de la Imagen de Nuestra Señora del Rocío desde la Aldea al Pueblo de Almonte- Aplicado declaración (0823)
56 | 663 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Traslado de la Imagen de Nuestra Señora del Rocío desde la Aldea al Pueblo de Almonte- Pendiente aplicación
57 | 676 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Europeo del Patrimonio Cultural (2018)- Deducción
58 | 689 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Europeo del Patrimonio Cultural (2018)- Aplicado declaración (0824)
59 | 702 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Europeo del Patrimonio Cultural (2018)- Pendiente aplicación
60 | 715 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación- Deducción
61 | 728 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación- Aplicado declaración (0825)
62 | 741 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación- Pendiente aplicación
63 | 754 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino de la Cruz de Caravaca- Deducción
64 | 767 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino de la Cruz de Caravaca- Aplicado declaración (0826)
65 | 780 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino de la Cruz de Caravaca- Pendiente aplicación
66 | 793 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad- Deducción
67 | 806 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad- Aplicado declaración (0827)
68 | 819 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad- Pendiente aplicación
69 | 832 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Automobile Barcelona 2019- Deducción
70 | 845 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Automobile Barcelona 2019- Aplicado declaración (0828)
71 | 858 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Automobile Barcelona 2019- Pendiente aplicación
72 | 871 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. Económicas 2017 (0830)
73 | 884 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (0831)
74 | 897 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (0832)
75 | 910 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. Económicas 2018 (0833)
76 | 923 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (0834)
77 | 936 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (0835)
78 | 949 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Deducción por inversión elementos nuevos  (0836)
79 | 962 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Saldo anterior
80 | 975 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Aplicado declaración (0837)
81 | 988 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Pendiente aplicación
82 | 1001 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Saldo anterior
83 | 1014 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Aplicado declaración (0838)
84 | 1027 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Pendiente aplicación
85 | 1040 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS - Deducción
86 | 1053 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS - Aplicado declaración (0839)
87 | 1066 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS- Pendiente aplicación
88 | 1079 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Deducción
89 | 1092 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS (0840)
90 | 1105 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Pendiente aplicación
91 | 1118 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Deducción
92 | 1131 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Aplicado declaración (0841)
93 | 1144 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad,  artº. 38 LIS - Pendiente de aplicación
94 | 1157 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental, artº.27.1.a) bis Ley 19/1994 - Deducción
95 | 1170 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental, artº.27.1.a) bis Ley 19/1994 - Aplicado declaración (0842)
96 | 1183 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción invers. territorio Africa Occidental, artº.27.1.a) bis Ley 19/1994 - Pendiente de aplicación
97 | 1196 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción por gastos de propaganda y publicidad, artº.27.1.b) bis Ley 19/1994  - Deducción
98 | 1209 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción por gastos de propaganda y publicidad, artº.27.1.b) bis Ley 19/1994 - Aplicado declaración (0843)
99 | 1222 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Deducción por gastos de propaganda y publicidad, artº.27.1.b) bis Ley 19/1994  - Pendiente aplicación
100 | 1235 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Deducción
101 | 1248 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Aplicado declaración (0844)
102 | 1261 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Pendiente aplicación
103 | 1274 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Importe total de las deducciones (0845)
104 | 1287 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Deducciones - Parte estatal (0554)
105 | 1300 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Deducciones - Parte autonómica (0555)
106 | 1313 | 600 | An | RESERVADO PARA LA A.E.A.T
107 | 1913 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10023000>
Total: |  | 1924

# Anexo B.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "24000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios de ayudas familiares (0850)
7 | 26 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios ayudas viviendas protegidas (0851)
8 | 39 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión vivienda habitual protegida/personas jóvenes (0852)
9 | 52 | 13 | N | Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler de vivienda habitual (0853)
10 | 65 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión en la adquisición de acciones y participaciones  (0854)
11 | 78 | 13 | N | Deducciones Autonómicas - Andalucía - Por adopción de hijos ámbito internacional (0855)
12 | 91 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con discapacidad (0856)
13 | 104 | 13 | N | Deducciones Autonómicas - Andalucía - Para padre/madre de familia monoparental con ascendientes mayores 75 años (0857)
14 | 117 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Deducción con carácter general  (0858)
15 | 130 | 11 | An | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Cuenta cotización (0859)
16 | 141 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Importe (0860)
17 | 154 | 11 | An | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Cuenta cotización (0861)
18 | 165 | 13 | N | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Importe (0862)
19 | 178 | 13 | N | Deducciones Autonómicas - Andalucía - Para trabajadores por gastos de defensa jurídica de la relación laboral (0863)
20 | 191 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con cónyuges o parejas de hecho con discapacidad (0864)
21 | 204 | 13 | N | Deducciones Autonómicas - Andalucía - Otras deducciones (0865)
22 | 217 | 13 | N | Deducciones Autonómicas - Andalucía - Total deducciones autonómicas (0534)
23 | 230 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del tercer hijo o sucesivos (0866)
24 | 243 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción de un hijo en atención al grado discapacidad (0867)
25 | 256 | 13 | N | Deducciones Autonómicas - Aragón - Por adopción internacional de niños (0868)
26 | 269 | 13 | N | Deducciones Autonómicas - Aragón - Por el cuidado de personas dependientes (0869)
27 | 282 | 13 | N | Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico (0870)
28 | 295 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo  (0871)
29 | 308 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en acciones de entidades que cotizan en Mercado Alternativo Bursátil (0872)
30 | 321 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en la adquisición de acciones o participaciones sociales (0873)
31 | 334 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición o rehabilitación de vivienda habitual en núcleos rurales o análogos (0874)
32 | 347 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición libros de texto y material escolar (0875)
33 | 360 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual vinculado operaciones dación en pago. Importe  (0876)
34 | 373 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda social (deducción arrendador) (0877)
35 | 386 | 13 | N | Deducciones Autonómicas - Aragón - Para mayores de 70 años (0878)
36 | 399 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en entidades de la economía social (0879)
37 | 412 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del primer y/o segundo hijo en poblaciones de menos de 10.000 habitantes (0880)
38 | 425 | 13 | N | Deducciones Autonómicas - Aragón - Por gastos de guardería de hijos menores de 3 años (0881)
39 | 438 | 13 | N | Deducciones Autonómicas - Aragón -  Otras deducciones (0882)
40 | 451 | 13 | N | Deducciones Autonómicas - Aragón - Total deducciones autonómicas (0564)
41 | 464 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (0883)
42 | 477 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes con discapacidad (0884)
43 | 490 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes con discapacidad (0885)
44 | 503 | 13 | N | Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (0886)
45 | 516 | 13 | N | Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual  (0887)
46 | 529 | 13 | N | Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (0888)
47 | 542 | 13 | N | Deducciones Autonómicas - Asturias - Por adopción internacional de menores (0889)
48 | 555 | 13 | N | Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones constituidas en la misma fecha  (0890)
49 | 568 | 13 | N | Deducciones Autonómicas - Asturias - Para familias numerosas (0891)
50 | 581 | 13 | N | Deducciones Autonómicas - Asturias - Para familias monoparentales (0892)
51 | 594 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (0893)
52 | 607 | 13 | N | Deducciones Autonómicas - Asturias - Por certificación de gestión forestal sostenible (0894)
53 | 620 | 13 | N | Deducciones Autonómicas - Asturias - Por gastos de descendientes en centros de 0 a 3 años (0895)
54 | 633 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición de libros de texto y material escolar (0896)
55 | 646 | 13 | N | Deducciones Autonómicas - Asturias -  Otras deducciones (0897)
56 | 659 | 13 | N | Deducciones Autonómicas - Asturias - Total deducciones autonómicas (0564)
57 | 672 | 600 | An | RESERVADO PARA LA A.E.A.T
58 | 1272 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10024000>
Total: |  | 1283

# Anexo B.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "25000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Illes Balears - Por determinadas inversiones de mejora de sostenibilidad vivienda habitual (0898)
7 | 26 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos adquisición libros de texto (0899)
8 | 39 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos de aprendizaje extraescolar de idiomas extranjeros (0900)
9 | 52 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones entidades destinadas investigación, desarrollo científico o tecnológico o innovación  (0901)
10 | 65 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones, cesiones uso o contratos comodato y convenios colaboración empresarial  (0902)
11 | 78 | 13 | N | Deducciones Autonómicas - Illes Balears - Por inversión en la adquisición de acciones o participaciones sociales de nuevas entidades (0903)
12 | 91 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones, cesiones uso o contrato de comodato y convenios colaboración, mecenazgo deportivo (0904)
13 | 104 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones a determinadas entidades fomento lengua catalana (0905)
14 | 117 | 13 | N | Deducciones Autonómicas - Illes Balears - Para declarentes con discapacidad física, psiquica o sensorial o con descendientes con esta condición (0906)
15 | 130 | 13 | N | Deducciones Autonómicas - Illes Balears - Por arrendamiento de vivienda habitual a favor de determinados colectivos (0907)
16 | 143 | 13 | N | Deducciones Autonómicas - Illes Balears - Para cursar estudios de educación superior fuera de la isla de residencia habitual  (0908)
17 | 156 | 13 | N | Deducciones Autonómicas - Illes Balears - Por arrendamiento de bienes inmuebles Illes Balears destinados a vivienda (0909)
18 | 169 | 13 | N | Deducciones Autonómicas - Illes Balears - Por arrendamiento vivienda en Illes Balears traslado de residencia por motivos laborales (0910)
19 | 182 | 20 | An | Deducciones Autonómicas - Illes Balears - Nif Arrendador (0911)
20 | 202 | 1 | Num | Deducciones Autonómicas - Illes Balears - Marque si ha consignado NIF de otro país.  "1 o cero" (0912)
21 | 203 | 13 | N | Deducciones Autonómicas - Illes Balears - Por donaciones a entidades del tercer sector (0913)
22 | 216 | 13 | N | Deducciones Autonómicas - Illes Balears - Por gastos relativos a los descendientes o acogidos menores de 6 años por conciliación (0914]
23 | 229 | 13 | N | Deducciones Autonómicas - Illes Balears -  Por determinadas subvenciones y ayudas otorgadas por declaración zona afectada gravemente por una emergencia de protección civil (0915)
24 | 242 | 13 | N | Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (0564)
25 | 255 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones con finalidad ecológica (0916)
26 | 268 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones rehabilitación o conservación patrimonio histórico de Canarias (0917)
27 | 281 | 13 | N | Deducciones Autonómicas - Canarias - Por cantidades destinadas restauración/rehabilitación/reparación bienes inmuebles declarados de Interés Cultural (0918)
28 | 294 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de estudios (0919)
29 | 307 | 13 | N | Deducciones Autonómicas - Canarias - Por trasladar residencia a otra isla para realizar actividad laboral cuenta ajena/actividad económica (0920)
30 | 320 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones en metálico a descendientes menores 35 años para adquisición/rehabilitación primera vivienda habitual (0921)
31 | 333 | 13 | N | Deducciones Autonómicas - Canarias - Por nacimiento o adopción de hijos (0922)
32 | 346 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes con discapacidad y mayores de 65 años (0923)
33 | 359 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de guardería (0924)
34 | 372 | 13 | N | Deducciones Autonómicas - Canarias - Por familia numerosa (0925)
35 | 385 | 13 | N | Deducciones Autonómicas - Canarias - Por inversión en vivienda habitual (0926)
36 | 398 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de adecuación vivienda habitual por razón discapacidad (0927)
37 | 411 | 13 | N | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Importe (0928)
38 | 424 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral 1 (0929)
39 | 444 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral 1. "1 o cero" (0930)
40 | 445 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral 2 (0931)
41 | 465 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral 2. "1 o cero" (0932)
42 | 466 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes desempleados (0933)
43 | 479 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones y aportaciones fines culturales, deportivos, investigación o docencia (0934)
44 | 492 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones a entidades sin ánimo de lucro y con finalidad ecológica (0935)
45 | 505 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de estudios en educación infantil, primaria, secundaria obligatoria bachillerato y formación profesional de grado medio (0936)
46 | 518 | 13 | N | Deducciones Autonómicas - Canarias - Por acogimiento de menores (0937)
47 | 531 | 13 | N | Deducciones Autonómicas - Canarias - Por familias monoparentales (0938)
48 | 544 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de rehabilitación energética de la vivienda habitual (0939)
49 | 557 | 13 | N | Deducciones Autonómicas - Canarias - Por gasto de enfermedad (0940)
50 | 570 | 13 | N | Deducciones Autonómicas - Canarias - Por familiares dependientes con discapacidad (0941)
51 | 583 | 13 | N | Deducciones Autonómicas - Canarias - Por arrendamiento de vivienda habitual vinculado a determinadas operaciones de dación en pago [0942]
52 | 596 | 13 | N | Deducciones Autonómicas - Canarias - Por arrendamientos a precios con sostenibilidad social (0943)
53 | 609 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (0944)
54 | 622 | 13 | N | Deducciones Autonómicas - Canarias - Otras deducciones (0945)
55 | 635 | 13 | N | Deducciones Autonómicas - Canarias - Total deducciones autonómicas (0564)
56 | 648 | 600 | An | RESERVADO PARA LA A.E.A.T
57 | 1248 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10025000>
Total: |  | 1259

# Anexo B.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "26000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con  discapacidad - Importe (0946)
7 | 26 | 13 | N | Deducciones Autonómicas - Cantabria - Por cuidado de familiares (0947)
8 | 39 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora. Importe 2016 y/o 2017 pendiente de aplicación (0948)
9 | 52 | 9 | An | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - NIF persona/entidad  obras (0949)
10 | 61 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - Importe deducción (0950)
11 | 74 | 13 | N | Deducciones Autonómicas - Cantabria - Por donativos a fundaciones o al Fondo Cantabria Coopera (0951)
12 | 87 | 13 | N | Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (0952)
13 | 100 | 13 | N | Deducciones Autonómicas - Cantabria - Por inversión adquisición acciones/participaciones sociales nuevas entidades o reciente creación (0953)
14 | 113 | 13 | N | Deducciones Autonómicas - Cantabria - Por gastos de enfermedad (0954)
15 | 126 | 13 | N | Deducciones Autonómicas - Cantabria - Otras deducciones (0955)
16 | 139 | 13 | N | Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (0564)
17 | 152 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora generadas en 2018 a deducir en los 2 años siguientes (0956)
18 | 165 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (0957)
19 | 178 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (0958)
20 | 191 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (0959)
21 | 204 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (0960)
22 | 217 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (0961)
23 | 230 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por cantidades para la Cooperación Internacional, lucha contra pobreza y exclusión social  (0962)
24 | 243 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por familia numerosa (0963)
25 | 256 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por donaciones con finalidad en investigación y desarrollo e innovación empresarial (0964)
26 | 269 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por gastos en la adquisición de libros de texto y enseñanza de idiomas (0965)
27 | 282 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento familiar no rumunerado de menores (0966)
28 | 295 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento no remunerado de mayores de 65 años y/o discapacitados (0967)
29 | 308 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha -  Por arrendamiento de vivienda habitual por menores de 36 años  (0968)
30 | 321 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Otras deducciones (0969)
31 | 334 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (0564)
32 | 347 | 13 | N | Deducciones Autonómicas - Castilla y León - Para contribuyentes afectados por discapacidad (0970)
33 | 360 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales  (0971)
34 | 373 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cantidades donadas a fundaciones (0972)
35 | 386 | 13 | N | Deducciones Autonómicas - Castilla y León - Poro cantidades donadas para el fomento de la investigación, desarrollo e innovación (0973)
36 | 399 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cantidades invertidas en la recuperación del patrimonio histórico, cultural y natural  (0974)
37 | 412 | 13 | N | Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años  (0975)
38 | 425 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión instalaciones medioambientales/adaptación a personas con discapacidad en vvda.habitual (0976)
39 | 438 | 8 | Num | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Fecha visado proyecto (0977)
40 | 446 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Importe  (0978)
41 | 459 | 13 | N | Deducciones Autonómicas - Castilla y León - Para el fomento de emprendimiento (0979)
42 | 472 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión en rehabilitación de viviendas destinadas a alquiler en núcleos rurales  (0980)
43 | 485 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2015 pdte. aplicación (0981)
44 | 498 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2016 pdte. aplicación (0982)
45 | 511 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2017 pdte. aplicación (0983)
46 | 524 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe aplicado en el ejercicio (0984)
47 | 537 | 13 | N | Deducciones Autonómicas - Castilla y León - Por familia numerosa (0985)
48 | 550 | 13 | N | Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (0986)
49 | 563 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas (0987)
50 | 576 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas en 2016  y/o 2017 (0988)
51 | 589 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Nif persona empleada (0989)
52 | 598 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Importe (0990)
53 | 611 | 13 | N | Deducciones Autonómicas - Castilla y León - Por paternidad  (0991)
54 | 624 | 13 | N | Deducciones Autonómicas - Castilla y León - Por gastos de adopción (0992)
55 | 637 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuotas Seg.Social empleados del hogar - Nif persona empleada (0993)
56 | 646 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuotas Seg.Social empleados del hogar - Importe (0994)
57 | 659 | 13 | N | Deducciones Autonómicas - Castilla y León - Importe total aplicado  (0995)
58 | 672 | 13 | N | Deducciones Autonómicas - Castilla y León - Otras deducciones (0996)
59 | 685 | 13 | N | Deducciones Autonómicas - Castilla y León - Total deducciones autonómicas  (0564)
60 | 698 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - Ejercicios siguientes. Importe 2016 pdte. aplicación (0997)
61 | 711 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - Ejercicios siguientes. Importe 2017 pdte. aplicación (0998)
62 | 724 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones familia numerosa, nacimiento o adopción, etc - Ejercicios siguientes. Importe 2018 pdte. aplicación (0999)
63 | 737 | 600 | An | RESERVADO PARA LA A.E.A.T
64 | 1337 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10026000>
Total: |  | 1348

# Anexo B.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "27000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Cataluña - Por nacimiento o adopción de un hijo (1000)
7 | 26 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan el uso lengua catalana (1001)
8 | 39 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan la investigación científica (1002)
9 | 52 | 13 | N | Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual  (1003)
10 | 65 | 13 | N | Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudios universitarios de master y doctorado (1004)
11 | 78 | 13 | N | Deducciones Autonómicas - Cataluña - Para los contribuyentes que queden viudos (1005)
12 | 91 | 13 | N | Deducciones Autonómicas - Cataluña - Por rehabilitación vivienda habitual (1006)
13 | 104 | 13 | N | Deducciones Autonómicas - Cataluña - Por donaciones entidades en beneficio del medio ambiente (1007)
14 | 117 | 13 | N | Deducciones Autonómicas - Cataluña - Por inversión por ángel inversor y por adquisición de acciones entidades nuevas o de creación reciente (1008)
15 | 130 | 13 | N | Deducciones Autonómicas - Cataluña - Otras deducciones (1009)
16 | 143 | 13 | N | Deducciones Autonómicas - Cataluña - Total deducciones autonómicas (0564)
17 | 156 | 13 | N | Deducciones Autonómicas - Extremadura - Por adquisición o rehabilitación vivienda habitual para jóvenes y víctimas del terrorismo (1010)
18 | 169 | 13 | N | Deducciones Autonómicas - Extremadura - Por trabajo dependiente (1011)
19 | 182 | 13 | N | Deducciones Autonómicas - Extremadura - Por cuidado de familiares con discapacidad (1012)
20 | 195 | 13 | N | Deducciones Autonómicas - Extremadura - Por acogimiento de menores (1013)
21 | 208 | 13 | N | Deducciones Autonómicas - Extremadura - Por  partos múltiples (1014)
22 | 221 | 13 | N | Deducciones Autonómicas - Extremadura - Por compra de material escolar (1015)
23 | 234 | 13 | N | Deducciones Autonómicas - Extremadura - Por inversión en la adquisición de acciones o participaciones sociales (1016)
24 | 247 | 13 | N | Deducciones Autonómicas - Extremadura - Por gastos de guardería para hijos menores de 4 años (1017)
25 | 260 | 13 | N | Deducciones Autonómicas - Extremadura - Para contribuyentes viudos (1018)
26 | 273 | 13 | N | Deducciones Autonómicas - Extremadura - Por arrendamiento vivienda habitual (1019)
27 | 286 | 13 | N | Deducciones Autonómicas - Extremadura -  Otras deducciones (1020)
28 | 299 | 13 | N | Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (0564)
29 | 312 | 13 | N | Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (1021)
30 | 325 | 13 | N | Deducciones Autonómicas - Galicia - Por familia numerosa (1022)
31 | 338 | 13 | N | Deducciones Autonómicas - Galicia - Por cuidado hijos menores (1023)
32 | 351 | 13 | N | Deducciones Autonómicas - Galicia - Por contribuyentes con discapacidad = > 65 años que precisan ayuda de terceras personas (1024)
33 | 364 | 13 | N | Deducciones Autonómicas - Galicia - Por gastos uso nuevas tecnologías en hogares gallegos (1025)
34 | 377 | 13 | N | Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual  por contribuyentes de edad igual o inferior a 35 años (1026)
35 | 390 | 13 | N | Deducciones Autonómicas - Galicia - Por acogimiento de menores (1027)
36 | 403 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación (1028)
37 | 416 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación y su financiación (1029)
38 | 429 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones de entidades empresas en expansión Mercado Alternativo Bolsista (1030)
39 | 442 | 13 | N | Deducciones Autonómicas - Galicia - Por donaciones finalidad en investigacion y desarrollo científico e innovación tecnológica (1031)
40 | 455 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables (1032)
41 | 468 | 20 | An | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables - Código de instalación (1033)
42 | 488 | 13 | N | Deducciones Autonómicas - Galicia - Por rehabilitación de bienes inmuebles situados en centros históricos (1034)
43 | 501 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en empresas agrarias y sociedades cooperativas agrarias (1035)
44 | 514 | 13 | N | Deducciones Autonómicas - Galicia - Por determinadas subvenciones y/o ayudas obtenidas a consecuencia de los incendios de octubre de 2017 (1036)
45 | 527 | 13 | N | Deducciones Autonómicas - Galicia - Para paliar los daños causados por la explosión de material pirotécnico en Tuy en mayo del 2018 (1037)
46 | 540 | 13 | N | Deducciones Autonómicas - Galicia - Otras deducciones (1038)
47 | 553 | 13 | N | Deducciones Autonómicas - Galicia - Total deducciones autonómicas (0564)
48 | 566 | 600 | An | RESERVADO PARA LA A.E.A.T
49 | 1166 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10027000>
Total: |  | 1177

# Anexo B.5

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "28000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Madrid - Por nacimiento o adopción de hijos (1039)
7 | 26 | 13 | N | Deducciones Autonómicas - Madrid - Por adopción internacional de niños (1040)
8 | 39 | 13 | N | Deducciones Autonómicas - Madrid - Por acogimiento familiar de menores (1041)
9 | 52 | 13 | N | Deducciones Autonómicas - Madrid - Por acogimiento no remunerado de mayores 65 años y/o con discapacidad (1042)
10 | 65 | 13 | N | Deducciones Autonómicas - Madrid - Por arrendamiento de vivienda habitual (1043)
11 | 78 | 13 | N | Deducciones Autonómicas - Madrid - Por gastos educativos (1044)
12 | 91 | 13 | N | Deducciones Autonómicas - Madrid - Para familias con dos o más descendientes e ingresos reducidos (1045)
13 | 104 | 13 | N | Deducciones Autonómicas - Madrid - Por inversión en adquisición de acciones y participaciones sociales de nuevas entidades o de reciente creación (1046)
14 | 117 | 13 | N | Deducciones Autonómicas - Madrid -  Para el fomento del autoempleo de jóvenes menores de 35 años (1047)
15 | 130 | 13 | N | Deducciones Autonómicas - Madrid - Por inversiones en entidades cotizadas en el Mercado Alternativo Bursátil (1048)
16 | 143 | 13 | N | Deducciones Autonómicas - Madrid - Por donativos a fundaciones y clubes deportivos (1049)
17 | 156 | 13 | N | Deducciones Autonómicas - Madrid - Por cuidado de hijos menores de 3 años (1050)
18 | 169 | 13 | N | Deducciones Autonómicas - Madrid - Otras deducciones (1051)
19 | 182 | 13 | N | Deducciones Autonómicas - Madrid - Total deducciones autonómicas (0564)
20 | 195 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión vivienda habitual jóvenes edad igual/inferior 35 años (incluido rég. transitorio) (1052)
21 | 208 | 13 | N | Deducciones Autonómicas - Murcia - Por donativos para la protección del patrimonio cultural o promoción de actividades culturales y deportivas (1053)
22 | 221 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de guardería para hijos menores de 3 años (1054)
23 | 234 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (1055)
24 | 247 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (1056)
25 | 260 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en la adquisición de acciones y participaciones sociales de nuevas entidades (1057)
26 | 273 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en entidades cotizadas Mercado Alternativo Bursátil (1058)
27 | 286 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de material escolar y libros de texto (1059)
28 | 299 | 13 | N | Deducciones Autonómicas - Murcia - Por donativos para la investigación biosanitaria (1060)
29 | 312 | 13 | N | Deducciones Autonómicas - Murcia - Total deducciones autonómicas (0564)
30 | 325 | 13 | N | Deducciones Autonómicas - La Rioja - Por nacimiento y adopción de hijos (1061)
31 | 338 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas rehabilitación vivienda habitual (1062)
32 | 351 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas adquisición o contrucción vivienda habitual para jóvenes (1063)
33 | 364 | 4 | Num | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Código municipio (1064)
34 | 368 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Importe  (1065)
35 | 381 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas en obras de adecuación de vivienda habitual para personas con discapacidad (1066)
36 | 394 | 4 | Num | Deducciones Autonómicas - La Rioja - Por adquisición, construcción y rehabilitación vivienda habitual pequeños municipios. Código municipio (1067)
37 | 398 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición, construcción y rehabilitación vivienda habitual pequeños municipios. Importe (1068)
38 | 411 | 13 | N | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado. Importe (1069)
39 | 424 | 9 | An | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado.NIF (1070)
40 | 433 | 4 | Num | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado.Código municipio (1071)
41 | 437 | 13 | N | Deducciones Autonómicas - La Rioja - Por acogimiento de menores (1072)
42 | 450 | 4 | Num | Deducciones Autonómicas - La Rioja - Por cada hijo de 0 a 3 años de contribuyentes con vivienda en pequeños municipios. Código municipio (1073)
43 | 454 | 13 | N | Deducciones Autonómicas - La Rioja - Por cada hijo de 0 a 3 años de contribuyentes con vivienda en pequeños municipios. Importe (1074)
44 | 467 | 13 | N | Deducciones Autonómicas - La Rioja - Por hijos de 0 a 3 años escolarizados en cualquier municipio de la Rioja. Importe (1075)
45 | 480 | 9 | An | Deducciones Autonómicas - La Rioja - Por hijos de 0 a 3 años escolarizados en cualquier municipio de la Rioja. NIF del centro (1076)
46 | 489 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición de vehículos eléctricos nuevos (1077)
47 | 502 | 13 | N | Deducciones Autonómicas - La Rioja - Por arrendamiento de vivienda a jóvenes (1078)
48 | 515 | 4 | Num | Deducciones Autonómicas - La Rioja - Por acceso a internet para jóvenes emancipados.Código municipio (1204)
49 | 519 | 13 | N | Deducciones Autonómicas - La Rioja - Por acceso a internet para jóvenes emancipados. Importe de la deducción (1079)
50 | 532 | 4 | Num | Deducciones Autonómicas - La Rioja - Por suministro de luz y gas de uso doméstico para jóvenes emancipados. Código municipio (1205)
51 | 536 | 13 | N | Deducciones Autonómicas - La Rioja - Por suministro de luz y gas de uso doméstico para jóvenes emancipados. Importe de la deducción (1080)
52 | 549 | 13 | N | Deducciones Autonómicas - La Rioja - Por inversión en vivienda habitual de jóvenes menores de 36 años (1081)
53 | 562 | 13 | N | Deducciones Autonómicas - La Rioja - Otras deducciones (1082)
54 | 575 | 13 | N | Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (0564)
55 | 588 | 600 | An | RESERVADO PARA LA A.E.A.T
56 | 1188 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10028000>
Total: |  | 1199

# Anexo B.6

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "29000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento, adopción o acogimiento familiar (1083)
7 | 26 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento o adopción múltiples (1084)
8 | 39 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por nacimiento o adopción hijos con discapacidad (1085)
9 | 52 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por familia numerosa o monoparental (1086)
10 | 65 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades custodia en guarderías y primer ciclo educación infantil hijos menores de 3 años (1087)
11 | 78 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por conciliación del trabajo con la vida familiar (1088)
12 | 91 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Para contribuyentes con un grado de discapacidad igual o superior al 33 por 100, de edad igual o superior a 65 años (1089)
13 | 104 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por ascendientes > 75 años ó > 65 años que sean personas con discapacidad (1090)
14 | 117 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por realización por uno de los cónyuges de labores no remuneradas en el hogar (1091)
15 | 130 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por primera adquisición vivienda habitual por contribuyentes edad igual o inferior 35 años (1092)
16 | 143 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición vivienda habitual por personas con discapacidad (1093)
17 | 156 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades adquisición o rehabilitación vivienda habitual, procedentes ayudas públicas (1094)
18 | 169 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento de la vivienda habitual (1095)
19 | 182 | 20 | An | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - NIF arrendador (1096)
20 | 202 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Importe (1097)
21 | 215 | 1 | Num | Deducciones Autonómicas - Comunitat Valenciana - Por arrendamiento vivienda actividades distinto municipio - Si ha consignado NIF de otro país (1098) "1 o cero"
22 | 216 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones con finalidad ecológica (1099)
23 | 229 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (1100)
24 | 242 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades donadas para la conservación, reparación y restauración de bienes (1101)
25 | 255 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades destinadas a la conservación, reparación y restauración de bienes (1102)
26 | 268 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por donaciones al fomento de la Lengua Valenciana (1103)
27 | 281 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por contribuyentes con dos o más descendientes (1104)
28 | 294 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (1105)
29 | 307 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición material escolar (1106)
30 | 320 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual  - NIF persona o entidad (1107)
31 | 329 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual - Importe  (1108)
32 | 342 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual realizadas en el periodo - NIF persona o entidad (1109)
33 | 351 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual realizadas en el periodo - Importe  (1110)
34 | 364 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones importes dinerarios a otros fines culturales (1111)
35 | 377 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones o cesiones de uso o comodatos para otros fines de interés cultural, científico o deportivo no profesional (1112)
36 | 390 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades destinadas a abonos culturales (1113)
37 | 403 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. Importe (1114)
38 | 416 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2017. Importe generado pendiente (1115)
39 | 429 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2017. Importe aplicado en el ejercicio  (1116)
40 | 442 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2017. Importe generado en 2017 pendiente de aplicación en ejercicios futuros(1117)
41 | 455 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2018. Importe generado (1118)
42 | 468 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2018. Importe aplicado en el ejercicio  (1119)
43 | 481 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2018. Importe generado en 2018 pendiente de aplicación en ejercicios futuros(1120)
44 | 494 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Otras deducciones (1121)
45 | 507 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Total deduciones autonómicas (0564)
46 | 520 | 20 | An | Información adicional deducción autonómica por arrendamiento - NIF/NIE arrendador - 1 (1122)
47 | 540 | 1 | Num | Información adicional deducción autonómica por arrendamiento - Si ha consignado NIF de otro país - 1 - "1 o cero"  (1123)
48 | 541 | 13 | N | Información adicional deducción autonómica por arrendamiento - Cantidades satisfechas - 1  (1124)
49 | 554 | 20 | An | Información adicional deducción autonómica por arrendamiento - NIF/NIE arrendador - 2 (1125)
50 | 574 | 1 | Num | Información adicional deducción autonómica por arrendamiento - Si ha consignado NIF de otro país - 2 - "1 o cero"  (1126)
51 | 575 | 13 | N | Información adicional deducción autonómica por arrendamiento - Cantidades satisfechas - 2  (1127)
52 | 588 | 13 | N | Información adicional deducción autonómica por arrendamiento - Importe total satisfecho (1128)
53 | 601 | 13 | N | Información adicional deducción autonómica por arrendamiento - Cantidades satisfechas con derecho a deducción  (1129)
54 | 614 | 13 | N | Información adicional deducción autonómica por arrendamiento - Importe deducción autonómica por arrendamiento  (1130)
55 | 627 | 600 | An | RESERVADO PARA LA A.E.A.T
56 | 1227 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10029000>
Total: |  | 1238

# Anexo B.7

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "30000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 9 | An | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Nif entidad - 1 (1131)
7 | 22 | 13 | N | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Importe - 1 (1132)
8 | 35 | 9 | An | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Nif entidad - 2 (1133)
9 | 44 | 13 | N | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Importe - 2 (1134)
10 | 57 | 13 | N | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Importe total con derecho a deducción (1135)
11 | 70 | 13 | N | Información adicional deducción autonómica por inversión en acciones entidades nuevas. Importe total deducción (1136)
12 | 83 | 9 | An | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Nif entidad - 1 (1137)
13 | 92 | 13 | N | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Importe inversión - 1 (1138)
14 | 105 | 9 | An | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Nif entidad - 2 (1139)
15 | 114 | 13 | N | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Importe inversión - 2 (1140)
16 | 127 | 13 | N | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Importe total con derecho a deducción  (1141)
17 | 140 | 13 | N | Información adicional deducción autonómica Aragón, Galicia, Madrid o Murcia por inversiones Mercado Alternativo Bursátil. Importe total deducción (1142)
18 | 153 | 9 | An | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Nif entidad - 1 (1143)
19 | 162 | 13 | N | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Importe inversión - 1 (1144)
20 | 175 | 9 | An | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Nif entidad - 2 (1145)
21 | 184 | 13 | N | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Importe inversión - 2 (1146)
22 | 197 | 13 | N | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Importe total con derecho a deducción (1147)
23 | 210 | 13 | N | Información adicional deducción autonómica Galicia por inversión en acciones entidades nuevas o reciente creación. Importe total deducción (1148)
24 | 223 | 9 | An | Información adicional deducción autonómica Galicia por inversión en empresas agrarias y cooperativas agrarias o de exp. comunitaria de la tierra. Nif entidad - 1 (1149)
25 | 232 | 13 | N | Información adicional deducción autonómica Galicia por inversión en empresas agrarias y cooperativas agrarias o de exp. comunitaria de la tierra. Importe inversión - 1 (1150)
26 | 245 | 9 | An | Información adicional deducción autonómica Galicia por inversión en empresas agrarias y cooperativas agrarias o de exp. comunitaria de la tierra. Nif entidad - 2 (1151)
27 | 254 | 13 | N | Información adicional deducción autonómica Galicia por inversión en empresas agrarias y cooperativas agrarias o de exp. comunitaria de la tierra. Importe inversión - 2 (1152)
28 | 267 | 13 | N | Información adicional deducción autonómica Galicia por inversión en empresas agrarias y cooperativas agrarias o de exp. comunitaria de la tierra. Importe total con derecho a deducción (1153)
29 | 280 | 13 | N | Información adicional deducción autonómica Galicia por inversión en empresas agrarias y cooperativas agrarias o de exp. comunitaria de la tierra. Importe total deducción (1154)
30 | 293 | 20 | An | Información adicional deducción autonómica Aragón y Canarias por arrendamiento de vivienda habitual vinculado a operaciones de dación en pago. NIF/NIE arrendador (1155)
31 | 313 | 1 | Num | Información adicional deducción autonómica Aragón y Canarias por arrendamiento de vivienda habitual vinculado a operaciones de dación en pago. Si ha consignado NIF de otro país - "1 o cero"  (1156)
32 | 314 | 13 | N | Información adicional deducción autonómica Aragón y Canarias por arrendamiento de vivienda habitual vinculado a operaciones de dación en pago. Cantidades satisfechas (1159)
33 | 327 | 13 | N | Información adicional deducción autonómica Aragón y Canarias por arrendamiento de vivienda habitual vinculado a operaciones de dación en pago. Importe de la deducción autonómica (1170)
34 | 340 | 600 | An | RESERVADO PARA LA A.E.A.T
35 | 940 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10030000>
Total: |  | 951

# Anexo B.8

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "31000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 20 | An | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). NIF/NIE del arrendatario - 1 (1171)
7 | 33 | 1 | Num | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Si ha consignado NIF de otro país - 1 - "1 o cero"  (1172)
8 | 34 | 20 | An | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Referencia catastral - 1 (1173)
9 | 54 | 1 | Num | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Sin referencia  catastral - 1 - "1 o cero" (1174)
10 | 55 | 13 | N | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Importe del rendimiento de capital inmobiliario reducido - 1 (1175)
11 | 68 | 20 | An | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). NIF/NIE del arrendatario - 2 (1176)
12 | 88 | 1 | Num | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Si ha consignado NIF de otro país - 2 - "1 o cero"  (1177)
13 | 89 | 20 | An | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Referencia catastral - 2 (1178)
14 | 109 | 1 | Num | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Sin referencia  catastral - 2 - "1 o cero" (1179)
15 | 110 | 13 | N | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Importe del rendimiento de capital inmobiliario reducido - 2 (1180)
16 | 123 | 20 | An | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). NIF/NIE del arrendatario - 3 (1181)
17 | 143 | 1 | Num | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Si ha consignado NIF de otro país - 3 - "1 o cero"  (1182)
18 | 144 | 20 | An | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Referencia catastral - 3 (1183)
19 | 164 | 1 | Num | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Sin referencia  catastral - 3 - "1 o cero" (1184)
20 | 165 | 13 | N | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Importe del rendimiento de capital inmobiliario reducido - 3 (1185)
21 | 178 | 13 | N | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Importe total de los rendimientos de capital inmobiliario que dan derecho a la deducción (1206)
22 | 191 | 13 | N | Información adicional a la deducción autonómica Canarias por arrendamientos a precios con sostenibilidad social (deducción del arrendador). Importe de la deducción autonómica (1186)
23 | 204 | 20 | An | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). NIF/NIE del arrendatario - 1 (1187)
24 | 224 | 1 | Num | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Si ha consignado NIF de otro país - 1 - "1 o cero"  (1188)
25 | 225 | 20 | An | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador).  Referencia catastral - 1 (1189)
26 | 245 | 1 | Num | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Sin referencia  catastral - 1 - "1 o cero" (1190)
27 | 246 | 13 | N | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Primas satisfechas - 1 (1191)
28 | 259 | 20 | An | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). NIF/NIE del arrendatario - 2 (1192)
29 | 279 | 1 | Num | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Si ha consignado NIF de otro país - 2 - "1 o cero"  (1193)
30 | 280 | 20 | An | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador).  Referencia catastral - 2 (1194)
31 | 300 | 1 | Num | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Sin referencia  catastral - 2 - "1 o cero" (1195)
32 | 301 | 13 | N | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Primas satisfechas - 2 (1196)
33 | 314 | 20 | An | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). NIF/NIE del arrendatario - 3 (1197)
34 | 334 | 1 | Num | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Si ha consignado NIF de otro país - 3 - "1 o cero"  (1198)
35 | 335 | 20 | An | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador).  Referencia catastral - 3 (1199)
36 | 355 | 1 | Num | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Sin referencia  catastral - 3 - "1 o cero" (1200)
37 | 356 | 13 | N | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Primas satisfechas - 3 (1201)
38 | 369 | 13 | N | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Importe total de la primas de seguro con derecho a deducción (1202)
39 | 382 | 13 | N | Información adicional a la deducción autonómica Canarias por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (deducción del arrendador). Importe de la deducción autonómica (1203)
40 | 395 | 600 | An | RESERVADO PARA LA A.E.A.T
41 | 995 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10031000>
Total: |  | 1006

# Anexo C.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "32000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 3 | Num | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - Número de orden  (1210)
7 | 16 | 1 | Tit | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - Contribuyente  "0" a "9" (1211)
8 | 17 | 20 | An | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - Referencia catastral (1212)
9 | 37 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2014. Pendiente principio periodo  (1213)
10 | 50 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2014. Aplicado en declaración (1214)
11 | 63 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2015. Pendiente principio periodo  (1215)
12 | 76 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2015. Aplicado en declaración  (1216)
13 | 89 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2015. Pdte. aplicación ejercicios futuros  (1217)
14 | 102 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Pendiente principio periodo  (1218)
15 | 115 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Aplicado en declaración (1219)
16 | 128 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Pdte. aplicación ejercicios futuros  (1220)
17 | 141 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2017. Pendiente principio periodo  (1221)
18 | 154 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2017. Aplicado en declaración  (1222)
19 | 167 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2017. Pdte. aplicación ejercicios futuros  (1223)
20 | 180 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2018. Pdte. aplicación ejercicios futuros  (1224)
21 | 193 | 1 | Tit | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Contribuyente "0" a "9" (1225)
22 | 194 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe total obtenido susceptible de reinversión (1226)
23 | 207 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Ganancia patrimonial obtenida (1227)
24 | 220 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe reinvertido hasta 31-12-2018 en adquisición nueva vivienda (1228)
25 | 233 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe que se compromete a reinvertir 2 años siguientes (1229)
26 | 246 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (1230)
27 | 259 | 1 | Tit | C | Exención por reinversión en entidades de nueva o reciente creación - Contribuyente "0" a "9" (1231)
28 | 260 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe total obtenido susceptible de reinversión (1232)
29 | 273 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Ganancia patrimonial obtenida (1233)
30 | 286 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe reinvertido hasta 31-12-2018 (1234)
31 | 299 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe que se compromete a reinvertir en 2019 (1235)
32 | 312 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Ganancia patrimonial exenta por reinversión (1236)
33 | 325 | 1 | Tit | C | Exención por reinversión en rentas vitalicias -  Contribuyente "0" a "9" (1237)
34 | 326 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe total transmisión elementos patrimoniales (1238)
35 | 339 | 13 | N | C | Exención por reinversión en rentas vitalicias - Ganancia patrimonial obtenida (1239)
36 | 352 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe reinvertido hasta 31-12-2018 en rentas vitalicias (1240)
37 | 365 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe que se compromete a reinvertir en 2019 (1241)
38 | 378 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe retención que se compromete a reinvertir en 2019 (1242)
39 | 391 | 13 | N | C | Exención por reinversión en rentas vitalicias - Ganancia patrimonial exenta por reinversión (1243)
40 | 404 | 1 | Tit | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. Contribuyente "0" a "9" (1245)
41 | 405 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2014. Pendiente principio periodo (1246)
42 | 418 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2014. Aplicado en declaración (1247)
43 | 431 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2015. Pendiente principio periodo (1248)
44 | 444 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2015. Aplicado en declaración (1249)
45 | 457 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2015. Pdte. aplicación ejercicios futuros (1250)
46 | 470 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Pendiente principio periodo (1251)
47 | 483 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Aplicado en declaración (1252)
48 | 496 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Pdte. aplicación ejercicios futuros (1253)
49 | 509 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2017. Pendiente principio periodo (1254)
50 | 522 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2017. Aplicado en declaración (1255)
51 | 535 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2017. Pdte. aplicación ejercicios futuros (1256)
52 | 548 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. Saldo negativo pendiente de compensación (1257)
53 | 561 | 1 | Tit | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. Contribuyente "0" a "9" (1258)
54 | 562 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2014. Pendiente principio periodo (1259)
55 | 575 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2014. Aplicado en declaración (1260)
56 | 588 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2015. Pendiente principio periodo (1261)
57 | 601 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2015. Aplicado en declaración (1262)
58 | 614 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2015. Pdte. aplicación ejercicios futuros (1263)
59 | 627 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Pendiente principio periodo (1264)
60 | 640 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Aplicado en declaración (1265)
61 | 653 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Pdte. aplicación ejercicios futuros (1266)
62 | 666 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2017. Pendiente principio periodo (1267)
63 | 679 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2017. Aplicado en declaración (1268)
64 | 692 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2017. Pdte. aplicación ejercicios futuros (1269)
65 | 705 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. Saldo negativo pendiente de compensación (1270)
66 | 718 | 600 | An |  | RESERVADO PARA LA A.E.A.T
67 | 1318 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10032000>
Total: |  | 1329

# Anexo C.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "33000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. Contribuyente "0" a "9" (1271)
7 | 14 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2014. Pendiente principio periodo (1272)
8 | 27 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2014. Aplicado en declaración (1273)
9 | 40 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2015. Pendiente principio periodo (1274)
10 | 53 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2015. Aplicado en declaración (1275)
11 | 66 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2015. Pdte. aplicación ejercicios futuros (1276)
12 | 79 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Pendiente principio periodo (1277)
13 | 92 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Aplicado en declaración (1278)
14 | 105 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Pdte. aplicación ejercicios futuros (1279)
15 | 118 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2017. Pendiente principio periodo (1280)
16 | 131 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2017. Aplicado en declaración (1281)
17 | 144 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2017. Pdte. aplicación ejercicios futuros (1282)
18 | 157 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. Saldo negativo pendiente de compensación (1283)
19 | 170 | 1 | Tit | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir.  Contribuyente "0" a "9" (1284)
20 | 171 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2013. Pendiente principio periodo (1285)
21 | 184 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2013. Aplicado en declaración (1286)
22 | 197 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2014. Pendiente principio periodo (1287)
23 | 210 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2014. Aplicado en declaración (1288)
24 | 223 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2014. Pdte. aplicación ejercicios futuros (1289)
25 | 236 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Pendiente principio periodo (1290)
26 | 249 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Aplicado en declaración (1291)
27 | 262 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Pdte. aplicación ejercicios futuros (1292)
28 | 275 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Pendiente principio periodo (1293)
29 | 288 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Aplicado en declaración (1294)
30 | 301 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Pdte. aplicación ejercicios futuros (1295)
31 | 314 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2017. Pendiente principio periodo (1296)
32 | 327 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2017. Aplicado en declaración (1297)
33 | 340 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2017. Pdte. aplicación ejercicios futuros (1298)
34 | 353 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. Aportaciones y contribuciones 2018 (1299)
35 | 366 | 1 | Tit | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. Contribuyente "0" a "9" (1300)
36 | 367 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2013. Pendiente principio periodo (1301)
37 | 380 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2013. Aplicado en declaración (1302)
38 | 393 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2014. Pendiente principio periodo (1303)
39 | 406 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2014. Aplicado en declaración (1304)
40 | 419 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2014. Pdte. aplicación ejercicios futuros (1305)
41 | 432 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Pendiente principio periodo (1306)
42 | 445 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Aplicado en declaración (1307)
43 | 458 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Pdte. aplicación ejercicios futuros (1308)
44 | 471 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Pendiente principio periodo (1309)
45 | 484 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Aplicado en declaración (1310)
46 | 497 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Pdte. aplicación ejercicios futuros (1311)
47 | 510 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2017. Pendiente principio periodo (1312)
48 | 523 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2017. Aplicado en declaración (1313)
49 | 536 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2017. Pdte. aplicación ejercicios futuros (1314)
50 | 549 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. Contribuciones 2018 (1315)
51 | 562 | 1 | Tit | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad.  Contribuyente "0" a "9" (1316)
52 | 563 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2013. Pendiente principio periodo (1317)
53 | 576 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2013. Aplicado en declaración (1318)
54 | 589 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2014. Pendiente principio periodo (1319)
55 | 602 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2014. Aplicado en declaración (1320)
56 | 615 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2014. Pdte. aplicación ejercicios futuros (1321)
57 | 628 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Pendiente principio periodo (1322)
58 | 641 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Aplicado en declaración (1323)
59 | 654 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Pdte. aplicación ejercicios futuros (1324)
60 | 667 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Pendiente principio periodo (1325)
61 | 680 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Aplicado en declaración (1326)
62 | 693 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Pdte. aplicación ejercicios futuros (1327)
63 | 706 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2017. Pendiente principio periodo (1328)
64 | 719 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2017. Aplicado en declaración (1329)
65 | 732 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2017. Pdte. aplicación ejercicios futuros (1330)
66 | 745 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. Aportaciones y contribuciones 2018 (1331)
67 | 758 | 1 | Tit | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes.  Contribuyente "0" a "9" (1332)
68 | 759 | 9 | An | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. NIF persona con discapacidad (1333)
69 | 768 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2013. Pendiente principio periodo (1334)
70 | 781 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2013. Aplicado en declaración (1335)
71 | 794 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2014. Pendiente principio periodo (1336)
72 | 807 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2014. Aplicado en declaración (1337)
73 | 820 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2014. Pdte. aplicación ejercicios futuros (1338)
74 | 833 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Pendiente principio periodo (1339)
75 | 846 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Aplicado en declaración (1340)
76 | 859 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Pdte. aplicación ejercicios futuros (1341)
77 | 872 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Pendiente principio periodo (1342)
78 | 885 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Aplicado en declaración (1343)
79 | 898 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Pdte. aplicación ejercicios futuros (1344)
80 | 911 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2017. Pendiente principio periodo (1345)
81 | 924 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2017. Aplicado en declaración (1346)
82 | 937 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2017. Pdte. aplicación ejercicios futuros (1347)
83 | 950 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. Aportaciones y contribuciones 2018 (1348)
84 | 963 | 1 | Tit | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.  Contribuyente "0" a "9" (1349)
85 | 964 | 9 | An | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.  NIF persona con discapacidad  (1350)
86 | 973 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2014. Pendiente principio periodo (1351)
87 | 986 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2014. Aplicado en declaración (1352)
88 | 999 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2015. Pendiente principio periodo (1353)
89 | 1012 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2015. Aplicado en declaración (1354)
90 | 1025 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2015. Pdte. aplicación ejercicios futuros (1355)
91 | 1038 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Pendiente principio periodo (1356)
92 | 1051 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Aplicado en declaración (1357)
93 | 1064 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Pdte. aplicación ejercicios futuros (1358)
94 | 1077 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2017. Pendiente principio periodo (1359)
95 | 1090 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2017. Aplicado en declaración (1360)
96 | 1103 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2017. Pdte. aplicación ejercicios futuros (1361)
97 | 1116 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir. Aportaciones 2018 (1362)
98 | 1129 | 600 | An |  | RESERVADO PARA LA A.E.A.T
99 | 1729 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10033000>
Total: |  | 1740

# Anexo C.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "34000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.  Contribuyente "0" a "9" (1363)
7 | 14 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2013. Pendiente principio periodo (1364)
8 | 27 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2013. Aplicado en declaración (1365)
9 | 40 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2014. Pendiente principio periodo (1366)
10 | 53 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2014. Aplicado en declaración (1367)
11 | 66 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2014. Pdte. aplicación ejercicios futuros (1368)
12 | 79 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Pendiente principio periodo (1369)
13 | 92 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Aplicado en declaración (1370)
14 | 105 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Pdte. aplicación ejercicios futuros (1371)
15 | 118 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Pendiente principio periodo (1372)
16 | 131 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Aplicado en declaración (1373)
17 | 144 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Pdte. aplicación ejercicios futuros (1374)
18 | 157 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2017. Pendiente principio periodo (1375)
19 | 170 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2017. Aplicado en declaración (1376)
20 | 183 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2017. Pdte. aplicación ejercicios futuros (1377)
21 | 196 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir. Aportaciones y contribuciones 2018 (1378)
22 | 209 | 1 | Tit | C | Bases liquidables generales negativas pendientes de compensar.  Contribuyente "0" a "9" (1379)
23 | 210 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2014. Pendiente principio periodo (1380)
24 | 223 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2014. Aplicado en declaración (1381)
25 | 236 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2015. Pendiente principio periodo (1382)
26 | 249 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2015. Aplicado en declaración (1383)
27 | 262 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2015. Pdte. aplicación ejercicios futuros (1384)
28 | 275 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Pendiente principio periodo (1385)
29 | 288 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Aplicado en declaración (1386)
30 | 301 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Pdte. aplicación ejercicios futuros (1387)
31 | 314 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2017. Pendiente principio periodo (1388)
32 | 327 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2017. Aplicado en declaración (1389)
33 | 340 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2017. Pdte. aplicación ejercicios futuros (1390)
34 | 353 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar. 2018 (1391)
35 | 366 | 600 | An |  | RESERVADO PARA LA A.E.A.T
36 | 966 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10034000>
Total: |  | 977

# I-D

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 1.01 |  | Impuesto sobre la Renta de las Personas Físicas 2018
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "35000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Resumen declaración (2) - Base liquidable general sometida a gravamen [0505]
7 | 26 | 13 | N | Resumen declaración (2) - Base liquidable del ahorro [0510]
8 | 39 | 13 | N | Resumen declaración (2) - Cuota íntegra estatal [0545]
9 | 52 | 13 | N | Resumen declaración (2) - Cuota íntegra autonómica [0546]
10 | 65 | 13 | N | Resumen declaración (2) - Cuota líquida estatal [0570]
11 | 78 | 13 | N | Resumen declaración (2) - Cuota líquida autonómica [0571]
12 | 91 | 13 | N | Resumen declaración (2) - Resultado a ingresar o a devolver [0695]
13 | 104 | 1 | Num | Opción de tributación. "1" Individual, "2" Conjunta.
14 | 105 | 1 | Num | Resumen declaración (2) - Solicitud de suspensión ingreso cónyuge/Renuncia cobro devolución otro cónyuge. "1" o "0" [7]
15 | 106 | 13 | N | Declaración Complementaria (3) - Resultado de Declaración Complementaria [0680]
16 | 119 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 0695 positiva - NO FRACCIONA el pago [1]  "1" o "0"
17 | 120 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 0695 positiva - SÍ FRACCIONA el pago [6] "1" o "0"
18 | 121 | 13 | N | Fraccionamiento del pago e ingreso (4) - Casilla 0695 positiva - Importe  [I1]
19 | 134 | 1 | Num | Fraccionamiento del pago e ingreso (4) - Casilla 0695 positiva - Forma de pago -"0" No consta; "1" Efectivo; "2" Adeudo en Cuenta; "3" Domiciliación
20 | 135 | 1 | Num | Opciones de pago 2º plazo (5) - NO DOMICILIA el pago [2]   "1" o "0"
21 | 136 | 1 | Num | Opciones de pago 2º plazo (5) - SÍ DOMICILIA el pago [3] "1" o "0"
22 | 137 | 13 | N | Opciones de pago 2º plazo (5) - Importe del 2º plazo [I2]
23 | 150 | 1 | Num | Devolución (6) - Casilla 0695 negativa - "0" No consta, "1" Devolución y "2" Renuncia devolución
24 | 151 | 13 | N | Devolución (6) - Casilla 0695 negativa - Importe [D]
25 | 164 | 34 | An | Cuenta bancaria (7) Número de cuenta IBAN
26 | 198 | 11 | An | Devolución - Código SWIFT-BIC
27 | 209 | 600 | An | RESERVADO PARA LA A.E.A.T
28 | 809 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10035000>
Total: |  | 820