# 100-00

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 17 | An | Constante. <T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "<T100020190A0000>"
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
12 | *** | 18 | An | Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "</T100020190A0000>"
Total |  | Variable
 |  |  |  | (**) A cumplimentar por las entidades desarrolladoras (EEDD)
 |  |  |  | Idioma de la declaración: (E) Castellano, (C) Catalán, (G) Gallego, (V) Valenciano
 |  |  |  | Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
 |  |  |  | NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
 |  |  | Páginas Complementarias
 |  |  | Pág | Apartado | Ocurrencias
 |  |  | 4 | Rendimientos del trabajo | 6
 |  |  | 5 | Rendimientos del capital mobiliario a integrar en la base imponible del ahorro | 6
 |  |  | 5 | Rend.capital mobiliario: Disp. Transitoria 4ª | 6
 |  |  | 5 | Rendimientos del capital mobiliario a integrar en la base imponible general | 6
 |  |  | 6 | Bienes inmuebles | 90
 |  |  | 8 | (D1) Rtos. aaee estim. directa | 6
 |  |  | 9 | (D2) Rtos. aaee estim. objetiva | 6
 |  |  | 10 | (D3) Rtos. activ. agricolas | 6
 |  |  | 11 | (E) Regímenes especiales | 8
 |  |  | 12 | (E) Relación de bienes inmuebles arrendados o cedidos a terceros por entidades en régimen de atribución de rentas | 60
 |  |  | 13 | (E) Imputaciones de agrupaciones de interés económico y uniones temporales de empresas | 8
 |  |  | 13 | (E) Imputaciones de rentas en el régimen de transparencia fiscal internacional | 8
 |  |  | 13 | (E) Imputación de rentas por la cesión de derechos de imagen | 8
 |  |  | 13 | (E) Imputación de rentas por la participación en Instituciones de Inversión Colectiva constituidas en paraísos fiscales | 8
 |  |  | 14 | (F1) Premios obtenidos por la participación en juegos, rifas o combinaciones aleatorias sin fines publicitarios | 6
 |  |  | 14 | (F1) Premios obtenidos por la participación en concursos o combinaciones aleatorias con fines publicitarios | 6
 |  |  | 14 | (F1) Otras ganancias y pérdidas patrimoniales que no derivan de la transmisión de elementos patrimoniales | 6
 |  |  | 14 | (F2) Aplicación disp. Transitoria 9ª | 40
 |  |  | 14 | (F2) G/P patrimoniales sometidas a retención o ingreso a cuenta derivadas de transmisiones o reembolsos de acciones o participaciones de instituciones de inversión colectiva | 60
 |  |  | 15 | (F2) G/P patrimoniales derivadas de transmisiones de acciones o participaciones negociadas | 60
 |  |  | 15 | (F2) Ganancias y pérdidas patrimoniales derivadas de transmisiones de derechos de suscripción | 60
 |  |  | 16 | (F2) G/P patrimoniales derivadas de transmisiones de otros elementos patrimoniales | 40
 |  |  | 16 | (F2) Otras ganancias patrimoniales | 15
 |  |  | 16 | (F2) Imputación a 2019 de G/P patrimoniales derivadas de transmisiones efectuadas en ejercicios anteriores (GANANCIAS) | 15
 |  |  | 16 | (F2) Imputación a 2019 de G/P patrimoniales derivadas de transmisiones efectuadas en ejercicios anteriores (PÉRDIDAS) | 15
 |  |  | 17 | (F2) Imputación a 2019 de ganancias patrimoniales acogidas a diferimiento por reinversión | 15
 |  |  | 17 | (F3) Ganancias patrimoniales por cambio de residencia fuera del territorio español | 15
 |  |  | 19 | (I) Reducciones por aportaciones y contribuciones a sistemas de previsión social | 4
 |  |  | 19 | (I) Reducciones por aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad | 4
 |  |  | 19 | (I) Reducciones por aportaciones a patrimonios protegidos de personas con discapacidad | 4
 |  |  | 19 | (I) Reducciones por pensiones compensatorias a favor del cónyuge y anualidades por alimentos, excepto en favor de los hijos | 4
 |  |  | 19 | (I) Reducciones por aportaciones a la mutualidad de previsión social de deportistas profesionales | 4
 |  |  | 22 | (M) Ded. Descendientes discapacidad | 15
 |  |  | 22 | (M) Ded. Ascendientes discapacidad | 6
 |  |  | 22 | (M) Ded. Cónyuge discapacidad | 3
 |  |  | 23 | (M) Ded. Familia numerosa | 3
 |  |  | 23 | (M) Ded. Ascendiente separado | 2
 |  |  | 23 | (M) Regularizaciones descendientes | 15
 |  |  | 23 | (M) Regularizaciones ascendientes | 6
 |  |  | C1 | Intereses de los capitales invertidos en la adquisición o mejora de inmuebles y gastos de reparación y conservación de los mismos, pendientes de deducir en los ejercicios siguientes. | 90
 |  |  | C1 | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación en ejercicios futuros | 40
 |  |  | C1 | Exención por reinversión de la ganancia patrimonial obtenida en 2019 por la transmisión de la vivienda habitual | 6
 |  |  | C1 | Exención por reinversión en entidades de nueva o reciente creación | 6
 |  |  | C1 | Exención por reinversión en rentas vitalicias | 6
 |  |  | C2 | Saldos negativos de ganancias y pérdidas patrimoniales pendientes de compensar en los ejercicios siguientes BIG | 6
 |  |  | C2 | Saldos negativos de ganancias y pérdidas patrimoniales pendientes de compensar en los ejercicios siguientes BIA | 6
 |  |  | C2 | Rendimientos de capital mobiliario negativos pendientes de compensar en los ejercicios siguientes | 6
 |  |  | C2 | Exceso no reducido de las aportaciones y contribuciones a sistemas de previsión social (régimen general) pendientes de compensar en los ejercicios siguientes(excepto los derivados de contribuciones empresariales a seguros colectivos de dependencia) | 4
 |  |  | C2 | Excesos no reducidos derivados de contribuciones empresariales a seguros colectivos de dependencia pendientes de compensar en los ejercicios siguientes | 4
 |  |  | C3 | Exceso no reducido de las aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad pendientes de reducir en los ejercicios siguientes (PARTÍCIPE) | 4
 |  |  | C3 | Exceso no reducido de las aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad pendientes de reducir en los ejercicios siguientes (PARIENTES) | 4
 |  |  | C3 | Exceso no reducido de las aportaciones a patrimonios protegidos de personas con discapacidad pendientes de compensar en los ejercicios siguientes | 4
 |  |  | C3 | Exceso no reducido de las aportaciones a la mutualidad de previsión social de deportistas profesionales pendientes de compensar en los ejercicios siguientes | 4
 |  |  | C3 | Bases liquidables generales negativas pendientes de compensar en los ejercicios siguientes | 6
 |  |  | D | Información adicional sobre gastos relacionados con bienes inmuebles | 90

# 100-01

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 1 | An | Tipo de declaración (Ver Nota)
7 | 14 | 9 | An | Primer Declarante - NIF (01) | OBLIGATORIO
8 | 23 | 80 | A | Primer Declarante - Apellidos y nombre  (02) | OBLIGATORIO
9 | 103 | 4 | Num | Ejercicio | OBLIGATORIO | Constante 2019
10 | 107 | 2 | An | Periodo | OBLIGATORIO | Constante 0A
11 | 109 | 1 | A | Primer Declarante - Sexo "H" Hombre, "M" Mujer (05) | OBLIGATORIO
12 | 110 | 1 | Num | Primer Declarante -Estado Civil. "1" Soltero/a, "2" Casado/a, "3" Viudo/a, "4" Divorciado/a o Separado/a | OBLIGATORIO
13 | 111 | 8 | Num | Primer Declarante - Fecha de nacimiento. (DDMMAAAA) Año < 2020 (10) | OBLIGATORIO
14 | 119 | 1 | Num | Primer Declarante - Grado de discapacidad   "0", "1", "2" ,"3" o "4" (11)
15 | 120 | 2 | An | Primer Declarante - País de residencia en la UE o EEE en 2019 (12)
16 | 122 | 9 | An | Cónyuge - NIF (13)
17 | 131 | 80 | A | Cónyuge - Apellidos y nombre (14)
18 | 211 | 1 | A | Cónyuge - Sexo "H" Hombre, "M" Mujer (59)
19 | 212 | 8 | Num | Cónyuge - Fecha de nacimiento. (DDMMAAAA) Año < 2019 o cero. (60)
20 | 220 | 1 | Num | Cónyuge - Grado de discapacidad   "0", "1", "2" ,"3" o "4" (61)
21 | 221 | 1 | Num | Cónyuge - No residente que no es contribuyente del I.R.P.F. - "1" o cero (62)
22 | 222 | 1 | Num | Cónyuge - No residente que reside en un país de la UE o del EEE, y se aplica la deducción por unidades familiares formadas por residentes fiscales en la UE o del EE.- "1" o cero  (64)
23 | 223 | 2 | An | Cónyuge - País de residencia en la UE o EEE en 2019 (43)
24 | 225 | 2 | Num | Comunidad/Ciudad autónoma de residencia en 2019 - Clave (70) Incluido en el fichero COMAUTO.TXT | OBLIGATORIO
25 | 227 | 1 | Num | Opción de tributación. "1" Individual, "2" Conjunta.  Campo OBLIGATORIO (68) (69) | OBLIGATORIO
26 | 228 | 8 | Num | Devengo - Fecha de  finalización del período impositivo (fallecimiento 2019)  (DDMMAAAA) o cero (67)
27 | 236 | 1 | A | Asignación tributaria a la Iglesia Católica. "X" o  blanco. (105)
28 | 237 | 1 | A | Asignación de cantidades a actividades de interés general consideradas de interés social. "X" o  blanco. (106)
29 | 238 | 12 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
30 | 250 | 9 | An | Representante -  N.I.F. (65)
31 | 259 | 32 | An | Representante -  Apellidos y nombre o razón social (66)
32 | 291 | 13 | Num | Nº de Justificante. RESERVADO PARA LA A.E.A.T. (Rellenar a ceros)
33 | 304 | 21 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE
34 | 325 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
35 | 338 | 600 | An | RESERVADO PARA LA A.E.A.T
36 | 938 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10001000>
Total |  | 949
 |  |  | Nota: | El Tipo de declaración puede ser: I (Ingreso), U (Domiciliación),  N (Negativa/Resultado cero), D (Solicitud de devolución) y R (Renuncia a la devolución)

# 100-02

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "02000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 9 | An | Hijos y descendientes - 1º -  N.I.F. (75)
7 | 22 | 60 | A | Hijos y descendientes - 1º -  Apellidos y nombre  (76)
8 | 82 | 8 | Num | Hijos y descendientes - 1º - Fecha de nacimiento.(DDMMAAAA) Año < 2020 o cero (77)
9 | 90 | 8 | Num | Hijos y descendientes - 1º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
10 | 98 | 1 | Num | Hijos y descendientes - 1º - Grado discapacidad   "0", "1", "2", "3" o "4" (79)
11 | 99 | 1 | An | Hijos y descendientes - 1º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (80)
12 | 100 | 2 | Num | Hijos y descendientes - 1º - Nº de orden (81)
13 | 102 | 1 | An | Hijos y descendientes - 1º - Otras situaciones  clave:"1","2","3","4" o blanco  (82)
14 | 103 | 9 | An | Hijos y descendientes - 2º - N.I.F. (75)
15 | 112 | 60 | A | Hijos y descendientes - 2º - Apellidos y nombre  (76)
16 | 172 | 8 | Num | Hijos y descendientes - 2º - Fecha de nacimiento.(DDMMAAAA) Año < 2020 o cero (77)
17 | 180 | 8 | Num | Hijos y descendientes - 2º - Fecha adopción o acogimiento.(DDMMAAAA) Año < 2020 o cero (78)
18 | 188 | 1 | Num | Hijos y descendientes - 2º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
19 | 189 | 1 | An | Hijos y descendientes - 2º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
20 | 190 | 2 | Num | Hijos y descendientes - 2º - Nº de orden (81)
21 | 192 | 1 | An | Hijos y descendientes - 2º - Otras situaciones  "1","2","3","4" o blanco  (82)
22 | 193 | 9 | An | Hijos y descendientes - 3º - N.I.F. (75)
23 | 202 | 60 | A | Hijos y descendientes - 3º - Apellidos y nombre  (76)
24 | 262 | 8 | Num | Hijos y descendientes - 3º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
25 | 270 | 8 | Num | Hijos y descendientes - 3º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
26 | 278 | 1 | Num | Hijos y descendientes - 3º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
27 | 279 | 1 | An | Hijos y descendientes - 3º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
28 | 280 | 2 | Num | Hijos y descendientes - 3º - Nº de orden (81)
29 | 282 | 1 | An | Hijos y descendientes - 3º - Otras situaciones  "1","2","3","4" o blanco  (82)
30 | 283 | 9 | An | Hijos y descendientes - 4º - N.I.F.  (75)
31 | 292 | 60 | A | Hijos y descendientes - 4º - Apellidos y nombre  (76)
32 | 352 | 8 | Num | Hijos y descendientes - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
33 | 360 | 8 | Num | Hijos y descendientes - 4º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
34 | 368 | 1 | Num | Hijos y descendientes - 4º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
35 | 369 | 1 | An | Hijos y descendientes - 4º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
36 | 370 | 2 | Num | Hijos y descendientes - 4º - Nº de orden (81)
37 | 372 | 1 | An | Hijos y descendientes - 4º - Otras situaciones  "1","2","3","4" o blanco  (82)
38 | 373 | 9 | An | Hijos y descendientes - 5º - N.I.F. (75)
39 | 382 | 60 | A | Hijos y descendientes - 5º - Apellidos y nombre  (76)
40 | 442 | 8 | Num | Hijos y descendientes - 5º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
41 | 450 | 8 | Num | Hijos y descendientes - 5º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
42 | 458 | 1 | Num | Hijos y descendientes - 5º - Grado discapacidad   "0", "1", "2", "3" o "4"  (79)
43 | 459 | 1 | An | Hijos y descendientes - 5º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
44 | 460 | 2 | Num | Hijos y descendientes - 5º - Nº de orden (81)
45 | 462 | 1 | An | Hijos y descendientes - 5º - Otras situaciones  "1","2","3","4" o blanco  (82)
46 | 463 | 9 | An | Hijos y descendientes - 6º - N.I.F. (75)
47 | 472 | 60 | A | Hijos y descendientes - 6º - Apellidos y nombre  (76)
48 | 532 | 8 | Num | Hijos y descendientes - 6º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
49 | 540 | 8 | Num | Hijos y descendientes - 6º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
50 | 548 | 1 | Num | Hijos y descendientes - 6º - Grado discapacidad  "0", "1", "2", "3" o "4" (79)
51 | 549 | 1 | An | Hijos y descendientes - 6º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
52 | 550 | 2 | Num | Hijos y descendientes - 6º - Nº de orden (81)
53 | 552 | 1 | An | Hijos y descendientes - 6º - Otras situaciones  "1","2","3","4" o blanco  (82)
54 | 553 | 9 | An | Hijos y descendientes - 7º - N.I.F.  (75)
55 | 562 | 60 | A | Hijos y descendientes - 7º - Apellidos y nombre  (76)
56 | 622 | 8 | Num | Hijos y descendientes - 7º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
57 | 630 | 8 | Num | Hijos y descendientes - 7º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
58 | 638 | 1 | Num | Hijos y descendientes - 7º - Grado discapacidad  "0", "1", "2", "3" o "4" (79)
59 | 639 | 1 | An | Hijos y descendientes - 7º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
60 | 640 | 2 | Num | Hijos y descendientes - 7º - Nº de orden (81)
61 | 642 | 1 | An | Hijos y descendientes - 7º - Otras situaciones  "1","2","3","4" o blanco  (82)
62 | 643 | 9 | An | Hijos y descendientes - 8º - N.I.F. (75)
63 | 652 | 60 | A | Hijos y descendientes - 8º - Apellidos y nombre  (76)
64 | 712 | 8 | Num | Hijos y descendientes - 8º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
65 | 720 | 8 | Num | Hijos y descendientes - 8º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
66 | 728 | 1 | Num | Hijos y descendientes - 8º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
67 | 729 | 1 | An | Hijos y descendientes - 8º - Vinculación.  clave:"1", "2", "3", "4", o blanco  (80)
68 | 730 | 2 | Num | Hijos y descendientes - 8º - Nº de orden (81)
69 | 732 | 1 | An | Hijos y descendientes - 8º - Otras situaciones  "1","2","3","4" o blanco  (82)
70 | 733 | 9 | An | Hijos y descendientes - 9º - N.I.F. (75)
71 | 742 | 60 | A | Hijos y descendientes - 9º - Apellidos y nombre  (76)
72 | 802 | 8 | Num | Hijos y descendientes - 9º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
73 | 810 | 8 | Num | Hijos y descendientes - 9º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
74 | 818 | 1 | Num | Hijos y descendientes - 9º - Grado discapacidad  "0", "1", "2", "3" o "4"  (79)
75 | 819 | 1 | An | Hijos y descendientes - 9º - Vinculación.  clave: "1", "2", "3", "4",  o blanco  (80)
76 | 820 | 2 | Num | Hijos y descendientes - 9º - Nº de orden (81)
77 | 822 | 1 | An | Hijos y descendientes - 9º - Otras situaciones  "1","2","3","4" o blanco  (82)
78 | 823 | 9 | An | Hijos y descendientes - 10º - N.I.F.  (75)
79 | 832 | 60 | A | Hijos y descendientes - 10º - Apellidos y nombre  (76)
80 | 892 | 8 | Num | Hijos y descendientes - 10º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
81 | 900 | 8 | Num | Hijos y descendientes - 10º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
82 | 908 | 1 | Num | Hijos y descendientes - 10º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
83 | 909 | 1 | An | Hijos y descendientes - 10º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
84 | 910 | 2 | Num | Hijos y descendientes - 10º - Nº de orden (81)
85 | 912 | 1 | An | Hijos y descendientes - 10º - Otras situaciones  "1","2","3","4" o blanco  (82)
86 | 913 | 9 | An | Hijos y descendientes - 11º - N.I.F. (75)
87 | 922 | 60 | A | Hijos y descendientes - 11º - Apellidos y nombre  (76)
88 | 982 | 8 | Num | Hijos y descendientes - 11º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
89 | 990 | 8 | Num | Hijos y descendientes - 11º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
90 | 998 | 1 | Num | Hijos y descendientes - 11º - Grado discapacidad "0", "1", "2", "3" o "4"  (79)
91 | 999 | 1 | An | Hijos y descendientes - 11º - Vinculación.  clave: "1", "2", "3", "4", o blanco  (80)
92 | 1000 | 2 | Num | Hijos y descendientes - 11º - Nº de orden (81)
93 | 1002 | 1 | An | Hijos y descendientes - 11º - Otras situaciones  "1","2","3","4" o blanco  (82)
94 | 1003 | 9 | An | Hijos y descendientes - 12º - N.I.F. (75)
95 | 1012 | 60 | A | Hijos y descendientes - 12º - Apellidos y nombre  (76)
96 | 1072 | 8 | Num | Hijos y descendientes - 12º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (77)
97 | 1080 | 8 | Num | Hijos y descendientes - 12º - Fecha adopción o acogimiento. (DDMMAAAA) Año < 2020 o cero (78)
98 | 1088 | 1 | Num | Hijos y descendientes - 12º - Grado discapacidad  "0", "1", "2", "3" o "4"  (79)
99 | 1089 | 1 | An | Hijos y descendientes - 12º - Vinculación.  clave:"1", "2", "3", "4",  o blanco  (80)
100 | 1090 | 2 | Num | Hijos y descendientes - 12º - Nº de orden (81)
101 | 1092 | 1 | An | Hijos y descendientes - 12º - Otras situaciones  "1","2","3","4" o blanco  (82)
102 | 1093 | 2 | Num | Hijos y descendientes - Fallecido 2019 - Nº Orden (83)
103 | 1095 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (84)
104 | 1103 | 2 | Num | Hijos y descendientes - Fallecido 2019 - Nº Orden (83)
105 | 1105 | 8 | Num | Hijos y descendientes - Fecha de fallecimiento (DDMMAAAA) (84)
106 | 1113 | 1 | Num | Si alguno de los hijos o descendientes es no residente, reside en un país de la UE o del EEE, y se aplica la deducción por unidades familiares formadas por residentes fiscales en la UE o del EEE (88) | "1" = SI;       cero = NO
107 | 1114 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
108 | 1123 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
109 | 1132 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
110 | 1141 | 9 | An | Hijos y descendientes - A efectos de la declaración conjunta los hijos 1, 2, 3 y 4 son relacionados con los NIF
111 | 1150 | 9 | An | Hijos y descendientes - Otro progenitor 1 - Nif (85)
112 | 1159 | 60 | A | Hijos y descendientes - Otro progenitor 1 - Apellidos y nombre (86)
113 | 1219 | 1 | A | Hijos y descendientes - Otro progenitor 1 - Sexo del otro progenitor.  "H" Hombre, "M" Mujer (89)
114 | 1220 | 1 | Num | Hijos y descendientes - Otro progenitor 1 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
115 | 1221 | 9 | An | Hijos y descendientes - Otro progenitor 2 - Nif (85)
116 | 1230 | 60 | A | Hijos y descendientes - Otro progenitor 2 - Apellidos y nombre (86)
117 | 1290 | 1 | A | Hijos y descendientes - Otro progenitor 2 - Sexo del otro progenitor.  "H" Hombre, "M" Mujer (89)
118 | 1291 | 1 | Num | Hijos y descendientes - Otro progenitor 2 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
119 | 1292 | 9 | An | Hijos y descendientes - Otro progenitor 3 - Nif (85)
120 | 1301 | 60 | A | Hijos y descendientes - Otro progenitor 3 - Apellidos y nombre (86)
121 | 1361 | 1 | A | Hijos y descendientes - Otro progenitor 3 - Sexo del otro progenitor.  "H" Hombre, "M" Mujer (89)
122 | 1362 | 1 | Num | Hijos y descendientes - Otro progenitor 3 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
123 | 1363 | 9 | An | Hijos y descendientes - Otro progenitor 4 - Nif (85)
124 | 1372 | 60 | A | Hijos y descendientes - Otro progenitor 4 - Apellidos y nombre (86)
125 | 1432 | 1 | A | Hijos y descendientes - Otro progenitor 4 - Sexo del otro progenitor.  "H" Hombre, "M" Mujer (89)
126 | 1433 | 1 | Num | Hijos y descendientes - Otro progenitor 4 - Si el otro progenitor no tiene NIF o NIE marque con una "X" esta casilla.  "1" o cero. (87)
127 | 1434 | 24 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
128 | 1458 | 9 | An | Ascendientes mayores 65 años o discapacitados - 1º - N.I.F.  (90)
129 | 1467 | 60 | A | Ascendientes mayores 65 años o discapacitados - 1º - Apellidos y nombre (91)
130 | 1527 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (92)
131 | 1535 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 1º - Grado discapacidad  "0", "1", "2", "3" o "4" (93)
132 | 1536 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Vinculación  clave:"1", "2" o blanco (94)
133 | 1537 | 1 | An | Ascendientes mayores 65 años o discapacitados - 1º - Convivencia   "2" a "9" o blanco (95)
134 | 1538 | 9 | An | Ascendientes mayores 65 años o discapacitados - 2º - N.I.F.  (90)
135 | 1547 | 60 | A | Ascendientes mayores 65 años o discapacitados - 2º - Apellidos y nombre (91)
136 | 1607 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (92)
137 | 1615 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 2º - Grado discapacidad  "0", "1", "2", "3" o "4"  (93)
138 | 1616 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Vinculación clave:"1", "2" o blanco  (94)
139 | 1617 | 1 | An | Ascendientes mayores 65 años o discapacitados - 2º - Convivencia  "2" a "9" o blanco  (95)
140 | 1618 | 9 | An | Ascendientes mayores 65 años o discapacitados - 3º - N.I.F.  (90)
141 | 1627 | 60 | A | Ascendientes mayores 65 años o discapacitados - 3º - Apellidos y nombre (91)
142 | 1687 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Fecha de nacimiento.(DDMMAAAA) Año < 2020 o cero (92)
143 | 1695 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 3º - Grado discapacidad  "0", "1", "2", "3" o "4"  (93)
144 | 1696 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Vinculación  clave:"1", "2" o blanco  (94)
145 | 1697 | 1 | An | Ascendientes mayores 65 años o discapacitados - 3º - Convivencia   "2" a "9" o blanco  (95)
146 | 1698 | 9 | An | Ascendientes mayores 65 años o discapacitados - 4º - N.I.F.  (90)
147 | 1707 | 60 | A | Ascendientes mayores 65 años o discapacitados - 4º - Apellidos y nombre (91)
148 | 1767 | 8 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Fecha de nacimiento. (DDMMAAAA) Año < 2020 o cero (92)
149 | 1775 | 1 | Num | Ascendientes mayores 65 años o discapacitados - 4º - Grado discapacidad  "0", "1", "2", "3" o "4" (93)
150 | 1776 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Vinculación  clave:"1", "2" o blanco  (94)
151 | 1777 | 1 | An | Ascendientes mayores 65 años o discapacitados - 4º - Convivencia  "2" a "9" o blanco  (95)
152 | 1778 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2019 - Nif (96)
153 | 1787 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
154 | 1795 | 9 | An | Ascendientes mayores 65 años o discapacitados -Fallecido 2019 - Nif (96)
155 | 1804 | 8 | Num | Ascendientes mayores 65 años o discapacitados - Fecha fallecimiento (97)
156 | 1812 | 600 | An | RESERVADO PARA LA A.E.A.T
157 | 2412 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10002000>
Total |  | 2423

