# M15100

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "151"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA) |  | 2023
5 | 11 | 2 | An | Período. (PP) |  | 0A
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T1510+Ejercicio+periodo+0000> |  | "</T151020230A0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# M15101000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N | Modelo | Constante "151"
3 | 6 | 2 | An | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An | Contribuyente. NIF [02]
8 | 23 | 80 | An | Contribuyente. Apellidos y nombre [03]
9 | 103 | 4 | An | Devengo. Ejercicio [01]
10 | 107 | 2 | An | Devengo - Periodo | 0A
11 | 109 | 1 | An | Contribuyente. Sexo [04] | "H" o "M"
12 | 110 | 8 | Num | Contribuyente. Fecha de nacimiento [05] | Formato: "dd/MM/yyyy"
13 | 118 | 1 | An | Contribuyente. Condicion. Contribuyente principal [06] | X ó blanco
14 | 119 | 1 | An | Contribuyente. Condicion. Contribuyente asociado a otro principal [07] | X ó blanco
15 | 120 | 1 | An | Contribuyente. Tipo de vinculación. Cónyuge [08] | X ó blanco
16 | 121 | 1 | An | Contribuyente. Tipo de vinculación. Progenitor sin vínculo matrimonial [09] | X ó blanco
17 | 122 | 1 | An | Contribuyente. Tipo de vinculación. Hijo/a [10] | X ó blanco
18 | 123 | 9 | An | Contribuyente. Datos del contribuyente principal. NIF [11]
19 | 132 | 80 | An | Contribuyente. Datos del contribuyente principal. Apellidos y nombre [12]
20 | 212 | 1 | An | Contribuyente. Cambio de domicilio [13] | X ó blanco
21 | 213 | 5 | An | Contribuyente. Tipo de vía [26]
22 | 218 | 50 | An | Contribuyente. Nombre de la vía pública [27]
23 | 268 | 3 | An | Contribuyente. Tipo de numeración [28]
24 | 271 | 5 | Num | Contribuyente. Número de casa [29]
25 | 276 | 3 | An | Contribuyente. Calificador de número [30]
26 | 279 | 3 | An | Contribuyente. Bloque [31]
27 | 282 | 3 | An | Contribuyente. Portal [32]
28 | 285 | 3 | An | Contribuyente. Escalera [33]
29 | 288 | 3 | An | Contribuyente. Planta [34]
30 | 291 | 3 | An | Contribuyente. Puerta [35]
31 | 294 | 40 | An | Contribuyente. Datos complementarios del domicilio [36]
32 | 334 | 30 | An | Contribuyente. Localidad/Poblacion [37]
33 | 364 | 5 | Num | Contribuyente. Código postal del domicilio [38]
34 | 369 | 2 | Num | Contribuyente. Codigo de Provincia [40]
35 | 371 | 5 | Num | Contribuyente. Nombre del Municipio [39]
36 | 376 | 9 | An | Contribuyente. Teléfono fijo [41]
37 | 385 | 9 | An | Contribuyente. Teléfono móvil [42]
 |  |  | An | Contribuyente. 61 - Nº de Fax.
38 | 394 | 50 | An | Contribuyente Domicilio Extranjero. Domicilio [43]
39 | 444 | 40 | An | Contribuyente Domicilio Extranjero. Datos complementarios domicilio [44]
40 | 484 | 30 | An | Contribuyente Domicilio Extranjero. Poblacion/Ciudad [45]
41 | 514 | 100 | An | Contribuyente Domicilio Extranjero. Email [46]
42 | 614 | 10 | An | Contribuyente Domicilio Extranjero. Codigo postal/ZIP  [47]
43 | 624 | 30 | An | Contribuyente Domicilio Extranjero. Provincia/Region/Estado [48]
44 | 654 | 2 | An | Contribuyente Domicilio Extranjero. Pais [50]
45 | 656 | 15 | An | Contribuyente Domicilio Extranjero. Teléfono Fijo [51]
46 | 671 | 15 | An | Contribuyente Domicilio Extranjero. Teléfono Móvil [52]
 |  |  | An | Contribuyente Domicilio Extranjero. 72 - Nº Fax
47 | 686 | 1 | Num | Contribuyente Datos Adicionales vivienda actual. Titularidad [14] | 1,2,3,4
48 | 687 | 5 | Num | Contribuyente Datos Adicionales vivienda actual. Porcentaje participación [15] | [3 enteros + 2 decmales]
49 | 692 | 1 | Num | Contribuyente Datos Adicionales vivienda actual. Situacion [16] | 1,2,3
50 | 693 | 20 | An | Contribuyente Datos Adicionales vivienda actual. Referencia catastral [17]
51 | 713 | 9 | An | Representante. NIF [18]
52 | 722 | 80 | An | Representante. Apellidos y nombre o razón social o denominación [19]
53 | 802 | 5 | An | Representante. Tipo de vía [26]
54 | 807 | 50 | An | Representante. Nombre de la vía pública [27]
55 | 857 | 3 | An | Representante. Tipo de numeración [28]
56 | 860 | 5 | Num | Representante. Número de casa [29]
57 | 865 | 3 | An | Representante. Calificador de número [30]
58 | 868 | 3 | An | Representante. Bloque [31]
59 | 871 | 3 | An | Representante. Portal [32]
60 | 874 | 3 | An | Representante. Escalera [33]
61 | 877 | 3 | An | Representante. Planta [34]
62 | 880 | 3 | An | Representante. Puerta [35]
63 | 883 | 40 | An | Representante. Datos complementarios del domicilio [36]
64 | 923 | 30 | An | Representante. Localidad/Poblacion (si es distinta del municipio) [37]
65 | 953 | 5 | Num | Representante. Código postal del domicilio [38]
66 | 958 | 2 | Num | Representante. Nombre del Municipio [39]
67 | 960 | 5 | Num | Representante. Codigo de Provincia [40]
68 | 965 | 9 | An | Representante. Teléfono fijo [41]
69 | 974 | 9 | An | Representante. Teléfono móvil [42]
 |  |  | An | Representante. 61 - Nº de Fax.
