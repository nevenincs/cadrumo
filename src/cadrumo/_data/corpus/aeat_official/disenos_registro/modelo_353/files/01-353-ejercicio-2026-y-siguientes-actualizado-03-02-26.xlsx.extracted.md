# 35300

 | Agencia Tributaria
Modelo 353
versión 1.2 |  | Diseño de registro
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "353"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) |  | "01"..."12"
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Tipo+> |  | "</T3530AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# 35301

 | Agencia Tributaria
Modelo 353 |  | Diseño de registro. Castellano
Version 1.2 |  | Impuesto sobre el Valor Añadido. Grupo de entidades. Modelo agregado. Autoliquidación mensual
Nº | Posic. | Lon | Tipo | Com. | Descripción | Validación | Contenido | Uso
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página |  | Constante "<T"
2 | 3 | 3 | Num |  | Modelo |  | Constante "353"
3 | 6 | 2 | Num |  | Página |  | Constante "01"
4 | 8 | 4 | An |  | Fin de identificador de modelo |  | Constante "000>"
5 | 12 | 1 | An |  | Indicador de página complementaria | obligatorio | blanco o "C" (compl.)
6 | 13 | 1 | An |  | Tipo de declaración |  | Ver Nota
7 | 14 | 9 | An |  | Identificación. Declarante. N.I.F.
8 | 23 | 60 | An |  | Identificación. Apellidos  o razón social
9 | 83 | 20 | An |  | Reservado para la Agencia Tributaria
10 | 103 | 4 | Num |  | Identificación. Ejercicio
11 | 107 | 2 | An |  | Identificación. Periodo
12 | 109 | 10 | An |  | Identificación. Nº Grupo
13 | 119 | 1 | Num |  | Identificación. Tipo régimen especial aplicable. Art. 163.sixies.cinco. S/N | obligatorio | 1 -Sí, 2 -No
14 | 120 | 1 | Num |  | Identificación. Tipo régimen especial aplicable. 
¿Esta inscrito en el Registro de devolución mensual (Art. 30 RIVA)? | obligatorio | 1 -Sí, 2 -No
15 | 121 | 1 | An |  | Identificación. Grupo sometido a normativa foral |  | X o blanco
16 | 122 | 9 | An |  | Entidades del grupo que tributan en el régimen especial. Entidad dominante. N.I.F.
17 | 131 | 17 | N |  | Entidades del grupo que tributan en el régimen especial. Entidad dominante. Resultado
18 | 148 | 5 | Num |  | Reservado para la Agencia Tributaria
19 | 153 | 13 | An |  | Entidades del grupo que tributan en el régimen especial. Entidad dominante. 
Número de justificante mod. 322
20 | 166 | 3 | An |  | Reservado para la Agencia Tributaria
21 | 169 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 1. Entidades dependientes. N.I.F.
22 | 178 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 1. Entidades dependientes. Resultado
23 | 195 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 1.
 Ent. depndtes. % de participac. al final del periodo
24 | 200 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 1. Entidades dependientes.
 Número de justificante mod. 322
25 | 213 | 3 | An |  | Reservado para la Agencia Tributaria
26 | 216 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 2. Entidades dependientes. N.I.F.
27 | 225 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 2. Entidades dependientes. Resultado
28 | 242 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 2. 
Ent. depndtes. % de participac. al final del periodo
29 | 247 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 2. Entidades dependientes.
 Número de justificante mod. 322
30 | 260 | 3 | An |  | Reservado para la Agencia Tributaria
31 | 263 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 3. Entidades dependientes. N.I.F.
32 | 272 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 3. Entidades dependientes. Resultado
33 | 289 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 3. 
Ent. depndtes. % de participac. al final del periodo
34 | 294 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 3. Entidades dependientes. 
Número de justificante mod. 322
35 | 307 | 3 | An |  | Reservado para la Agencia Tributaria
36 | 310 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 4. Entidades dependientes. N.I.F.
37 | 319 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 4. Entidades dependientes. Resultado
38 | 336 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 4. 
Ent. depndtes. % de participac. al final del periodo
39 | 341 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 4. Entidades dependientes.
 Número de justificante mod. 322
40 | 354 | 3 | An |  | Reservado para la Agencia Tributaria
41 | 357 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 5. Entidades dependientes. N.I.F.
42 | 366 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 5. Entidades dependientes. Resultado
43 | 383 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 5. 
Ent. depndtes. % de participac. al final del periodo
44 | 388 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 5. Entidades dependientes.
 Número de justificante mod. 322
45 | 401 | 3 | An |  | Reservado para la Agencia Tributaria
46 | 404 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 6. Entidades dependientes. N.I.F.
47 | 413 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 6. Entidades dependientes. Resultado
48 | 430 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 6. 
Ent. depndtes. % de participac. al final del periodo
49 | 435 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 6. Entidades dependientes.
 Número de justificante mod. 322