# 100-03

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
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
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "04000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (A) Rdto. Trabajo - Contribuyente que obtiene los rendimientos . "0" a "9" (0001)
7 | 14 | 1 | Num | C | En el caso de los rendimientos derivados de la cesión de la explotación de los derechos de autor, si opta por imputar el anticipo a cuenta de los mismos a medida que vayan devengándose los derechos (0002) | "1" = SI; cero = NO
8 | 15 | 13 | N | C | Rdto. Trabajo - Retribuciones dinerarias (0003)
9 | 28 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Valoracion (0004)
10 | 41 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta (0005)
11 | 54 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Ingresos a cuenta repercutidos (0006)
12 | 67 | 13 | N | C | Rdto. Trabajo - Retribuciones en especie - Importe íntegro (0007)
13 | 80 | 13 | N | C | Rdto. Trabajo - Contribuciones empresariales a planes de pensiones, planes de previsión social empresarial  y mutualidades previsión social  (0008)
14 | 93 | 13 | N | C | Rdto. Trabajo - Contribuciones empresariales a seguros colectivos dependencia. Imputado al contribuyente (0009)
15 | 106 | 13 | N | C | Rdto. Trabajo - Aportaciones al patrimonio protegido de discapacitados - Importe (0010)
16 | 119 | 13 | N | C | Rdto. Trabajo - Reducciones (0011)
17 | 132 | 13 | N | C | Rdto. Trabajo - Total ingresos íntegros computables (0012)
18 | 145 | 13 | N | C | Rdto. Trabajo - Cotizaciones Seguridad Social/mutualidades funcionarios, detracciones por derechos pasivos y cotizaciones  colegios huérfanos (0013)
19 | 158 | 13 | N | C | Rdto. Trabajo - Cuotas satisfechas a sindicatos (0014)
20 | 171 | 13 | N | C | Rdto. Trabajo - Cuotas satisfechas a colegios profesionales (0015)
21 | 184 | 13 | N | C | Rdto. Trabajo - Gastos defensa jurídica derivados litigios con empleador (0016)
22 | 197 | 13 | N | C | Rdto. Trabajo - Rendimiento neto previo (0017)
23 | 210 | 13 | N |  | Rdto. Trabajo -Suma de rendimientos netos previos (0018)
24 | 223 | 13 | N |  | Rdto. Trabajo - Otros gastos deducibles (0019)
25 | 236 | 13 | N |  | Rdto. Trabajo - Incremento contribuyentes desempleados con traslado de residencia  (0020)
26 | 249 | 13 | N |  | Rdto. Trabajo - Incremento para trabajadores activos que sean personas con discapacidad  (0021)
27 | 262 | 13 | N |  | Rdto. Trabajo - Rendimiento neto  (0022)
28 | 275 | 13 | N |  | Rdto. Trabajo - Reducción por obtención rendimientos de trabajo. Cuantía aplicable con carácter general (0023)
29 | 288 | 13 | N |  | Rdto. Trabajo - Rendimiento neto reducido (0025)
30 | 301 | 600 | An |  | RESERVADO PARA LA A.E.A.T
31 | 901 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10004000>
Total: |  | 912

# 100-05

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "05000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (B) Rdto.capital mobiliario - Base imponible ahorro - Contribuyente que obtiene los rendimientos . "0" a "9" (0026)
7 | 14 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Intereses de cuentas, depósitos y activos financieros (0027)
8 | 27 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro  - Intereses de activos financieros con derecho a bonificación (0028)
9 | 40 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Dividendos y demás rendimientos por participación fondos propios entidades (0029)
10 | 53 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. transmisión o amortización de Letras del Tesoro (0030)
11 | 66 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. transmisión, amortización o reembolso otros activos financieros (0031)
12 | 79 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. contratos seguro vida o invalidez y operaciones capitalización. (0032)
13 | 92 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. procedentes de rentas que tengan por causa la imposición de capitales (0033)
14 | 105 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. derivados de valores de deuda subordinada o participaciones preferentes. (0034)
15 | 118 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rdtos. procedentes de seguros de vida, depósitos financieros que instrumenten Planes Ahorro (0035)
16 | 131 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Total ingresos íntegros (0036)
17 | 144 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Gastos fiscalmente deducibles (0037)
18 | 157 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rendimiento neto (0038)
19 | 170 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Reducción rendimientos determinados contratos de seguro (0039]
20 | 183 | 13 | N | C | Rdto.capital mobiliario -  Base imponible ahorro - Rendimiento neto reducido (0040)
21 | 196 | 13 | N |  | Rdto.capital mobiliario -  Base imponible ahorro  - Suma de rendimientos del capital mobiliario base imponible del ahorro (0041)
22 | 209 | 1 | Tit | C | Aplicación DT 4 - Contribuyente 1  "0" a "9" (0042)
23 | 210 | 13 | N | C | Aplicación DT 4 - Contribuyente 1 - Importe total acumulado del capital diferido percibido en 2015, 2016, 2017 y 2018 (0043)
24 | 223 | 13 | N | C | Aplicación DT 4 - Contribuyente 1 - Importe total de los capitales diferidos correspondientes a seguros de vida (0044)
25 | 236 | 1 | Tit | C | Rdto.capital mobiliario - Base imponible general - Contribuyente que obtiene los rendimientos . "0" a "9" (0045)
26 | 237 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos arrendamiento bienes muebles, negocios, minas, subarrendamientos (0046)
27 | 250 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos prestación asistencia técnica, salvo actividad económica (0047)
28 | 263 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos propiedad intelectual contribuyente no autor (0048)
29 | 276 | 1 | Num | C | Rdto.capital mobiliario -  Base imponible general -  Rendimientos derivados de la cesión de derechos de autor (0049) | "1" = SI; cero = NO
30 | 277 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimientos propiedad industrial no afecta a actividad económica (0050)
31 | 290 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Otros rendimientos del capital mobiliario a integrar en base imponible general (0051)
32 | 303 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Total ingresos íntegros (0052)
33 | 316 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Gastos fiscalmente deducibles (0053)
34 | 329 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimiento neto (0054)
35 | 342 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Reducciones de rendimientos generados en más de 2 años u obtenidos de forma irregular (0055)
36 | 355 | 13 | N | C | Rdto.capital mobiliario -  Base imponible general - Rendimiento neto reducido (0056)
37 | 368 | 13 | N |  | Rdto.capital mobiliario -  Base imponible general  - Suma de rendimientos del capital mobiliario base imponible general (0060)
38 | 381 | 600 | An |  | RESERVADO PARA LA A.E.A.T
39 | 981 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10005000>
Total: |  | 992

# 100-06 y 07

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "06000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 3 | Num | C | (C) Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Número de orden (0061)
7 | 16 | 1 | Tit | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Contribuyente "0" a "9" (0062)
8 | 17 | 5 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Porcentaje propiedad (3 enteros y 2 decimales) (0063)
9 | 22 | 5 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Porcentaje usufructo (3 enteros y 2 decimales) (0064)
10 | 27 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Situación "0", "1", "2", "3", "4" o "5" (0065)
11 | 28 | 20 | An | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Referencia catastral (0066)
12 | 48 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Naturaleza urbana "1 o cero" (0067)
13 | 49 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Naturaleza rústica "1 o cero" (0068)
14 | 50 | 65 | An | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Dirección (0069)
15 | 115 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Uso - Vivienda habitual 2019. "1 o cero" (0070)
16 | 116 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Uso - Vivienda en la que residen los hijos y/o el excónyuge. "1 o cero" (0071)
17 | 117 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Uso - Inmueble afecto a actividades económicas. "1 o cero" (0072)
18 | 118 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Uso - A disposición de sus titulares. "1 o cero" (0073)
19 | 119 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Uso - Arrendamiento como inmueble accesorio. "1 o cero" (0074)
20 | 120 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Uso - Arrendamiento. "1 o cero" (0075)
21 | 121 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Vivienda habitual. Número de días (0076)
22 | 124 | 20 | An | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Vivienda hijos y/o excónyuge. NIF del excónyuge (0077)
23 | 144 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Vivienda hijos y/o excónyuge. NIF de otro país. "1 o cero" (0078)
24 | 145 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Vivienda hijos y/o excónyuge. Número de días (0079)
25 | 148 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Afecto a actividades económicas. Afecto a actividades económicas. Número de días (0080)
26 | 151 | 1 | Tit | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Afecto a actividades económicas. Afecto a actividades económicas. Contribuyente "0", "2", "3", "4", "5", "6", "7", "8" o "9" (0081)
27 | 152 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Afecto a actividades económicas. Objeto de arrendamiento. Número de días (0082)
28 | 155 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. A disposición. Valor catastral (0083)
29 | 168 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. A disposición. Valor catastral revisado (0084) |  | "0" - blanco, "1" - Si,    "2" .- No
30 | 169 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. A disposición. Número de días (0085)
31 | 172 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. A disposición. Parte a disposición y parte a otros usos "1 o cero" (0086)
32 | 173 | 5 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. A disposición. Porcentaje a disposición (3 enteros y 2 decimales) (0087)
33 | 178 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. A disposición. Número de días a disposición (0088)
34 | 181 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. A disposición. Renta imputada (0089)
35 | 194 | 20 | An | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Arrendamiento como inmueble accesorio. Referencia catastral inmueble principal (0090)
36 | 214 | 20 | An | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Arrendatario 1. NIF (0091)
37 | 234 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Arrendatario 1. NIF de otro país "1 o cero" (0092)
38 | 235 | 20 | An | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Arrendatario 2. NIF (0094)
39 | 255 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Arrendatario 2. NIF de otro país "1 o cero" (0095)
40 | 256 | 20 | An | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Arrendatario 3. NIF (0097)
41 | 276 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Arrendatario 3. NIF de otro país "1 o cero" (0098)
42 | 277 | 8 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Arrendatario. Fecha contrato (DDMMAAAA) (0093)
43 | 285 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Arrendamiento con derecho a reducción "1 o cero" (0100)
44 | 286 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Número de días (0101)
45 | 289 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Ingresos íntegros computables (0102)
46 | 302 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Importe pendiente de deducir 2015, 2016, 2017 y 2018 (0103)
47 | 315 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Importe que se aplica (0104)
48 | 328 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Intereses 2019 (0105)
49 | 341 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Gastos de reparación 2019 (0106)
50 | 354 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Intereses y gastos de reparación de 2019 que se aplica (0107)
51 | 367 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Importe de 2019 pendiente de deducir (0108)
52 | 380 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Gastos comunidad (0109)
53 | 393 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Gastos formalización contrato (0110)
54 | 406 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Gastos defensa jurídica (0111)
55 | 419 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Otras cantidades (0112)
56 | 432 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Servicios y suministros (0113)
57 | 445 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Primas de contratos de seguro (0114)
58 | 458 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Tributos, recargos y tasas (0115)
59 | 471 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Saldos de dudoso cobro (0116)
60 | 484 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización de bienes muebles (0117)
61 | 497 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Adquisición onerosa "1 o cero" (0118)
62 | 498 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Adquisición lucrativa "1 o cero" (0119)
63 | 499 | 8 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Fecha adquisición (DDMMAAAA) (0120)
64 | 507 | 8 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Fecha transmisión (DDMMAAAA) (0121)
65 | 515 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Número de días arrendado (0122)
66 | 518 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Valor catastral (0123)
67 | 531 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Valor catastral construcción (0124)
68 | 544 | 5 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. % valor catastral construcción (3 enteros, 2 decimales) (0125)
69 | 549 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Importe adquisición (0126)
70 | 562 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Gastos y tributos (0127)
71 | 575 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Mejoras años anteriores (0128)
72 | 588 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Mejoras año 2019 (0129)
73 | 601 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Base de la amortización (0130)
74 | 614 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Amortización del inmueble y la mejora (0131)
75 | 627 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmueble. Amortización en casos especiales (0132)
76 | 640 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Adquisición onerosa "1 o cero" (0133)
77 | 641 | 1 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Adquisición lucrativa "1 o cero" (0134)
78 | 642 | 8 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Fecha adquisición (DDMMAAAA) (0135)
79 | 650 | 8 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Fecha de transmisión (0136)
80 | 658 | 3 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Número de días (0137)
81 | 661 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Valor catastral (0138)
82 | 674 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Valor catastral construcción (0139)
83 | 687 | 5 | Num | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. % Valor catastral construcción (3 enteros y 2 decimales) (0140)
84 | 692 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Importe de adquisición (0141)
85 | 705 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Gastos y tributos (0142)
86 | 718 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Mejoras años anteriores (0143)
87 | 731 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Mejoras año 2019 (0144)
88 | 744 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Base de la amortización (0145)
89 | 757 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Amortización del inmueble y las mejoras (0146)
90 | 770 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Amortización inmuebles accesorios. Amortización en casos especiales (0147)
91 | 783 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Gastos deducibles. Otros gastos fiscalmente deducibles (0148)
92 | 796 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Rendimiento neto (0149)
93 | 809 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Reducción por arrendamiento destinado a vivienda (0150)
94 | 822 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Reducción por rendimientos generados en más de 2 años(0151)
95 | 835 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Rendimiento mínimo computable en caso de parentesco (0152)
96 | 848 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Retenciones e ingresos a cuenta (0153)
97 | 861 | 13 | N | C | Bienes inmuebles. Relación inmuebles y rentas. Inmueble. Inmueble arrendado. Rendimiento neto reducido del capital inmobiliario (0154)
98 | 874 | 13 | N |  | Bienes inmuebles. Relación inmuebles y rentas. Suma de rentas inmobiliarias imputadas (0155)
99 | 887 | 13 | N |  | Bienes inmuebles. Relación inmuebles y rentas. Suma de rendimientos netos reducidos del capital inmobiliario (0156)
100 | 900 | 13 | N |  | Bienes inmuebles. Relación inmuebles y rentas. Suma de retenciones e ingresos a cuenta (0598)
101 | 913 | 600 | An |  | RESERVADO PARA LA A.E.A.T
102 | 1513 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10006000>
Total: |  | 1524
NOTA: Dentro de este registro se incluyen las partidas de las páginas 6 y 7 del modelo

