# Pág. 0

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | Constante "<T"
2 | 3 | 3 | An | Modelo. |  | Constante "390"
3 | 6 | 1 | An | Discriminante |  | Constante "0"
4 | 7 | 4 | An | Ejercicio de devengo (EEEE) |  | Nota 2
5 | 11 | 2 | An | Periodo (PP) |  | "0A"
6 | 13 | 5 | An | Tipo y cierre |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa |  | Nota 1
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo |  | Nota 1
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | variable | An | Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Tipo+> |  | "</T3900EEEEPP0000>"
TOTAL |  | variable | POSICIONES
Nota1:
A cumplimentar por las entidades desarrolladoras (EEDD):
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota2:
EEEE indica las cuatro cifras del ejercicio en curso
Nota3:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 1

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 1 | A | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
7 | 14 | 9 | An | 1. Sujeto pasivo - NIF. | OBLIGATORIO | Cualquier NIF válido PF o PJ.
8 | 23 | 60 | An | 1. Sujeto pasivo - Apellidos o Razón Social. | OBLIGATORIO
9 | 83 | 20 | An | 1. Sujeto pasivo - Nombre. | OBLIGATORIO (persona fisica)
10 | 103 | 4 | Num | 2. Devengo - Ejercicio. | OBLIGATORIO
11 | 107 | 2 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
12 | 109 | 1 | An | 1. Sujeto pasivo - Registro de devolución mensual. |  | "0" ó "1"
13 | 110 | 1 | An | 1. Sujeto pasivo - Regimen especial del grupo de entidades |  | "0" ó "1"
14 | 111 | 7 | An | 1. Sujeto pasivo - Número de grupo
15 | 118 | 1 | An | 1. Sujeto pasivo - dominante? |  | "0" ó "1"
16 | 119 | 1 | An | 1. Sujeto pasivo - dependiente? |  | "0" ó "1"
17 | 120 | 1 | An | 1. Sujeto pasivo - Tipo régimen especial aplicable. Art 163 sexies.cinco. Si o No |  | "0" - blanco, "1" - Si, "2" .- No
18 | 121 | 9 | An | 1. Sujeto pasivo - NIF entidad dominante
19 | 130 | 1 | An | 1. Sujeto pasivo - Concurso acreedores en este ejercicio |  | "0" - blanco, "1" - Si, "2" .- No
20 | 131 | 1 | An | 1. Sujeto pasivo - Regimen especial del criterio de caja |  | "0" - blanco, "1" - Si, "2" .- No
21 | 132 | 1 | An | 1. Sujeto pasivo - Ha sido destinatario del régimen especial del criterio de caja |  | "0" - blanco, "1" - Si, "2" .- No
22 | 133 | 1 | Num | 2. Devengo - Sustitutiva? |  | "0" ó "1"
23 | 134 | 1 | Num | 2. Devengo - Sustitutiva por rectificación de cuotas? |  | "0" ó "1"
24 | 135 | 13 | An | 2. Devengo - Nº justificante declaración anterior
25 | 148 | 40 | An | 3. Datos estadísticos - A - Actividades - Principal
26 | 188 | 3 | An | 3. Datos estadísticos - B - Código de actividad - Principal
27 | 191 | 4 | An | 3. Datos estadísticos - C -Epígrafe I.A.E. - Principal
28 | 195 | 40 | An | 3. Datos estadísticos - A - Actividades - Otras - 1ª
29 | 235 | 3 | An | 3. Datos estadísticos - B - Código de actividad - Otras 1ª
30 | 238 | 4 | An | 3. Datos estadísticos - C -Epígrafe I.A.E. - Otras 1º
31 | 242 | 40 | An | 3. Datos estadísticos - A - Actividades - Otras - 2ª
32 | 282 | 3 | An | 3. Datos estadísticos - B - Código de actividad - Otras 2ª
33 | 285 | 4 | An | 3. Datos estadísticos - C -Epígrafe I.A.E. - Otras 2º
34 | 289 | 40 | An | 3. Datos estadísticos - A - Actividades - Otras - 3ª
35 | 329 | 3 | An | 3. Datos estadísticos - B - Código de actividad - Otras 3ª
36 | 332 | 4 | An | 3. Datos estadísticos - C -Epígrafe I.A.E. - Otras 3º
37 | 336 | 40 | An | 3. Datos estadísticos - A - Actividades - Otras - 4ª
38 | 376 | 3 | An | 3. Datos estadísticos - B - Código de actividad - Otras 4ª
39 | 379 | 4 | An | 3. Datos estadísticos - C -Epígrafe I.A.E. - Otras 4º
40 | 383 | 40 | An | 3. Datos estadísticos - A - Actividades - Otras - 5ª
41 | 423 | 3 | An | 3. Datos estadísticos - B - Código de actividad - Otras 5ª
42 | 426 | 4 | An | 3. Datos estadísticos - C -Epígrafe I.A.E. - Otras 5º
43 | 430 | 1 | An | 3. Datos estadísticos - D - Declaración anual operac. con terceras personas. |  | "0" ó "1"
44 | 431 | 9 | An | 3. Datos estadísticos - Declaración conjunta - NIF.
45 | 440 | 37 | An | 3. Datos estadísticos - Declaración conjunta - Razón social
46 | 477 | 9 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - NIF.
47 | 486 | 80 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Apellidos y Nombre/Razón social
48 | 566 | 2 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Calle/Pza./Avda.
49 | 568 | 17 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Nombre de la vía pública
50 | 585 | 5 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Número
51 | 590 | 2 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Esc.
52 | 592 | 2 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Piso
53 | 594 | 2 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Prta.
54 | 596 | 9 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Teléfono
55 | 605 | 20 | A | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Municipio
56 | 625 | 15 | A | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Provincia
57 | 640 | 5 | An | 4. Representante - Personas Físicas/Comunid. Bienes - Represent. - Código Postal
58 | 645 | 80 | An | 4. Representante - Personas Jurídicas - Represent. 1 - Nombre y Apellidos
59 | 725 | 9 | An | 4. Representante - Personas Jurídicas - Represent. 1 - NIF
60 | 734 | 8 | Num | 4. Representante - Personas Jurídicas - Represent. 1 - Fecha Poder (DDMMAAAA)
61 | 742 | 12 | An | 4. Representante - Personas Jurídicas - Represent. 1 - Notaría
62 | 754 | 80 | An | 4. Representante - Personas Jurídicas - Represent. 2 - Nombre y Apellidos
63 | 834 | 9 | An | 4. Representante - Personas Jurídicas - Represent. 2 - NIF
64 | 843 | 8 | Num | 4. Representante - Personas Jurídicas - Represent. 2 - Fecha Poder (DDMMAAAA)
65 | 851 | 12 | An | 4. Representante - Personas Jurídicas - Represent. 2 - Notaría
66 | 863 | 80 | An | 4. Representante - Personas Jurídicas - Represent. 3 - Nombre y Apellidos
67 | 943 | 9 | An | 4. Representante - Personas Jurídicas - Represent. 3 - NIF
68 | 952 | 8 | Num | 4. Representante - Personas Jurídicas - Represent. 3 - Fecha Poder (DDMMAAAA)
69 | 960 | 12 | An | 4. Representante - Personas Jurídicas - Represent. 3 - Notaría
70 | 972 | 21 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia PADRE's
71 | 993 | 13 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Sello electrónico
72 | 1006 | 20 | An | Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
73 | 1026 | 150 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
74 | 1176 | 12 | An | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39001000>"
TOTAL |  | 1187 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 2

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "02000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En Blanco
6 | 13 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 0% - Base imponible [700] |  | 15 enteros 2 decimales
7 | 30 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 0% - Cuota [701] |  | 15 enteros 2 decimales
8 | 47 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 2% - Base imponible [667] |  | 15 enteros 2 decimales
9 | 64 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 2% - Cuota [668] |  | 15 enteros 2 decimales
10 | 81 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 4% - Base imponible [01] |  | 15 enteros 2 decimales
11 | 98 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 4% - Cuota [02] |  | 15 enteros 2 decimales
12 | 115 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 5% - Base imponible [702] |  | 15 enteros 2 decimales
13 | 132 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 5% - Cuota [703] |  | 15 enteros 2 decimales
14 | 149 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 7,5% - Base imponible [669] |  | 15 enteros 2 decimales
15 | 166 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 7,5% - Cuota [670] |  | 15 enteros 2 decimales
16 | 183 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 10% - Base imponible [03] |  | 15 enteros 2 decimales
17 | 200 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 10% - Cuota [04] |  | 15 enteros 2 decimales
18 | 217 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 21% - Base imponible [05] |  | 15 enteros 2 decimales
19 | 234 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 21% - Cuota [06] |  | 15 enteros 2 decimales
20 | 251 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 0% - Base imponible [704] |  | 15 enteros 2 decimales
21 | 268 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 0% - Cuota [705] |  | 15 enteros 2 decimales
22 | 285 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 2% - Base imponible [671] |  | 15 enteros 2 decimales
23 | 302 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 2% - Cuota [672] |  | 15 enteros 2 decimales
24 | 319 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 4% - Base imponible [500] |  | 15 enteros 2 decimales
25 | 336 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 4% - Cuota [501] |  | 15 enteros 2 decimales
26 | 353 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 5% - Base imponible [706] |  | 15 enteros 2 decimales
27 | 370 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 5% - Cuota [707] |  | 15 enteros 2 decimales
28 | 387 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 7,5% - Base imponible [673] |  | 15 enteros 2 decimales
29 | 404 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 7,5% - Cuota [674] |  | 15 enteros 2 decimales
30 | 421 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 10% - Base imponible [502] |  | 15 enteros 2 decimales
31 | 438 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 10% - Cuota [503] |  | 15 enteros 2 decimales
32 | 455 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 21% - Base imponible [504] |  | 15 enteros 2 decimales
33 | 472 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - operaciones intragrupo - Tipo 21% - Cuota [505] |  | 15 enteros 2 decimales
34 | 489 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 0% - Base imponible [708] |  | 15 enteros 2 decimales
35 | 506 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 0% - Cuota [709] |  | 15 enteros 2 decimales
36 | 523 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 2% - Base imponible [675] |  | 15 enteros 2 decimales
37 | 540 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 2% - Cuota [676] |  | 15 enteros 2 decimales
38 | 557 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 4% - Base imponible [643] |  | 15 enteros 2 decimales
39 | 574 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 4% - Cuota [644] |  | 15 enteros 2 decimales
40 | 591 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 5% - Base imponible [710] |  | 15 enteros 2 decimales
41 | 608 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 5% - Cuota [711] |  | 15 enteros 2 decimales
42 | 625 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 7,5% - Base imponible [677] |  | 15 enteros 2 decimales
43 | 642 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 7,5% - Cuota [678] |  | 15 enteros 2 decimales
44 | 659 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 10% - Base imponible [645] |  | 15 enteros 2 decimales
45 | 676 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 10% - Cuota [646] |  | 15 enteros 2 decimales
46 | 693 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 21% - Base imponible [647] |  | 15 enteros 2 decimales
47 | 710 | 17 | N | 5. Operaciones Reg. Gral. - Base imponible y cuota - regimen especial criterio caja - Tipo 21% - Cuota [648] |  | 15 enteros 2 decimales
48 | 727 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 0% - Base imponible [712] |  | 15 enteros 2 decimales
49 | 744 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 0% - Cuota [713] |  | 15 enteros 2 decimales
50 | 761 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 2% - Base imponible [679] |  | 15 enteros 2 decimales
51 | 778 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 2% - Cuota [680] |  | 15 enteros 2 decimales
52 | 795 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 4% - Base imponible [07] |  | 15 enteros 2 decimales
53 | 812 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 4% - Cuota [08] |  | 15 enteros 2 decimales
54 | 829 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 5% - Base imponible [714] |  | 15 enteros 2 decimales
55 | 846 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 5% - Cuota [715] |  | 15 enteros 2 decimales
56 | 863 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 7,5% - Base imponible [681] |  | 15 enteros 2 decimales
57 | 880 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 7,5% - Cuota [682] |  | 15 enteros 2 decimales
58 | 897 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 10% - Base imponible [09] |  | 15 enteros 2 decimales
59 | 914 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 10% - Cuota [10] |  | 15 enteros 2 decimales
60 | 931 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 21% - Base imponible [11] |  | 15 enteros 2 decimales
61 | 948 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. bienes usados - Tipo 21% - Cuota [12] |  | 15 enteros 2 decimales
62 | 965 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. agencias viajes - Tipo 21% - Base imponible [13] |  | 15 enteros 2 decimales
63 | 982 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. espec. agencias viajes - Tipo 21% - Cuota [14] |  | 15 enteros 2 decimales
64 | 999 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 0% - Base imponible [716] |  | 15 enteros 2 decimales
65 | 1016 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 0% - Cuota [717] |  | 15 enteros 2 decimales
66 | 1033 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 2% - Base imponible [683] |  | 15 enteros 2 decimales
67 | 1050 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 2% - Cuota [684] |  | 15 enteros 2 decimales
68 | 1067 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 4% - Base imponible [21] |  | 15 enteros 2 decimales
69 | 1084 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 4% - Cuota [22] |  | 15 enteros 2 decimales
70 | 1101 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 5% - Base imponible [718] |  | 15 enteros 2 decimales
71 | 1118 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 5% - Cuota [719] |  | 15 enteros 2 decimales
72 | 1135 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 7,5% - Base imponible [685] |  | 15 enteros 2 decimales
73 | 1152 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 7,5% - Cuota [686] |  | 15 enteros 2 decimales
74 | 1169 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 10% - Base imponible [23] |  | 15 enteros 2 decimales
75 | 1186 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 10% - Cuota [24] |  | 15 enteros 2 decimales
76 | 1203 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 21% - Base imponible [25] |  | 15 enteros 2 decimales
77 | 1220 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. bienes - Tipo 21% - Cuota [26] |  | 15 enteros 2 decimales
78 | 1237 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 0% - Base Imponible [720] |  | 15 enteros 2 decimales
79 | 1254 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 0% - Cuota [721] |  | 15 enteros 2 decimales
80 | 1271 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 2% - Base Imponible [687] |  | 15 enteros 2 decimales
81 | 1288 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 2% - Cuota [688] |  | 15 enteros 2 decimales
82 | 1305 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 4% - Base Imponible [545] |  | 15 enteros 2 decimales
83 | 1322 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 4% - Cuota [546] |  | 15 enteros 2 decimales
84 | 1339 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 5% - Base Imponible [722] |  | 15 enteros 2 decimales
85 | 1356 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 5% - Cuota [723] |  | 15 enteros 2 decimales
86 | 1373 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 7,5% - Base Imponible [689] |  | 15 enteros 2 decimales
87 | 1390 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 7,5% - Cuota [690] |  | 15 enteros 2 decimales
88 | 1407 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 10% - Base Imponible [547] |  | 15 enteros 2 decimales
89 | 1424 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 10% - Cuota [548] |  | 15 enteros 2 decimales
90 | 1441 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 21% - Base Imponible [551] |  | 15 enteros 2 decimales
91 | 1458 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Adquis. intracomunit. servicios - Tipo 21% - Cuota [552] |  | 15 enteros 2 decimales
92 | 1475 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - IVA deveng. invers. sujeto pasivo - Base imponible [27] |  | 15 enteros 2 decimales
93 | 1492 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - IVA deveng. invers. sujeto pasivo - Cuota [28] |  | 15 enteros 2 decimales
94 | 1509 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modificac. bases y cuotas - Base imponible [29] |  | 15 enteros 2 decimales
95 | 1526 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modificac. bases y cuotas - Cuota [30] |  | 15 enteros 2 decimales
96 | 1543 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modificac. bases y cuotas intragrupo - Base [649] |  | 15 enteros 2 decimales
97 | 1560 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modificac. bases y cuotas intragrupo - Cuota [650] |  | 15 enteros 2 decimales
98 | 1577 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modificac. bases/cuotas concurso acreedores - Base imponible [31] |  | 15 enteros 2 decimales
99 | 1594 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modificac. bases/cuotas concurso acreedores - Cuota [32] |  | 15 enteros 2 decimales
100 | 1611 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Total bases y cuotas IVA - Base imponible [33] |  | 15 enteros 2 decimales
101 | 1628 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Total bases y cuotas IVA - Cuota [34] |  | 15 enteros 2 decimales
102 | 1645 | 150 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
103 | 1795 | 12 | An | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39002000>"
TOTAL |  | 1806 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 2 bis

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "02B00"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En Blanco
6 | 13 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0% - Base imponible [663] |  | 15 enteros 2 decimales
7 | 30 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0% - Cuota [664] |  | 15 enteros 2 decimales
8 | 47 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0,26% - Base imponible [691] |  | 15 enteros 2 decimales
9 | 64 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0,26% - Cuota [692] |  | 15 enteros 2 decimales
10 | 81 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0,5% - Base imponible [35] |  | 15 enteros 2 decimales
11 | 98 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0,5% - Cuota [36] |  | 15 enteros 2 decimales
12 | 115 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0,62% - Base imponible [665] |  | 15 enteros 2 decimales
13 | 132 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0,62% - Cuota [666] |  | 15 enteros 2 decimales
14 | 149 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 1% - Base imponible [693] |  | 15 enteros 2 decimales
15 | 166 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 1% - Cuota [694] |  | 15 enteros 2 decimales
16 | 183 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 1,4% - Base imponible [599] |  | 15 enteros 2 decimales
17 | 200 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 1,4% - Cuota [600] |  | 15 enteros 2 decimales
18 | 217 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 5,2% - Base imponible [601] |  | 15 enteros 2 decimales
19 | 234 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 5,2% - Cuota [602] |  | 15 enteros 2 decimales
20 | 251 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 1,75% - Base imponible [41] |  | 15 enteros 2 decimales
21 | 268 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 1,75% - Cuota [42] |  | 15 enteros 2 decimales
22 | 285 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modific. recargo equivalencia - Base imponible [43] |  | 15 enteros 2 decimales
23 | 302 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modific. recargo equivalencia - Cuota [44] |  | 15 enteros 2 decimales
24 | 319 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modific. recargo equiv. Concurso acreedores - Base imponible [45] |  | 15 enteros 2 decimales
25 | 336 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Modific. recargo equiv. Concurso acreedores - Cuota [46] |  | 15 enteros 2 decimales
26 | 353 | 17 | N | 5. Operaciones Reg. Gral. - Base Imponible y cuota - Total cuotas IVA y recargo equivalencia [47] |  | 15 enteros 2 decimales
27 | 370 | 150 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
28 | 520 | 12 | An | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39002B00>"
TOTAL |  | 531 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 3

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "03000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En Blanco
6 | 13 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 2% - Base imponible [695] |  | 15 enteros 2 decimales
7 | 30 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 2% - Cuota [696] |  | 15 enteros 2 decimales
8 | 47 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 4% - Base imponible [190] |  | 15 enteros 2 decimales
9 | 64 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 4% - Cuota [191] |  | 15 enteros 2 decimales
10 | 81 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 5% - Base imponible [724] |  | 15 enteros 2 decimales
11 | 98 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 5% - Cuota [725] |  | 15 enteros 2 decimales
12 | 115 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 7,5% - Base imponible [697] |  | 15 enteros 2 decimales
13 | 132 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 7,5% - Cuota [698] |  | 15 enteros 2 decimales
14 | 149 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 10% - Base imponible [603] |  | 15 enteros 2 decimales
15 | 166 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 10% - Cuota [604] |  | 15 enteros 2 decimales
16 | 183 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 21% - Base imponible [605] |  | 15 enteros 2 decimales
17 | 200 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. corrientes bienes y servic. - Tipo 21% - Cuota [606] |  | 15 enteros 2 decimales
18 | 217 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total oper. inter. corrientes bienes y servic. - Base imponible [48] |  | 15 enteros 2 decimales
19 | 234 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total oper. inter. corrientes bienes y servic. - Cuota [49] |  | 15 enteros 2 decimales
20 | 251 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 2% - Base imponible [745] |  | 15 enteros 2 decimales
21 | 268 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 2% - Cuota [746] |  | 15 enteros 2 decimales
22 | 285 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 4% - Base imponible [506] |  | 15 enteros 2 decimales
23 | 302 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 4% - Cuota [507] |  | 15 enteros 2 decimales
24 | 319 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 5% - Base imponible [726] |  | 15 enteros 2 decimales
25 | 336 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 5% - Cuota [727] |  | 15 enteros 2 decimales
26 | 353 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 7,5% - Base imponible [747] |  | 15 enteros 2 decimales
27 | 370 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 7,5% - Cuota [748] |  | 15 enteros 2 decimales
28 | 387 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 10% - Base imponible [607] |  | 15 enteros 2 decimales
29 | 404 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 10% - Cuota [608] |  | 15 enteros 2 decimales
30 | 421 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 21% - Base imponible [609] |  | 15 enteros 2 decimales
31 | 438 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intragrupo corrientes - Tipo 21% - Cuota [610] |  | 15 enteros 2 decimales
32 | 455 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total oper. intragrupo corrientes - Base imponible [512] |  | 15 enteros 2 decimales
33 | 472 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total oper. intragrupo corrientes - Cuota [513] |  | 15 enteros 2 decimales
34 | 489 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 2% - Base imponible [749] |  | 15 enteros 2 decimales
35 | 506 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 2% - Cuota [750] |  | 15 enteros 2 decimales
36 | 523 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 4% - Base imponible [196] |  | 15 enteros 2 decimales
37 | 540 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 4% - Cuota [197] |  | 15 enteros 2 decimales
38 | 557 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 5% - Base imponible [728] |  | 15 enteros 2 decimales
39 | 574 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 5% - Cuota [729] |  | 15 enteros 2 decimales
40 | 591 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 7,5% - Base imponible [751] |  | 15 enteros 2 decimales
41 | 608 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 7,5% - Cuota [752] |  | 15 enteros 2 decimales
42 | 625 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 10% - Base imponible [611] |  | 15 enteros 2 decimales
43 | 642 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 10% - Cuota [612] |  | 15 enteros 2 decimales
44 | 659 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 21% - Base imponible [613] |  | 15 enteros 2 decimales
45 | 676 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. inter. bienes de inversion - Tipo 21% - Cuota [614] |  | 15 enteros 2 decimales
46 | 693 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total oper. inter. bienes de inversion - Base imponible [50] |  | 15 enteros 2 decimales
47 | 710 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total oper. inter. bienes de inversion - Cuota [51] |  | 15 enteros 2 decimales
48 | 727 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 2% - Base imponible [753] |  | 15 enteros 2 decimales
49 | 744 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 2% - Cuota [754] |  | 15 enteros 2 decimales
50 | 761 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 4% - Base imponible [514] |  | 15 enteros 2 decimales
51 | 778 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 4% - Cuota [515] |  | 15 enteros 2 decimales
52 | 795 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 5% - Base imponible [730] |  | 15 enteros 2 decimales
53 | 812 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 5% - Cuota [731] |  | 15 enteros 2 decimales
54 | 829 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 7,5% - Base imponible [755] |  | 15 enteros 2 decimales
55 | 846 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 7,5% - Cuota [756] |  | 15 enteros 2 decimales
56 | 863 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 10% - Base imponible [615] |  | 15 enteros 2 decimales
57 | 880 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 10% - Cuota [616] |  | 15 enteros 2 decimales
58 | 897 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 21% - Base imponible [617] |  | 15 enteros 2 decimales
59 | 914 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Oper. intra. bienes de inversion - Tipo 21% - Cuota [618] |  | 15 enteros 2 decimales
60 | 931 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total oper. intra. bienes de inversion - Base imponible [520] |  | 15 enteros 2 decimales
61 | 948 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total oper. intra. bienes de inversion - Cuota [521] |  | 15 enteros 2 decimales
62 | 965 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 2% - Base imponible [757] |  | 15 enteros 2 decimales
63 | 982 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 2% - Cuota [758] |  | 15 enteros 2 decimales
64 | 999 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 4% - Base imponible [202] |  | 15 enteros 2 decimales
65 | 1016 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 4% - Cuota [203] |  | 15 enteros 2 decimales
66 | 1033 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 5% - Base imponible [732] |  | 15 enteros 2 decimales
67 | 1050 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 5% - Cuota [733] |  | 15 enteros 2 decimales
68 | 1067 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 7,5% - Base imponible [759] |  | 15 enteros 2 decimales
69 | 1084 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 7,5% - Cuota [760] |  | 15 enteros 2 decimales
70 | 1101 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 10% - Base imponible [619] |  | 15 enteros 2 decimales
71 | 1118 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 10% - Cuota [620] |  | 15 enteros 2 decimales
72 | 1135 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 21% - Base imponible [621] |  | 15 enteros 2 decimales
73 | 1152 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Import. bienes corrientes - Tipo 21% - Cuota [622] |  | 15 enteros 2 decimales
74 | 1169 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total import. bienes corrientes - Base imponible [52] |  | 15 enteros 2 decimales
75 | 1186 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total import. bienes corrientes - Cuota [53] |  | 15 enteros 2 decimales
76 | 1203 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 2% - Base imponible [761] |  | 15 enteros 2 decimales
77 | 1220 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 2% - Cuota [762] |  | 15 enteros 2 decimales
78 | 1237 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 4% - Base imponible [208] |  | 15 enteros 2 decimales
79 | 1254 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 4% - Cuota [209] |  | 15 enteros 2 decimales
80 | 1271 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 5% - Base imponible [734] |  | 15 enteros 2 decimales
81 | 1288 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 5% - Cuota [735] |  | 15 enteros 2 decimales
82 | 1305 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 7,5% - Base imponible [763] |  | 15 enteros 2 decimales
83 | 1322 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 7,5% - Cuota [764] |  | 15 enteros 2 decimales
84 | 1339 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 10% - Base imponible [623] |  | 15 enteros 2 decimales
85 | 1356 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 10% - Cuota [624] |  | 15 enteros 2 decimales
86 | 1373 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 21% - Base imponible [625] |  | 15 enteros 2 decimales
87 | 1390 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Importacion bienes inversion - Tipo 21% - Cuota [626] |  | 15 enteros 2 decimales
88 | 1407 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total importacion bienes inversion - Base imponible [54] |  | 15 enteros 2 decimales
89 | 1424 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total importacion bienes inversion - Cuota [55] |  | 15 enteros 2 decimales
90 | 1441 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 2% - Base imponible [765] |  | 15 enteros 2 decimales
91 | 1458 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 2% - Cuota [766] |  | 15 enteros 2 decimales
92 | 1475 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 4% - Base imponible [214] |  | 15 enteros 2 decimales
93 | 1492 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 4% - Cuota [215] |  | 15 enteros 2 decimales
94 | 1509 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 5% - Base imponible [736] |  | 15 enteros 2 decimales
95 | 1526 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 5% - Cuota [737] |  | 15 enteros 2 decimales
96 | 1543 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 7,5% - Base imponible [767] |  | 15 enteros 2 decimales
97 | 1560 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 7,5% - Cuota [768] |  | 15 enteros 2 decimales
98 | 1577 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 10% - Base imponible [627] |  | 15 enteros 2 decimales
99 | 1594 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 10% - Cuota [628] |  | 15 enteros 2 decimales
100 | 1611 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 21% - Base imponible [629] |  | 15 enteros 2 decimales
101 | 1628 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes corrientes - Tipo 21% - Cuota [630] |  | 15 enteros 2 decimales
102 | 1645 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total adqui. intra. bienes corrientes - Base imponible [56] |  | 15 enteros 2 decimales
103 | 1662 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total adqui. intra. bienes corrientes - Cuota [57] |  | 15 enteros 2 decimales
104 | 1679 | 150 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
105 | 1829 | 12 | An | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39003000>"
TOTAL |  | 1840 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 4

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | Página. | OBLIGATORIO | Constante "04000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En Blanco
6 | 13 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 2% - Base imponible [769] |  | 15 enteros 2 decimales
7 | 30 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 2% - Cuota [770] |  | 15 enteros 2 decimales
8 | 47 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 4% - Base imponible [220] |  | 15 enteros 2 decimales
9 | 64 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 4% - Cuota [221] |  | 15 enteros 2 decimales
10 | 81 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 5% - Base imponible [738] |  | 15 enteros 2 decimales
11 | 98 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 5% - Cuota [739] |  | 15 enteros 2 decimales
12 | 115 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 7,5% - Base imponible [771] |  | 15 enteros 2 decimales
13 | 132 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 7,5% - Cuota [772] |  | 15 enteros 2 decimales
14 | 149 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 10% - Base imponible [631] |  | 15 enteros 2 decimales
15 | 166 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 10% - Cuota [632] |  | 15 enteros 2 decimales
16 | 183 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 21% - Base imponible [633] |  | 15 enteros 2 decimales
17 | 200 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. bienes inversion - Tipo 21% - Cuota [634] |  | 15 enteros 2 decimales
18 | 217 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total adqui. intra. bienes inversion - Base imponible [58] |  | 15 enteros 2 decimales
19 | 234 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total adqui. intra. bienes inversion - Cuota [59] |  | 15 enteros 2 decimales
20 | 251 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 2% - Base imponible [773] |  | 15 enteros 2 decimales
21 | 268 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 2% - Cuota [774] |  | 15 enteros 2 decimales
22 | 285 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 4% - Base imponible [587] |  | 15 enteros 2 decimales
23 | 302 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 4% - Cuota [588] |  | 15 enteros 2 decimales
24 | 319 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 5% - Base imponible [740] |  | 15 enteros 2 decimales
25 | 336 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 5% - Cuota [741] |  | 15 enteros 2 decimales
26 | 353 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 7,5% - Base imponible [775] |  | 15 enteros 2 decimales
27 | 370 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 7,5% - Cuota [776] |  | 15 enteros 2 decimales
28 | 387 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 10% - Base imponible [635] |  | 15 enteros 2 decimales
29 | 404 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 10% - Cuota [636] |  | 15 enteros 2 decimales
30 | 421 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 21% - Base imponible [637] |  | 15 enteros 2 decimales
31 | 438 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Adqui. intra. servicios - Tipo 21% - Cuota [638] |  | 15 enteros 2 decimales
32 | 455 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total adqui. intra. servicios - Base imponible [597] |  | 15 enteros 2 decimales
33 | 472 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Total adqui. intra. servicios - Cuota [598] |  | 15 enteros 2 decimales
34 | 489 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Compensac. rég. especial agric./ganad./pesca - Base impon. [60] |  | 15 enteros 2 decimales
35 | 506 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Compensac. rég. especial agric./ganad./pesca - Cuota deduc. [61] |  | 15 enteros 2 decimales
36 | 523 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Cuotas deducibles en virtud de resolución administrativa o sentencia firmes con tipos no vigentes - Base impon.  [660] |  | 15 enteros 2 decimales
37 | 540 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Cuotas deducibles en virtud de resolución administrativa o sentencia firmes con tipos no vigentes - Cuota deduc. [661] |  | 15 enteros 2 decimales
38 | 557 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Rectificación de deducciones - Base imponible [639] |  | 15 enteros 2 decimales
39 | 574 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Rectificación de deducciones - Cuota [62] |  | 15 enteros 2 decimales
40 | 591 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Rectificación de deducciones intragrupo - Base impon. [651] |  | 15 enteros 2 decimales
41 | 608 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Rectificación de deducciones intragrupo - Cuota [652] |  | 15 enteros 2 decimales
42 | 625 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Regularización de inversiones [63] |  | 15 enteros 2 decimales
43 | 642 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Regularización por aplicación porcentaje definitivo de prorrata [522] |  | 15 enteros 2 decimales
44 | 659 | 17 | N | 5. Operaciones Reg. Gral. - IVA deducible - Suma de deducciones [64] |  | 15 enteros 2 decimales
45 | 676 | 17 | N | 5. Operaciones Reg. Gral. - Resultado régimen general [65] |  | 15 enteros 2 decimales
46 | 693 | 150 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
47 | 843 | 12 | An | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39004000>"
TOTAL |  | 854 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 5

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | C | Página. | OBLIGATORIO | Constante "05000"
4 | 11 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. |  | Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 4 | An | C | 6. Operaciones Reg. Simplificado - Actividad 1 - Epígrafe I.A.E. [66]
7 | 17 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - A - Nº unidades Módulo 1 |  | 8 enteros 2 decimales
8 | 27 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - B - Importe Módulo 1 |  | 15 enteros 2 decimales
9 | 44 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - A - Nº unidades Módulo 2 |  | 8 enteros 2 decimales
10 | 54 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - B - Importe Módulo 2 |  | 15 enteros 2 decimales
11 | 71 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - A - Nº unidades Módulo 3 |  | 8 enteros 2 decimales
12 | 81 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - B - Importe Módulo 3 |  | 15 enteros 2 decimales
13 | 98 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - A - Nº unidades Módulo 4 |  | 8 enteros 2 decimales
14 | 108 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - B - Importe Módulo 4 |  | 15 enteros 2 decimales
15 | 125 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - A - Nº unidades Módulo 5 |  | 8 enteros 2 decimales
16 | 135 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - B - Importe Módulo 5 |  | 15 enteros 2 decimales
17 | 152 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - A - Nº unidades Módulo 6 |  | 8 enteros 2 decimales
18 | 162 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - B - Importe Módulo 6 |  | 15 enteros 2 decimales
19 | 179 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - A - Nº unidades Módulo 7 |  | 8 enteros 2 decimales
20 | 189 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - B - Importe Módulo 7 |  | 15 enteros 2 decimales
21 | 206 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - C- Cuota devengada operaciones corrientes |  | 15 enteros 2 decimales
22 | 223 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - Reducción aplicable por actividad realizada en el término municipal de Lorca |  | 15 enteros 2 decimales
23 | 240 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - D- Cuota soportadas operaciones corrientes |  | 15 enteros 2 decimales
24 | 257 | 3 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - E - Índice corrector |  | 1 enteros 2 decimales
25 | 260 | 17 | N | C | 6. Operaciones Reg. Simplificado - Actividad 1 - F - Resultado |  | 15 enteros 2 decimales
26 | 277 | 5 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - G - % Cuota mínima |  | 3 enteros 2 decimales
27 | 282 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - H - Devolución cuotas soportadas otros países |  | 15 enteros 2 decimales
28 | 299 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - I - Cuota mínima |  | 15 enteros 2 decimales
29 | 316 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - Cuota derivada régimen simplificado [J1] |  | 15 enteros 2 decimales
30 | 333 | 4 | An | C | 6. Operaciones Reg. Simplificado - Actividad 2 - Epígrafe I.A.E. [66]
31 | 337 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - A - Nº unidades Módulo 1 |  | 8 enteros 2 decimales
32 | 347 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - B - Importe Módulo 1 |  | 15 enteros 2 decimales
33 | 364 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - A - Nº unidades Módulo 2 |  | 8 enteros 2 decimales
34 | 374 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - B - Importe Módulo 2 |  | 15 enteros 2 decimales
35 | 391 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - A - Nº unidades Módulo 3 |  | 8 enteros 2 decimales
36 | 401 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - B - Importe Módulo 3 |  | 15 enteros 2 decimales
37 | 418 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - A - Nº unidades Módulo 4 |  | 8 enteros 2 decimales
38 | 428 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - B - Importe Módulo 4 |  | 15 enteros 2 decimales
39 | 445 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - A - Nº unidades Módulo 5 |  | 8 enteros 2 decimales
40 | 455 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - B - Importe Módulo 5 |  | 15 enteros 2 decimales
41 | 472 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - A - Nº unidades Módulo 6 |  | 8 enteros 2 decimales
42 | 482 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - B - Importe Módulo 6 |  | 15 enteros 2 decimales
43 | 499 | 10 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - A - Nº unidades Módulo 7 |  | 8 enteros 2 decimales
44 | 509 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - B - Importe Módulo 7 |  | 15 enteros 2 decimales
45 | 526 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - C- Cuota devengada operaciones corrientes |  | 15 enteros 2 decimales
46 | 543 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - Reducción aplicable por actividad realizada en el término municipal de Lorca |  | 15 enteros 2 decimales
47 | 560 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - D- Cuota soportadas operaciones corrientes |  | 15 enteros 2 decimales
48 | 577 | 3 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - E - Índice corrector |  | 1 enteros 2 decimales
49 | 580 | 17 | N | C | 6. Operaciones Reg. Simplificado - Actividad 2 - F - Resultado |  | 15 enteros 2 decimales
50 | 597 | 5 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - G - % Cuota mínima |  | 3 enteros 2 decimales
51 | 602 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - H - Devolución cuotas soportadas otros países |  | 15 enteros 2 decimales
52 | 619 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - I - Cuota mínima |  | 15 enteros 2 decimales
53 | 636 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - Cuota derivada régimen simplificado [J2] |  | 15 enteros 2 decimales
54 | 653 | 2 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 1 - Código
55 | 655 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 1 - Volumen  ingresos |  | 15 enteros 2 decimales
56 | 672 | 6 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 1 - Indice cuota |  | 1 entero 5 decimales
57 | 678 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 1 - Cuota devengada |  | 15 enteros 2 decimales
58 | 695 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 1 - Cuota soportada |  | 15 enteros 2 decimales
59 | 712 | 17 | N |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 1 - Cuota derivada Regimen Simplificado [K1] |  | 15 enteros 2 decimales
60 | 729 | 2 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 2 - Código
61 | 731 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 2 - Volumen  ingresos |  | 15 enteros 2 decimales
62 | 748 | 6 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 2 - Indice cuota |  | 1 entero 5 decimales
63 | 754 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 2 - Cuota devengada |  | 15 enteros 2 decimales
64 | 771 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 2 - Cuota soportada |  | 15 enteros 2 decimales
65 | 788 | 17 | N |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 2 - Cuota derivada Regimen Simplificado [K2] |  | 15 enteros 2 decimales
66 | 805 | 2 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 3 - Código
67 | 807 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 3 - Volumen  ingresos |  | 15 enteros 2 decimales
68 | 824 | 6 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 3 - Indice cuota |  | 1 entero 5 decimales
69 | 830 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 3 - Cuota devengada |  | 15 enteros 2 decimales
70 | 847 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 3 - Cuota soportada |  | 15 enteros 2 decimales
71 | 864 | 17 | N |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 3 - Cuota derivada Regimen Simplificado [K3] |  | 15 enteros 2 decimales
72 | 881 | 2 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 4 - Código
73 | 883 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 4 - Volumen  ingresos |  | 15 enteros 2 decimales
74 | 900 | 6 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 4 - Indice cuota |  | 1 entero 5 decimales
75 | 906 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 4 - Cuota devengada |  | 15 enteros 2 decimales
76 | 923 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 4 - Cuota soportada |  | 15 enteros 2 decimales
77 | 940 | 17 | N |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 4 - Cuota derivada Regimen Simplificado [K4] |  | 15 enteros 2 decimales
78 | 957 | 2 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 5 - Código
79 | 959 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 5 - Volumen  ingresos |  | 15 enteros 2 decimales
80 | 976 | 6 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 5 - Indice cuota |  | 1 entero 5 decimales
81 | 982 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 5 - Cuota devengada |  | 15 enteros 2 decimales
82 | 999 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 5 - Cuota soportada |  | 15 enteros 2 decimales
83 | 1016 | 17 | N |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 5 - Cuota derivada Regimen Simplificado [K5] |  | 15 enteros 2 decimales
84 | 1033 | 17 | N |  | 6. Operaciones Reg. Simplificado - IVA devengado - Suma cuotas actividades no agríc., ganad. y forest.  [74] |  | 15 enteros 2 decimales
85 | 1050 | 17 | N |  | 6. Operaciones Reg. Simplificado - IVA devengado - Suma cuotas  actividades agríc., ganad. y forest. [75] |  | 15 enteros 2 decimales
86 | 1067 | 17 | N |  | 6. Operaciones Reg. Simplificado - IVA devengado en adquisiciones intracomunitarias [76] |  | 15 enteros 2 decimales
87 | 1084 | 17 | N |  | 6. Operaciones Reg. Simplificado - IVA devengado - IVA devengado por inversión del sujeto pasivo [77] |  | 15 enteros 2 decimales
88 | 1101 | 17 | N |  | 6. Operaciones Reg. Simplificado - IVA devengado - IVA devengado en entregas de activos fijos [78] |  | 15 enteros 2 decimales
89 | 1118 | 17 | N |  | 6. Operaciones Reg. Simplificado - IVA devengado - Total cuota resultante [79] |  | 15 enteros 2 decimales
90 | 1135 | 17 | N |  | 6. Operaciones Reg. Simplificado - Deducciones - IVA soportado en adquisicion de activos fijos [80] |  | 15 enteros 2 decimales
91 | 1152 | 17 | N |  | 6. Operaciones Reg. Simplificado - Deducciones - Regularización de bienes de inversion [81] |  | 15 enteros 2 decimales
92 | 1169 | 17 | N |  | 6. Operaciones Reg. Simplificado - Deducciones - Suma de deducciones [82] |  | 15 enteros 2 decimales
93 | 1186 | 17 | N |  | 6. Operaciones Reg. Simplificado - Resultado régimen simplificado [83] |  | 15 enteros 2 decimales
94 | 1203 | 1 | An | C | 6. Operaciones Reg. Simplificado - Actividad 1 - Epigrafe IAE
 - Indicador auxiliar de actividad en el caso de epígrafes 691.9 y 722 |  | blanco, "1" o "2" (Nota 2)