70 | 983 | 2 | Num | Comunidad Autonoma de residencia durante el ejercicio indicado [20]
71 | 985 | 1 | An | Asignacion Tributaria a la Iglesia Catolica [21] | X ó blanco
72 | 986 | 1 | An | Asignacion de cantidades a fines sociales [22] | X ó blanco
73 | 987 | 1 | An | Declaracion Complementaria [23] | X ó blanco
74 | 988 | 1 | An | Declaracion Complementaria 2 [24] | X ó blanco
75 | 989 | 13 | An | Número de Justificante [25]
76 | 1002 | 137 | An | Reservado AEAT | En blanco
77 | 1139 | 12 | An | Indicador de fin de registro | Constante "</T15101000>"
 | TOTAL | 1150 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES

# M15102000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "02"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 1 | An |  | Naturaleza [02]
8 | 16 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
9 | 33 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
10 | 50 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
11 | 67 | 17 | Num |  | Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
12 | 84 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
13 | 101 | 9 | An |  | Pagador. NIF [50]
14 | 110 | 1 | An |  | Pagador. F/J [51] | "F", "J"
15 | 111 | 80 | An |  | Pagador. Apellidos y nombre o razón social [52]
16 | 191 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Rendimiento íntegro obtenido y gravado en el extranjero [08]
17 | 208 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Impuesto satisfecho en el extranjero [09]
18 | 225 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Propiedad (%) [10] | [3 enteros + 2 decimales]
19 | 230 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Usufructo (%) [11] | [3 enteros + 2 decimales]
20 | 235 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Origen [12]
21 | 236 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Situación [13] | 1,2,3
22 | 237 | 20 | An |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Referencia catastral [14]
23 | 257 | 2 | Num |  | Tipo de Renta [01]
24 | 259 | 1 | An |  | Naturaleza [02]
25 | 260 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
26 | 277 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
27 | 294 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
28 | 311 | 17 | Num |  | Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
29 | 328 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
30 | 345 | 9 | An |  | Pagador. NIF [50]
31 | 354 | 1 | An |  | Pagador. F/J [51] | "F", "J"
32 | 355 | 80 | An |  | Pagador. Apellidos y nombre o razón social [52]
33 | 435 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Rendimiento íntegro obtenido y gravado en el extranjero [08]
34 | 452 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Impuesto satisfecho en el extranjero [09]
35 | 469 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Propiedad (%) [10] | [3 enteros + 2 decimales]
36 | 474 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Usufructo (%) [11] | [3 enteros + 2 decimales]
37 | 479 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Origen [12]
38 | 480 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Situación [13] | 1,2,3
39 | 481 | 20 | An |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Referencia catastral [14]
40 | 501 | 2 | Num |  | Tipo de Renta [01]
41 | 503 | 1 | An |  | Naturaleza [02]
42 | 504 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
43 | 521 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
44 | 538 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
45 | 555 | 17 | Num |  | Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
46 | 572 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
47 | 589 | 9 | An |  | Pagador. NIF [50]
48 | 598 | 1 | An |  | Pagador. F/J [51] | "F", "J"
49 | 599 | 80 | An |  | Pagador. Apellidos y nombre o razón social [52]
50 | 679 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Rendimiento íntegro obtenido y gravado en el extranjero [08]
51 | 696 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Impuesto satisfecho en el extranjero [09]
52 | 713 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Propiedad (%) [10] | [3 enteros + 2 decimales]
53 | 718 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Usufructo (%) [11] | [3 enteros + 2 decimales]
54 | 723 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Origen [12]
55 | 724 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Situación [13] | 1,2,3
56 | 725 | 20 | An |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Referencia catastral [14]
57 | 745 | 2 | Num |  | Tipo de Renta [01]
58 | 747 | 1 | An |  | Naturaleza [02]
59 | 748 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
60 | 765 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
61 | 782 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
62 | 799 | 17 | Num |  | Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
63 | 816 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
64 | 833 | 9 | An |  | Pagador. NIF [50]
65 | 842 | 1 | An |  | Pagador. F/J [51] | "F", "J"
66 | 843 | 80 | An |  | Pagador. Apellidos y nombre o razón social [52]
67 | 923 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Rendimiento íntegro obtenido y gravado en el extranjero [08]
68 | 940 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Impuesto satisfecho en el extranjero [09]
69 | 957 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Propiedad (%) [10] | [3 enteros + 2 decimales]
70 | 962 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Usufructo (%) [11] | [3 enteros + 2 decimales]
71 | 967 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Origen [12]
72 | 968 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Situación [13] | 1,2,3
73 | 969 | 20 | An |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Referencia catastral [14]
74 | 989 | 100 | An |  | Reservado AEAT | En blanco
75 | 1089 | 12 | An |  | Indicador de fin de registro | Constante "</T15102000>"
 | TOTAL | 1100 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  |  | POSICIONES