50 | 448 | 3 | An |  | Reservado para la Agencia Tributaria
51 | 451 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 7. Entidades dependientes. N.I.F.
52 | 460 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 7. Entidades dependientes. Resultado
53 | 477 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 7. 
Ent. depndtes. % de participac. al final del periodo
54 | 482 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 7. Entidades dependientes. 
Número de justificante mod. 322
55 | 495 | 3 | An |  | Reservado para la Agencia Tributaria
56 | 498 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 8. Entidades dependientes. N.I.F.
57 | 507 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 8. Entidades dependientes. Resultado
58 | 524 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 8. 
Ent. depndtes. % de participac. al final del periodo
59 | 529 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 8. Entidades dependientes. 
Número de justificante mod. 322
60 | 542 | 3 | An |  | Reservado para la Agencia Tributaria
61 | 545 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 9. Entidades dependientes. N.I.F.
62 | 554 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 9. Entidades dependientes. Resultado
63 | 571 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 9. 
Ent. depndtes. % de participac. al final del periodo
64 | 576 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 9. Entidades dependientes. 
Número de justificante mod. 322
65 | 589 | 3 | An |  | Reservado para la Agencia Tributaria
66 | 592 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 10. Entidades dependientes. N.I.F.
67 | 601 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 10. Entidades dependientes. Resultado
68 | 618 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 10. 
Ent. depndtes. % de participac. al final del periodo
69 | 623 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 10. Entidades dependientes. 
Número de justificante mod. 322
70 | 636 | 3 | An |  | Reservado para la Agencia Tributaria
71 | 639 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 11. Entidades dependientes. N.I.F.
72 | 648 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 11. Entidades dependientes. Resultado
73 | 665 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 11. 
Ent. depndtes. % de participac. al final del periodo
74 | 670 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 11. Entidades dependientes.
 Número de justificante mod. 322
75 | 683 | 3 | An |  | Reservado para la Agencia Tributaria
76 | 686 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 12. Entidades dependientes. N.I.F.
77 | 695 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 12. Entidades dependientes. Resultado
78 | 712 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 12.
 Ent. depndtes. % de participac. al final del periodo
79 | 717 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 12. Entidades dependientes.
 Número de justificante mod. 322
80 | 730 | 3 | An |  | Reservado para la Agencia Tributaria
81 | 733 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 13. Entidades dependientes. N.I.F.
82 | 742 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 13. Entidades dependientes. Resultado
83 | 759 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 13. 
Ent. depndtes. % de participac. al final del periodo
84 | 764 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 13. Entidades dependientes. 
Número de justificante mod. 322
85 | 777 | 3 | An |  | Reservado para la Agencia Tributaria
86 | 780 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 14. Entidades dependientes. N.I.F.
87 | 789 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 14. Entidades dependientes. Resultado
88 | 806 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 14. 
Ent. depndtes. % de participac. al final del periodo
89 | 811 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 14. Entidades dependientes. 
Número de justificante mod. 322
90 | 824 | 3 | An |  | Reservado para la Agencia Tributaria
91 | 827 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 15. Entidades dependientes. N.I.F.
92 | 836 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 15. Entidades dependientes. Resultado
93 | 853 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 15. 
Ent. depndtes. % de participac. al final del periodo
94 | 858 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 15. Entidades dependientes.
 Número de justificante mod. 322
95 | 871 | 3 | An |  | Reservado para la Agencia Tributaria
96 | 874 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 16. Entidades dependientes. N.I.F.
97 | 883 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 16. Entidades dependientes. Resultado
98 | 900 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 16.
 Ent. depndtes. % de participac. al final del periodo
99 | 905 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 16. Entidades dependientes. 
Número de justificante mod. 322
100 | 918 | 3 | An |  | Reservado para la Agencia Tributaria
101 | 921 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 17. Entidades dependientes. N.I.F.
102 | 930 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 17. Entidades dependientes. Resultado
103 | 947 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 17. 
Ent. depndtes. % de participac. al final del periodo
104 | 952 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 17. Entidades dependientes. 
Número de justificante mod. 322
105 | 965 | 3 | An |  | Reservado para la Agencia Tributaria
106 | 968 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 18. Entidades dependientes. N.I.F.
107 | 977 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 18. Entidades dependientes. Resultado
108 | 994 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 18. 
Ent. depndtes. % de participac. al final del periodo
109 | 999 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 18. Entidades dependientes. 
Número de justificante mod. 322
110 | 1012 | 3 | An |  | Reservado para la Agencia Tributaria
111 | 1015 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 19. Entidades dependientes. N.I.F.
112 | 1024 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 19. Entidades dependientes. Resultado
113 | 1041 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 19. 
Ent. depndtes. % de participac. al final del periodo
114 | 1046 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 19. Entidades dependientes.
 Número de justificante mod. 322