95 | 1204 | 1 | An | C | 6. Operaciones Reg. Simplificado - Actividad 2 - Epigrafe IAE
 - Indicador auxiliar de actividad en el caso de epígrafes 691.9 y 722 |  | blanco, "1" o "2" (Nota 2)
96 | 1205 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - Reducción aplicable por actividad realizada en municipios afectados por la DANA |  | 15 enteros 2 decimales
97 | 1222 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 1 - Reducciones (total) |  | 15 enteros 2 decimales
98 | 1239 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - Reducción aplicable por actividad realizada en municipios afectados por la DANA |  | 15 enteros 2 decimales
99 | 1256 | 17 | Num | C | 6. Operaciones Reg. Simplificado - Actividad 2 - Reducciones (total) |  | 15 enteros 2 decimales
100 | 1273 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 1 - Reducción aplicable por actividad realizada en municipios afectados por la DANA |  | 15 enteros 2 decimales
101 | 1290 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 2 - Reducción aplicable por actividad realizada en municipios afectados por la DANA |  | 15 enteros 2 decimales
102 | 1307 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 3 - Reducción aplicable por actividad realizada en municipios afectados por la DANA |  | 15 enteros 2 decimales
103 | 1324 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 4 - Reducción aplicable por actividad realizada en municipios afectados por la DANA |  | 15 enteros 2 decimales
104 | 1341 | 17 | Num |  | 6. Operaciones Reg. Simplificado - Act. Agrícolas y Ganaderas - Actividad 5 - Reducción aplicable por actividad realizada en municipios afectados por la DANA |  | 15 enteros 2 decimales
105 | 1358 | 150 | An |  | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
106 | 1508 | 12 | An |  | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39005000>"
TOTAL |  | 1519 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 2:
La cumplimentación de estos campos deberá realizarse de la siguiente forma:
 | blanco | Cuando el epígrafe de la actividad correspondiente sea distinto de 691.9 ó 722 (o no esté cumplimentada esa actividad).