# M15103000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "03"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 1 | An |  | Naturaleza [02]
8 | 16 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
9 | 33 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
10 | 50 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
11 | 67 | 17 | Num |  | Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
12 | 84 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
13 | 101 | 9 | An |  | Pagador. NIF [50]
14 | 110 | 1 | An |  | Pagador. F/J [51] | "F", "J"
15 | 111 | 80 | An |  | Pagador. Apellidos y nombre o razón social [52]
16 | 191 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Rendimiento íntegro obtenido y gravado en el extranjero [08]
17 | 208 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Impuesto satisfecho en el extranjero [09]
18 | 225 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Propiedad (%) [10] | [3 enteros + 2 decimales]
19 | 230 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Usufructo (%) [11] | [3 enteros + 2 decimales]
20 | 235 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Origen [12]
21 | 236 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Situación [13] | 1,2,3
22 | 237 | 20 | An |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Referencia catastral [14]
23 | 257 | 2 | Num |  | Tipo de Renta [01]
24 | 259 | 1 | An |  | Naturaleza [02]
25 | 260 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
26 | 277 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
27 | 294 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
28 | 311 | 17 | Num |  | Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
29 | 328 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
30 | 345 | 9 | An |  | Pagador. NIF [50]
31 | 354 | 1 | An |  | Pagador. F/J [51] | "F", "J"
32 | 355 | 80 | An |  | Pagador. Apellidos y nombre o razón social [52]
33 | 435 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Rendimiento íntegro obtenido y gravado en el extranjero [08]
34 | 452 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Impuesto satisfecho en el extranjero [09]
35 | 469 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Propiedad (%) [10] | [3 enteros + 2 decimales]
36 | 474 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Usufructo (%) [11] | [3 enteros + 2 decimales]
37 | 479 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Origen [12]
38 | 480 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Situación [13] | 1,2,3
39 | 481 | 20 | An |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Referencia catastral [14]
40 | 501 | 2 | Num |  | Tipo de Renta [01]
41 | 503 | 1 | An |  | Naturaleza [02]
42 | 504 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
43 | 521 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
44 | 538 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
45 | 555 | 17 | Num |  | Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
46 | 572 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
47 | 589 | 9 | An |  | Pagador. NIF [50]
48 | 598 | 1 | An |  | Pagador. F/J [51] | "F", "J"
49 | 599 | 80 | An |  | Pagador. Apellidos y nombre o razón social [52]
50 | 679 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Rendimiento íntegro obtenido y gravado en el extranjero [08]
51 | 696 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Impuesto satisfecho en el extranjero [09]
52 | 713 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Propiedad (%) [10] | [3 enteros + 2 decimales]
53 | 718 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Usufructo (%) [11] | [3 enteros + 2 decimales]
54 | 723 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Origen [12]
55 | 724 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Situación [13] | 1,2,3
56 | 725 | 20 | An |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Referencia catastral [14]
57 | 745 | 2 | Num |  | Tipo de Renta [01]
58 | 747 | 1 | An |  | Naturaleza [02]
59 | 748 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
60 | 765 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
61 | 782 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
62 | 799 | 17 | Num |  | Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
63 | 816 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
64 | 833 | 9 | An |  | Pagador. NIF [50]
65 | 842 | 1 | An |  | Pagador. F/J [51] | "F", "J"
66 | 843 | 80 | An |  | Pagador. Apellidos y nombre o razón social [52]
67 | 923 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Rendimiento íntegro obtenido y gravado en el extranjero [08]
68 | 940 | 17 | Num |  | Datos Adicionales Rendimiento Trabajo. Impuesto satisfecho en el extranjero [09]
69 | 957 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Propiedad (%) [10] | [3 enteros + 2 decimales]
70 | 962 | 5 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Usufructo (%) [11] | [3 enteros + 2 decimales]
71 | 967 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Origen [12]
72 | 968 | 1 | Num |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Situación [13] | 1,2,3
73 | 969 | 20 | An |  | Datos Adicionales de las rentas derivadas de bienes e inmuebles. Referencia catastral [14]
72 | 989 | 17 | Num |  | RESTO. Rendimiento integro/Renta inmobiliaria imputada [06] | [15 enteros + 2 decimales]
73 | 1006 | 17 | Num |  | RESTO. Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
74 | 1023 | 17 | Num |  | Total rendimientos íntegros/Renta inmobiliaria imputada [15] | [15 enteros + 2 decimales]
75 | 1040 | 17 | Num |  | Total retenciones o ingresos a cuenta [16] | [15 enteros + 2 decimales]
76 | 1057 | 82 | An |  | Reservado AEAT | En blanco
77 | 1139 | 12 | An |  | Indicador de fin de registro | Constante "</T15103000>"
 | TOTAL | 1150 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  |  | POSICIONES

# M15104000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "04"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 1 | An |  | Naturaleza [02]
8 | 16 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
9 | 33 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
10 | 50 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
11 | 67 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
12 | 84 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
13 | 101 | 2 | Num |  | Tipo de Renta [01]
14 | 103 | 1 | An |  | Naturaleza [02]
15 | 104 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
16 | 121 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
17 | 138 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
18 | 155 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
19 | 172 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
20 | 189 | 2 | Num |  | Tipo de Renta [01]
21 | 191 | 1 | An |  | Naturaleza [02]
22 | 192 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
23 | 209 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
24 | 226 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
25 | 243 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
26 | 260 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
27 | 277 | 2 | Num |  | Tipo de Renta [01]
28 | 279 | 1 | An |  | Naturaleza [02]
29 | 280 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
30 | 297 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
31 | 314 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
32 | 331 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
33 | 348 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
34 | 365 | 2 | Num |  | Tipo de Renta [01]
35 | 367 | 1 | An |  | Naturaleza [02]
36 | 368 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
37 | 385 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
38 | 402 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
39 | 419 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
40 | 436 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
41 | 453 | 2 | Num |  | Tipo de Renta [01]
42 | 455 | 1 | An |  | Naturaleza [02]
43 | 456 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
44 | 473 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
45 | 490 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
46 | 507 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
47 | 524 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
48 | 541 | 2 | Num |  | Tipo de Renta [01]
49 | 543 | 1 | An |  | Naturaleza [02]
50 | 544 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
51 | 561 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
52 | 578 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
53 | 595 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
54 | 612 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
55 | 629 | 2 | Num |  | Tipo de Renta [01]
56 | 631 | 1 | An |  | Naturaleza [02]
57 | 632 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
58 | 649 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
59 | 666 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
60 | 683 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
61 | 700 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
62 | 717 | 2 | Num |  | Tipo de Renta [01]
63 | 719 | 1 | An |  | Naturaleza [02]
64 | 720 | 17 | Num |  | Valoración [03] | [15 enteros + 2 decimales]
65 | 737 | 17 | Num |  | Ingresos a cuenta [04] | [15 enteros + 2 decimales]
66 | 754 | 17 | Num |  | Ingresos a cuenta repercutidos [05] | [15 enteros + 2 decimales]
67 | 771 | 17 | Num |  | Rendimiento integro [06] | [15 enteros + 2 decimales]
68 | 788 | 17 | Num |  | Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
69 | 805 | 17 | Num |  | RESTO. Rendimientos íntegro [06] | [15 enteros + 2 decimales]
70 | 822 | 17 | Num |  | RESTO. Rentención o ingreso a cuenta [07] | [15 enteros + 2 decimales]
23 | 839 | 17 | Num |  | Total rendimientos íntegros [08] | [15 enteros + 2 decimales]
23 | 856 | 17 | Num |  | Total retenciones o ingresos a cuenta [09] | [15 enteros + 2 decimales]
23 | 873 | 116 | An |  | Reservado AEAT | En blanco
23 | 989 | 12 | An |  | Indicador de fin de registro | Constante "</T15104000>"
 | TOTAL | 1000 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  |  | POSICIONES