# 100-08

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "08000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (D1) Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Contribuyente  "0" a "9" (0165)
7 | 14 | 1 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Tipo actividad. Clave (Blanco o de "1" a "5") (0166)
8 | 15 | 5 | An | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Epígrafe IAE (0167) (**)
9 | 20 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Modalidad aplicable "0" no consta "N" 1  o "S" 2 [0168)
10 | 21 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Criterio cobros/pagos. "1" o cero. (0169)
11 | 22 | 1 | Num | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Actv.realizada - Actividad - Cesión derechos de autor. "1" o cero. (0170)
12 | 23 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Explotación (0171)
13 | 36 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Financieros (0172)
14 | 49 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Por subvenciones (0173)
15 | 62 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Imputación de ingresos (0174)
16 | 75 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Autoconsumo bienes/servicios (0175)
17 | 88 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - IVA devengado (0176)
18 | 101 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Variación de existencias (0177)
19 | 114 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Otros ingresos (0178)
20 | 127 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Transmisión elementos patrimoniales: exceso amortización deducida (0179)
21 | 140 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Ingresos íntegros - Actividad - Total ingresos computables (0180)
22 | 153 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Compra de existencias (0181)
23 | 166 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Variación de existencias (0182)
24 | 179 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros consumos de explotación (0183)
25 | 192 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Sueldos y salarios (0184)
26 | 205 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Seguridad Social a cargo de la empresa (0185)
27 | 218 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Seguridad Social o aportaciones a mutualidades (0186)
28 | 231 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Indemnizaciones (0187)
29 | 244 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Dietas y asignaciones de viajes (0188)
30 | 257 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Aportaciones a sistemas de previsión social (0189)
31 | 270 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros gastos de personal (0190)
32 | 283 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Manutención del contribuyente (0191)
33 | 296 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Arrendamientos y cánones (0192)
34 | 309 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Reparación y conservación (0193)
35 | 322 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Suministros (luz, agua, gas, telefonía e internet) (0194)
36 | 335 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros suministros (0198)
37 | 348 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Servicios profesionales independientes (0199)
38 | 361 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Primas de seguros (0200)
39 | 374 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros servicios exteriores (0202)
40 | 387 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Gastos financieros (0203)
41 | 400 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - IVA soportado (0205)
42 | 413 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros tributos (0206)
43 | 426 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Dotaciones del ejercicio para amortización de inmovilizado material (0208)
44 | 439 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Dotaciones del ejercicio para amortización del inmovilizado inmaterial (0227)
45 | 452 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Pérdidas por insolvencia de deudores  (0214)
46 | 465 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Mecenazgo (convenios) (0215)
47 | 478 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Mecenazgo (gastos) (0216)
48 | 491 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Otros conceptos fiscalmente deducibles (0217)
49 | 504 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Suma  (0218)
50 | 517 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Normal - Provisiones (0219)
51 | 530 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Normal - Total gastos deducibles (0220)
52 | 543 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Simplificada - Diferencia (0221)
53 | 556 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Simplificada - Provisiones deduc./gastos difícil justif. (0222)
54 | 569 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Gastos - Actividad - Modalidad  Simplificada - Total gastos deducibles (0223)
55 | 582 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad - Rdto. neto (0224)
56 | 595 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad - Reducciones (0225)
57 | 608 | 13 | N | C | Rdto.actv.econ.est.directa - Actividad y rdto. obtenido - Rdto. neto y rdto. neto reduc. - Actividad - Rdto. neto reducido (0226)
58 | 621 | 13 | N |  | Rdto.actv.econ.est.directa - Suma de rendimientos netos reducidos  (0231)
59 | 634 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción ejercicio determinadas actividades económicas  (artículo 32.2.1º) (0232)
60 | 647 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción ejercicio determinadas actividades económicas (artículo 32.2.3º) (0233)
61 | 660 | 13 | N |  | Rdto.actv.econ.est.directa -  Reducción por inicio de una actividad económica (0234)
62 | 673 | 13 | N |  | Rdto.actv.econ.est.directa - Rendimiento neto reducido total actividades económicas en estimación directa (0235)
63 | 686 | 600 | An |  | RESERVADO PARA LA A.E.A.T
64 | 1286 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10008000>
Total: |  | 1297
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignarán las tres cifras seguidas de dos blancos.

# 100-09

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "09000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (D2) Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Contribuyente titular actividad   "0" a "9" (1441)
7 | 14 | 5 | An | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Clasificación IAE (1442) (**)
8 | 19 | 1 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Criterio cobros/pagos: "1" ó "0" (1443)
9 | 20 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Definición (1444)
10 | 44 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Unidades (nº) (7 enteros y 2 decimales) (1445)
11 | 53 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 1 - Rdto. por módulo (9 enteros y 2 decimales) (1446)
12 | 64 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Definición (1447)
13 | 88 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Unidades (nº) (7 enteros y 2 decimales) (1448)
14 | 97 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 2 - Rdto. por módulo (9 enteros y 2 decimales) (1449)
15 | 108 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Definición (1450)
16 | 132 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Unidades (nº) (7 enteros y 2 decimales) (1451)
17 | 141 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 3 - Rdto. por módulo (9 enteros y 2 decimales) (1452)
18 | 152 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Definición (1453)
19 | 176 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Unidades (nº) (7 enteros y 2 decimales) (1454)
20 | 185 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 4 - Rdto. por módulo (9 enteros y 2 decimales) (1455)
21 | 196 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Definición (1456)
22 | 220 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Unidades (nº) (7 enteros y 2 decimales) (1457)
23 | 229 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 5 - Rdto. por módulo (9 enteros y 2 decimales) (1458)
24 | 240 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Definición (1459)
25 | 264 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Unidades (nº) (7 enteros y 2 decimales) (1460)
26 | 273 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 6 - Rdto. por módulo (9 enteros y 2 decimales) (1461)
27 | 284 | 24 | A | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Definición (1462)
28 | 308 | 9 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Unidades (nº) (7 enteros y 2 decimales) (1463)
29 | 317 | 11 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Módulo 7 - Rdto. por módulo (9 enteros y 2 decimales) (1464)
30 | 328 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto previo (suma)  (1465)
31 | 341 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos al empleo  (1466)
32 | 354 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Minorizaciones por incentivos a la inversion (1467)
33 | 367 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto minorado (1468)
34 | 380 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector especial (2 enteros y 2 decimales) (1469)
35 | 384 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr.empresas pequeña dimensión (2 enteros y 2 decimales) (1470)
36 | 388 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de temporada (2 enteros y 2 decimales) (1471)
37 | 392 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corrector de exceso (2 enteros y 2 decimales) (1472)
38 | 396 | 4 | Num | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Indice corr. por inicio nueva activ. (2 enteros y 2 decimales) (1473)
39 | 400 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rdto. neto de módulos (1474)
40 | 413 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción de carácter general (1475)
41 | 426 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción para actividades económicas desarrolladas en el término municipal de Lorca (1476)
42 | 439 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Gastos extraordinarios circunstancias  excepcionales (1477)
43 | 452 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Otras percepciones empresariales (1478)
44 | 465 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª -Rendimiento neto actividad (1479)
45 | 478 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Reducción rdtos. más de 2 años o forma irregular (1480)
46 | 491 | 13 | N | C | Rdtos.activ.económ.est.objetiva - Act. realiz./rdtos. obtenidos - Activ. 1ª - Rendimiento neto reducido (1481)
47 | 504 | 13 | N |  | Rdtos.activ.económ.est.objetiva -  Suma rendimientos netos reducidos de las actividades económicas (1482)
48 | 517 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Reducción por el ejercicio determinadas actividades económicas (1483)
49 | 530 | 13 | N |  | Rdtos.activ.económ.est.objetiva - Rendimiento neto reducido total de las actividades económicas (1484)
50 | 543 | 600 | An |  | RESERVADO PARA LA A.E.A.T
51 | 1143 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10009000>
Total: |  | 1154
 |  |  |  |  | (**) Cuando el código IAE tenga cuatro cifras significativas se insertará un punto entre la tercera y cuarta cifra. En otro caso se consignaran las tres cifras seguidas de dos blancos.

# 100-10

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "10000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (D3) Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Contribuyente titular de actividad: de "0" a "9"  (1485)
7 | 14 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Clave actividad: de "0" a "9" (1486)
8 | 15 | 1 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Criterio cobros/pagos:  "1" ó "0" (1487)
9 | 16 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 1º - Ingresos íntegros (1488)
10 | 27 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 1º - Índice (1489)
11 | 33 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 1º - Rdto. base producto (1490)
12 | 44 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 2º - Ingresos íntegros (1491)
13 | 55 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 2º - Índice (1492)
14 | 61 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 2º - Rdto. base producto (1493)
15 | 72 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 3º - Ingresos íntegros (1494)
16 | 83 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 3º - Índice (1495)
17 | 89 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 3º - Rdto. base producto (1496)
18 | 100 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 4º - Ingresos íntegros (1497)
19 | 111 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 4º - Índice (1498)
20 | 117 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 4º - Rdto. base producto (1499)
21 | 128 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 5º - Ingresos íntegros (1500)
22 | 139 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 5º - Índice (1501)
23 | 145 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 5º - Rdto. base producto (1502)
24 | 156 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 6º - Ingresos íntegros (1503)
25 | 167 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 6º - Índice (1504)
26 | 173 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 6º - Rdto. base producto (1505)
27 | 184 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 7º - Ingresos íntegros (1506)
28 | 195 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 7º - Índice (1507)
29 | 201 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 7º - Rdto. base producto (1508)
30 | 212 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 8º - Ingresos íntegros (1509)
31 | 223 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 8º - Índice (1510)
32 | 229 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 8º - Rdto. base producto (1511)
33 | 240 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 9º - Ingresos íntegros (1512)
34 | 251 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 9º - Índice (1513)
35 | 257 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 9º - Rdto. base producto (1514)
36 | 268 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 10º - Ingresos íntegros (1515)
37 | 279 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 10º - Índice (1516)
38 | 285 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 10º - Rdto. base producto (1517)
39 | 296 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 11º - Ingresos íntegros (1518)
40 | 307 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 11º - Índice (1519)
41 | 313 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 11º - Rdto. base producto (1520)
42 | 324 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 12º - Ingresos íntegros (1521)
43 | 335 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 12º - Índice (1522)
44 | 341 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 12º - Rdto. base producto (1523)
45 | 352 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 13º - Ingresos íntegros (1524)
46 | 363 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 13º - Índice (1525)
47 | 369 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 13º - Rdto. base producto (1526)
48 | 380 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 14º - Ingresos íntegros (1527)
49 | 391 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 14º - Índice (1528)
50 | 397 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 14º - Rdto. base producto (1529)
51 | 408 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 15º - Ingresos íntegros (1530)
52 | 419 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 15º - Índice (1531)
53 | 425 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 15º - Rdto. base producto (1532)
54 | 436 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 16º - Ingresos íntegros (1533)
55 | 447 | 6 | An | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 16º - Índice (1534)
56 | 453 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Producto 16º - Rdto. base producto (1535)
57 | 464 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Total  ingresos íntegros (1536)
58 | 475 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Rendimiento neto previo (suma) (1537)
59 | 486 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Amortización inmovilizado (1538)
60 | 497 | 11 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Rdto. neto minorado  (1539)
61 | 508 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Medios de producción ajenos (2 enteros y 2 decimales) (1540)
62 | 512 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Utilización personal asalariado (2 enteros y 2 decimales) (1541)
63 | 516 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Cultivos tierras arrendadas (2 enteros y 2 decimales) (1542)
64 | 520 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 1 (1543) Ver NOTA
65 | 524 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Piensos adquir. 3º,más del 50 % (2 enteros y 2 decimales) Índice 2 Ver NOTA
66 | 528 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Actividades agricultura ecológica (2 enteros y dos decimales)  (1544)
67 | 532 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Cultivo en tierras regadío utilice energía electrica ( 2 enteros y 2 decimales) (1545)
68 | 536 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Empresa rdto.neto no supera 9447,91 € (2 enteros y 2 decimales)  (1546)
69 | 540 | 4 | Num | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Ind. correct.- Determinadas actividades forestales  (2 enteros y 2 decimales)  (1547)
70 | 544 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Rdto. neto de módulos (1548)
71 | 557 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Reducción carácter general (1549)
72 | 570 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Diferencia (1550)
73 | 583 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Reducción agricultores jóvenes (1551)
74 | 596 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Gastos extraordinarios por circunstancias excepcionales (1552)
75 | 609 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Rendimiento neto  (1553)
76 | 622 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Reducciones rendimientos generados más 2 años o forma irregular (1554)
77 | 635 | 13 | N | C | Rdtos. agríc.ganad.y forest. est. objetiva -Act. realiz./rdtos- Actividad - Rendimiento neto reducido (1555)
78 | 648 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Suma rendimientos netos reducidos de las actividades agrícolas, ganaderas y forestales en estimación objetiva  (1558)
79 | 661 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva -  Reducción por ejercicio determinadas actividades económicas (1559)
80 | 674 | 13 | N |  | Rdtos. agríc.ganad.y forest. est. objetiva - Rendimiento neto reducido total de las actividades agrícolas, ganaderas y forestales en estimación objetiva  (1560)
81 | 687 | 600 | An |  | RESERVADO PARA LA A.E.A.T
82 | 1287 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10010000>
Total: |  | 1298
 |  |  |  |  | NOTA: Cumplimentar sólo cuando el índice 2 sea distinto al índice 1.

# 100-11

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. Constante "<T" | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "11000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco ( No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (E) Regs. especiales - Régimen atribución rentas - Entidad - Entidades y contribuyentes partícipes - Contribuyente "0" a "9" (1561)
7 | 14 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Entidad - Entidades y contribuyentes partícipes - NIF Entidad (1562)
8 | 34 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad - Entidades y contribuyentes partícipes - Si ha consignado NIF de otro país "cero o 1" (1563)
9 | 35 | 4 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad - Entidades y contribuyentes partícipes - Porcentaje participación  (2 enteros y 2 decimales) (1564)
10 | 39 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Rdto. neto atribuido (1565)
11 | 52 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Minoraciones  aplicables (1566)
12 | 65 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdto. integrar base imponible general - Reducciones aplicables (1567)
13 | 78 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdto. integrar base imponible general . Rdto. neto computable (1568)
14 | 91 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Neto atribuido por la entidad . Imp. computable (1569)
15 | 104 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital mobiliario. - Rdtos. integrar base imponible ahorro. Rdto. Derivado valores deuda subordinada o partic. preferentes (1570)
16 | 117 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Rdto. neto atribuido (1571)
17 | 130 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Minoraciones aplicables (1572)
18 | 143 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Reducciones aplicables 23.2 (1573)
19 | 156 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Reducciones aplicables 23.3 y DT 25 (1574)
20 | 169 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. capital inmobiliario - Rdto. neto computable (1575)
21 | 182 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Criterio cobros/pagos. "1" o cero (1576)
22 | 183 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Rendimiento neto (1577)
23 | 196 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Minoraciones aplicables (1578)
24 | 209 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Provisiones deducibles y gastos difícil justificación (1579)
25 | 222 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Reducción aplicable art.32.1 y DT 25 (1580)
26 | 235 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Reducción aplicable art.32.2.3 (1581)
27 | 248 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Reducción aplicable art.32.3 (1582)
28 | 261 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Rdtos. actividades económicas - Rdto. Neto computable (1583)
29 | 274 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas  patrimoniales - No derivadas transmisiones - Ganancias patrimoniales no derivadas de transmisiones, atribuidas por la entidad (1584)
30 | 287 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - No derivadas transmisiones - Pérdidas patrimoniales no derivadas de transmisiones, atribuidas por la entidad (1585)
31 | 300 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales (1586)
32 | 313 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión destinado a constituir renta vitalicia (1587)
33 | 326 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Valor transmisión al que resulta aplicable (1588)
34 | 339 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas 50 por 100 (sólo determinados inmuebles urbanos) (1589)
35 | 352 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias exentas reinversión rentas vitalicias (1590)
36 | 365 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancia exenta reinversión en entidades de nueva o reciente creación (1591)
37 | 378 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Parte ganancias susceptibles reducción  (1592)
38 | 391 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Reducciones aplicables  (1593)
39 | 404 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas  (1594)
40 | 417 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Ganancias patrimoniales reducidas no exentas imputable 2019  (1595)
41 | 430 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución ganancias y pérdidas patrimoniales - Derivadas de transmisiones elementos patrimoniales (a integrar en BI ahorro) - Pérdidas patrimoniales atribuidas por la entidad  (1596)
42 | 443 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución de retenciones e ingresos a cuenta -  Retenciones de rendimientos de capital mobiliario (1597)
43 | 456 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución de retenciones e ingresos a cuenta -  Retenciones de rendimientos de capital inmobiliario (1598)
44 | 469 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución de retenciones e ingresos a cuenta -  Retenciones de rendimientos de actividades económicas (1599)
45 | 482 | 13 | N | C | Regs. especiales - Régimen atribución rentas - Entidad - Atribución de retenciones e ingresos a cuenta -  Retenciones de ganancias y pérdidas patrimoniales imputables a 2019 (1600)
46 | 495 | 600 | An |  | RESERVADO PARA LA A.E.A.T
47 | 1095 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10011000>
Total: |  | 1106

# 100-12

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "12000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de rendimientos netos de capital mobiliario (a integrar en la BI general) atribuidos (1601)
7 | 26 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de rendimientos netos de capital mobiliario (a integrar en la BI del ahorrol) atribuidos (1602)
8 | 39 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de rendimientos derivados de valores de deuda subordinada o participaciones preferentes (BI del ahorro) atribuidos (1603)
9 | 52 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de rendimientos netos del capital mobiliario atribuidos (1604)
10 | 65 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de rendimientos netos de actividades económicas atribuidos (1605)
11 | 78 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de ganancias patrimoniales no derivadas de transmisiones (a integrar en la BI general) atribuidas (1606)
12 | 91 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de pérdidas patrimoniales no derivadas de transmisiones (a integrar en la BI general) atribuidas (1607)
13 | 104 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de ganancias patrimoniales derivadas de transmisiones (a integrar en la BI del ahorro) atribuidas (1608)
14 | 117 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de pérdidas patrimoniales derivadas de transmisiones (a integrar en la BI del ahorro) atribuidas (1609)
15 | 130 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de retenciones e ingresos a cuenta atribuidos del capital mobiliario (0592)
16 | 143 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de retenciones e ingresos a cuenta atribuidos del capital inmobiliario (0593)
17 | 156 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de retenciones e ingresos a cuenta atribuidos de actividades económicas (0594)
18 | 169 | 13 | N |  | Regs. especiales - Régimen atribución rentas - Suma de retenciones e ingresos a cuenta atribuidos de ganancias y pérdidas patrimoniales imputables (0600)
19 | 182 | 1 | Tit | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - Contribuyente partícipe "0" a "9" (1614)
20 | 183 | 5 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - Porcentaje titularidad (3 enteros, 2 decimales) (1615)
21 | 188 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - Naturaleza urbana "cero o 1" (1616)
22 | 189 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - Naturaleza rústica "cero o 1" (1617)
23 | 190 | 3 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - Nº de días (1618)
24 | 193 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - Situación (clave) "1", "2", "3", "4" o "5" (1619)
25 | 194 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - Referencia catastral (1620)
26 | 214 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - NIF de la entidad (1621)
27 | 234 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 1 - No residente "cero o 1" (1622)
28 | 235 | 1 | Tit | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - Contribuyente partícipe "0" a "9" (1614)
29 | 236 | 5 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - Porcentaje titularidad (3 enteros, 2 decimales) (1615)
30 | 241 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - Naturaleza urbana "cero o 1" (1616)
31 | 242 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - Naturaleza rústica "cero o 1" (1617)
32 | 243 | 3 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - Nº de días (1618)
33 | 246 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - Situación (clave) "1", "2", "3", "4" o "5" (1619)
34 | 247 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - Referencia catastral (1620)
35 | 267 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - NIF de la entidad (1621)
36 | 287 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 2 - No residente "cero o 1" (1622)
37 | 288 | 1 | Tit | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - Contribuyente partícipe "0" a "9" (1614)
38 | 289 | 5 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - Porcentaje titularidad (3 enteros, 2 decimales) (1615)
39 | 294 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - Naturaleza urbana "cero o 1" (1616)
40 | 295 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - Naturaleza rústica "cero o 1" (1617)
41 | 296 | 3 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - Nº de días (1618)
42 | 299 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - Situación (clave) "1", "2", "3", "4" o "5" (1619)
43 | 300 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - Referencia catastral (1620)
44 | 320 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - NIF de la entidad (1621)
45 | 340 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 3 - No residente "cero o 1" (1622)
46 | 341 | 1 | Tit | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - Contribuyente partícipe "0" a "9" (1614)
47 | 342 | 5 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - Porcentaje titularidad (3 enteros, 2 decimales) (1615)
48 | 347 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - Naturaleza urbana "cero o 1" (1616)
49 | 348 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - Naturaleza rústica "cero o 1" (1617)
50 | 349 | 3 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - Nº de días (1618)
51 | 352 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - Situación (clave) "1", "2", "3", "4" o "5" (1619)
52 | 353 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - Referencia catastral (1620)
53 | 373 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - NIF de la entidad (1621)
54 | 393 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 4 - No residente "cero o 1" (1622)
55 | 394 | 1 | Tit | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - Contribuyente partícipe "0" a "9" (1614)
56 | 395 | 5 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - Porcentaje titularidad (3 enteros, 2 decimales) (1615)
57 | 400 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - Naturaleza urbana "cero o 1" (1616)
58 | 401 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - Naturaleza rústica "cero o 1" (1617)
59 | 402 | 3 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - Nº de días (1618)
60 | 405 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - Situación (clave) "1", "2", "3", "4" o "5" (1619)
61 | 406 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - Referencia catastral (1620)
62 | 426 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - NIF de la entidad (1621)
63 | 446 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 5 - No residente "cero o 1" (1622)
64 | 447 | 1 | Tit | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - Contribuyente partícipe "0" a "9" (1614)
65 | 448 | 5 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - Porcentaje titularidad (3 enteros, 2 decimales) (1615)
66 | 453 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - Naturaleza urbana "cero o 1" (1616)
67 | 454 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - Naturaleza rústica "cero o 1" (1617)
68 | 455 | 3 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - Nº de días (1618)
69 | 458 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - Situación (clave) "1", "2", "3", "4" o "5" (1619)
70 | 459 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - Referencia catastral (1620)
71 | 479 | 20 | An | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - NIF de la entidad (1621)
72 | 499 | 1 | Num | C | Regs. especiales - Régimen atribución rentas - Inmuebles arrendados - Inmueble 6 - No residente "cero o 1" (1622)
73 | 500 | 600 | An |  | RESERVADO PARA LA A.E.A.T
74 | 1100 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10012000>
Total: |  | 1111