Epígrafe I.A.E.: 691.9
 | 1 | Actividad: Reparación de calzado.
 | 2 | Actividad: Reparación de otros bienes de consumo n.c.o.p. (excepto reparación de calzado, restauración de obras de arte, muebles, antigüedades e instrumentos musicales).
Epígrafe I.A.E.: 722
 | 1 | Actividad: Transporte de mercancías por carretera, excepto residuos.
 | 2 | Actividad: Transporte de residuos por carretera.

# Pág. 6

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo.. | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | Página. | OBLIGATORIO. | Constante "06000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | 7. Resultado liquidación anual - Regularización cuotas art. 80.Cinco.5ª LIVA [658] |  | 15 enteros 2 decimales
7 | 30 | 17 | N | 7. Resultado liquidación anual - Suma de resultados [84] |  | 15 enteros 2 decimales
8 | 47 | 17 | Num | 7. Resultado liquidación anual - IVA a la importación liquidado por la Aduana (sólo sujetos pasivos con opción de diferimiento) [659] |  | 15 enteros 2 decimales
9 | 64 | 17 | Num | 7. Resultado liquidación anual - Compensación de cuotas ejercicio anterior [85] |  | 15 enteros 2 decimales
10 | 81 | 17 | N | 7. Resultado liquidación anual - Resultado de la liquidación [86] |  | 15 enteros 2 decimales
11 | 98 | 5 | Num | 8. Tributación razón de territorio - Administraciones - Territorio común [87] |  | 3 enteros 2 decimales
12 | 103 | 5 | Num | 8. Tributación razón de territorio - Administraciones - Álava [88] |  | 3 enteros 2 decimales
13 | 108 | 5 | Num | 8. Tributación razón de territorio - Administraciones - Guipúzcoa [89] |  | 3 enteros 2 decimales
14 | 113 | 5 | Num | 8. Tributación razón de territorio - Administraciones - Vizcaya [90] |  | 3 enteros 2 decimales
15 | 118 | 5 | Num | 8. Tributación razón de territorio - Administraciones - Navarra [91] |  | 3 enteros 2 decimales
16 | 123 | 17 | N | 8. Tributación razón de territorio - Administraciones - Regularización cuotas art. 80.Cinco.5ª LIVA [658] |  | 15 enteros 2 decimales
17 | 140 | 17 | N | 8. Tributación razón de territorio - Administraciones - Suma de resultados [84] |  | 15 enteros 2 decimales
18 | 157 | 17 | N | 8. Tributación razón de territorio - Administraciones - Resultado atribuible a territorio común [92] |  | 15 enteros 2 decimales
19 | 174 | 17 | Num | 8. Tributación razón de territorio - Administraciones - IVA a la importación liquidado por la Aduana(sólo sujetos pasivos con opción de diferimiento) [659] |  | 15 enteros 2 decimales
20 | 191 | 17 | Num | 8. Tributación razón de territorio - Administraciones - Compens. cuotas ej. anterior atrib. territ. com. [93] |  | 15 enteros 2 decimales
21 | 208 | 17 | N | 8. Tributación razón de territorio - Administraciones - Resultado liq. anual atribuible territ. comun [94] |  | 15 enteros 2 decimales
22 | 225 | 17 | Num | 9. Resultado de las liquidaciones - Total resultados a ingresar autoliquidaciones de IVA del ejercicio [95] |  | 15 enteros 2 decimales
23 | 242 | 17 | Num | 9. Resultado de las liquidaciones - Total devoluc. mensuales IVA suj. pasivos Regtro. de devolución mensual [96] |  | 15 enteros 2 decimales
24 | 259 | 17 | Num | 9. Resultado de las liquidaciones - Total devoluc. Por cuotas en la adquisicion de elementos de transporte [524] |  | 15 enteros 2 decimales
25 | 276 | 17 | Num | 9. Resultado de las liquidaciones - Resultado declaración-liquidación último periodo - A compensar [97] |  | 15 enteros 2 decimales
26 | 293 | 17 | Num | 9. Resultado de las liquidaciones - Resultado declaración-liquidación último periodo - A devolver [98] |  | 15 enteros 2 decimales
27 | 310 | 17 | Num | 9. Resultado de las liquidaciones - Cuotas pendientes de compensación generadas en el ejercicio y distintas de las incluidas en la casilla 97 [662] |  | 15 enteros 2 decimales
28 | 327 | 17 | Num | 9. Resultado de las liquidaciones - Total resultados positivos del ejercicio (modelo 322) [525] |  | 15 enteros 2 decimales
29 | 344 | 17 | Num | 9. Resultado de las liquidaciones - Total resultados negativos del ejercicio (modelo 322) [526] |  | 15 enteros 2 decimales
30 | 361 | 17 | N | 10. Volumen de operaciones - Operaciones en régimen general [99] |  | 15 enteros 2 decimales
31 | 378 | 17 | N | 10. Volumen de operaciones - Operaciones régimen especial del criterio de caja [653] |  | 15 enteros 2 decimales
32 | 395 | 17 | N | 10. Volumen de operaciones - Entregas intracomunitarias de bienes y servicios [103] |  | 15 enteros 2 decimales
33 | 412 | 17 | N | 10. Volumen de operaciones - Exportaciones y otras operaciones exentas con derecho a deducción [104] |  | 15 enteros 2 decimales
34 | 429 | 17 | N | 10. Volumen de operaciones - Operaciones exentas sin derecho a deducción [105] |  | 15 enteros 2 decimales
35 | 446 | 17 | N | 10. Volumen de operaciones - Operaciones no sujetas por reglas de localización (excepto las incluidas en la casilla 126) [110] |  | 15 enteros 2 decimales
36 | 463 | 17 | N | 10. Volumen de operaciones - Operaciones sujetas con inversión del sujeto pasivo [125] |  | 15 enteros 2 decimales
37 | 480 | 17 | N | 10. Volumen de operaciones - OSS. Operaciones no sujetas por reglas de localización acogidas a la OSS [126] |  | 15 enteros 2 decimales
38 | 497 | 17 | N | 10. Volumen de operaciones - OSS. Operaciones sujetas y acogidas a la OSS [127] |  | 15 enteros 2 decimales
39 | 514 | 17 | N | 10. Volumen de operaciones - Operaciones intragrupo valoradas conforme a lo dispuesto en los arts. 78 y 79 LIVA [128] |  | 15 enteros 2 decimales
40 | 531 | 17 | N | 10. Volumen de operaciones - Operaciones en régimen simplificado [100] |  | 15 enteros 2 decimales
41 | 548 | 17 | N | 10. Volumen de operaciones - Operaciones en régimen especias de la agricultura, ganadería y pesca [101] |  | 15 enteros 2 decimales
42 | 565 | 17 | N | 10. Volumen de operaciones - Operaciones en régimen especial del recargo de equivalencia [102]. |  | 15 enteros 2 decimales
43 | 582 | 17 | N | 10. Volumen de operaciones - Operaciones en régimen especias de bienes usados, objetos de arte, antigüedades y objetos de colección [227]. |  | 15 enteros 2 decimales
44 | 599 | 17 | N | 10. Volumen de operaciones - Operaciones en régimen especial de agencias de viajes [228]. |  | 15 enteros 2 decimales
45 | 616 | 17 | N | 10. Volumen de operaciones - Entrega de bienes inmuebles y operaciones financieras no habituales [106] |  | 15 enteros 2 decimales
46 | 633 | 17 | N | 10. Volumen de operaciones - Entrega de bienes de inversion [107] |  | 15 enteros 2 decimales
47 | 650 | 17 | N | 10. Volumen de operaciones - Total volumen de operaciones [108] |  | 15 enteros 2 decimales
48 | 667 | 150 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
49 | 817 | 12 | An | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39006000>"
TOTAL |  | 828 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 7

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | C | Página | OBLIGATORIO. | Constante "07000"
4 | 11 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A |  | Indicador de página complementaria. |  | Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 17 | N |  | 11. Oper. Específicas - Adquisiciones interiores exentas [230] |  | 15 enteros 2 decimales
7 | 30 | 17 | N |  | 11. Oper. específicas - Adquisiciones intracomunitarias exentas [109] |  | 15 enteros 2 decimales
8 | 47 | 17 | N |  | 11. Oper. Específicas - Importaciones exentas [231] |  | 15 enteros 2 decimales
9 | 64 | 17 | N |  | 11. Oper. Específicas - Bases imponibles IVA soportado no deducible [232] |  | 15 enteros 2 decimales
10 | 81 | 17 | N |  | 11. Oper. específicas - Oper. sujetas que originan el derecho a la devolución mensual [111] |  | 15 enteros 2 decimales
11 | 98 | 17 | N |  | 11. Oper. específicas - Entrega interior bienes devengada por invers. sujet. pasiv. operac. triangul. [113] |  | 15 enteros 2 decimales
12 | 115 | 17 | N |  | 11. Oper. Específicas - Servicios localizados en el territorio de aplicación del impuesto por inversión del sujeto pasivo [523] |  | 15 enteros 2 decimales
13 | 132 | 17 | N |  | 11. Oper. Específicas - Importes de las entregas de bienes regimen especial criterio caja - Base imponible [654] |  | 15 enteros 2 decimales
14 | 149 | 17 | N |  | 11. Oper. Específicas - Importes de las entregas de bienes regimen especial criterio caja - Cuota [655] |  | 15 enteros 2 decimales
15 | 166 | 17 | N |  | 11. Oper. Específicas - Importes de las adquisiciones de bienes regimen especial criterio caja - Base imponible [656] |  | 15 enteros 2 decimales
16 | 183 | 17 | N |  | 11. Oper. Específicas - Importes de las adquisiciones de bienes regimen especial criterio caja - Cuota [657] |  | 15 enteros 2 decimales
17 | 200 | 40 | An | C | 12. Prorratas - 1 - Actividad desarrollada
18 | 240 | 3 | An | C | 12. Prorratas - 1 - Código CNAE [114] |  | Incluido en fichero CNAE.TXT.
19 | 243 | 17 | Num | C | 12. Prorratas - 1 - Importe de operaciones [115] |  | 15 enteros 2 decimales
20 | 260 | 17 | Num | C | 12. Prorratas - 1 - Importe de operaciones con derecho a deducción [116] |  | 15 enteros 2 decimales
21 | 277 | 1 | An | C | 12. Prorratas - 1 - Tipo de prorrata [117] |  | "G", "E" o blanco.
22 | 278 | 5 | Num | C | 12. Prorratas - 1 - % de prorrata [118] |  | 3 enteros 2 decimales, menor o igual que 100.
23 | 283 | 40 | An | C | 12. Prorratas - 2 - Actividad desarrollada
24 | 323 | 3 | An | C | 12. Prorratas - 2 - Código CNAE [114] |  | Incluido en fichero CNAE.TXT.
25 | 326 | 17 | Num | C | 12. Prorratas - 2 - Importe de operaciones [115] |  | 15 enteros 2 decimales
26 | 343 | 17 | Num | C | 12. Prorratas - 2 - Importe de operaciones con derecho a deducción [116] |  | 15 enteros 2 decimales
27 | 360 | 1 | An | C | 12. Prorratas - 2 - Tipo de prorrata [117] |  | "G", "E" o blanco.
28 | 361 | 5 | Num | C | 12. Prorratas - 2 - % de prorrata [118] |  | 3 enteros 2 decimales, menor o igual que 100.
29 | 366 | 40 | An | C | 12. Prorratas - 3 - Actividad desarrollada
30 | 406 | 3 | An | C | 12. Prorratas - 3 - Código CNAE [114] |  | Incluido en fichero CNAE.TXT.
31 | 409 | 17 | Num | C | 12. Prorratas - 3 - Importe de operaciones [115] |  | 15 enteros 2 decimales
32 | 426 | 17 | Num | C | 12. Prorratas - 3 - Importe de operaciones con derecho a deducción [116] |  | 15 enteros 2 decimales
33 | 443 | 1 | An | C | 12. Prorratas - 3 - Tipo de prorrata [117] |  | "G", "E" o blanco.
34 | 444 | 5 | Num | C | 12. Prorratas - 3 - % de prorrata [118] |  | 3 enteros 2 decimales, menor o igual que 100.
35 | 449 | 40 | An | C | 12. Prorratas - 4 - Actividad desarrollada
36 | 489 | 3 | An | C | 12. Prorratas - 4 - Código CNAE [114] |  | Incluido en fichero CNAE.TXT.
37 | 492 | 17 | Num | C | 12. Prorratas - 4 - Importe de operaciones [115] |  | 15 enteros 2 decimales
38 | 509 | 17 | Num | C | 12. Prorratas - 4 - Importe de operaciones con derecho a deducción [116] |  | 15 enteros 2 decimales
39 | 526 | 1 | An | C | 12. Prorratas - 4 - Tipo de prorrata [117] |  | "G", "E" o blanco.
40 | 527 | 5 | Num | C | 12. Prorratas - 4 - % de prorrata [118] |  | 3 enteros 2 decimales, menor o igual que 100.
41 | 532 | 40 | An | C | 12. Prorratas - 5 - Actividad desarrollada
42 | 572 | 3 | An | C | 12. Prorratas - 5 - Código CNAE [114] |  | Incluido en fichero CNAE.TXT.
43 | 575 | 17 | Num | C | 12. Prorratas - 5 - Importe de operaciones [115] |  | 15 enteros 2 decimales
44 | 592 | 17 | Num | C | 12. Prorratas - 5 - Importe de operaciones con derecho a deducción [116] |  | 15 enteros 2 decimales
45 | 609 | 1 | An | C | 12. Prorratas - 5 - Tipo de prorrata [117] |  | "G", "E" o blanco.
46 | 610 | 5 | Num | C | 12. Prorratas - 5 - % de prorrata [118] |  | 3 enteros 2 decimales, menor o igual que 100.
47 | 615 | 150 | An |  | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
48 | 765 | 12 | An | C | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39007000>"
TOTAL |  | 776 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 8

 | Agencia Tributaria