115 | 1059 | 3 | An |  | Reservado para la Agencia Tributaria
116 | 1062 | 9 | An | C | Entidades del grupo que tributan en el régimen especial. 20. Entidades dependientes. N.I.F.
117 | 1071 | 17 | N | C | Entidades del grupo que tributan en el régimen especial. 20. Entidades dependientes. Resultado
118 | 1088 | 5 | Num | C | Entidades del grupo que tributan en el régimen especial. 20. 
Ent. depndtes. % de participac. al final del periodo
119 | 1093 | 13 | An | C | Entidades del grupo que tributan en el régimen especial. 20. Entidades dependientes.
 Número de justificante mod. 322
120 | 1106 | 3 | An |  | Reservado para la Agencia Tributaria
121 | 1109 | 17 | N |  | Liquidación. Resultado total (sumatorio del resultado de entidades)  [01]
122 | 1126 | 17 | Num |  | Liquidación. Cuotas a compensar pendientes de ejercicios anteriores  [02]
123 | 1143 | 17 | Num |  | Liquidación. Cuotas a compensar de periodos anteriores aplicadas en este periodo  [08]
124 | 1160 | 17 | Num |  | Liquidación. Cuotas a compensar de periodos previos 
pendientes para periodos posteriores  ([02]-[08]) [09]
(No se incluyen las cuotas a compensar generadas en este periodo)
125 | 1177 | 17 | N |  | Liquidación. Resultado ([01] - [08]).  [03]
126 | 1194 | 17 | N |  | Liquidación. A deducir. Resultado de las autoliq. anter. presentadas por el mismo conpto,
 ejerc. y periodo  [04]
127 | 1211 | 17 | Num |  | Liquidación. Pago a cuenta de entregas de gasolinas, gasóleos y biocarburantes posteriores a la ultimación del régimen de depósito distinto del aduanero atribuible a la Administración del Estado [10] |  | Nota 4.
128 | 1228 | 17 | N |  | Liquidación. Resultado de la autoliquidación ([03] - [04]).  [05]
129 | 1245 | 1 | An |  | Autoliquidación complementaria. Autoliquidación complementaria. |  | X o blanco
130 | 1246 | 13 | An |  | Autoliquidación complementaria. Número de justificante de la autoliquidación anterior
131 | 1259 | 1 | An |  | Sin actividad |  | X o blanco
132 | 1260 | 416 | An |  | Reservado para la Agencia Tributaria
133 | 1676 | 13 | An |  | SELLO ELECTRÓNICO RESERVADO PARA LA AEAT
134 | 1689 | 12 | An |  | Identificador de fin de registro. |  | </T35301000>
TOTAL |  | 1700 | Posiciones
 | Nota 1:
 | 1. Los campos deben ser A (Alfabético), An (Alfanumérico), Núm (Numérico sin signo)  o N (Numérico con signo).
 | 2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
 | 3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
 | 5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
 | 5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | Nota 2:
 | El tipo de declaración para la presentación por lotes puede ser: I (a ingresar) U (domiciliación) D (a devolver)  C (a compensar) N (sin actividad/resultado cero)
 | Nota 3:
 | El campo indicador de página complementaria se cumplientará cuando en el fichero van más de una página del mismo tipo.
 | La C de la columna Comp indica los campos que pueden tener contenido en las  páginas complementarias
 | Nota 4:
 | Solo para periodos 02 y siguientes.

# 35302

 | Agencia Tributaria
Modelo 353 |  | Diseño de registro. Castellano
Version 1.2 |  | Impuesto sobre el Valor Añadido. Grupo de entidades. Modelo agregado. Autoliquidación mensual
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido | Uso
1 | 1 | 2 | An | Inicio del identificador de modelo y página |  | Constante "<T"
2 | 3 | 3 | Num | Modelo |  | Constante "353"
3 | 6 | 2 | Num | Página |  | Constante "02"
4 | 8 | 4 | An | Fin de identificador de modelo |  | Constante "000>"
5 | 12 | 1 | An | Indicador de página complementaria | obligatorio | blanco
6 | 13 | 34 | An | Domiciliación/Devolución - IBAN
7 | 47 | 11 | An | Devolución. SWIFT-BIC
8 | 58 | 331 | An | Reservado para la Agencia Tributaria
9 | 389 | 12 | An | Identificador de fin de registro. |  | </T35302000>
TOTAL |  | 400 | Posiciones