# M15105000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "05"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
8 | 32 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
9 | 49 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
10 | 66 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
11 | 83 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
12 | 100 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
13 | 117 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
14 | 118 | 3 | An |  | Reservado para la Administración | En blanco
15 | 121 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
16 | 125 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
17 | 142 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
18 | 159 | 2 | Num |  | Tipo de Renta [01]
19 | 161 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
20 | 178 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
21 | 195 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
22 | 212 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
23 | 229 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
24 | 246 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
25 | 263 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
26 | 264 | 3 | An |  | Reservado para la Administración | En blanco
27 | 267 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
28 | 271 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
29 | 288 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
30 | 305 | 2 | Num |  | Tipo de Renta [01]
31 | 307 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
32 | 324 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
33 | 341 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
34 | 358 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
35 | 375 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
36 | 392 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
37 | 409 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
38 | 410 | 3 | An |  | Reservado para la Administración | En blanco
39 | 413 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
40 | 417 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
41 | 434 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
42 | 451 | 2 | Num |  | Tipo de Renta [01]
43 | 453 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
44 | 470 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
45 | 487 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
46 | 504 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
47 | 521 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
48 | 538 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
49 | 555 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
50 | 556 | 3 | An |  | Reservado para la Administración | En blanco
51 | 559 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
52 | 563 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
53 | 580 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
54 | 597 | 2 | Num |  | Tipo de Renta [01]
55 | 599 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
56 | 616 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
57 | 633 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
58 | 650 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
59 | 667 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
60 | 684 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
61 | 701 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
62 | 702 | 3 | An |  | Reservado para la Administración | En blanco
63 | 705 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
64 | 709 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
65 | 726 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
66 | 743 | 46 | An |  | Reservado AEAT | En blanco
67 | 789 | 12 | An |  | Indicador de fin de registro | Constante "</T15105000>"
 | TOTAL | 800 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 1:
Valores posibles:
 | 1-actividad emprendedora
 | 2-profesional altamente cualificado que preste servicios a empresas emergentes
 | 3-actividades de formación, investigación, desarrollo e innovación
 | 4-otras actividades sin establecimiento permanente no incluidas en los apartados anteriores
 | TOTAL: | -1 |  |  | POSICIONES

