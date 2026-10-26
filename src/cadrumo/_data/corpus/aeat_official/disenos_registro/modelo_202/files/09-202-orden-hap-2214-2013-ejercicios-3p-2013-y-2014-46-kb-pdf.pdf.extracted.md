# Pag. 1

Página 1
Agencia Tributaria
Modelo 202 Diseño de registro. Castellano.
vers. 3.4 Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº Posic. Lon Tipo Descripción Contenido
1 1 2 An Inicio del identificador de modelo y página Constante "<T"
2 3 3 Num Modelo Constante "202"
3 6 2 Num Página Constante "01"
4 8 1 An Fin de identificador de modelo Constante ">"
5 9 1 An Reservado para la Administración En blanco
6 10 1 A Tipo de declaración Ver nota 1
7 11 9 An Identificación (1). NIF
8 20 40 An Identificación (1). Apellidos y nombre o razón social
9 60 4 Num Devengo (2). Ejercicio
10 64 2 An Devengo (2). Periodo "1P", "2P" o "3P"
11 66 8 Num Devengo (2). Fecha de inicio del período impositivo ddmmaaaa
12 74 4 Num Devengo (2). C.N.A.E. actividad principal
13 78 1 An Datos adicionales (3) - Entidad que aplica el régimen de las entidades navieras en función del tonelaje X o blanco
14 79 1 An Datos adicionales (3) - Entidades que aplican incentivos de empresa de reducida dimensión X o blanco
15 80 1 An Datos adicionales (3) - Vol. Operaciones doce meses anteriores a inicio periodo impositivo > 6.010.121,04 euros X o blanco
"0" No consta,
Datos adicionales (3) - Cooperativa fiscalmente protegida u Otras entidades con posibilidad de aplicar dos tipos impositivos (ej. "1" Cooperativa,
16 81 1 Num entidades ZEC) "2" Otras entidades
"01","10","19","25","30","35","00
",
"20/25","04/30","20/30","25/30"
y
1177 8822 55 AAnn DDaattooss aaddiicciioonnaalleess ((33)) - TTiippoo ddee ggrraavvaammeenn ddeell IImmppuueessttoo ssoobbrree SSoocciieeddaaddeess ddeell eejjeerrcciicciioo eenn ccuurrssoo ""3355//3300""
"0" No consta,
"1" (>= 10 M y < 20 M €),
"2" (>= 20 M y < 60 M €),
18 87 1 Num Datos adicionales (3) - Importe neto de la cifra de negocios "3" (>= 60 M €)
19 88 1 An Datos adicionales (3) - Entidades en las que al menos el 85% de ingresos del periodo impositivo(…) X o blanco
20 89 17 Num A) Liquidación. Mod. 45.2 TRLIS - Base del pago fraccionado [01] 15 enteros + 2 decimales
21 106 17 Num A) Liquidación. Mod. 45.2 TRLIS - Resultado de la declaración anterior (complementarias) [02] 15 enteros + 2 decimales
22 123 17 Num A) Liquidación. Mod. 45.2 TRLIS - A Ingresar [03] 15 enteros + 2 decimales
23 140 17 N B) Liquidación. Mod. 45.3 TRLIS - Resultado contable después del IS [04] 15 enteros + 2 decimales
24 157 17 Num B) Liquidación. Mod. 45.3 TRLIS - Correcciones al resultado contable - por Impuesto sobre Sociedades - Aumentos [05] 15 enteros + 2 decimales
25 174 17 Num B) Liquidación. Mod. 45.3 TRLIS - Correcciones al resultado contable - por Impuesto sobre Sociedades - Disminuciones [06] 15 enteros + 2 decimales
26 191 17 Num B) Liquidación. Mod. 45.3 TRLIS - 30% gastos amortiz (exc. emp. reducidas) - Aumentos [36] 15 enteros + 2 decimales
27 208 17 Num B) Liquidación. Mod. 45.3 TRLIS - 30% gastos amortiz (exc. emp. reducidas) - Disminuciones [37] 15 enteros + 2 decimales
28 225 17 Num B) Liquidación. Mod. 45.3 TRLIS - Resto correcciones al resultado contable, excepto comp. - Aumentos [07] 15 enteros + 2 decimales
29 242 17 Num B) Liquidación. Mod. 45.3 TRLIS - Resto correcciones al resultado contable, excepto comp. - Disminuciones [08] 15 enteros + 2 decimales
30 259 17 Num B) Liquidación. Mod. 45.3 TRLIS - TOTAL. - Aumentos [38] 15 enteros + 2 decimales
31 276 17 Num B) Liquidación. Mod. 45.3 TRLIS - TOTAL - Disminuciones [39] 15 enteros + 2 decimales
32 293 17 Num B) Liquidación. Mod. 45.3 TRLIS - 25% del importe de los dividendos y rentas devengadas de fuente extranjera [09] 15 enteros + 2 decimales
33 310 17 N B) Liquidación. Mod. 45.3 TRLIS - Base imponible previa [13] 15 enteros + 2 decimales
34 327 17 Num B) Liquidación. Mod. 45.3 TRLIS - Compensación de bases negativas de ejercicios anteriores [14] 15 enteros + 2 decimales
35 344 17 Num B) Liquidación. Mod. 45.3 TRLIS - B1 - Caso general (porcentaje único) - Base pago fraccionado [16] 15 enteros + 2 decimales
36 361 5 Num B) Liquidación. Mod. 45.3 TRLIS - B1 - Caso general (porcentaje único) - Porcentaje [17] 3 enteros + 2 decimales
B) Liquidación. Mod. 45.3 TRLIS - B1 - Caso general. Compensación de cuotas negativas ejer. anteriores
37 366 17 Num (sólo cooperativas) [40] 15 enteros + 2 decimales
Página 1 de 3