# 100-13

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "13000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (E) Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1-  Entidades y contribuyentes socios. Contribuyente "0" a "9" (0256)
7 | 14 | 9 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1-  Entidades y contribuyentes socios. N.I.F. Entidad (0257)
8 | 23 | 1 | An | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Entidades y contribuyentes socios. Criterio imputación temporal. Clave (blanco, "1" ó "2") (0258)
9 | 24 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Base imponible imputada  (0259)
10 | 37 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones inversión empresarial (0260)
11 | 50 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones creación empleo (0261)
12 | 63 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deduccciones rentas Ceuta/Melilla (0262)
13 | 76 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones bases imponibles y deducciones - Deducciones doble imposición internacional. (0263)
14 | 89 | 13 | N | C | Regs. especiales - Agrupaciones interés económico y UTES - Entidad 1- Imputaciones retenciones e ingresos a cuenta  - Retenciones e ingresos a cuenta imputados (0264)
15 | 102 | 13 | N |  | Regs. especiales - Agrupaciones interés económico y UTES - Suma de bases imponibles imputadas  (0265)
16 | 115 | 13 | N |  | Regs. especiales - Agrupaciones interés económico y UTES - Suma de retenciones e ingresos a cuenta imputados (0601)
17 | 128 | 1 | Tit | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Contribuyente  "0" a "9" (0267)
18 | 129 | 24 | An | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Denominación entidad no residente (0268)
19 | 153 | 13 | N | C | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Entidad 1 - Importe imputación  (0269)
20 | 166 | 13 | N |  | Regs. especiales - Imputación rentas transparencia fiscal internacional -  Suma imputaciones de rentas transparencia fiscal internacional (0270)
21 | 179 | 1 | Tit | C | Regs. especiales - Imputación rentas cesión derechos imagen - Contribuyente que debe efectuar la imputacion.  "0" a "9" (0271)
22 | 180 | 25 | An | C | Regs. especiales - Imputación rentas cesión derechos imagen - NIF o denominación persona/entidad cesionaria derechos imagen (0272)
23 | 205 | 25 | An | C | Regs. especiales - Imputación rentas cesión derechos imagen - NIF o denominación persona/entidad relación laboral (0273)
24 | 230 | 13 | N | C | Regs. especiales - Imputación rentas cesión derechos imagen - Cantidad a imputar  (0274)
25 | 243 | 13 | N |  | Regs. especiales - Imputación rentas cesión derechos imagen - Suma imputaciones de rentas por cesión derechos de imagen (0275)
26 | 256 | 1 | Tit | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Contribuyente  "0" a "9" (0276)
27 | 257 | 24 | An | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Denominación Institución (0277)
28 | 281 | 13 | N | C | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales - I. I. C. 1 - Importe imputación (0278)
29 | 294 | 13 | N |  | Regs. especiales - Imputación rentas  I. I.Colectiva  paraísos fiscales -Suma de imputaciones de rentas por participación en IIC (0280)
30 | 307 | 600 | An |  | RESERVADO PARA LA A.E.A.T
31 | 907 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10013000>
Total: |  | 918

# 100-14

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "14000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (F1) Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Contribuyente  que obtiene los premios   "0" a "9" (0281)
7 | 14 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En metálico - Importe (0282)
8 | 27 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Valoración (0283)
9 | 40 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta (0284)
10 | 53 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Ingresos a cuenta repercutidos (0285)
11 | 66 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - En especie - Importe computable (0286)
12 | 79 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Pérdidas patrimoniales derivadas de estos juegos (0287)
13 | 92 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de ganancias patrimoniales derivadas de estos juegos (0288)
14 | 105 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de pérdidas patrimoniales derivadas de estos juegos (0289)
15 | 118 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios en juegos, rifas - Suma de ganancias patrimoniales netas derivadas de estos juegos (0290)
16 | 131 | 1 | Tit | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - Contribuyente que obtiene los premios. "0" a "9" (0291)
17 | 132 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En metálico - Importe (0292)
18 | 145 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Valoración (0293)
19 | 158 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta (0294)
20 | 171 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Ingresos a cuenta repercutidos (0295)
21 | 184 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - En especie - Importe computable (0296)
22 | 197 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Premios, concursos o combinaciones aleatorias con fines publicitarios - Suma de ganancias patrimoniales derivadas de premios (0297)
23 | 210 | 1 | Tit | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Contribuyente que obtiene otras ganancias/pérdidas. "0" a "9" (0298)
24 | 211 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Subvenciones adquisición vivienda (0299)
25 | 224 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Otras subvenciones o ayudas (0300)
26 | 237 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Demás ganancias patrimoniales derivadas de ayudas públicas (0301)
27 | 250 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Ganancias patrimoniales vecinos por aprovechamientos forestales (0302)
28 | 263 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Renta básica emancipación (0303)
29 | 276 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe ganancias (0304)
30 | 289 | 13 | N | C | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Importe pérdidas (0305)
31 | 302 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Suma de otras ganancias que no derivan de la transmisión (0306)
32 | 315 | 13 | N |  | Ganancias/pérdidas patrimoniales no derivan transmisión - Otras Ganancias/pérdidas - Suma de otras pérdidas que no derivan de la transmisión (0307)
33 | 328 | 1 | Tit | C | (F2) Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente "0" a "9" [0308]
34 | 329 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Aplicación DT 9  - Contribuyente - Valor total acumulado [0309]
35 | 342 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) - Inst. inv. Colectiva o SOCIMI- Sociedad/Fondo - Contribuyente "0" a "9" (0310)
36 | 343 | 9 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo - N.I.F. (0311)
37 | 352 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo -  Importe global transmisiones (0312)
38 | 365 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo - Importe global transmisiones -  Valor transmisión para renta vitalicia (0313)
39 | 378 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo - Importe global transmisiones -  Valor transmisión aplicable D.T.9ª (0314)
40 | 391 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Sociedad/Fondo - Importe global adquisiciones (0315)
41 | 404 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados -  Sociedad/Fondo -Ganancias patrimoniales (0316)
42 | 417 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados - Sociedad/Fondo -Ganancias exentas reinversión rentas vitalicias (0317)
43 | 430 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados  - Sociedad/Fondo - Parte ganancias suceptible reducción (0318)
44 | 443 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados -Sociedad/Fondo - Reducción aplicable (0319)
45 | 456 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados - Sociedad/Fondo - Ganancias patrimoniales reducidas no exentas (0320)
46 | 469 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados - Sociedad/Fondo - Pérdidas patrimoniales (0321)
47 | 482 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. colectiva o SOCIMI- Resultados - Sociedad/Fondo - Pérdidas patrimoniales imputables a 2019 (0322)
48 | 495 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. Colectiva - Suma de ganancias patrimoniales de transmisiones o reembolsos acciones o participaciones Inst.Inv.Colectiva o SOCIMI (0324)
49 | 508 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro)  - Inst. inv. Colectiva - Suma de pérdidas patrimoniales de transmisiones o reembolsos acciones o participaciones Inst.Inv.Colectiva o SOCIMI (0325)
50 | 521 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
51 | 524 | 600 | An |  | RESERVADO PARA LA A.E.A.T
52 | 1124 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10014000>
Total: |  | 1135

# 100-15

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "15000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones - Entidad -  Contribuyente valores transmitidos "0" a "9" (0326)
7 | 14 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones - Entidad - Denominación valores (0327)
8 | 34 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Acciones  - Entidad - Importe global efectuadas en 2017 (0328)
9 | 47 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones - Entidad - Importe global efectuadas en 2017 - Valor transmisión a constituir en renta vitalicia  (0329)
10 | 60 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Acciones - Entidad - Importe global efectuadas en 2017 - Valor transmisión aplicable D.T.9ª (0330)
11 | 73 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Valor adquisición global (0331)
12 | 86 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados -  Ganancias patrimoniales (0332)
13 | 99 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0333)
14 | 112 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0334)
15 | 125 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Reducción aplicable (0335)
16 | 138 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Ganancias patrimoniales no exentas (0336)
17 | 151 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Pérdidas patrim. Importe obtenido (0337)
18 | 164 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Entidad - Resultados  - Pérdidas patrim. Importe computable (0338)
19 | 177 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Suma de ganancias patrimoniales derivadas de transmisiones de acciones  negociadas (0339)
20 | 190 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Acciones  - Suma de pérdidas patrimoniales derivadas de transmisiones de acciones  negociadas (0340)
21 | 203 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
22 | 206 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad - Contribuyente valores transmitidos "0" a "9" (0341)
23 | 207 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción - Entidad - Denominación valores (0342)
24 | 227 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Derechos de suscripción  - Entidad - Importe global efectuadas en 2019 (0343)
25 | 240 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad - Importe global efectuadas en 2019 - Valor transmisión a constituir en renta vitalicia  (0344)
26 | 253 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -  Derechos de suscripción - Entidad - Importe global efectuadas en 2019 - Valor transmisión aplicable D.T.9ª (0345)
27 | 266 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Valor adquisición global (0346)
28 | 279 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados -  Ganancias patrimoniales (0347)
29 | 292 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Ganancias exentas reinversión en rentas vitalicias (0348)
30 | 305 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Parte ganancias patrimoniales susceptibles reducción (0349)
31 | 318 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Reducción aplicable (0350)
32 | 331 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Ganancias patrimoniales no exentas (0351)
33 | 344 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Pérdidas patrim. Importe obtenido (0352)
34 | 357 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Entidad - Resultados  - Pérdidas patrim. Importe computable (0353)
35 | 370 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Suma de ganancias patrimoniales derivadas de transmisiones de derechos de suscripción (0354)
36 | 383 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) -Derechos de suscripción  - Suma de pérdidas patrimoniales derivadas de transmisiones de derechos de suscripción (0355)
37 | 396 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
38 | 399 | 600 | An |  | RESERVADO PARA LA A.E.A.T
39 | 999 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10015000>
Total: |  | 1010

# 100-16

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "16000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 3 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Nº orden operación (1623)
7 | 16 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Contribuyente "0" a "9" (1624)
8 | 17 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Imput. temporal: Operaciones a plazos o aplazado. "1" ó "0" (1625)
9 | 18 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Tipo elemento. Clave "0" a "7" (1626)
10 | 19 | 1 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Inmuebles. Situación. Clave "0" a "5" (1627)
11 | 20 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Inmuebles. Ref. catastral 1 (1628)
12 | 40 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Inmuebles. Ref. catastral 2 (1629)
13 | 60 | 20 | An | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Inmuebles. Ref. catastral 3 (1630)
14 | 80 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha transmisión (1631)
15 | 88 | 8 | Num | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Fecha adquisición (1632)
16 | 96 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión (1633)
17 | 109 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Constituir renta vitalicia (1634)
18 | 122 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - De la vivienda habitual (1635)
19 | 135 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor transmisión - Susceptible de reducción (1636)
20 | 148 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 -Valor adquisición (1637)
21 | 161 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida obtenida (1638)
22 | 174 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia negativa - Pérdida imputable (1639)
23 | 187 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia obtenida (1640)
24 | 200 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta 50 por 100 (1641)
25 | 213 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en rentas vitalicias (1642)
26 | 226 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en vivienda habitual (1643)
27 | 239 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia exenta reinversión en entidades de nueva o reciente creación (1644)
28 | 252 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Diferencia positiva - Ganancia no exenta (1645)
29 | 265 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Parte ganancia susceptible reducción  (1646)
30 | 278 | 4 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Nº años permanencia hasta 31/12/1994  (1647)
31 | 282 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Reducción aplicable (1648)
32 | 295 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida (1649)
33 | 308 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos no afectos - Ganancia patrimonial reducida  no exenta  (1650)
34 | 321 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Parte ganancia susceptible reducción  (1651)
35 | 334 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Reducción licencia autotaxis  (1652)
36 | 347 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida (1653)
37 | 360 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Elemento 1 - Elementos afectos - Ganancia patrimonial reducida no exenta  (1654)
38 | 373 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de pérdidas patrimoniales derivadas de transmisiones de otros elementos patrimoniales (0385)
39 | 386 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de ganancias patrimoniales derivadas de transmisiones de otros elementos patrimoniales no afectos a actividades económicas (0386)
40 | 399 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otros elementos - Suma de ganancias patrimoniales derivadas de transmisiones de otros elementos patrimoniales afectos a actividades económicas (0387)
41 | 412 | 3 | Num |  | Número de Ganancias/Pérdidas en declaración conjunta (Reservado para la Administración)
42 | 415 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Contribuyente "0" a "9" (0388)
43 | 416 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Otras ganancias BI ahorro (0389)
44 | 429 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Otras ganancias patrimoniales - Suma de otras ganancias BI ahorro (0390)
45 | 442 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2019. Ganancias/pérdidas ejercicios anteriores - Ganancia 1 -  Contribuyente "0" a "9" (0391)
46 | 443 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2019. Ganancias/pérdidas ejercicios anteriores - Ganancia 1 -  Importe a imputar (0392)
47 | 456 | 1 | Tit | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2019. Ganancias/pérdidas ejercicios anteriores - Pérdida  1 -  Contribuyente "0" a "9" (0394)
48 | 457 | 13 | N | C | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2019. Ganancias/pérdidas ejercicios anteriores - Pérdida  1 -  Importe pérdida a imputar (0395)
49 | 470 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2019. Ganancias/pérdidas ejercicios anteriores - Importe ganancia a imputar  - Total (0393)
50 | 483 | 13 | N |  | Ganancias/pérdidas patrimoniales derivadas transmisión (a integrar en BI ahorro) (continuación) - Imputación a 2019. Ganancias/pérdidas ejercicios anteriores -  Importe pérdida a imputar - Total  (0396)
51 | 496 | 600 | An |  | RESERVADO PARA LA A.E.A.T
52 | 1096 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10016000>
Total: |  | 1107

# 100-17

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "17000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | (F2) Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2019 diferimiento por reinversión - Ganancia - Contribuyente "0" a "9" (0398)
7 | 14 | 13 | N | C | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2019 diferimiento por reinversión - Ganancia - Importe ganancia (0399)
8 | 27 | 13 | N |  | Ganancias/pérdidas derivadas transmisión (BI general) - Imputación 2018 diferimiento por reinversión - Suma de imputación a 2018 ganancias patrimoniales acogidas a diferimiento por reinversión (0400)
9 | 40 | 1 | Num | C | (F3) Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Contribuyente que ha transmitido intervivos las acciones "1" o "0" (0401)
10 | 41 | 1 | Tit | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Contribuyente titular valores "0" a "9" (0402)
11 | 42 | 9 | An | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Nif sociedad emisora o fondo de inversión (0403)
12 | 51 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Valor de mercado  acciones/participaciones (0404)
13 | 64 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Valor transmisión acciones (0405)
14 | 77 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Valor al que resulta aplicable D.T.9ª (0406)
15 | 90 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Valor adquisición (0407)
16 | 103 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Resultados - Ganancias patrimoniales (0408)
17 | 116 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Resultados - Ganancias suceptibles reducción (0409)
18 | 129 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Resultados - Reducción aplicable (0410)
19 | 142 | 13 | N | C | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Entidad -  Resultados - Ganancias patrimoniales reducidas (0411)
20 | 155 | 13 | N |  | Ganancias por cambio residencia fuera territorio español (BI ahorro) -  Suma de ganancias patrimoniales por cambio de residencia fuera del territorio español (0412)
21 | 168 | 1 | Tit |  | (F4) Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente1 "0" a "9" (0413)
22 | 169 | 2 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España -  Número de operaciones1 (0414)
23 | 171 | 1 | Tit |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Contribuyente 2   "0" a "9" (0415)
24 | 172 | 2 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Número de operaciones 2 (0416)
25 | 174 | 1 | Num |  | Régimen especial fusiones, escisiones y canje valores entidades no residentes en España - Si entidades no residentes no han aplicado régimen fiscal similar a éste  (0417)
26 | 175 | 13 | N |  | (G) Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2019 - A integrar en base imponible general -  Suma ganancias (0418)
27 | 188 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2019 - A integrar base imponible general -  Suma pérdidas (0419)
28 | 201 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2019 - A integrar base imponible general -  Saldo neto - Diferencia positiva (0420)
29 | 214 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2019 - A integrar base imponible general -  Saldo neto - Diferencia negativa (0421)
30 | 227 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2019 - A integrar base imponible ahorro - Suma ganancias (0422)
31 | 240 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2019 - A integrar base imponible ahorro - Suma pérdidas (0423)
32 | 253 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2019 - A integrar base imponible ahorro - Saldo neto  - Diferencia positiva (0424)
33 | 266 | 13 | N |  | Integración y compensación de rentas - Integración y compensación ganancias/pérdidas patrimoniales imputables 2019 - A integrar base imponible ahorro - Saldo neto - Diferencia negativa (0425)
34 | 279 | 13 | N |  | Integración y compensación de rentas - Integración y compensación rdtos. capital mobiliario imputables 2019 a integrar B.I. ahorro - Saldo neto positivo rdto. capital mobiliario (0429)
35 | 292 | 13 | N |  | Integración y compensación de rentas - Integración y compensación rdtos. capital mobiliario imputables 2019 a integrar B.I. ahorro - Saldo neto negativo rdto. capital mobiliario (0430)
36 | 305 | 600 | An |  | RESERVADO PARA LA A.E.A.T
37 | 905 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10017000>
Total: |  | 916

# 100-18

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "18000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (H) Base imponible general y base imponible ahorro - BI general - Saldo neto positivo ganancias/pérdidas 2019 a integrar base imponible general (0420)
7 | 26 | 13 | N | Base imponible general y base imponible ahorro - BI general - Compensación - Saldos netos negativos ganancias/pérdidas 2015 a 2018  pendientes compensasión (0431)
8 | 39 | 13 | N | Base imponible general y base imponible ahorro - BI general - Saldos neto rendimientos a integrar en base Imponible general (0432)
9 | 52 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Saldo neto negativo ganancias/pérdidas 2019 (0433)
10 | 65 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Compensaciones - Resto saldos netos negativos ganancias/pérdidas 2015 a 2018 pendientes compensación (0434)
11 | 78 | 13 | N | Base imponible general y base imponible ahorro - BI general -  Base imponible general (0435)
12 | 91 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo ganancias/pérdidas  (0424)
13 | 104 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro -  Compensaciones - Saldos netos negativos rendimientos capital mobiliario  (0436)
14 | 117 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2015 pendientes compensación (0439)
15 | 130 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2016 pendientes compensación (0440)
16 | 143 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2017 pendientes compensación (0441)
17 | 156 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Saldos netos negativos ganancias/pérdidas 2018 pendientes compensación (0442)
18 | 169 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2015 pendiente compensación (0443)
19 | 182 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2016 pendiente compensación (0444)
20 | 195 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2017 pendiente compensación (0445)
21 | 208 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones - Resto saldos netos negativos rdtos.capital mobiliario 2018 pendiente compensación (0447)
22 | 221 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Saldo neto positivo rendimientos capital mobiliario a integrar en BI ahorro (0429)
23 | 234 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro -  Compensaciones -  Saldos netos negativos ganancias/pérdidas (0446)
24 | 247 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2015 pendientes compensación (0449)
25 | 260 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2016 pendientes compensación (0450)
26 | 273 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2017 pendientes compensación (0451)
27 | 286 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Saldos netos negativos rdtos capital mobiliario 2018 pendientes compensación (0452)
28 | 299 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2015 pendientes compensación (0453)
29 | 312 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2016 pendientes compensación (0454)
30 | 325 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2017 pendientes compensación (0455)
31 | 338 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Compensaciones -  Resto saldos netos negativos ganancias/pérdidas 2018 pendientes compensación (0448)
32 | 351 | 13 | N | Base imponible general y base imponible ahorro - BI ahorro - Base imponible del ahorro (0460)
33 | 364 | 600 | An | RESERVADO PARA LA A.E.A.T
34 | 964 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10018000>
Total: |  | 975