Modelo 390 |  | Diseño de registro. Castellano.
vers.1.03 |  | IVA
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo | OBLIGATORIO | Constante "390"
3 | 6 | 5 | Num | Página | OBLIGATORIO. | Constante "08000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes y servic. - Base imponible [139] |  | 15 enteros 2 decimales
7 | 30 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes y servic. - Cuota deducible [140] |  | 15 enteros 2 decimales
8 | 47 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes inversión - Base imponible [141] |  | 15 enteros 2 decimales
9 | 64 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Operac. Interiores - Bienes inversión - Cuota deducible [142] |  | 15 enteros 2 decimales
10 | 81 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes corrientes - Base imponible [143] |  | 15 enteros 2 decimales
11 | 98 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes corrientes - Cuota deducible [144] |  | 15 enteros 2 decimales
12 | 115 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes inversión - Base imponible [145] |  | 15 enteros 2 decimales
13 | 132 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Importaciones - Bienes inversión - Cuota deducible [146] |  | 15 enteros 2 decimales
14 | 149 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes corrientes - Base imponible [147] |  | 15 enteros 2 decimales
15 | 166 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun.  - Bienes corrientes - Cuota deducible [148] |  | 15 enteros 2 decimales
16 | 183 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes inversión - Base imponible [149] |  | 15 enteros 2 decimales
17 | 200 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - IVA ded. Adquisic. intracomun. - Bienes inversión - Cuota deducible [150] |  | 15 enteros 2 decimales
18 | 217 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - Compensac. rég. especial agric./ganad./pesca - Base impon. [151] |  | 15 enteros 2 decimales
19 | 234 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - Compensac. rég. especial agric./ganad./pesca - Cuota deduc. [152] |  | 15 enteros 2 decimales
20 | 251 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - Rectificación de deducciones - Base impon.  [640] |  | 15 enteros 2 decimales
21 | 268 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - Rectificación de deducciones - Cuota deduc. [153] |  | 15 enteros 2 decimales
22 | 285 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - Regularización de inversiones [154] |  | 15 enteros 2 decimales
23 | 302 | 17 | N | 13. Reg. Deducc. Diferenc.- 1 - Suma de deducciones [155] |  | 15 enteros 2 decimales
24 | 319 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes y servic. - Base imponible [156] |  | 15 enteros 2 decimales
25 | 336 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes y servic. - Cuota deducible [157] |  | 15 enteros 2 decimales
26 | 353 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes inversión - Base imponible [158] |  | 15 enteros 2 decimales
27 | 370 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Operac. Interiores - Bienes inversión - Cuota deducible [159] |  | 15 enteros 2 decimales
28 | 387 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes corrientes - Base imponible [160] |  | 15 enteros 2 decimales
29 | 404 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes corrientes - Cuota deducible [161] |  | 15 enteros 2 decimales
30 | 421 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes inversión - Base imponible [162] |  | 15 enteros 2 decimales
31 | 438 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Importaciones - Bienes inversión - Cuota deducible [163] |  | 15 enteros 2 decimales
32 | 455 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes corrientes - Base imponible [164] |  | 15 enteros 2 decimales
33 | 472 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun.  - Bienes corrientes - Cuota deducible [165] |  | 15 enteros 2 decimales
34 | 489 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes inversión - Base imponible [166] |  | 15 enteros 2 decimales
35 | 506 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - IVA ded. Adquisic. intracomun. - Bienes inversión - Cuota deducible [167] |  | 15 enteros 2 decimales
36 | 523 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - Compensac. rég. especial agric./ganad./pesca - Base impon. [168] |  | 15 enteros 2 decimales
37 | 540 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - Compensac. rég. especial agric./ganad./pesca - Cuota deduc. [169] |  | 15 enteros 2 decimales
38 | 557 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - Rectificación de deducciones - Base impon. [641] |  | 15 enteros 2 decimales
39 | 574 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - Rectificación de deducciones - Cuota decuc. [170] |  | 15 enteros 2 decimales
40 | 591 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - Regularización de inversiones [171] |  | 15 enteros 2 decimales
41 | 608 | 17 | N | 13. Reg. Deducc. Diferenc.- 2 - Suma de deducciones [172] |  | 15 enteros 2 decimales
42 | 625 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Operac. Interiores - Bienes y servic. - Base imponible [173] |  | 15 enteros 2 decimales
43 | 642 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Operac. Interiores - Bienes y servic. - Cuota deducible [174] |  | 15 enteros 2 decimales
44 | 659 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Operac. Interiores - Bienes inversión - Base imponible [175] |  | 15 enteros 2 decimales
45 | 676 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Operac. Interiores - Bienes inversión - Cuota deducible [176] |  | 15 enteros 2 decimales
46 | 693 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Importaciones - Bienes corrientes - Base imponible [177] |  | 15 enteros 2 decimales
47 | 710 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Importaciones - Bienes corrientes - Cuota deducible [178] |  | 15 enteros 2 decimales
48 | 727 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Importaciones - Bienes inversión - Base imponible [179] |  | 15 enteros 2 decimales
49 | 744 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Importaciones - Bienes inversión - Cuota deducible [180] |  | 15 enteros 2 decimales
50 | 761 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Adquisic. intracomun. - Bienes corrientes - Base imponible [181] |  | 15 enteros 2 decimales
51 | 778 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Adquisic. intracomun.  - Bienes corrientes - Cuota deducible [182] |  | 15 enteros 2 decimales
52 | 795 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Adquisic. intracomun. - Bienes inversión - Base imponible [183] |  | 15 enteros 2 decimales
53 | 812 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - IVA ded. Adquisic. intracomun. - Bienes inversión - Cuota deducible [184] |  | 15 enteros 2 decimales
54 | 829 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - Compensac. rég. especial agric./ganad./pesca - Base impon. [185] |  | 15 enteros 2 decimales
55 | 846 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - Compensac. rég. especial agric./ganad./pesca - Cuota deduc. [186] |  | 15 enteros 2 decimales
56 | 863 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - Rectificación de deducciones - Base impon. [642] |  | 15 enteros 2 decimales
57 | 880 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - Rectificación de deducciones - Cuota deduc. [187] |  | 15 enteros 2 decimales
58 | 897 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - Regularización de inversiones [188] |  | 15 enteros 2 decimales
59 | 914 | 17 | N | 13. Reg. Deducc. Diferenc.- 3 - Suma de deducciones [189] |  | 15 enteros 2 decimales
60 | 931 | 150 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
61 | 1081 | 12 | An | Indentificador de Fin de registro | OBLIGATORIO | Constante "</T39008000>"
TOTAL |  | 1092 | POSICIONES
Nota1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.