# M15106000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "06"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
8 | 32 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
9 | 49 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
10 | 66 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
11 | 83 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
12 | 100 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
13 | 117 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
14 | 118 | 3 | An |  | Reservado para la Administración | En blanco
15 | 121 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
16 | 125 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
17 | 142 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
18 | 159 | 2 | Num |  | Tipo de Renta [01]
19 | 161 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
20 | 178 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
21 | 195 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
22 | 212 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
23 | 229 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
24 | 246 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
25 | 263 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
26 | 264 | 3 | An |  | Reservado para la Administración | En blanco
27 | 267 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
28 | 271 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
29 | 288 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
30 | 305 | 2 | Num |  | Tipo de Renta [01]
31 | 307 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
32 | 324 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
33 | 341 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
34 | 358 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
35 | 375 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
36 | 392 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
37 | 409 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
38 | 410 | 3 | An |  | Reservado para la Administración | En blanco
39 | 413 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
40 | 417 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
41 | 434 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
42 | 451 | 2 | Num |  | Tipo de Renta [01]
43 | 453 | 17 | Num |  | Ingresos íntegros [02] | [15 enteros + 2 decimales]
44 | 470 | 17 | Num |  | Gastos de personal [03] | [15 enteros + 2 decimales]
45 | 487 | 17 | Num |  | Gastos de aprovisionamiento de materiales y de suministros [04] | [15 enteros + 2 decimales]
46 | 504 | 17 | Num |  | Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
47 | 521 | 17 | N |  | Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
48 | 538 | 17 | Num |  | Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
49 | 555 | 1 | An |  | Actividad: Código y tipo de actividad [10] | Nota 1
50 | 556 | 3 | An |  | Reservado para la Administración | En blanco
51 | 559 | 4 | An |  | Actividad: Grupo o epígrafe IAE [11]
52 | 563 | 17 | Num |  | Datos adicionales (actividad emprendedora. Rendimiento íntegro obtenido y gravado en el extranjero [12] | [15 enteros + 2 decimales]
53 | 580 | 17 | Num |  | Datos adicionales (actividad emprendedora. Impuesto satisfecho en el extranjero [13] | [15 enteros + 2 decimales]
54 | 597 | 17 | Num |  | RESTO. Rendimiento neto: positivo [05] | [15 enteros + 2 decimales]
55 | 614 | 17 | N |  | RESTO. Rendimiento neto: negativo [07] | [15 enteros + 2 decimales]
56 | 631 | 17 | Num |  | RESTO. Rentención o ingreso a cuenta [06] | [15 enteros + 2 decimales]
57 | 648 | 17 | Num |  | Total rendimientos netos positivos [08] | [15 enteros + 2 decimales]
58 | 665 | 17 | Num |  | Total retenciones o ingresos a cuenta [09] | [15 enteros + 2 decimales]
59 | 682 | 107 | An |  | Reservado AEAT | En blanco
60 | 789 | 12 | An |  | Indicador de fin de registro | Constante "</T15106000>"
 | TOTAL | 800 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 1:
Valores posibles:
 | 1-actividad emprendedora
 | 2-profesional altamente cualificado que preste servicios a empresas emergentes
 | 3-actividades de formación, investigación, desarrollo e innovación
 | 4-otras actividades sin establecimiento permanente no incluidas en los apartados anteriores
 | TOTAL: | -1 |  |  | POSICIONES

# M15107000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "07"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 9 | An |  | NIF de la sociedad o fondo de inversión [53]
8 | 24 | 17 | Num |  | Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
9 | 41 | 17 | Num |  | Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
10 | 58 | 2 | Num |  | Tipo de Renta [01]
11 | 60 | 9 | An |  | NIF de la sociedad o fondo de inversión [53]
12 | 69 | 17 | Num |  | Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
13 | 86 | 17 | Num |  | Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
14 | 103 | 2 | Num |  | Tipo de Renta [01]
15 | 105 | 9 | An |  | NIF de la sociedad o fondo de inversión [53]
16 | 114 | 17 | Num |  | Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
17 | 131 | 17 | Num |  | Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
18 | 148 | 2 | Num |  | Tipo de Renta [01]
19 | 150 | 9 | An |  | NIF de la sociedad o fondo de inversión [53]
20 | 159 | 17 | Num |  | Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
21 | 176 | 17 | Num |  | Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
22 | 193 | 2 | Num |  | Tipo de Renta [01]
23 | 195 | 9 | An |  | NIF de la sociedad o fondo de inversión [53]
24 | 204 | 17 | Num |  | Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
25 | 221 | 17 | Num |  | Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
26 | 238 | 2 | Num |  | Tipo de Renta [01]
27 | 240 | 9 | An |  | NIF de la sociedad o fondo de inversión [53]
28 | 249 | 17 | Num |  | Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
29 | 266 | 17 | Num |  | Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
30 | 283 | 2 | Num |  | Tipo de Renta [01]
31 | 285 | 9 | An |  | NIF de la sociedad o fondo de inversión [53]
32 | 294 | 17 | Num |  | Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
33 | 311 | 17 | Num |  | Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
34 | 328 | 2 | Num |  | Tipo de Renta [01]
35 | 330 | 9 | An |  | NIF de la sociedad o fondo de inversión [53]
36 | 339 | 17 | Num |  | Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
37 | 356 | 17 | Num |  | Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
38 | 373 | 17 | Num |  | RESTO. Ganancia Patrimonial [02] | [15 enteros + 2 decimales]
39 | 390 | 17 | Num |  | RESTO. Rentención o ingreso a cuenta [03] | [15 enteros + 2 decimales]
40 | 407 | 17 | Num |  | Total ganancias patrimoniales [04] | [15 enteros + 2 decimales]
41 | 424 | 17 | Num |  | Total retenciones o ingresos a cuenta [05] | [15 enteros + 2 decimales]
25 | 441 | 48 | An |  | Reservado AEAT | En blanco
26 | 489 | 12 | An |  | Indicador de fin de registro | Constante "</T15107000>"
 | TOTAL | 500 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  |  | POSICIONES

# M15108000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "08"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 13 | An |  | Número Justificante del modelo 211 [54]
8 | 28 | 17 | Num |  | Valor de transmisión (Adquisición) [02] | [15 enteros + 2 decimales]
9 | 45 | 17 | Num |  | Valor de adquisición (Adquisición) [03] | [15 enteros + 2 decimales]
10 | 62 | 17 | N |  | Diferencia (Adquisición) [04] | [15 enteros + 2 decimales]
11 | 79 | 17 | N |  | Ganancia o pérdida (Adquisición) [05] | [15 enteros + 2 decimales]
12 | 96 | 17 | Num |  | Valor de transmisión (Mejora o 2ª adquisición) [06] | [15 enteros + 2 decimales]
13 | 113 | 17 | Num |  | Valor de Mejora o 2ª adquisición (Mejora o 2ª adquisición) [07] | [15 enteros + 2 decimales]
14 | 130 | 17 | N |  | Diferencia (Mejora o 2ª adquisición) [08] | [15 enteros + 2 decimales]
15 | 147 | 17 | N |  | Ganancia o pérdida (Mejora o 2ª adquisición) [09] | [15 enteros + 2 decimales]
16 | 164 | 17 | Num |  | Ganancia Patrimonial total obtenida [10] | [15 enteros + 2 decimales]
17 | 181 | 17 | Num |  | Retención o ingreso a cuenta [11] | [15 enteros + 2 decimales]
18 | 198 | 8 | Num |  | Fecha de adquisición [55]
19 | 206 | 8 | Num |  | Fecha de mejora o 2ª adquisición [56]
20 | 214 | 8 | Num |  | Fecha de transmisión [57]
21 | 222 | 5 | Num |  | Cuota de participación [58] | [3 enteros + 2 decimales]
22 | 227 | 9 | An |  | Adquiriente. NIF [59]
23 | 236 | 1 | An |  | Adquiriente. F/J [60] | "F", "J"
24 | 237 | 80 | An |  | Adquiriente. Apellidos y nombre o razón social [61]
25 | 317 | 5 | An |  | Tipo de vía [26]
26 | 322 | 50 | An |  | Nombre de la vía pública [27]
27 | 372 | 3 | An |  | Tipo de numeración [28]
28 | 375 | 5 | Num |  | Número de casa [29]
29 | 380 | 3 | An |  | Calificador de número [30]
30 | 383 | 3 | An |  | Bloque [31]
31 | 386 | 3 | An |  | Portal [32]
32 | 389 | 3 | An |  | Escalera [33]
33 | 392 | 3 | An |  | Planta [34]
34 | 395 | 3 | An |  | Puerta [35]
35 | 398 | 40 | An |  | Datos complementarios de domicilio [36]
36 | 438 | 30 | An |  | Localidad/Población [37]
37 | 468 | 5 | Num |  | Código postal [38]
38 | 473 | 2 | Num |  | Provincia [39]
39 | 475 | 5 | Num |  | Municipio [40]
40 | 480 | 20 | An |  | Referencia Catastral [53]
41 | 500 | 1 | Num |  | Documento publico o privado [62] [63] | 0,1,2
42 | 501 | 100 | An |  | Notario o fedetario [64]
43 | 601 | 20 | An |  | Número de protocolo [65]
44 | 621 | 2 | Num |  | Tipo de Renta [01]
45 | 623 | 13 | An |  | Número Justificante del modelo 211 [54]
46 | 636 | 17 | Num |  | Valor de transmisión (Adquisición) [02] | [15 enteros + 2 decimales]
47 | 653 | 17 | Num |  | Valor de adquisición (Adquisición) [03] | [15 enteros + 2 decimales]
48 | 670 | 17 | N |  | Diferencia (Adquisición) [04] | [15 enteros + 2 decimales]
49 | 687 | 17 | N |  | Ganancia o pérdida (Adquisición) [05] | [15 enteros + 2 decimales]
50 | 704 | 17 | Num |  | Valor de transmisión (Mejora o 2ª adquisición) [06] | [15 enteros + 2 decimales]
51 | 721 | 17 | Num |  | Valor de Mejora o 2ª adquisición (Mejora o 2ª adquisición) [07] | [15 enteros + 2 decimales]
52 | 738 | 17 | N |  | Diferencia (Mejora o 2ª adquisición) [08] | [15 enteros + 2 decimales]
53 | 755 | 17 | N |  | Ganancia o pérdida (Mejora o 2ª adquisición) [09] | [15 enteros + 2 decimales]
54 | 772 | 17 | Num |  | Ganancia Patrimonial total obtenida [10] | [15 enteros + 2 decimales]
55 | 789 | 17 | Num |  | Retención o ingreso a cuenta [11] | [15 enteros + 2 decimales]
56 | 806 | 8 | Num |  | Fecha de adquisición [55]
57 | 814 | 8 | Num |  | Fecha de mejora o 2ª adquisición [56]
58 | 822 | 8 | Num |  | Fecha de transmisión [57]
59 | 830 | 5 | Num |  | Cuota de participación [58] | [3 enteros + 2 decimales]
60 | 835 | 9 | An |  | Adquiriente. NIF [59]
61 | 844 | 1 | An |  | Adquiriente. F/J [60] | "F", "J"
62 | 845 | 80 | An |  | Adquiriente. Apellidos y nombre o razón social [61]
63 | 925 | 5 | An |  | Tipo de vía [26]
64 | 930 | 50 | An |  | Nombre de la vía pública [27]
65 | 980 | 3 | An |  | Tipo de numeración [28]
66 | 983 | 5 | Num |  | Número de casa [29]
67 | 988 | 3 | An |  | Calificador de número [30]
68 | 991 | 3 | An |  | Bloque [31]
69 | 994 | 3 | An |  | Portal [32]
70 | 997 | 3 | An |  | Escalera [33]
71 | 1000 | 3 | An |  | Planta [34]
72 | 1003 | 3 | An |  | Puerta [35]
73 | 1006 | 40 | An |  | Datos complementarios de domicilio [36]
74 | 1046 | 30 | An |  | Localidad/Población [37]
75 | 1076 | 5 | Num |  | Código postal [38]
76 | 1081 | 2 | Num |  | Provincia [39]
77 | 1083 | 5 | Num |  | Municipio [40]
78 | 1088 | 20 | An |  | Referencia Catastral [53]
79 | 1108 | 1 | Num |  | Documento publico o privado [62] [63] | 0,1,2
80 | 1109 | 100 | An |  | Notario o fedetario [64]
81 | 1209 | 20 | An |  | Número de protocolo [65]
82 | 1229 | 17 | Num |  | RESTO. Ganancia Patrimonial total obtenida [10] | [15 enteros + 2 decimales]
83 | 1246 | 17 | Num |  | RESTO. Retención o ingreso a cuenta [11] | [15 enteros + 2 decimales]
84 | 1263 | 17 | Num |  | Total ganancias patrimoniales [12] | [15 enteros + 2 decimales]
85 | 1280 | 17 | Num |  | Total retenciones o ingresos a cuenta [13] | [15 enteros + 2 decimales]
86 | 1297 | 92 | An |  | Reservado AEAT | En blanco
87 | 1389 | 12 | An |  | Indicador de fin de registro | Constante "</T15108000>"
 | TOTAL | 1400 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  |  | POSICIONES

# M15109000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "09"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 100 | An |  | Descripción de la ganancia patrimonial [66]
8 | 115 | 1 | An |  | Naturaleza [02]
9 | 116 | 17 | Num |  | Ganancia patrimonial [03] | [15 enteros + 2 decimales]
10 | 133 | 17 | Num |  | Retención o ingreso a cuenta [04] | [15 enteros + 2 decimales]
11 | 150 | 2 | Num |  | Tipo de Renta [01]
12 | 152 | 100 | An |  | Descripción de la ganancia patrimonial [66]
13 | 252 | 1 | An |  | Naturaleza [02]
14 | 253 | 17 | Num |  | Ganancia patrimonial [03] | [15 enteros + 2 decimales]
15 | 270 | 17 | Num |  | Retención o ingreso a cuenta [04] | [15 enteros + 2 decimales]
16 | 287 | 2 | Num |  | Tipo de Renta [01]
17 | 289 | 100 | An |  | Descripción de la ganancia patrimonial [66]
18 | 389 | 1 | An |  | Naturaleza [02]
19 | 390 | 17 | Num |  | Ganancia patrimonial [03] | [15 enteros + 2 decimales]
20 | 407 | 17 | Num |  | Retención o ingreso a cuenta [04] | [15 enteros + 2 decimales]
21 | 424 | 17 | Num |  | RESTO. Ganancia patrimonial [03] | [15 enteros + 2 decimales]
22 | 441 | 17 | Num |  | RESTO. Retención o ingreso a cuenta [04] | [15 enteros + 2 decimales]
23 | 458 | 17 | Num |  | Total ganancias patrimoniales [05] | [15 enteros + 2 decimales]
24 | 475 | 17 | Num |  | Total retencion o ingresos a cuenta [06] | [15 enteros + 2 decimales]
25 | 492 | 2 | Num |  | Tipo de Renta [01]
26 | 494 | 100 | An |  | Descripción del elemento patrimonial [67]
27 | 594 | 8 | Num |  | Fecha de transmisión [68]
28 | 602 | 8 | Num |  | Fecha de adquisición [69]
29 | 610 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
30 | 627 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
31 | 644 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
32 | 661 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
33 | 678 | 2 | Num |  | Tipo de Renta [01]
34 | 680 | 100 | An |  | Descripción del elemento patrimonial [67]
35 | 780 | 8 | Num |  | Fecha de transmisión [68]
36 | 788 | 8 | Num |  | Fecha de adquisición [69]
37 | 796 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
38 | 813 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
39 | 830 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
40 | 847 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
41 | 864 | 2 | Num |  | Tipo de Renta [01]
42 | 866 | 100 | An |  | Descripción del elemento patrimonial [67]
43 | 966 | 8 | Num |  | Fecha de transmisión [68]
44 | 974 | 8 | Num |  | Fecha de adquisición [69]
45 | 982 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
46 | 999 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
47 | 1016 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
48 | 1033 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
49 | 1050 | 2 | Num |  | Tipo de Renta [01]
50 | 1052 | 100 | An |  | Descripción del elemento patrimonial [67]
51 | 1152 | 8 | Num |  | Fecha de transmisión [68]
52 | 1160 | 8 | Num |  | Fecha de adquisición [69]
53 | 1168 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
54 | 1185 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
55 | 1202 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
56 | 1219 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
57 | 1236 | 2 | Num |  | Tipo de Renta [01]
58 | 1238 | 100 | An |  | Descripción del elemento patrimonial [67]
59 | 1338 | 8 | Num |  | Fecha de transmisión [68]
60 | 1346 | 8 | Num |  | Fecha de adquisición [69]
61 | 1354 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
62 | 1371 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
63 | 1388 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
64 | 1405 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
65 | 1422 | 67 | An |  | Reservado AEAT | En blanco
66 | 1489 | 12 | An |  | Indicador de fin de registro | Constante "</T15109000>"
 | TOTAL | 1500 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  |  | POSICIONES

# M15100000

 | Agencia Tributaria
Modelo 151
vers 1.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Com. | Datos Adicionales de las rentas derivadas de bienes e inmuebles. | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N |  | Modelo | Constante "151"
3 | 6 | 2 | An |  | Página | Constante "10"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An |  | Reservado para la Administración | En blanco
6 | 13 | 2 | Num |  | Tipo de Renta [01]
7 | 15 | 100 | An |  | Descripción del elemento patrimonial [67]
8 | 115 | 8 | Num |  | Fecha de transmisión [68]
9 | 123 | 8 | Num |  | Fecha de adquisición [69]
10 | 131 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
11 | 148 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
12 | 165 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
13 | 182 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
14 | 199 | 2 | Num |  | Tipo de Renta [01]
15 | 201 | 100 | An |  | Descripción del elemento patrimonial [67]
16 | 301 | 8 | Num |  | Fecha de transmisión [68]
17 | 309 | 8 | Num |  | Fecha de adquisición [69]
18 | 317 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
19 | 334 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
20 | 351 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
21 | 368 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
22 | 385 | 2 | Num |  | Tipo de Renta [01]
23 | 387 | 100 | An |  | Descripción del elemento patrimonial [67]
24 | 487 | 8 | Num |  | Fecha de transmisión [68]
25 | 495 | 8 | Num |  | Fecha de adquisición [69]
26 | 503 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
27 | 520 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
28 | 537 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
29 | 554 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
30 | 571 | 2 | Num |  | Tipo de Renta [01]
31 | 573 | 100 | An |  | Descripción del elemento patrimonial [67]
32 | 673 | 8 | Num |  | Fecha de transmisión [68]
33 | 681 | 8 | Num |  | Fecha de adquisición [69]
34 | 689 | 17 | Num |  | Valor de transmisión [02] | [15 enteros + 2 decimales]
35 | 706 | 17 | Num |  | Valor de adquisición [03] | [15 enteros + 2 decimales]
36 | 723 | 17 | N |  | Diferencia [04] | [15 enteros + 2 decimales]
37 | 740 | 17 | Num |  | Ganancia patrimonial [05] | [15 enteros + 2 decimales]
38 | 757 | 17 | Num |  | RESTO. Ganancia patrimonial [05] | [15 enteros + 2 decimales]
39 | 774 | 17 | Num |  | Total ganancias patrimoniales [06] | [15 enteros + 2 decimales]
40 | 791 | 17 | Num |  | Base liquidable general [17] | [15 enteros + 2 decimales]
41 | 808 | 17 | Num |  | Base liquidable del ahorro [18] | [15 enteros + 2 decimales]
42 | 825 | 17 | Num |  | Cuota correspondiente a la base liquidable general [19] | [15 enteros + 2 decimales]
43 | 842 | 17 | Num |  | Cuota correspondiente a la base liquidable general del ahorro [20] | [15 enteros + 2 decimales]
44 | 859 | 17 | Num |  | Cuota íntegra total [21] | [15 enteros + 2 decimales]
45 | 876 | 17 | Num |  | Cuota íntegra total. Parte estatal [22] | [15 enteros + 2 decimales]
46 | 893 | 17 | Num |  | Cuota íntegra total. Parte autonómica [23] | [15 enteros + 2 decimales]
47 | 910 | 17 | Num |  | Deducción por donativos [24] | [15 enteros + 2 decimales]
48 | 927 | 17 | Num |  | Deducción por donativos. Parte estatal [25] | [15 enteros + 2 decimales]
49 | 944 | 17 | Num |  | Deducción por donativos. Parte autonómica [26] | [15 enteros + 2 decimales]
50 | 961 | 17 | Num |  | Deducción por doble imposición internacional por razón de los rendimientos de trabajo obtenidos y gravados en el extranjero [27] | [15 enteros + 2 decimales]
51 | 978 | 17 | Num |  | Deducción por doble imposición internacional por razón de los rendimientos de trabajo obtenidos y gravados en el extranjero. Parte estatal [28] | [15 enteros + 2 decimales]
52 | 995 | 17 | Num |  | Deducción por doble imposición internacional por razón de los rendimientos de trabajo obtenidos y gravados en el extranjero. Parte autonómica [29] | [15 enteros + 2 decimales]
53 | 1012 | 17 | Num |  | Cuota líquida total [30] | [15 enteros + 2 decimales]
54 | 1029 | 17 | Num |  | Cuota líquida total. Parte estatal [31] | [15 enteros + 2 decimales]
55 | 1046 | 17 | Num |  | Cuota líquida total. Parte autonómica [32] | [15 enteros + 2 decimales]
56 | 1063 | 17 | Num |  | Retención e ingresos a cuenta [33] | [15 enteros + 2 decimales]
57 | 1080 | 17 | Num |  | Cuotas del impuesto sobre la Renta de no Residentes pagadas respecto de las rentas incluidas en la declaración [34] | [15 enteros + 2 decimales]
58 | 1097 | 17 | Num |  | Epígrafe A1 [35] | [15 enteros + 2 decimales]
59 | 1114 | 17 | Num |  | Epígrafe A2 [36] | [15 enteros + 2 decimales]
60 | 1131 | 17 | Num |  | Epígrafe B [37] | [15 enteros + 2 decimales]
61 | 1148 | 17 | Num |  | Epígrafe C [38] | [15 enteros + 2 decimales]
62 | 1165 | 17 | Num |  | Epígrafe D [39] | [15 enteros + 2 decimales]
63 | 1182 | 17 | Num |  | Epígrafe E1 y E2 [40] | [15 enteros + 2 decimales]
64 | 1199 | 17 | Num |  | Resultados a ingresar de las anteriores declaraciones o liquidacion administrativas [41] | [15 enteros + 2 decimales]
65 | 1216 | 17 | Num |  | Devoluciones acordadas por la Administración [42] | [15 enteros + 2 decimales]
66 | 1233 | 17 | N |  | Resultado de la declaración [43] | [15 enteros + 2 decimales]
67 | 1250 | 89 | An |  | Reservado AEAT | En blanco
68 | 1339 | 12 | An |  | Indicador de fin de registro | Constante "</T15110000>"
 | TOTAL | 1350 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  |  | POSICIONES

# M151DID00

 | Agencia Tributaria
Modelo 151 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Persona Físicas. Régimen especial aplicable a los trabajdores desplazados a territorio español
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | N | Modelo | Constante "151"
3 | 6 | 3 | An | Página | Constante "DID"
4 | 9 | 3 | An | Fin de identificador de modelo | Constante "00>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 1 | An | Devolución. Renuncia a la devolución a favor del Tesoro Público | X ó blanco
7 | 14 | 1 | An | Devolución. Solicita la devolución por transferencia | X ó blanco
8 | 15 | 34 | An | Ingreso/Domiciliación/Devolución - IBAN
9 | 49 | 11 | An | Devolución. SWIFT-BIC
10 | 60 | 70 | An | Devolución - Banco/Bank name
11 | 130 | 35 | An | Devolución - Dirección del Banco/ Bank address
12 | 165 | 30 | An | Devolución - Ciudad/City
13 | 195 | 2 | An | Devolución - Código País/Country code
14 | 197 | 1 | Num | Devolución - Marca SEPA | "0", "1", "2", "3" Nota 2
15 | 198 | 1 | An | Cuota cero
16 | 199 | 277 | An | Reservado AEAT | En blanco
17 | 476 | 13 | An | Reservado para la Administración. Sello electronico | En blanco
18 | 489 | 12 | An | Indicador de fin de registro | Constante "</T151DID00>"
 | TOTAL | 500 | POSICIONES
Nota 1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
6. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
Nota 2: Devolución marca SEPA
Valor | Descripción
0 | Vacía
1 | Cuenta España
2 | Unión Europea SEPA
3 | Resto Países