# 100-19

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "19000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 13 | N |  | (I) Reducciones base imponible - Reducción por tributación conjunta - Reducción unidades familiares tributación conjunta (0461)
7 | 26 | 1 | Tit | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuyente "0" a "9"  (0462)
8 | 27 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 a 2017 (0463)
9 | 40 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Excesos pendientes reducir 2013 a 2017 de contribuciones a seguros colectivos de dependencia (0464)
10 | 53 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Aportaciones y contribuciones (0465)
11 | 66 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Contribuciones a seguros colectivos de dependencia (0466)
12 | 79 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Importes con derecho a reducción (0467)
13 | 92 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Régimen general - Total con derecho a reducción (0468)
14 | 105 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social - Aportaciones sistemas previsión social cónyuge del contribuyente - Total con derecho a reducción (0469)
15 | 118 | 1 | Tit | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Contribuyente "0" a "9" (0470)
16 | 119 | 9 | An | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - NIF persona con discapacidad (0471)
17 | 128 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones por la persona con discapacidad. Excesos pendientes reducir (0472)
18 | 141 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones a favor de parientes. Excesos pendientes reducir (0473)
19 | 154 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones 2018 propia persona con discapacidad (0474)
20 | 167 | 13 | N | C | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Aportaciones 2018 parientes o tutores (0475)
21 | 180 | 13 | N |  | Reducciones base imponible - Aportaciones sistemas previsión social a favor de personas con discapacidad - Total con derecho a reducción (0476)
22 | 193 | 1 | Tit | C | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Contribuyente "0" a "9" (0477)
23 | 194 | 9 | An | C | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - NIF persona discapacidad (0478)
24 | 203 | 13 | N | C | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Excesos pendientes reducir (0479)
25 | 216 | 13 | N | C | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Aportaciones (0480)
26 | 229 | 13 | N |  | Reducciones base imponible - Aportaciones patrimonios protegidos personas discapacidad - Total con derecho a reducción (0481)
27 | 242 | 1 | Tit | C | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos -  Contribuyente "0" a "9" (0482)
28 | 243 | 20 | An | C | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - NIF persona recibe pensión/anualidad (0483)
29 | 263 | 1 | Num | C | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Si ha consignado NIF de otro país 1 (431) "1" o "0" (0484)
30 | 264 | 13 | N | C | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Importe pensión/anualidad decisión judicial (0485)
31 | 277 | 13 | N |  | Reducciones base imponible - Pensiones compensatorias a cónyuge y anualidades alimentos, excepto hijos - Total derecho reducción (0486)
32 | 290 | 1 | Tit | C | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Contribuyente "0" a "9" (0487)
33 | 291 | 13 | N | C | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales -  Excesos pendientes reducir (0488)
34 | 304 | 13 | N | C | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Aportaciones y contribuciones (0489)
35 | 317 | 13 | N |  | Reducciones base imponible - Aportaciones mutualidad previsión social deportistas profesionales - Total con derecho a reducción (0490)
36 | 330 | 600 | An |  | RESERVADO PARA LA A.E.A.T
37 | 930 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10019000>
Total: |  | 941

# 100-20

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "20000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (J) Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base imponible general (0435)
7 | 26 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Tributación conjunta (0491)
8 | 39 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social (régimen general) (0492)
9 | 52 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social cónyuge (0493)
10 | 65 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones previsión social personas discapacidad (0494)
11 | 78 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones patrimonios protegidos personas discapacidad (0495)
12 | 91 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Pensiones compensatorias/anualidades alimentos (0496)
13 | 104 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Reducciones base imponible general - Aportaciones mutualidades prev. soc. deportistas profesionales (0497)
14 | 117 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general (0500)
15 | 130 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Compensación bases liquidables generales negativas (0501)
16 | 143 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable general - Base liquidable general sometida a gravamen (0505)
17 | 156 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base imponible ahorro (0460)
18 | 169 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción tributación conjunta (0506)
19 | 182 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Remanente reducciones no aplicadas - Reducción pensiones comp./anualidades alimentos (0507)
20 | 195 | 13 | N | Base liquidable general/base liquidable ahorro - Determinación base liquidable ahorro - Base liquidable del ahorro (0510)
21 | 208 | 13 | N | (K) Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe parte estatal (0511)
22 | 221 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo contribuyente - Importe parte autonómica (0512)
23 | 234 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe parte estatal  (0513)
24 | 247 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo descendientes - Importe parte autonómica (0514)
25 | 260 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe  parte estatal (0515)
26 | 273 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo ascendientes - Importe parte autonómica (0516)
27 | 286 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe parte estatal (0517)
28 | 299 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo discapacidad - Importe parte autonómica (0518)
29 | 312 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Mínimo personal y familiar parte estatala (0519)
30 | 325 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe total cálculo gravamen autonómico (0520)
31 | 338 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general - gravamen estatal  (0521)
32 | 351 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen estatal (0522)
33 | 364 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable general  - gravamen autonómico (0523)
34 | 377 | 13 | N | Adecuación impuesto circunstancias personales y familiares: mínimo personal y familiar - Importe mínimo personal/familiar base liquidable ahorro - gravamen autonómico (0524)
35 | 390 | 13 | N | (L) Datos adicionales - Rentas exentas excepto para determinar gravamen. Base liquidable general (0525)
36 | 403 | 13 | N | Datos adicionales - Rentas exentas excepto para determinar gravamen. Base liquidable ahorro (0526)
37 | 416 | 9 | An | Datos adicionales - Anualidades para alimentos a favor de los hijos. NIF/NIE hijo 1 (0456)
38 | 425 | 1 | Num | Datos adicionales - Anualidades para alimentos a favor de los hijos. Hijo 1 no tiene NIF o NIE "1 o cero" (0457)
39 | 426 | 9 | An | Datos adicionales - Anualidades para alimentos a favor de los hijos. NIF/NIE hijo 2 (0458)
40 | 435 | 1 | Num | Datos adicionales - Anualidades para alimentos a favor de los hijos. Hijo 2 no tiene NIF o NIE "1 o cero" (0459)
41 | 436 | 13 | N | Datos adicionales - Anualidades para alimentos a favor de los hijos. Importe (0527)
42 | 449 | 13 | An | RESERVADO PARA LA A.E.A.T
43 | 462 | 587 | An | RESERVADO PARA LA A.E.A.T
44 | 1049 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10020000>
Total: |  | 1060

# 100-21

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "21000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | (M) Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del Impuesto importe casilla (0505) - Parte estatal (0528)
7 | 26 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general y autonómica del  Impuesto importe casilla (0505) - Parte autonómica (0529)
8 | 39 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala general del Impuesto importe casilla (0521) - Parte estatal (0530)
9 | 52 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Aplicación escala autonómica del Impuesto importe casilla (0523) - Parte autonómica (0531)
10 | 65 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte estatal (0532)
11 | 78 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Cuota base liquidable general - Parte autonómica (0533)
12 | 91 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medios gravamen - Parte estatal (0534)
13 | 95 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable general - Tipos medios gravamen - Parte autonómica (0535)
14 | 99 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla (0510) - Parte estatal (0536)
15 | 112 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general y autonómica del lmpuesto importe casilla (0510) - Parte autonómica (0537)
16 | 125 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala general del lmpuesto importe casilla (0522) - Parte estatal (0538)
17 | 138 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Aplicación escala autonómica del Impuesto importe casilla (0524) - Parte autonómica (0539)
18 | 151 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte estatal (0540)
19 | 164 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Cuota base liquidable ahorro - Parte autonómica  (0541)
20 | 177 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medios gravamen - Parte estatal (0542)
21 | 181 | 4 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Gravamen base liquidable ahorro - Tipos medios gravamen - Parte autonómica (0543)
22 | 185 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra estatal - Parte estatal (0545)
23 | 198 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas íntegras - Cuota íntegra autonómica - Parte autonómica (0546)
24 | 211 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte estatal (0547)
25 | 224 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión vivienda habitual - Parte autonómica (0548)
26 | 237 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversión empresas nueva o reciente creación - Parte estatal (0549)
27 | 250 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte estatal (0550)
28 | 263 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Inversiones/gastos interés cultural - Parte autonómica (0551)
29 | 276 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones- Parte estatal (0552)
30 | 289 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Donativos y otras aportaciones - Parte autonómica (0553)
31 | 302 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte estatal (0554)
32 | 315 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Incentivos inversión empresarial - Parte autonómica (0555)
33 | 328 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte estatal (0556)
34 | 341 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Dotaciones Reserva Canarias - Parte autonómica (0557)
35 | 354 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte estatal (0558)
36 | 367 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras -  Rendimientos venta bienes Canarias - Parte autonómica (0559)
37 | 380 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte estatal (0560)
38 | 393 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Rentas obtenidas Ceuta o Melilla - Parte autonómica (0561)
39 | 406 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte estatal (0562)
40 | 419 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones cuotas íntegras - Alquiler vivienda habitual - Parte autonómica (0563)
41 | 432 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducciones autonómicas - Suma deducciones autonómicas (0564)
42 | 445 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducción  por unidades familiares formadas por residentes en la UE. Parte estatal (0565)
43 | 458 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Deducción  por unidades familiares formadas por residentes en la UE - Parte autonómica (0566)
44 | 471 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida estatal - Parte estatal (0570)
45 | 484 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Cuotas líquidas - Cuota líquida autonómica - Parte autonómica (0571)
46 | 497 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Importe - Parte estatal (0572]
47 | 510 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones 1996 y anteriores - Intereses demora - Parte estatal (0573)
48 | 523 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2018 - Importe - Parte estatal (0574)
49 | 536 | 1 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2018 - Regularización motivada por DA 45. "1" o "0" (0575)
50 | 537 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2018 - Intereses demora -  Parte estatal (0576)
51 | 550 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2018 - Importe - Parte autonómica (0577)
52 | 563 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones generales 1997-2018 - Intereses demora - Parte autonómica (0578)
53 | 576 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2018 - Importe - Parte autonómica (0579)
54 | 589 | 1 | Num | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2018 - Regularización motivada por  DA 45. "1" o "0" (0580)
55 | 590 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Deducciones autonómicas 1998-2018 - Intereses demora - Parte autonómica (0581)
56 | 603 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida estatal incrementada - Parte estatal (0585)
57 | 616 | 13 | N | Cálculo impuesto y resultado declaración - Determinación gravámenes estatal y autonómico - Incremento cuotas líquidas pérdida derecho deducciones - Cuota líquida autonómica incrementada - Parte autonómica (0586)
58 | 629 | 600 | An | RESERVADO PARA LA A.E.A.T
59 | 1229 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10021000>
Total: |  | 1240

# 100-22

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "22000"
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
16 | 143 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Atribución de retenciones de rendimientos del capital mobiliario (0592)
17 | 156 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Atribución de retenciones de rendimientos del capital inmobiliario (0593)
18 | 169 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Atribución de retenciones de rendimientos de actividades económicas (0594)
19 | 182 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Atribución de retenciones de ganancias y pérdidas patrimoniales (0600)
20 | 195 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Imputados por agrupaciones de interés económico y UTE's (0601)
21 | 208 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Ingresos a cuenta art. 92.8 Ley del Impuesto (0602)
22 | 221 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Ganancias patrimoniales, incluidos premios (0603)
23 | 234 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Pagos fraccionados (actividades económicas) (0604)
24 | 247 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Cuotas del Impuesto sobre la Renta de no Residentes (0605)
25 | 260 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Retenciones art. 11  Directiva 2003/48/CE (0606)
26 | 273 | 13 | N |  | Cálculo impuesto y resultado declaración  - Retenciones y demás pagos a cuenta - Total pagos a cuenta (0609)
27 | 286 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Cuota diferencial (0610)
28 | 299 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción por maternidad - Importe deducción (0611)
29 | 312 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción por maternidad - Importe abono anticipado deducción (0612)
30 | 325 | 13 | N |  | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción por maternidad - Incremento por gastos de guarderías  (0613)
31 | 338 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF descendiente (0614)
32 | 347 | 15 | A | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Nombre (0615)
33 | 362 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (0616)
34 | 370 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (0617)
35 | 378 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Nº personas derecho mínimo (0618)
36 | 380 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Le han cedido el derecho a la deducción (0619) |  | "0" - blanco, "1" - Si,    "2" .- No
37 | 381 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF cedente (0620)
38 | 390 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Cede el derecho a la deducción (0621) |  | "0" - blanco, "1" - Si,    "2" .- No
39 | 391 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - NIF beneficiario (0622)
40 | 400 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Importe deducción (0623)
41 | 413 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción descendientes discapacidad - Importe abono anticipado deducción (0624)
42 | 426 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF ascendiente (0625)
43 | 435 | 15 | A | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Nombre (0626)
44 | 450 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Fecha inicio discapacidad (DDMMAAAA) (0627)
45 | 458 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Fecha fin discapacidad (DDMMAAAA) (0628)
46 | 466 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Nº personas derecho mínimo (0629)
47 | 468 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Le han cedido el derecho a la deducción (0630) |  | "0" - blanco, "1" - Si,    "2" .- No
48 | 469 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad  - NIF cedente 1 (0631)
49 | 478 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF cedente 2 (0632)
50 | 487 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF cedente 3 (0633)
51 | 496 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Cede el derecho a la deducción (0634) |  | "0" - blanco, "1" - Si,    "2" .- No
52 | 497 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - NIF beneficiario (0635)
53 | 506 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Importe deducción (0636)
54 | 519 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción ascendientes discapacidad - Importe abono anticipado deducción (0637)
55 | 532 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - NIF del cónyuge  (0240)
56 | 541 | 15 | A | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Nombre del cónyuge  (0241)
57 | 556 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Fecha inicio discapacidad (DDMMAAAA)(0242)
58 | 564 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Fecha fin discapacidad  (DDMMAAAA)(0243)
59 | 572 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Otro contribuyente tiene derecho respecto del cónyuge a la deducción (0244) |  | "0" - No, "1" - Si
60 | 573 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Matrimonio vigente todo el año (0245) |  | "0" - No, "1" - Si
61 | 574 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Primer mes vigencia matrimonio (0246)
62 | 576 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Último mes vigencia matrimonio  (0247)
63 | 578 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado -  Importe de la deducción (0248)
64 | 591 | 13 | N | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción cónyuge discapacitado no separado - Importe del abono anticipado  (0249)
65 | 604 | 600 | An |  | RESERVADO PARA LA A.E.A.T
66 | 1204 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10022000>
Total: |  | 1215

# 100-23

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "23000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 30 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Nº identificación título familia numerosa (0647)
7 | 43 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Categoría familia numerosa - General (0648)
8 | 44 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Categoría familia numerosa - Especial (0649)
9 | 45 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Fecha inicio título familia numerosa (DDMMAAAA) (0650)
10 | 53 | 8 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Fecha finalización título familia numerosa (DDMMAAAA) (0651)
11 | 61 | 2 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Nº ascendientes forman parte familia numerosa  (0652)
12 | 63 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Le han cedido el derecho a la deducción (0653) |  | "0" - blanco, "1" - Si,    "2" .- No
13 | 64 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 1 (0654)
14 | 73 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 2 (0655)
15 | 82 | 9 | An | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - NIF cedente 3 (0656)
16 | 91 | 1 | Num | C | Cálculo impuesto y resultado declaración  - Cuota diferencial y resultado - Deducción familia numerosa - Cede el derecho a la deducción (0657) |  | "0" - blanco, "1" - Si,    "2" .- No
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
31 | 250 | 13 | N |  | (O) Regularización - Mediante declaración complemetaria - Resultados a ingresar anteriores autoliquidaciones o liquidaciones administrativas (0676)
32 | 263 | 13 | N |  | Regularización - Mediante declaración complemetaria - Devoluciones acordadas Agencia Tributaria, tramitación anteriores autoliquidaciones  (0677)
33 | 276 | 13 | N |  | Regularización -Mediante declaración complemetaria - Resultado declaración complementaria (0680)
34 | 289 | 13 | N |  | Regularización - Mediante rectificación de autoliquidación - Resultados a ingresar de autoliquidaciones o liquidaciones administrativas (0681)
35 | 302 | 13 | N |  | Regularización - Mediante rectificación de autoliquidación - Devoluciones solicitadas a la Agencia Tributaria,  tramitación anteriores autoliquidaciones (0682)
36 | 315 | 13 | N |  | Regularización - Mediante rectificación de autoliquidación - Resultado de la solicitud de rectificación de autoliquidación (0685)
37 | 328 | 13 | Num |  | Regularización - Mediante rectificación de autoliquidación - Número de justificante de la autoliquidación cuya rectificación se solicita (0686)
38 | 341 | 34 | An |  | Regularización - Mediante rectificación de autoliquidación - Número de cuenta - IBAN (0687)
39 | 375 | 11 | An |  | Regularización - Mediante rectificación de autoliquidación - Número de cuenta - Código SWIFT-BIC (0688)
40 | 386 | 600 | An |  | RESERVADO PARA LA A.E.A.T
41 | 986 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10023000>
Total: |  | 997

# 100-24

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "24000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | P) Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Importe resultado ingresar de su declaración cuya suspensión se solicita (0693)
7 | 26 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado positivo - Resto a ingresar del resultado de su declaración (0695)
8 | 39 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Importe resultado devolver de su declaración a cuyo cobro efectivo se renuncia (0694)
9 | 52 | 13 | N | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Resto del resultado de su declaración cuya devolución se solicita (0695)
10 | 65 | 34 | An | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Número de cuenta - IBAN (0696)
11 | 99 | 11 | An | Solicitud suspensión ingreso un cónyuge/Renuncia otro cónyuge cobro devolución - Si resultado negativo - Número de cuenta - Código SWIFT-BIC (0697)
12 | 110 | 600 | An | RESERVADO PARA LA A.E.A.T
13 | 710 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10024000>
Total: |  | 721

# Anexo A.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "25000"
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
42 | 1040 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10025000>
Total: |  | 1051

# Anexo A.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "26000"
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
30 | 325 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Importe dotaciones (0733)
31 | 338 | 4 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Año de la dotación (0734)
32 | 342 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0777)
33 | 355 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2015 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0778)
34 | 368 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Importe dotaciones (0735)
35 | 381 | 4 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Año de la dotación (0789)
36 | 385 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0736)
37 | 398 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0737)
38 | 411 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2016 - Pendiente de materializar (0790)
39 | 424 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Importe dotaciones (0738)
40 | 437 | 4 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Año de la dotación (0792)
41 | 441 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0739)
42 | 454 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0740)
43 | 467 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2017 - Pendiente de materializar (0741)
44 | 480 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Importe dotaciones (0742)
45 | 493 | 4 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Año de la dotación (0794)
46 | 497 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0743)
47 | 510 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0744)
48 | 523 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2018 - Pendiente de materializar (0745)
49 | 536 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2019 - Importe dotaciones (0746)
50 | 549 | 4 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2019 - Año de la dotación (0802)
51 | 553 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2019 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0747)
52 | 566 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2019 - Inversiones previstas letras C y D 2º. a 6º.) artº. 27.4 (0748)
53 | 579 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - 2019 - Pendiente de materializar (0749)
54 | 592 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Importe de la deducción 2019
55 | 605 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2019 - Inversiones previstas letras A, B, B bis y D (1º.) artº. 27.4 (0750)
56 | 618 | 13 | N | Reserva para Inversiones en Canarias (Ley 19/1994) - Dotaciones, materializaciones e inversiones anticipadas - Futuras dotaciones RIC 2019 - Inversiones prev. letras C y D 2º. a 6º.) artº. 27.4 (0751)
57 | 631 | 600 | An | RESERVADO PARA LA A.E.A.T
58 | 1231 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10026000>
Total: |  | 1242