# Pag. 2

Página 2
Nº Posic. Lon Tipo Descripción Contenido
38 383 17 Num B) Liquidación. Mod. 45.3 TRLIS - B1 - Caso general (porcentaje único) - Resultado previo (clave ([16] x [17]) - [40]) [18] 15 enteros + 2 decimales
39 400 17 Num B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos (más de un porcentaje) - Base del pago fraccionado [19] 15 enteros + 2 decimales
40 417 17 N B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 1 [20] 15 enteros + 2 decimales
41 434 5 Num B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos (más de un porcentaje) - Porcentaje [21] 3 enteros + 2 decimales
42 439 17 N B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos (más de un porcentaje) - Importe pago fraccionado [22] 15 enteros + 2 decimales
43 456 17 N B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 2 [23] 15 enteros + 2 decimales
44 473 5 Num B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos (más de un porcentaje) - Porcentaje [24] 3 enteros + 2 decimales
45 478 17 N B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos (más de un porcentaje) - Importe pago fraccionado [25] 15 enteros + 2 decimales
B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos. Compensación de cuotas negativas ejer. anteriores
46 495 17 Num (sólo cooperativas) [42] 15 enteros + 2 decimales
47 512 17 Num B) Liquidación. Mod. 45.3 TRLIS - B2 - Casos específicos (más de un porcentaje)-Resultado previo(claves [22]+[25]-[42]) [26] 15 enteros + 2 decimales
48 529 17 Num B) Liquidación. Mod. 45.3 TRLIS - Bonificaciones[27] 15 enteros + 2 decimales
49 546 17 Num B) Liquidación. Mod. 45.3 TRLIS - Retenciones e ingresos a cuenta practicados sobre ingresos periodo computado [28] 15 enteros + 2 decimales
50 563 5 Num B) Liquidación. Mod. 45.3 TRLIS - Volumen operaciones en Territorio Común (%) [29] 3 enteros + 2 decimales
51 568 17 Num B) Liquidación. Mod. 45.3 TRLIS - Pagos fraccionados de periodos anteriores en Territorio Común [30] 15 enteros + 2 decimales
52 585 17 Num B) Liquidación. Mod. 45.3 TRLIS - Resultado de la declaración anterior (exclusivamente si ésta es complementaria) [31] 15 enteros + 2 decimales
53 602 17 Num B) Liquidación. Mod. 45.3 TRLIS - Resultado [32] 15 enteros + 2 decimales
54 619 17 Num B) Liquidación. Mod. 45.3 TRLIS - Mínimo a ingresar (sólo para empresas con CN igual o superior a 20 millones euros) [33] 15 enteros + 2 decimales
55 636 17 Num B) Liquidación. Mod. 45.3 TRLIS - Cantidad a ingresar (mayor de claves [32] y [33] ) [34] 15 enteros + 2 decimales
56 653 39 An Reservado para la Administración En blanco
57 692 9 An Indicador de fin de registro Constante "</T20201>"
TOTAL 700 POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 202.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
55. LLooss ccaammppooss nnuumméérriiccooss ccoonn ssiiggnnoo ((NN)) aaddmmiitteenn nnúúmmeerrooss mmááss eell ccaarráácctteerr NN . LLooss ddaattooss nnuumméérriiccooss ddeebbeerráánn eessttaarr aalliinneeaaddooss aa llaa ddeerreecchhaa rreelllleennaannddoo ccoonn cceerrooss ppoorr llaa iizzqquuiieerrddaa.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Página 2 de 3

# Pag. 3

Página 3
Agencia Tributaria
Modelo 202 Diseño de registro. Castellano.
vers. 3.3 Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº Posic. Lon Tipo Descripción Contenido
1 1 2 An Inicio del identificador de modelo y página Constante "<T"
2 3 3 Num Modelo Constante "202"
3 6 2 Num Página Constante "02"
4 8 1 An Fin de identificador de modelo Constante ">"
5 9 1 An Reservado para la Administración En blanco
6 10 1 An Información adicional (5). Comunicación de datos adicionales a la declaración X o blanco
7 11 22 An Información adicional (5). Numero de Referencia de Sociedades (NRS)
8 33 1 An Declaración complementaria (6) X o blanco
9 34 13 An Declaración complementaria (6). Número de justificante de la declaración anterior
10 47 1 An Negativa (7). Declaración negativa X o blanco
"0" No consta,
"1" ó "2" En efectivo/Adeudo en
cuenta,
11 48 1 Num Ingreso (8). Forma de pago "3" Domiciliación
12 49 34 An Domiciliación - IBAN nota 7
13 83 22 An Reservado para la Administración. Número de Referencia Completo (N.R.C.)
14 105 16 An Reservado para la Administración
15 121 100 An Nombre y apellidos de la persona de contacto
16 221 9 An Teléfono fijo de contacto
17 230 9 An Teléfono móvil de contacto
18 239 50 An Dirección de correo electrónico
19 289 13 An Reservado para el sello electrónico de la AEAT En blanco
2200 330022 339900 AAnn RReesseerrvvaaddoo ppaarraa llaa AAddmmiinniissttrraacciióónn EEnn bbllaannccoo
21 692 9 An Indicador de fin de registro Constante "</T20202>"
TOTAL 700 POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 202.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
7. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
Página 3 de 3