# Anexo A.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "27000"
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
27 | 286 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Deducción inversiones África Occidental art.º 27.1.a) bis de la Ley 19/1994 - Deducción
28 | 299 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Deducción inversiones África Occidental art.º 27.1.a) bis de la Ley 19/1994 - Aplicado declaración (0759)
29 | 312 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Deducción inversiones África Occidental art.º 27.1.a) bis de la Ley 19/1994 - Pendiente aplicación
30 | 325 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Deducción gastos propaganda y publicidad art.º 27.1.b) bis de la Ley 19/1994 - Deducción
31 | 338 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Deducción gastos propaganda y publicidad art.º 27.1.b) bis de la Ley 19/1994 - Aplicado declaración (0843)
32 | 351 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - R. gral. LIS - Deducción gastos propaganda y publicidad art.º 27.1.b) bis de la Ley 19/1994 - Pendiente aplicación
33 | 364 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Deducción
34 | 377 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Aplicado declaración (0760)
35 | 390 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "200 Anivers. Teatro Real y vigésimo Anivers. reapertura Teatro Real" - Pendiente aplicación
36 | 403 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Deducción
37 | 416 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Aplicado declaración (0761)
38 | 429 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - "VIII Centenario Universiada de Salamanca" - Pendiente aplicación
39 | 442 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Deducción
40 | 455 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Aplicado declaración (0766)
41 | 468 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - II Centenario Museo Nacional del Prado- Pendiente aplicación
42 | 481 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Deducción
43 | 494 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Aplicado declaración (0767)
44 | 507 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 20 Aniversario Reapertura Teatro del Liceo- Pendiente aplicación
45 | 520 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Deducción
46 | 533 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Aplicado declaración (0776)
47 | 546 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Prevención de la Obesidad. Aligera tu vida- Pendiente aplicación
48 | 559 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Deducción
49 | 572 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Aplicado declaración (0779)
50 | 585 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Programa preparación deportistas españoles Tokio 2020- Pendiente aplicación
51 | 598 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Deducción
52 | 611 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Aplicado declaración (0780)
53 | 624 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 Aniversario de la Casa América- Pendiente aplicación
54 | 637 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Deducción
55 | 650 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Aplicado declaración (0781)
56 | 663 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - World Roller Games Barcelona 2019- Pendiente aplicación
57 | 676 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Deducción
58 | 689 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Aplicado declaración (0782)
59 | 702 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Madrid Horse Week 17/19- Pendiente aplicación
60 | 715 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Deducción
61 | 728 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Aplicado declaración (0783)
62 | 741 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Liga World Challenge- Pendiente aplicación
63 | 754 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Deducción
64 | 767 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Aplicado declaración (0784)
65 | 780 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - V centenario expedición primera vuelta al mundo- Pendiente aplicación
66 | 793 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Deducción
67 | 806 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Aplicado declaración (0785)
68 | 819 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 25 aniversario declaración Unesco Mérida Patrimonio de la Humanidad- Pendiente aplicación
69 | 832 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Deducción
70 | 845 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Aplicado declaración (0786)
71 | 858 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonatos del mundo de canoa 2019- Pendiente aplicación
72 | 871 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Deducción
73 | 884 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Aplicado declaración (0787)
74 | 897 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 250 Aniversario Fuero de Población 1767- Pendiente aplicación
75 | 910 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Deducción
76 | 923 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Aplicado declaración (0788)
77 | 936 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario nacimiento de Bartolomé Esteban Murillo - Pendiente aplicación
78 | 949 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Deducción
79 | 962 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Aplicado declaración (0791)
80 | 975 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - IV Centenario de la Plaza Mayor de Madrid- Pendiente aplicación
81 | 988 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Deducción
82 | 1001 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Aplicado declaración (0793)
83 | 1014 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VII Centenario del Archivo de la Corona de Aragón- Pendiente aplicación
84 | 1027 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Deducción
85 | 1040 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Aplicado declaración (0795)
86 | 1053 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan de Fomento de la Lectura 2017-2020- Pendiente aplicación
87 | 1066 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Deducción
88 | 1079 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Aplicado declaración (0796)
89 | 1092 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 Apoyo a los Nuevos Creadores Cinematográficos- Pendiente aplicación
90 | 1105 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro- Deducción
91 | 1118 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro- Aplicado declaración (0797)
92 | 1131 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro- Pendiente aplicación
93 | 1144 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75º Aniversario de la Escuela Diplomática- Deducción
94 | 1157 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75º Aniversario de la Escuela Diplomática- Aplicado declaración (0798)
95 | 1170 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 75º Aniversario de la Escuela Diplomática- Pendiente aplicación
96 | 1183 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Deducción
97 | 1196 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Aplicado declaración (0800)
98 | 1209 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 40 Aniversario de la Constitución Española- Pendiente aplicación
99 | 1222 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50° aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya- Deducción
100 | 1235 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50° aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya- Aplicado declaración (0801)
101 | 1248 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50° aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya- Pendiente aplicación
102 | 1261 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Deducción
103 | 1274 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Aplicado declaración (0804)
104 | 1287 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan Decenio Milliarium Montserrat 1025-2025- Pendiente aplicación
105 | 1300 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de Ordesa y Monte Perdido- Deducción
106 | 1313 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de Ordesa y Monte Perdido- Aplicado declaración (0805)
107 | 1326 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de Ordesa y Monte Perdido- Pendiente aplicación
108 | 1339 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de los Picos de Europa- Deducción
109 | 1352 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de los Picos de Europa- Aplicado declaración (0806)
110 | 1365 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - I Centenario del Parque Nacional de los Picos de Europa- Pendiente aplicación
111 | 1378 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 Edición del Festival Internacional de Jazz de Barcelona- Deducción
112 | 1391 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 Edición del Festival Internacional de Jazz de Barcelona- Aplicado declaración (0807)
113 | 1404 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - 50 Edición del Festival Internacional de Jazz de Barcelona- Pendiente aplicación
114 | 1417 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenarios del Real Sitio de Covadonga- Deducción
115 | 1430 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenarios del Real Sitio de Covadonga- Aplicado declaración (0808)
116 | 1443 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenarios del Real Sitio de Covadonga- Pendiente aplicación
117 | 1456 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Junior Balonmano Masculino 2019- Deducción
118 | 1469 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Junior Balonmano Masculino 2019- Aplicado declaración (0809)
119 | 1482 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Junior Balonmano Masculino 2019- Pendiente aplicación
120 | 1495 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Balonmano Femenino 2021- Deducción
121 | 1508 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Balonmano Femenino 2021- Aplicado declaración (0762)
122 | 1521 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato Mundial Balonmano Femenino 2021- Pendiente aplicación
123 | 1534 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Andalucía Valderrama Masters- Deducción
124 | 1547 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Andalucía Valderrama Masters- Aplicado declaración (0810)
125 | 1560 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Andalucía Valderrama Masters- Pendiente aplicación
126 | 1573 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Transición: 40 años de Libertad de Expresión- Deducción
127 | 1586 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Transición: 40 años de Libertad de Expresión- Aplicado declaración (0811)
128 | 1599 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - La Transición: 40 años de Libertad de Expresión- Pendiente aplicación
129 | 1612 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Mobile World Capital- Deducción
130 | 1625 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Mobile World Capital- Aplicado declaración (0812)
131 | 1638 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Mobile World Capital- Pendiente aplicación
132 | 1651 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Ceuta y la Legión, 100 años de unión- Deducción
133 | 1664 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Ceuta y la Legión, 100 años de unión- Aplicado declaración (0813)
134 | 1677 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Ceuta y la Legión, 100 años de unión- Pendiente aplicación
135 | 1690 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019- Deducción
136 | 1703 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019- Aplicado declaración (0814)
137 | 1716 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019- Pendiente aplicación
138 | 1729 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Bádminton World Tour- Deducción
139 | 1742 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Bádminton World Tour- Aplicado declaración (0815)
140 | 1755 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Bádminton World Tour- Pendiente aplicación
141 | 1768 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Nuevas Metas- Deducción
142 | 1781 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Nuevas Metas- Aplicado declaración (0816)
143 | 1794 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Nuevas Metas- Pendiente aplicación
144 | 1807 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge (3ª Edición)- Deducción
145 | 1820 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge (3ª Edición)- Aplicado declaración (0763)
146 | 1833 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Barcelona Equestrian Challenge (3ª Edición)- Pendiente aplicación
147 | 1846 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Universo Mujer II- Deducción
148 | 1859 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Universo Mujer II- Aplicado declaración (0764)
149 | 1872 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Universo Mujer II- Pendiente aplicación
150 | 1885 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Logroño 2021, nuestro V Centenario- Deducción
151 | 1898 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Logroño 2021, nuestro V Centenario- Aplicado declaración (0817)
152 | 1911 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Logroño 2021, nuestro V Centenario- Pendiente aplicación
153 | 1924 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario Delibes- Deducción
154 | 1937 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario Delibes- Aplicado declaración (0765)
155 | 1950 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Centenario Delibes- Pendiente aplicación
156 | 1963 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Santo Jacobeo 2021- Deducción
157 | 1976 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Santo Jacobeo 2021- Aplicado declaración (0818)
158 | 1989 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Año Santo Jacobeo 2021- Pendiente aplicación
159 | 2002 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VIII Centenario de la Catedral de Burgos 2021- Deducción
160 | 2015 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VIII Centenario de la Catedral de Burgos 2021- Aplicado declaración (0819)
161 | 2028 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - VIII Centenario de la Catedral de Burgos 2021- Pendiente aplicación
162 | 2041 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Deporte Inclusivo- Deducción
163 | 2054 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Deporte Inclusivo- Aplicado declaración (0820)
164 | 2067 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Deporte Inclusivo- Pendiente aplicación
165 | 2080 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 de Apoyo al Deporte de Base II- Deducción
166 | 2093 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 de Apoyo al Deporte de Base II- Aplicado declaración (0768)
167 | 2106 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Plan 2020 de Apoyo al Deporte de Base II- Pendiente aplicación
168 | 2119 | 600 | An | RESERVADO PARA LA A.E.A.T
169 | 2719 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10027000>
Total: |  | 2730

# Anexo A.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "28000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante Blanco
6 | 13 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - España, Capital del Talento Joven- Deducción
7 | 26 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - España, Capital del Talento Joven- Aplicado declaración (0821)
8 | 39 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - España, Capital del Talento Joven- Pendiente aplicación
9 | 52 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Conmemoración del Centenario de la Coronación de Nuestra Señora del Rocío (1919-2019)- Deducción
10 | 65 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Conmemoración del Centenario de la Coronación de Nuestra Señora del Rocío (1919-2019)- Aplicado declaración (0822)
11 | 78 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Conmemoración del Centenario de la Coronación de Nuestra Señora del Rocío (1919-2019)- Pendiente aplicación
12 | 91 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Traslado de la Imagen de Nuestra Señora del Rocío desde la Aldea al Pueblo de Almonte- Deducción
13 | 104 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Traslado de la Imagen de Nuestra Señora del Rocío desde la Aldea al Pueblo de Almonte- Aplicado declaración (0823)
14 | 117 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Traslado de la Imagen de Nuestra Señora del Rocío desde la Aldea al Pueblo de Almonte- Pendiente aplicación
15 | 130 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino Lebaniego- Deducción
16 | 143 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino Lebaniego- Aplicado declaración (0769)
17 | 156 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino Lebaniego- Pendiente aplicación
18 | 169 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Expo Dubai 2020- Deducción
19 | 182 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Expo Dubai 2020- Aplicado declaración (0770)
20 | 195 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Expo Dubai 2020- Pendiente aplicación
21 | 208 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación- Deducción
22 | 221 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación- Aplicado declaración (0825)
23 | 234 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación- Pendiente aplicación
24 | 247 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino de la Cruz de Caravaca- Deducción
25 | 260 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino de la Cruz de Caravaca- Aplicado declaración (0826)
26 | 273 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Camino de la Cruz de Caravaca- Pendiente aplicación
27 | 286 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad- Deducción
28 | 299 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad- Aplicado declaración (0827)
29 | 312 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad- Pendiente aplicación
30 | 325 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Automobile Barcelona 2019- Deducción
31 | 338 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Automobile Barcelona 2019- Aplicado declaración (0828)
32 | 351 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Automobile Barcelona 2019- Pendiente aplicación
33 | 364 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinta sesión de la Conferencia de las Partes de la Convención Marco de Naciones Unidas sobre el Cambio Climático (COP25)- Deducción
34 | 377 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Reg. apoyo - Vigésimo quinta sesión de la Conferencia de las Partes de la Convención Marco de Naciones Unidas sobre el Cambio Climático (COP25)- Aplicado declaración (0829)
35 | 390 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Rég. gral. LIS/especiales acontecimientos interés público - Vigésimo quinta sesión de la Conferencia de las Partes de la Convención Marco de Naciones Unidas sobre el Cambio Climático (COP25)- Pendiente aplicación
36 | 403 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. Económicas 2018 (0830)
37 | 416 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (0831)
38 | 429 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (0832)
39 | 442 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe rendimientos netos act. Económicas 2019 (0833)
40 | 455 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe derecho deducción  (0834)
41 | 468 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Importe deducción  (0835)
42 | 481 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducción invers. elementos nuevos inmovilizado material o invers. inmobiliarias - Deducción por inversión elementos nuevos  (0836)
43 | 494 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Saldo anterior
44 | 507 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Aplicado declaración (0837)
45 | 520 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Inversiones adquisición activos fijos - Pendiente aplicación
46 | 533 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Saldo anterior
47 | 546 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Aplicado declaración (0838)
48 | 559 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Deducción ejercicios anteriores - Restantes modalidades - Pendiente aplicación
49 | 572 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS - Deducción
50 | 585 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS - Aplicado declaración (0839)
51 | 598 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Activ. Investigación y desarrollo e innovación tecnológica, artº. 35 LIS- Pendiente aplicación
52 | 611 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Deducción
53 | 624 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS -  Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS (0840)
54 | 637 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Inversiones produc. cinematográficas, series audiovisuales y espectáculos en vivo, artº. 36 LIS - Pendiente aplicación
55 | 650 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Deducción
56 | 663 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad, artº. 38 LIS - Aplicado declaración (0841)
57 | 676 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Modalidades LIS - Creación empleo trabajadores con discapacidad,  artº. 38 LIS - Pendiente de aplicación
58 | 689 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Deducción
59 | 702 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Aplicado declaración (0844)
60 | 715 | 13 | N | Deducciones incentivos/estímulos inv. empres. - Deducciones invers. Canarias - Inversiones en la adquisición de activos fijos - Pendiente aplicación
61 | 728 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Importe total de las deducciones (0845)
62 | 741 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Deducciones - Parte estatal (0554)
63 | 754 | 13 | N | Deducciones por incentivos y estímulos a la inversión empresarial - Deducciones incentivos y estímulos inversión empresarial: importe aplicado importe aplicado - Deducciones - Parte autonómica (0555)
64 | 767 | 600 | An | RESERVADO PARA LA A.E.A.T
65 | 1367 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10028000>
Total: |  | 1378

# Anexo B.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "29000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios de ayudas familiares (aplicable sólo a contribuyentes fallecidos antes del 25 de julio de 2019) (0849)
7 | 26 | 13 | N | Deducciones Autonómicas - Andalucía - Por nacimiento o adopción de hijos (No aplicable por los contribuyentes fallecidos antes del 25 de julio de 2019) (0850)
8 | 39 | 13 | N | Deducciones Autonómicas - Andalucía - Para beneficiarios ayudas viviendas protegidas (0851)
9 | 52 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión vivienda habitual protegida/personas jóvenes (0852)
10 | 65 | 13 | N | Deducciones Autonómicas - Andalucía - Por cantidades invertidas en alquiler de vivienda habitual (0853)
11 | 78 | 13 | N | Deducciones Autonómicas - Andalucía - Por inversión en la adquisición de acciones y participaciones  (0854)
12 | 91 | 13 | N | Deducciones Autonómicas - Andalucía - Por adopción de hijos ámbito internacional (0855)
13 | 104 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con discapacidad (0856)
14 | 117 | 13 | N | Deducciones Autonómicas - Andalucía - Para padre/madre de familia monoparental con ascendientes mayores 75 años (0857)
15 | 130 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Deducción con carácter general  (0858)
16 | 143 | 11 | An | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Cuenta cotización (0859)
17 | 154 | 13 | N | Deducciones Autonómicas - Andalucía - Por asistencia a personas con discapacidad - Si precisan ayuda de terceras personas. Importe (0860)
18 | 167 | 11 | An | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Cuenta cotización (0861)
19 | 178 | 13 | N | Deducciones Autonómicas - Andalucía - Por ayuda doméstica. Importe (0862)
20 | 191 | 13 | N | Deducciones Autonómicas - Andalucía - Para trabajadores por gastos de defensa jurídica de la relación laboral (0863)
21 | 204 | 13 | N | Deducciones Autonómicas - Andalucía - Para contribuyentes con cónyuges o parejas de hecho con discapacidad (0864)
22 | 217 | 13 | N | Deducciones Autonómicas - Andalucía - Otras deducciones (0865)
23 | 230 | 13 | N | Deducciones Autonómicas - Andalucía - Total deducciones autonómicas (0564)
24 | 243 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del tercer hijo o sucesivos (0866)
25 | 256 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción de un hijo en atención al grado discapacidad (0867)
26 | 269 | 13 | N | Deducciones Autonómicas - Aragón - Por adopción internacional de niños (0868)
27 | 282 | 13 | N | Deducciones Autonómicas - Aragón - Por el cuidado de personas dependientes (0869)
28 | 295 | 13 | N | Deducciones Autonómicas - Aragón - Por donaciones con finalidad ecológica y en investigación y desarrollo científico y técnico (0870)
29 | 308 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición vivienda habitual por víctimas del terrorismo  (0871)
30 | 321 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en acciones de entidades que cotizan en Mercado Alternativo Bursátil (0872)
31 | 334 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en la adquisición de acciones o participaciones sociales (0873)
32 | 347 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición o rehabilitación de vivienda habitual en núcleos rurales o análogos (0874)
33 | 360 | 13 | N | Deducciones Autonómicas - Aragón - Por adquisición libros de texto y material escolar (0875)
34 | 373 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda habitual vinculado operaciones dación en pago. Importe  (0876)
35 | 386 | 13 | N | Deducciones Autonómicas - Aragón - Por arrendamiento de vivienda social (deducción arrendador) (0877)
36 | 399 | 13 | N | Deducciones Autonómicas - Aragón - Para mayores de 70 años (0878)
37 | 412 | 13 | N | Deducciones Autonómicas - Aragón - Por inversión en entidades de la economía social (0879)
38 | 425 | 13 | N | Deducciones Autonómicas - Aragón - Por nacimiento o adopción del primer y/o segundo hijo en poblaciones de menos de 10.000 habitantes (0880)
39 | 438 | 13 | N | Deducciones Autonómicas - Aragón - Por gastos de guardería de hijos menores de 3 años (0881)
40 | 451 | 13 | N | Deducciones Autonómicas - Aragón -  Otras deducciones (0882)
41 | 464 | 13 | N | Deducciones Autonómicas - Aragón - Total deducciones autonómicas (0564)
42 | 477 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento no remunerado mayores 65 años (0883)
43 | 490 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vivienda habitual contribuyentes con discapacidad (0884)
44 | 503 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición/adecuación vvda. habitual con cónyuge, ascendientes o descendientes con discapacidad (0885)
45 | 516 | 13 | N | Deducciones Autonómicas - Asturias - Por inversión vivienda habitual protegida (0886)
46 | 529 | 13 | N | Deducciones Autonómicas - Asturias - Por arrendamiento de vivienda habitual  (0887)
47 | 542 | 13 | N | Deducciones Autonómicas - Asturias - Por donación de fincas rústicas a favor del Principado de Asturias (0888)
48 | 555 | 13 | N | Deducciones Autonómicas - Asturias - Por adopción internacional de menores (0889)
49 | 568 | 13 | N | Deducciones Autonómicas - Asturias - Por partos múltiples o por dos o más adopciones constituidas en la misma fecha  (0890)
50 | 581 | 13 | N | Deducciones Autonómicas - Asturias - Para familias numerosas (0891)
51 | 594 | 13 | N | Deducciones Autonómicas - Asturias - Para familias monoparentales (0892)
52 | 607 | 13 | N | Deducciones Autonómicas - Asturias - Por acogimiento familiar de menores (0893)
53 | 620 | 13 | N | Deducciones Autonómicas - Asturias - Por certificación de gestión forestal sostenible (0894)
54 | 633 | 13 | N | Deducciones Autonómicas - Asturias - Por gastos de descendientes en centros de 0 a 3 años (0895)
55 | 646 | 13 | N | Deducciones Autonómicas - Asturias - Por adquisición de libros de texto y material escolar (0896)
56 | 659 | 13 | N | Deducciones Autonómicas - Asturias -  Otras deducciones (0897)
57 | 672 | 13 | N | Deducciones Autonómicas - Asturias - Total deducciones autonómicas (0564)
58 | 685 | 600 | An | RESERVADO PARA LA A.E.A.T
59 | 1285 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10029000>
Total: |  | 1296

# Anexo B.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "30000"
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
24 | 242 | 13 | N | Deducciones Autonómicas - Illes Balears - Otras deducciones (0771)
25 | 255 | 13 | N | Deducciones Autonómicas - Illes Balears - Total deducciones autonómicas (0564)
26 | 268 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones con finalidad ecológica (0916)
27 | 281 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones rehabilitación o conservación patrimonio histórico de Canarias (0917)
28 | 294 | 13 | N | Deducciones Autonómicas - Canarias - Por cantidades destinadas restauración/rehabilitación/reparación bienes inmuebles declarados de Interés Cultural (0918)
29 | 307 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de estudios (0919)
30 | 320 | 13 | N | Deducciones Autonómicas - Canarias - Por trasladar residencia a otra isla para realizar actividad laboral cuenta ajena/actividad económica (0920)
31 | 333 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones en metálico a descendientes menores 35 años para adquisición/rehabilitación primera vivienda habitual (0921)
32 | 346 | 13 | N | Deducciones Autonómicas - Canarias - Por nacimiento o adopción de hijos (0922)
33 | 359 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes con discapacidad y mayores de 65 años (0923)
34 | 372 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de guardería (0924)
35 | 385 | 13 | N | Deducciones Autonómicas - Canarias - Por familia numerosa (0925)
36 | 398 | 13 | N | Deducciones Autonómicas - Canarias - Por inversión en vivienda habitual (0926)
37 | 411 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de adecuación vivienda habitual por razón discapacidad (0927)
38 | 424 | 13 | N | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Importe (0928)
39 | 437 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral 1 (0929)
40 | 457 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral 1. "1 o cero" (0930)
41 | 458 | 20 | An | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Referencia catastral 2 (0931)
42 | 478 | 1 | Num | Deducciones Autonómicas - Canarias - Por alquiler de vivienda habitual - Si no tiene referencia catastral 2. "1 o cero" (0932)
43 | 479 | 13 | N | Deducciones Autonómicas - Canarias - Por contribuyentes desempleados (0933)
44 | 492 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones y aportaciones fines culturales, deportivos, investigación o docencia (0934)
45 | 505 | 13 | N | Deducciones Autonómicas - Canarias - Por donaciones a entidades sin ánimo de lucro y con finalidad ecológica (0935)
46 | 518 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos de estudios en educación infantil, primaria, secundaria obligatoria bachillerato y formación profesional de grado medio (0936)
47 | 531 | 13 | N | Deducciones Autonómicas - Canarias - Por acogimiento de menores (0937)
48 | 544 | 13 | N | Deducciones Autonómicas - Canarias - Por familias monoparentales (0938)
49 | 557 | 13 | N | Deducciones Autonómicas - Canarias - Por obras de rehabilitación energética de la vivienda habitual (0939)
50 | 570 | 13 | N | Deducciones Autonómicas - Canarias - Por gasto de enfermedad (0940)
51 | 583 | 13 | N | Deducciones Autonómicas - Canarias - Por familiares dependientes con discapacidad (0941)
52 | 596 | 13 | N | Deducciones Autonómicas - Canarias - Por arrendamiento de vivienda habitual vinculado a determinadas operaciones de dación en pago [0942]
53 | 609 | 13 | N | Deducciones Autonómicas - Canarias - Por arrendamientos a precios con sostenibilidad social (0943)
54 | 622 | 13 | N | Deducciones Autonómicas - Canarias - Por gastos en primas de seguros de crédito para cubrir impagos de rentas de arrendamientos de vivienda (0944)
55 | 635 | 13 | N | Deducciones Autonómicas - Canarias - Otras deducciones (0945)
56 | 648 | 13 | N | Deducciones Autonómicas - Canarias - Total deducciones autonómicas (0564)
57 | 661 | 600 | An | RESERVADO PARA LA A.E.A.T
58 | 1261 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10030000>
Total: |  | 1272

# Anexo B.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "31000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Cantabria - Por arrendamiento de vivienda habitual jóvenes, mayores y con  discapacidad - Importe (0946)
7 | 26 | 13 | N | Deducciones Autonómicas - Cantabria - Por cuidado de familiares (0947)
8 | 39 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora. Importe 2017 y/o 2018 pendiente de aplicación (0948)
9 | 52 | 9 | An | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - NIF persona/entidad  obras (0949)
10 | 61 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora en viviendas - Importe deducción (0950)
11 | 74 | 13 | N | Deducciones Autonómicas - Cantabria - Por donativos a fundaciones o al Fondo Cantabria Coopera (0951)
12 | 87 | 13 | N | Deducciones Autonómicas - Cantabria - Por acogimiento familiar de menores (0952)
13 | 100 | 13 | N | Deducciones Autonómicas - Cantabria - Por inversión adquisición acciones/participaciones sociales nuevas entidades o reciente creación (0953)
14 | 113 | 13 | N | Deducciones Autonómicas - Cantabria - Por gastos de enfermedad (0954)
15 | 126 | 13 | N | Deducciones Autonómicas - Cantabria - Por gastos de guardería (0772)
16 | 139 | 11 | An | Deducciones Autonómicas - Cantabria - Por ayuda doméstica. Cuenta cotización (0773)
17 | 150 | 13 | N | Deducciones Autonómicas - Cantabria - Por ayuda doméstica. Importe (0774)
18 | 163 | 13 | N | Deducciones Autonómicas - Cantabria - Por familias monoparentales (0775)
19 | 176 | 13 | N | Deducciones Autonómicas - Cantabria - Otras deducciones (0955)
20 | 189 | 13 | N | Deducciones Autonómicas - Cantabria - Total deducciones autonómicas (0564)
21 | 202 | 13 | N | Deducciones Autonómicas - Cantabria - Por obras de mejora generadas en 2019 a deducir en los 2 años siguientes (0956)
22 | 215 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por nacimiento o adopción de hijos (0957)
23 | 228 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad del contribuyente (0958)
24 | 241 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por discapacidad de ascendientes o descendientes (0959)
25 | 254 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Para contribuyentes mayores de 75 años (0960)
26 | 267 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por el cuidado de ascendientes mayores de 75 años (0961)
27 | 280 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por cantidades para la Cooperación Internacional, lucha contra pobreza y exclusión social  (0962)
28 | 293 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por familia numerosa (0963)
29 | 306 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por donaciones con finalidad en investigación y desarrollo e innovación empresarial (0964)
30 | 319 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por gastos en la adquisición de libros de texto y enseñanza de idiomas (0965)
31 | 332 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento familiar no rumunerado de menores (0966)
32 | 345 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Por acogimiento no remunerado de mayores de 65 años y/o discapacitados (0967)
33 | 358 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha -  Por arrendamiento de vivienda habitual por menores de 36 años  (0968)
34 | 371 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Otras deducciones (0969)
35 | 384 | 13 | N | Deducciones Autonómicas - Castilla-La Mancha - Total deducciones autonómicas (0564)
36 | 397 | 13 | N | Deducciones Autonómicas - Castilla y León - Para contribuyentes afectados por discapacidad (0970)
37 | 410 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de viviendas por jóvenes en núcleos rurales  (0971)
38 | 423 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cantidades donadas a fundaciones (0972)
39 | 436 | 13 | N | Deducciones Autonómicas - Castilla y León - Poro cantidades donadas para el fomento de la investigación, desarrollo e innovación (0973)
40 | 449 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cantidades invertidas en la recuperación del patrimonio histórico, cultural y natural  (0974)
41 | 462 | 13 | N | Deducciones Autonómicas - Castilla y León - Por el fomento de la movilidad sostenible (0799)
42 | 475 | 13 | N | Deducciones Autonómicas - Castilla y León - Por alquiler vivienda habitual contribuyentes menores de 36 años  (0975)
43 | 488 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión instalaciones medioambientales/adaptación a personas con discapacidad en vvda.habitual (0976)
44 | 501 | 8 | Num | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Fecha visado proyecto (0977)
45 | 509 | 13 | N | Deducciones Autonómicas - Castilla y León - Por adquisición de vivienda de nueva construcción para residencia habitual. Importe  (0978)
46 | 522 | 13 | N | Deducciones Autonómicas - Castilla y León - Para el fomento de emprendimiento (0979)
47 | 535 | 13 | N | Deducciones Autonómicas - Castilla y León - Por inversión en rehabilitación de viviendas destinadas a alquiler en núcleos rurales  (0980)
48 | 548 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2016 pdte. aplicación (0981)
49 | 561 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2017 pdte. aplicación (0982)
50 | 574 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe generado 2018 pdte. aplicación (0983)
51 | 587 | 13 | N | Deducciones Autonómicas - Castilla y León - Deducciones por familia numerosa, nacimiento o adopción, etc. Importe aplicado en el ejercicio (0984)
52 | 600 | 13 | N | Deducciones Autonómicas - Castilla y León - Por familia numerosa (0985)
53 | 613 | 13 | N | Deducciones Autonómicas - Castilla y León - Por nacimiento o adopción de hijos (0986)
54 | 626 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas (0987)
55 | 639 | 13 | N | Deducciones Autonómicas - Castilla y León - Por partos múltiples o adopciones simultáneas en 2017  y/o 2018 (0988)
56 | 652 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Nif persona empleada (0989)
57 | 661 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuidado de hijos menores - Importe (0990)
58 | 674 | 13 | N | Deducciones Autonómicas - Castilla y León - Por paternidad  (0991)
59 | 687 | 13 | N | Deducciones Autonómicas - Castilla y León - Por gastos de adopción (0992)
60 | 700 | 9 | An | Deducciones Autonómicas - Castilla y León - Por cuotas Seg.Social empleados del hogar - Nif persona empleada (0993)
61 | 709 | 13 | N | Deducciones Autonómicas - Castilla y León - Por cuotas Seg.Social empleados del hogar - Importe (0994)
62 | 722 | 600 | An | RESERVADO PARA LA A.E.A.T
63 | 1322 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10031000>
Total: |  | 1333

# Anexo B.4

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "32000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. Constante. Blanco
6 | 13 | 13 | N | Deducciones Autonómicas - Castilla y León (cont.) - Importe total aplicado  (0995)
7 | 26 | 13 | N | Deducciones Autonómicas - Castilla y León (cont.) - Otras deducciones (0996)
8 | 39 | 13 | N | Deducciones Autonómicas - Castilla y León (cont.) - Total deducciones autonómicas  (0564)
9 | 52 | 13 | N | Deducciones Autonómicas - Castilla y León (cont.) - Deducciones familia numerosa, nacimiento o adopción, etc - Ejercicios siguientes. Importe 2017 pdte. aplicación (0997)
10 | 65 | 13 | N | Deducciones Autonómicas - Castilla y León (cont.) - Deducciones familia numerosa, nacimiento o adopción, etc - Ejercicios siguientes. Importe 2018 pdte. aplicación (0998)
11 | 78 | 13 | N | Deducciones Autonómicas - Castilla y León (cont.) - Deducciones familia numerosa, nacimiento o adopción, etc - Ejercicios siguientes. Importe 2019 pdte. aplicación (0999)
12 | 91 | 13 | N | Deducciones Autonómicas - Cataluña - Por nacimiento o adopción de un hijo (1000)
13 | 104 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan el uso lengua catalana (1001)
14 | 117 | 13 | N | Deducciones Autonómicas - Cataluña - Por donativos a entidades que fomentan la investigación científica (1002)
15 | 130 | 13 | N | Deducciones Autonómicas - Cataluña - Por alquiler de vivienda habitual  (1003)
16 | 143 | 13 | N | Deducciones Autonómicas - Cataluña - Por pago intereses préstamos estudios universitarios de master y doctorado (1004)
17 | 156 | 13 | N | Deducciones Autonómicas - Cataluña - Para los contribuyentes que queden viudos (1005)
18 | 169 | 13 | N | Deducciones Autonómicas - Cataluña - Por rehabilitación vivienda habitual (1006)
19 | 182 | 13 | N | Deducciones Autonómicas - Cataluña - Por donaciones entidades en beneficio del medio ambiente (1007)
20 | 195 | 13 | N | Deducciones Autonómicas - Cataluña - Por inversión por ángel inversor y por adquisición de acciones entidades nuevas o de creación reciente (1008)
21 | 208 | 13 | N | Deducciones Autonómicas - Cataluña - Otras deducciones (1009)
22 | 221 | 13 | N | Deducciones Autonómicas - Cataluña - Total deducciones autonómicas (0564)
23 | 234 | 13 | N | Deducciones Autonómicas - Extremadura - Por adquisición o rehabilitación vivienda habitual para jóvenes y víctimas del terrorismo (1010)
24 | 247 | 13 | N | Deducciones Autonómicas - Extremadura - Por trabajo dependiente (1011)
25 | 260 | 13 | N | Deducciones Autonómicas - Extremadura - Por cuidado de familiares con discapacidad (1012)
26 | 273 | 13 | N | Deducciones Autonómicas - Extremadura - Por acogimiento de menores (1013)
27 | 286 | 13 | N | Deducciones Autonómicas - Extremadura - Por  partos múltiples (1014)
28 | 299 | 13 | N | Deducciones Autonómicas - Extremadura - Por compra de material escolar (1015)
29 | 312 | 13 | N | Deducciones Autonómicas - Extremadura - Por inversión en la adquisición de acciones o participaciones sociales (1016)
30 | 325 | 13 | N | Deducciones Autonómicas - Extremadura - Por gastos de guardería para hijos menores de 4 años (1017)
31 | 338 | 13 | N | Deducciones Autonómicas - Extremadura - Para contribuyentes viudos (1018)
32 | 351 | 13 | N | Deducciones Autonómicas - Extremadura - Por arrendamiento vivienda habitual (1019)
33 | 364 | 13 | N | Deducciones Autonómicas - Extremadura -  Otras deducciones (1020)
34 | 377 | 13 | N | Deducciones Autonómicas - Extremadura - Total deducciones autonómicas (0564)
35 | 390 | 13 | N | Deducciones Autonómicas - Galicia - Por nacimiento o adopción hijos (1021)
36 | 403 | 13 | N | Deducciones Autonómicas - Galicia - Por familia numerosa (1022)
37 | 416 | 13 | N | Deducciones Autonómicas - Galicia - Por cuidado hijos menores (1023)
38 | 429 | 13 | N | Deducciones Autonómicas - Galicia - Por contribuyentes con discapacidad = > 65 años que precisan ayuda de terceras personas (1024)
39 | 442 | 13 | N | Deducciones Autonómicas - Galicia - Por gastos uso nuevas tecnologías en hogares gallegos (1025)
40 | 455 | 13 | N | Deducciones Autonómicas - Galicia - Por alquiler de vivienda habitual  por contribuyentes de edad igual o inferior a 35 años (1026)
41 | 468 | 13 | N | Deducciones Autonómicas - Galicia - Por acogimiento de menores (1027)
42 | 481 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación (1028)
43 | 494 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones o participaciones sociales en entidades nuevas o de reciente creación y su financiación (1029)
44 | 507 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en acciones de entidades empresas en expansión Mercado Alternativo Bolsista (1030)
45 | 520 | 13 | N | Deducciones Autonómicas - Galicia - Por donaciones finalidad en investigacion y desarrollo científico e innovación tecnológica (1031)
46 | 533 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables (1032)
47 | 546 | 20 | An | Deducciones Autonómicas - Galicia - Por inversión instalaciones climatización y agua caliente vivienda habitual, empleen energías renovables - Código de instalación (1033)
48 | 566 | 13 | N | Deducciones Autonómicas - Galicia - Por rehabilitación de bienes inmuebles situados en centros históricos (1034)
49 | 579 | 13 | N | Deducciones Autonómicas - Galicia - Por inversión en empresas agrarias y sociedades cooperativas agrarias (1035)
50 | 592 | 13 | N | Deducciones Autonómicas - Galicia - Por determinadas subvenciones y/o ayudas obtenidas a consecuencia de los incendios de octubre de 2017 (1036)
51 | 605 | 13 | N | Deducciones Autonómicas - Galicia - Para paliar los daños causados por la explosión de material pirotécnico en Tuy en mayo del 2018 (1037)
52 | 618 | 13 | N | Deducciones Autonómicas - Galicia - Otras deducciones (1038)
53 | 631 | 13 | N | Deducciones Autonómicas - Galicia - Total deducciones autonómicas (0564)
54 | 644 | 600 | An | RESERVADO PARA LA A.E.A.T
55 | 1244 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10032000>
Total: |  | 1255

# Anexo B.5

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "33000"
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
22 | 221 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de guardería (1054)
23 | 234 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en instalaciones de recursos energéticos renovables (1055)
24 | 247 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en dispositivos domésticos de ahorro de agua (1056)
25 | 260 | 13 | N | Deducciones Autonómicas - Murcia - Por inversión en la adquisición de acciones y participaciones sociales de nuevas entidades (1057)
26 | 273 | 13 | N | Deducciones Autonómicas - Murcia - Por inversiones en entidades cotizadas Mercado Alternativo Bursátil (1058)
27 | 286 | 13 | N | Deducciones Autonómicas - Murcia - Por gastos de material escolar y libros de texto (1059)
28 | 299 | 13 | N | Deducciones Autonómicas - Murcia - Por donativos para la investigación biosanitaria (1060)
29 | 312 | 13 | N | Deducciones Autonómicas - Murcia - Por adopción o nacimiento (1073)
30 | 325 | 13 | N | Deducciones Autonómicas - Murcia - Otras deducciones (1074)
31 | 338 | 13 | N | Deducciones Autonómicas - Murcia - Total deducciones autonómicas (0564)
32 | 351 | 13 | N | Deducciones Autonómicas - La Rioja - Por nacimiento y adopción de hijos (1061)
33 | 364 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas rehabilitación vivienda habitual (1062)
34 | 377 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas adquisición o contrucción vivienda habitual para jóvenes (1063)
35 | 390 | 4 | Num | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Código municipio (1064)
36 | 394 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición o rehabilitación 2ª vivienda en el medio rural - Importe  (1065)
37 | 407 | 13 | N | Deducciones Autonómicas - La Rioja - Por cantidades invertidas en obras de adecuación de vivienda habitual para personas con discapacidad (1066)
38 | 420 | 4 | Num | Deducciones Autonómicas - La Rioja - Por adquisición, construcción y rehabilitación vivienda habitual pequeños municipios. Código municipio (1067)
39 | 424 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición, construcción y rehabilitación vivienda habitual pequeños municipios. Importe (1068)
40 | 437 | 13 | N | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado. Importe (1069)
41 | 450 | 9 | An | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado.NIF (1070)
42 | 459 | 4 | Num | Deducciones Autonómicas - La Rioja - Por gastos en escuelas o centros infantiles o personal contratado.Código municipio (1071)
43 | 463 | 13 | N | Deducciones Autonómicas - La Rioja - Por acogimiento de menores (1072)
44 | 476 | 13 | N | Deducciones Autonómicas - La Rioja - Por hijos de 0 a 3 años escolarizados en cualquier municipio de la Rioja. Importe (1075)
45 | 489 | 9 | An | Deducciones Autonómicas - La Rioja - Por hijos de 0 a 3 años escolarizados en cualquier municipio de la Rioja. NIF del centro (1076)
46 | 498 | 13 | N | Deducciones Autonómicas - La Rioja - Por adquisición de vehículos eléctricos nuevos (1077)
47 | 511 | 13 | N | Deducciones Autonómicas - La Rioja - Por arrendamiento de vivienda a jóvenes (1078)
48 | 524 | 4 | Num | Deducciones Autonómicas - La Rioja - Por acceso a internet para jóvenes emancipados.Código municipio (1204)
49 | 528 | 13 | N | Deducciones Autonómicas - La Rioja - Por acceso a internet para jóvenes emancipados. Importe de la deducción (1079)
50 | 541 | 4 | Num | Deducciones Autonómicas - La Rioja - Por suministro de luz y gas de uso doméstico para jóvenes emancipados. Código municipio (1205)
51 | 545 | 13 | N | Deducciones Autonómicas - La Rioja - Por suministro de luz y gas de uso doméstico para jóvenes emancipados. Importe de la deducción (1080)
52 | 558 | 13 | N | Deducciones Autonómicas - La Rioja - Por inversión en vivienda habitual de jóvenes menores de 36 años (1081)
53 | 571 | 13 | N | Deducciones Autonómicas - La Rioja - Otras deducciones (1082)
54 | 584 | 13 | N | Deducciones Autonómicas - La Rioja - Total deducciones autonómicas (0564)
55 | 597 | 600 | An | RESERVADO PARA LA A.E.A.T
56 | 1197 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10033000>
Total: |  | 1208

# Anexo B.6

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "34000"
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
22 | 216 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obtención de rentas derivadas del arrendamiento de vivienda cuya renta no supere el precio de referencia de alquileres privados (1111)
23 | 229 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones con finalidad ecológica (1099)
24 | 242 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donación de bienes integrantes Patrimonio Cultural Valenciano (1100)
25 | 255 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades donadas para la conservación, reparación y restauración de bienes (1101)
26 | 268 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades destinadas a la conservación, reparación y restauración de bienes (1102)
27 | 281 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por donaciones al fomento de la Lengua Valenciana (1103)
28 | 294 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por contribuyentes con dos o más descendientes (1104)
29 | 307 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana -  Por cantidades procedentes de ayudas públicas concedidas por la Generalitat (1105)
30 | 320 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por adquisición material escolar (1106)
31 | 333 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual  - NIF persona o entidad (1107)
32 | 342 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual - Importe  (1108)
33 | 355 | 9 | An | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual realizadas en el periodo - NIF persona o entidad (1109)
34 | 364 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por obras de conservación y mejora en la vivienda habitual realizadas en el periodo - Importe  (1110)
35 | 377 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por donaciones o cesiones de uso o comodatos para otros fines de interés cultural, científico o deportivo no profesional (1112)
36 | 390 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por cantidades destinadas a abonos culturales (1113)
37 | 403 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. Importe (1114)
38 | 416 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. Ejercicios anteriores. Importe 2017 y/o 2018 pendiente (1115)
39 | 429 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. Ejercicios anteriores. Importe aplicado en el ejercicio  (1116)
40 | 442 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. Ejercicios anteriores. Importe 2017 y/o 2018 pendiente de aplicación en ejercicios futuros (1117)
41 | 455 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2019. Importe generado (1118)
42 | 468 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2019. Importe aplicado en el ejercicio  (1119)
43 | 481 | 13 | N | Deducciones Autonómicas - Comunitat Valenciana - Por inversión en instalaciones de autoconsumo energía eléctrica. 2019. Importe generado en 2018 pendiente de aplicación en ejercicios futuros(1120)
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
56 | 1227 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10034000>
Total: |  | 1238

# Anexo B.7

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "35000"
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
35 | 940 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10035000>
Total: |  | 951

# Anexo B.8

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "36000"
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
41 | 995 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10036000>
Total: |  | 1006

# Anexo C.1

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "37000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 3 | Num | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - Número de orden  (1210)
7 | 16 | 1 | Tit | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - Contribuyente  "0" a "9" (1211)
8 | 17 | 20 | An | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - Referencia catastral (1212)
9 | 37 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2015. Pendiente principio periodo  (1213)
10 | 50 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2015. Aplicado en declaración (1214)
11 | 63 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Pendiente principio periodo  (1215)
12 | 76 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Aplicado en declaración  (1216)
13 | 89 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2016. Pdte. aplicación ejercicios futuros  (1217)
14 | 102 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2017. Pendiente principio periodo  (1218)
15 | 115 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2017. Aplicado en declaración (1219)
16 | 128 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2017. Pdte. aplicación ejercicios futuros  (1220)
17 | 141 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2018. Pendiente principio periodo  (1221)
18 | 154 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2018. Aplicado en declaración  (1222)
19 | 167 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2018. Pdte. aplicación ejercicios futuros  (1223)
20 | 180 | 13 | N | C | Intereses capitales invertidos adquisición o mejora inmuebles pendientes de deducir - 2019. Pdte. aplicación ejercicios futuros  (1224)
21 | 193 | 3 | Num | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Número de orden  (0356)
22 | 196 | 1 | Tit | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Contribuyente  "0" a "9" (0357)
23 | 197 | 3 | Num | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Nº de años de cobro pendiente (0358)
24 | 200 | 4 | Num | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Último año de cobro (0359)
25 | 204 | 20 | An | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Referencia catastral 1 (0360)
26 | 224 | 20 | An | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Referencia catastral 2 (0361)
27 | 244 | 20 | An | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Referencia catastral 3 (0362)
28 | 264 | 4 | Num | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Año imputación 1 (0363)
29 | 268 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Importe a percibir 1 (0364)
30 | 281 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Ganancia patrimonial pendiente 1 (0365)
31 | 294 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Pérdida patrimonial pendiente 1 (0366)
32 | 307 | 4 | Num | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Año imputación 2 (0367)
33 | 311 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Importe a percibir 2 (0368)
34 | 324 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Ganancia patrimonial pendiente 2 (0369)
35 | 337 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Pérdida patrimonial pendiente 2 (0370)
36 | 350 | 4 | Num | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Año imputación 3 (0371)
37 | 354 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Importe a percibir 3 (0372)
38 | 367 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Ganancia patrimonial pendiente 3 (0373)
39 | 380 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Pérdida patrimonial pendiente 3 (0374)
40 | 393 | 4 | Num | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Año imputación 4 (0375)
41 | 397 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Importe a percibir 4 (0376)
42 | 410 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Ganancia patrimonial pendiente 4 (0377)
43 | 423 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Pérdida patrimonial pendiente 4 (0378)
44 | 436 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Resto Importe a percibir (0379)
45 | 449 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Resto ganancia patrimonial pendiente (0380)
46 | 462 | 13 | N | C | Ganancias y pérdidas patrimoniales con precio aplazado pendientes de imputación - Resto pérdida patrimonial pendiente (0381)
47 | 475 | 1 | Tit | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Contribuyente "0" a "9" (1225)
48 | 476 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe total obtenido susceptible de reinversión (1226)
49 | 489 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Ganancia patrimonial obtenida (1227)
50 | 502 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe reinvertido hasta 31-12-2019 en adquisición nueva vivienda (1228)
51 | 515 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Importe que se compromete a reinvertir 2 años siguientes (1229)
52 | 528 | 13 | N | C | Exención por reinversión ganancia patrimonial por transmisión vivienda habitual - Ganancia patrimonial exenta por reinversión (1230)
53 | 541 | 1 | Tit | C | Exención por reinversión en entidades de nueva o reciente creación - Contribuyente "0" a "9" (1231)
54 | 542 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe total obtenido susceptible de reinversión (1232)
55 | 555 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Ganancia patrimonial obtenida (1233)
56 | 568 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe reinvertido hasta 31-12-2019 (1234)
57 | 581 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Importe que se compromete a reinvertir en 2020 (1235)
58 | 594 | 13 | N | C | Exención por reinversión en entidades de nueva o reciente creación - Ganancia patrimonial exenta por reinversión (1236)
59 | 607 | 1 | Tit | C | Exención por reinversión en rentas vitalicias -  Contribuyente "0" a "9" (1237)
60 | 608 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe total transmisión elementos patrimoniales (1238)
61 | 621 | 13 | N | C | Exención por reinversión en rentas vitalicias - Ganancia patrimonial obtenida (1239)
62 | 634 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe reinvertido hasta 31-12-2019 en rentas vitalicias (1240)
63 | 647 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe que se compromete a reinvertir en 2020 (1241)
64 | 660 | 13 | N | C | Exención por reinversión en rentas vitalicias - Importe retención que se compromete a reinvertir en 2020 (1242)
65 | 673 | 13 | N | C | Exención por reinversión en rentas vitalicias - Ganancia patrimonial exenta por reinversión (1243)
66 | 686 | 600 | An |  | RESERVADO PARA LA A.E.A.T
67 | 1286 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10037000>
Total: |  | 1297

# Anexo C.2

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "38000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. Contribuyente "0" a "9" (1245)
7 | 14 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2015. Pendiente principio periodo (1246)
8 | 27 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2015. Aplicado en declaración (1247)
9 | 40 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Pendiente principio periodo (1248)
10 | 53 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Aplicado en declaración (1249)
11 | 66 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2016. Pdte. aplicación ejercicios futuros (1250)
12 | 79 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2017. Pendiente principio periodo (1251)
13 | 92 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2017. Aplicado en declaración (1252)
14 | 105 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2017. Pdte. aplicación ejercicios futuros (1253)
15 | 118 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2018. Pendiente principio periodo (1254)
16 | 131 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2018. Aplicado en declaración (1255)
17 | 144 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. 2018. Pdte. aplicación ejercicios futuros (1256)
18 | 157 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI general. Saldo negativo pendiente de compensación (1257)
19 | 170 | 1 | Tit | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. Contribuyente "0" a "9" (1258)
20 | 171 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2015. Pendiente principio periodo (1259)
21 | 184 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2015. Aplicado en declaración (1260)
22 | 197 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Pendiente principio periodo (1261)
23 | 210 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Aplicado en declaración (1262)
24 | 223 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2016. Pdte. aplicación ejercicios futuros (1263)
25 | 236 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2017. Pendiente principio periodo (1264)
26 | 249 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2017. Aplicado en declaración (1265)
27 | 262 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2017. Pdte. aplicación ejercicios futuros (1266)
28 | 275 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2018. Pendiente principio periodo (1267)
29 | 288 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2018. Aplicado en declaración (1268)
30 | 301 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. 2018. Pdte. aplicación ejercicios futuros (1269)
31 | 314 | 13 | N | C | Saldos negativos ganancias y pérdidas pendientes compensar. Saldo neto negativo BI ahorro. Saldo negativo pendiente de compensación (1270)
32 | 327 | 1 | Tit | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. Contribuyente "0" a "9" (1271)
33 | 328 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2015. Pendiente principio periodo (1272)
34 | 341 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2015. Aplicado en declaración (1273)
35 | 354 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Pendiente principio periodo (1274)
36 | 367 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Aplicado en declaración (1275)
37 | 380 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2016. Pdte. aplicación ejercicios futuros (1276)
38 | 393 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2017. Pendiente principio periodo (1277)
39 | 406 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2017. Aplicado en declaración (1278)
40 | 419 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2017. Pdte. aplicación ejercicios futuros (1279)
41 | 432 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2018. Pendiente principio periodo (1280)
42 | 445 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2018. Aplicado en declaración (1281)
43 | 458 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. 2018. Pdte. aplicación ejercicios futuros (1282)
44 | 471 | 13 | N | C | Rendimientos capital mobiliario negativos pendientes compensar. BI ahorro. Saldo negativo pendiente de compensación (1283)
45 | 484 | 1 | Tit | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir.  Contribuyente "0" a "9" (1284)
46 | 485 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2014. Pendiente principio periodo (1285)
47 | 498 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2014. Aplicado en declaración (1286)
48 | 511 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Pendiente principio periodo (1287)
49 | 524 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Aplicado en declaración (1288)
50 | 537 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2015. Pdte. aplicación ejercicios futuros (1289)
51 | 550 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Pendiente principio periodo (1290)
52 | 563 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Aplicado en declaración (1291)
53 | 576 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2016. Pdte. aplicación ejercicios futuros (1292)
54 | 589 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2017. Pendiente principio periodo (1293)
55 | 602 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2017. Aplicado en declaración (1294)
56 | 615 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2017. Pdte. aplicación ejercicios futuros (1295)
57 | 628 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2018. Pendiente principio periodo (1296)
58 | 641 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2018. Aplicado en declaración (1297)
59 | 654 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. 2018. Pdte. aplicación ejercicios futuros (1298)
60 | 667 | 13 | N | C | Exceso no reducido aportaciones sistemas previsión social pendientes de reducir. Aportaciones y contribuciones 2019 (1299)
61 | 680 | 1 | Tit | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. Contribuyente "0" a "9" (1300)
62 | 681 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2014. Pendiente principio periodo (1301)
63 | 694 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2014. Aplicado en declaración (1302)
64 | 707 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Pendiente principio periodo (1303)
65 | 720 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Aplicado en declaración (1304)
66 | 733 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2015. Pdte. aplicación ejercicios futuros (1305)
67 | 746 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Pendiente principio periodo (1306)
68 | 759 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Aplicado en declaración (1307)
69 | 772 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2016. Pdte. aplicación ejercicios futuros (1308)
70 | 785 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2017. Pendiente principio periodo (1309)
71 | 798 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2017. Aplicado en declaración (1310)
72 | 811 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2017. Pdte. aplicación ejercicios futuros (1311)
73 | 824 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2018. Pendiente principio periodo (1312)
74 | 837 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2018. Aplicado en declaración (1313)
75 | 850 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. 2018. Pdte. aplicación ejercicios futuros (1314)
76 | 863 | 13 | N | C | Exceso no reducido contribuciones a seguros colectivos de dependencia pendientes de reducir. Contribuciones 2019 (1315)
77 | 876 | 600 | An |  | RESERVADO PARA LA A.E.A.T
78 | 1476 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10038000>
Total: |  | 1487

# Anexo C.3

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "39000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 1 | Tit | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad.  Contribuyente "0" a "9" (1316)
7 | 14 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2014. Pendiente principio periodo (1317)
8 | 27 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2014. Aplicado en declaración (1318)
9 | 40 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Pendiente principio periodo (1319)
10 | 53 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Aplicado en declaración (1320)
11 | 66 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2015. Pdte. aplicación ejercicios futuros (1321)
12 | 79 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Pendiente principio periodo (1322)
13 | 92 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Aplicado en declaración (1323)
14 | 105 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2016. Pdte. aplicación ejercicios futuros (1324)
15 | 118 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2017. Pendiente principio periodo (1325)
16 | 131 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2017. Aplicado en declaración (1326)
17 | 144 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2017. Pdte. aplicación ejercicios futuros (1327)
18 | 157 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2018. Pendiente principio periodo (1328)
19 | 170 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2018. Aplicado en declaración (1329)
20 | 183 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. 2018. Pdte. aplicación ejercicios futuros (1330)
21 | 196 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. Persona con discapacidad. Aportaciones y contribuciones 2019 (1331)
22 | 209 | 1 | Tit | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes.  Contribuyente "0" a "9" (1332)
23 | 210 | 9 | An | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. NIF persona con discapacidad (1333)
24 | 219 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2014. Pendiente principio periodo (1334)
25 | 232 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2014. Aplicado en declaración (1335)
26 | 245 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Pendiente principio periodo (1336)
27 | 258 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Aplicado en declaración (1337)
28 | 271 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2015. Pdte. aplicación ejercicios futuros (1338)
29 | 284 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Pendiente principio periodo (1339)
30 | 297 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Aplicado en declaración (1340)
31 | 310 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2016. Pdte. aplicación ejercicios futuros (1341)
32 | 323 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2017. Pendiente principio periodo (1342)
33 | 336 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2017. Aplicado en declaración (1343)
34 | 349 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2017. Pdte. aplicación ejercicios futuros (1344)
35 | 362 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2018. Pendiente principio periodo (1345)
36 | 375 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2018. Aplicado en declaración (1346)
37 | 388 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. 2018. Pdte. aplicación ejercicios futuros (1347)
38 | 401 | 13 | N | C | Exceso no reducido aportaciones sist.previsión social personas con discapacidad pendientes de reducir. A favor de parientes. Aportaciones y contribuciones 2019 (1348)
39 | 414 | 1 | Tit | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.  Contribuyente "0" a "9" (1349)
40 | 415 | 9 | An | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.  NIF persona con discapacidad  (1350)
41 | 424 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2015. Pendiente principio periodo (1351)
42 | 437 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2015. Aplicado en declaración (1352)
43 | 450 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Pendiente principio periodo (1353)
44 | 463 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Aplicado en declaración (1354)
45 | 476 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2016. Pdte. aplicación ejercicios futuros (1355)
46 | 489 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2017. Pendiente principio periodo (1356)
47 | 502 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2017. Aplicado en declaración (1357)
48 | 515 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2017. Pdte. aplicación ejercicios futuros (1358)
49 | 528 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2018. Pendiente principio periodo (1359)
50 | 541 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2018. Aplicado en declaración (1360)
51 | 554 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir.2018. Pdte. aplicación ejercicios futuros (1361)
52 | 567 | 13 | N | C | Exceso no reducido aportaciones patrimonios protegidos personas con discapacidad pendientes de reducir. Aportaciones 2019 (1362)
53 | 580 | 1 | Tit | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.  Contribuyente "0" a "9" (1363)
54 | 581 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2014. Pendiente principio periodo (1364)
55 | 594 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2014. Aplicado en declaración (1365)
56 | 607 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Pendiente principio periodo (1366)
57 | 620 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Aplicado en declaración (1367)
58 | 633 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2015. Pdte. aplicación ejercicios futuros (1368)
59 | 646 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Pendiente principio periodo (1369)
60 | 659 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Aplicado en declaración (1370)
61 | 672 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2016. Pdte. aplicación ejercicios futuros (1371)
62 | 685 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2017. Pendiente principio periodo (1372)
63 | 698 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2017. Aplicado en declaración (1373)
64 | 711 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2017. Pdte. aplicación ejercicios futuros (1374)
65 | 724 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2018. Pendiente principio periodo (1375)
66 | 737 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2018. Aplicado en declaración (1376)
67 | 750 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir.2018. Pdte. aplicación ejercicios futuros (1377)
68 | 763 | 13 | N | C | Exceso no reducido aportaciones mutualidades deportistas profesionales pendientes de reducir. Aportaciones y contribuciones 2019 (1378)
69 | 776 | 1 | Tit | C | Bases liquidables generales negativas pendientes de compensar.  Contribuyente "0" a "9" (1379)
70 | 777 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2015. Pendiente principio periodo (1380)
71 | 790 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2015. Aplicado en declaración (1381)
72 | 803 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Pendiente principio periodo (1382)
73 | 816 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Aplicado en declaración (1383)
74 | 829 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2016. Pdte. aplicación ejercicios futuros (1384)
75 | 842 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2017. Pendiente principio periodo (1385)
76 | 855 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2017. Aplicado en declaración (1386)
77 | 868 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2017. Pdte. aplicación ejercicios futuros (1387)
78 | 881 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2018. Pendiente principio periodo (1388)
79 | 894 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2018. Aplicado en declaración (1389)
80 | 907 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar.2018. Pdte. aplicación ejercicios futuros (1390)
81 | 920 | 13 | N | C | Bases liquidables generales negativas pendientes de compensar. 2019 (1391)
82 | 933 | 600 | An |  | RESERVADO PARA LA A.E.A.T
83 | 1533 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10039000>
Total: |  | 1544

# Anexo D

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num |  | Página. | OBLIGATORIO | Constante "40000"
4 | 11 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 3 | Num | C | Información adicional sobre gastos relacionados con bienes inmuebles. Datos Adicionales. Número de orden del inmueble (1392)
7 | 16 | 1 | Tit | C | Información adicional sobre gastos relacionados con bienes inmuebles. Datos Adicionales. Contribuyente  "0" a "9" (1393)
8 | 17 | 20 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Datos Adicionales. Referencia catastral (1394)
9 | 37 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 1. NIF de quién realizó la obra o servicio (1395)
10 | 46 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 1. Importe (1396)
11 | 59 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 2. NIF de quién realizó la obra o servicio (1397)
12 | 68 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 2. Importe (1398)
13 | 81 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 3. NIF de quién realizó la obra o servicio (1399)
14 | 90 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 3. Importe (1400)
15 | 103 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 4. NIF de quién realizó la obra o servicio (1401)
16 | 112 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 4. Importe (1402)
17 | 125 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 5. NIF de quién realizó la obra o servicio (1403)
18 | 134 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Gasto 5. Importe (1404)
19 | 147 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de reparación y conservación. Importe resto de gastos (1405)
20 | 160 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de formalización de contrato. Gasto 1. NIF de quién prestó el servicio (1406)
21 | 169 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de formalización de contrato. Gasto 1. Importe (1407)
22 | 182 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de formalización de contrato. Gasto 2. NIF de quién prestó el servicio (1408)
23 | 191 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de formalización de contrato. Gasto 2. Importe (1409)
24 | 204 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de formalización de contrato. Importe resto de gastos (1410)
25 | 217 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de defensa jurídica. Gasto 1. NIF de quién prestó el servicio (1411)
26 | 226 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de defensa jurídica. Gasto 1. Importe (1412)
27 | 239 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de defensa jurídica. Gasto 2. NIF de quién prestó el servicio (1413)
28 | 248 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de defensa jurídica. Gasto 2. Importe (1414)
29 | 261 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Gastos de defensa jurídica. Importe resto de gastos (1415)
30 | 274 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Cantidades devengadas por terceros por servicios personales. Gasto 1. NIF de quién prestó el servicio (1416)
31 | 283 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Cantidades devengadas por terceros por servicios personales. Gasto 1. Importe (1417)
32 | 296 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Cantidades devengadas por terceros por servicios personales. Gasto 2. NIF de quién prestó el servicio (1418)
33 | 305 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Cantidades devengadas por terceros por servicios personales. Gasto 2. Importe (1419)
34 | 318 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Cantidades devengadas por terceros por servicios personales. Importe resto de gastos (1420)
35 | 331 | 8 | Num | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 1. Fecha realización (DDMMAAA) (1421)
36 | 339 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 1. NIF de quién realizó la obra o servicio (1422)
37 | 348 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 1. Importe (1423)
38 | 361 | 8 | Num | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 2. Fecha realización (DDMMAAA) (1424)
39 | 369 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 2. NIF de quién realizó la obra o servicio (1425)
40 | 378 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 2. Importe (1426)
41 | 391 | 8 | Num | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 3. Fecha realización (DDMMAAA) (1427)
42 | 399 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 3. NIF de quién realizó la obra o servicio (1428)
43 | 408 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Gasto 3. Importe (1429)
44 | 421 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble. Importe resto de gastos (1430)
45 | 434 | 8 | Num | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 1. Fecha realización (DDMMAAA) (1431)
46 | 442 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 1. NIF de quién realizó la obra o servicio (1432)
47 | 451 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 1. Importe (1433)
48 | 464 | 8 | Num | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 2. Fecha realización (DDMMAAA) (1434)
49 | 472 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 2. NIF de quién realizó la obra o servicio (1435)
50 | 481 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 2. Importe (1436)
51 | 494 | 8 | Num | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 3. Fecha realización (DDMMAAA) (1437)
52 | 502 | 9 | An | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 3. NIF de quién realizó la obra o servicio (1438)
53 | 511 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Gasto 3. Importe (1439)
54 | 524 | 13 | N | C | Información adicional sobre gastos relacionados con bienes inmuebles. Mejoras realizadas en el inmueble accesorio. Importe resto de gastos (1440)
55 | 537 | 600 | An |  | RESERVADO PARA LA A.E.A.T
56 | 1137 | 12 | An |  | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10040000>
Total: |  | 1148

# I-D

 | Agencia Tributaria
Modelo 100 |  | Diseño de registro
vers 0.15 |  | Impuesto sobre la Renta de las Personas Físicas 2019
Nº | Posic. | Long. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "100"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "41000"
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
28 | 809 | 12 | An | Identificador de Fin de registro. | OBLIGATORIO | Constante </T10041000>
Total: |  | 820