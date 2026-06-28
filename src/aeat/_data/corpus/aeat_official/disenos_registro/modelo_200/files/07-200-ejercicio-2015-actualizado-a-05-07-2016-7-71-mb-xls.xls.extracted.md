# DP200000

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 17 | An | Constante. <T + modelo + discriminante (*) + Ejercicio devengo + periodo + tipo + > |  | "<T200020150A0000>"
2 | 18 | 5 | An | Constante |  | "<AUX>"
3 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
4 | 93 | 4 | An | Versión del programa (**)
5 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos
6 | 101 | 9 | An | NIF Empresa Desarrollo (**)
7 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos
8 | 323 | 6 | An | Constante |  | "</AUX>"
12 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
13 | *** | 18 | An | Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "</T200020150A0000>"
14 | *** | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total |  | Variable
 |  |  |  | (*) NOTA. Valor discriminante: "0" Normal, Abreviado y PYMES; "A" Aseguradoras; "E" Entidades de crédito; "I" Inversión colectiva; "G" Garantía recíproca.
 |  |  |  | Debe rellenarse en función del estado de cuentas que se cumplimenta.
 |  |  |  | (**) A cumplimentar por las entidades desarrolladoras (EEDD):
 |  |  |  | Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
 |  |  |  | NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
 | ATENCIÓN: Los ficheros de declaración del modelo 200 generados según este Diseño de Registro deben respetar el orden de las páginas indicado.

# DP200001

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "010"
4 | 9 | 1 | An | Fin de identificador de modelo y página. Constante ">". | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria. |  | En blanco
6 | 11 | 4 | Num | Periodo Impositivo - Año inicio
7 | 15 | 2 | Num | Periodo Impositivo - Mes inicio
8 | 17 | 2 | Num | Periodo Impositivo - Día Inicio
9 | 19 | 4 | Num | Periodo Impositivo - Año final
10 | 23 | 2 | Num | Periodo Impositivo - Mes final
11 | 25 | 2 | Num | Periodo Impositivo - Día final
12 | 27 | 1 | Num | Identificación - Tipo de ejercicio |  | "1", "2" ó "3"
13 | 28 | 4 | Num | Identificación - C.N.A.E.  Actividad principal |  | Incluido en el fichero CNAE.TXT.
14 | 32 | 9 | An | Identificación - NIF
15 | 41 | 40 | An | Identificación - Apellidos y nombre o Razón Social
16 | 81 | 9 | An | Identificación - Teléfono 1
17 | 90 | 9 | An | Identificación - Teléfono 2
18 | 99 | 4 | Num | Ejercicio
19 | 103 | 1 | Num | Entidad sin ánimo de lucro acogida régimen fiscal Título II Ley 49/2002 [00001]
20 | 104 | 1 | Num | Entidad parcialmente exenta [00002]
21 | 105 | 1 | Num | Sociedad de inversión de capital variable o fondo de inversión de carácter financiero [00003]
22 | 106 | 1 | Num | Sociedad de inversión inmobiliaria o fondo de inversión inmobiliaria [00004]
23 | 107 | 1 | Num | Comunidades titulares de montes vecinales en mano común [00005]
24 | 108 | 1 | Num | Entidad de tenencia de valores extranjeros [00011]
25 | 109 | 1 | Num | Agrupación de interés económico española o U.T.E. [00013]
26 | 110 | 1 | Num | Agrupación europea de  interés económico [00014]
27 | 111 | 1 | Num | Cooperativa protegida [00017]
28 | 112 | 1 | Num | Cooperativa especialmente protegida [00018]
29 | 113 | 1 | Num | Resto cooperativas [00019]
30 | 114 | 1 | Num | Establecimiento permanente [00021]
31 | 115 | 1 | Num | Gran empresa [00023]
32 | 116 | 1 | Num | Entidad de crédito [00024]
33 | 117 | 1 | Num | Entidad aseguradora [00025]
34 | 118 | 1 | Num | Entidades de capital-riesgo [00031]
35 | 119 | 1 | Num | Sociedades desarrollo industrial regional [00032]
36 | 120 | 1 | Num | Sociedad de garantía recíproca o de reafianzamiento [00036]
37 | 121 | 1 | Num | Fondo de Pensiones Real Decreto Legislativo 1/2002 de 29 de noviembre [00048]
38 | 122 | 1 | Num | Mutua de seguros o Mutualidad de previsión social [00058]
39 | 123 | 1 | Num | Fondos o activos de titulización [00060]
40 | 124 | 1 | Num | Entidad patrimonial [00066]
41 | 125 | 1 | Num | Incentivos entidad de reducida dimensión ( cap XI, tít. VII LIS )  [00006]
42 | 126 | 1 | Num | Entidad ZEC [00015]
43 | 127 | 1 | Num | Régimen entidades navieras en función del tonelaje [00022]
44 | 128 | 1 | Num | Tributación conjunta Estado/Diput.Cdad.Forales [00028]
45 | 129 | 1 | Num | Entidades sometidas a normativa foral [00047]
46 | 130 | 1 | Num | Aplicación rég.especial fusiones, escisiones, aportaciones activos y canjes valores (Cap.VII, Tit. VII)  [00035]
47 | 131 | 1 | Num | Regímenes especiales de normativa foral [00049]
48 | 132 | 1 | Num | Régimen especial Canarias [00029]
49 | 133 | 1 | Num | Régimen especial minería [00033]
50 | 134 | 1 | Num | Régimen especial hidrocarburos [00034]
51 | 135 | 1 | Num | Entidad dedicada al arrend. viviendas [00038]
52 | 136 | 1 | Num | Entidad en rég. Atribuc. de rentas constituida en el extranjero con presencia en territorio español [00046]
53 | 137 | 1 | Num | SOCIMI [00012]
54 | 138 | 1 | Num | Régimen fiscal entrada SOCIMI [00064]
55 | 139 | 1 | Num | Régimen fiscal salida SOCIMI [00057]
56 | 140 | 1 | Num | Otros regímenes especiales [00020]
57 | 141 | 1 | Num | Reg.fiscal de operac.de aportación de activos a sdades. para la gestion de activos (ley 8/2012)  [00062]
58 | 142 | 1 | Num | Tipo gravamen reducido mant. o creación empleo (DT 22ª y 34ª k) LIS)  [00056]
59 | 143 | 1 | Num | Imputación en base imponible rentas positivas art. 100 LIS   [00007]
60 | 144 | 1 | Num | Entidad dominante de grupo fiscal [00009]
61 | 145 | 1 | Num | Entidad dependiente de grupo fiscal [00010]
62 | 146 | 1 | Num | Opción  art. 46.2  LIS  [00016]
63 | 147 | 1 | Num | Entidad  inactiva  [00026]
64 | 148 | 1 | Num | Base imponible negativa o cero [00027]
65 | 149 | 1 | Num | Transmisión elementos patrimoniales arts. 27.2.d) y 77.1 L.I.S. [00030]
66 | 150 | 1 | Num | Entidad que forma parte de un grupo mercantil (art. 42 del Cód. Comercio) [00039]
67 | 151 | 1 | Num | Obligación información DT 5ª RIS [00043]
68 | 152 | 1 | Num | Obligación información art. 14 RIS [00067]
69 | 153 | 1 | Num | Documento normalizado art. 16.4 RIS  [00068]
70 | 154 | 1 | Num | Obligación información operaciones vinculadas (art. 13.4 RIS)  [00069]
71 | 155 | 1 | Num | Inversiones anticipadas - reserva inversiones en Canarias (art. 27.11 Ley 19/1994) [00045]
72 | 156 | 1 | Num | Tipo de gravamen reducido para entidades de nueva creción  (DT 22ª LIS) [00063]
73 | 157 | 1 | Num | Tipo gravamen reducido para entid.de nueva creación (art. 29.1 LIS)  [00071]
74 | 158 | 1 | Num | Opción  art. 39.2 y 39.3 LIS  [00059]
75 | 159 | 1 | Num | Bonificación personal investigador (RD 475/2014) [00065]
76 | 160 | 1 | Num | Balance y ECPN 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
77 | 161 | 1 | Num | Pérdidas y ganancias 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
78 | 162 | 1 | Num | Estados de cuentas de Instituciones de inversión colectiva [00061]
79 | 163 | 7 | An | Nº de grupo fiscal al que pertenecen las entidades  que hayan marcado las claves 00009 ó 00010  [00040]
80 | 170 | 9 | An | N.I.F. de la sociedad representante/dominante (incluida en el grupo fiscal)
81 | 179 | 9 | An | Nº identificación de la sociedad dominante (en el caso de grupos constituidos solo por entidades depend.)
82 | 188 | 9 | Num | Personal asalariado (cifra media del ejercicio) Personal fijo [00041] |  | 7enteros 2 decimales
83 | 197 | 9 | Num | Personal asalariado (cifra media del ejercicio) Personal no fijo [00042] |  | 7enteros 2 decimales
84 | 206 | 1 | Num | Declaración complementaria
85 | 207 | 13 | Num | Nº de justificante de la declaración anterior
86 | 220 | 21 | An | D. - Nombre o Razón social - Secretario del Consejo de Administración
87 | 241 | 9 | An | N.I.F. - Secretario del Consejo de Administración
88 | 250 | 8 | Num | Fecha - Contribuyentes por el I.R.N.R. |  | AAAAMMDD
89 | 258 | 36 | An | Declaración representantes legales entidad - 1 - Nombre y apellidos
90 | 294 | 9 | An | Declaración representantes legales entidad - 1 - N.I.F
91 | 303 | 8 | Num | Declaración representantes legales entidad - 1 - Fecha Poder |  | AAAAMMDD
92 | 311 | 12 | An | Declaración representantes legales entidad - 1 - Notaría
93 | 323 | 36 | An | Declaración representantes legales entidad - 2 - Nombre y apellidos
94 | 359 | 9 | An | Declaración representantes legales entidad - 2 - N.I.F
95 | 368 | 8 | Num | Declaración representantes legales entidad - 2 - Fecha Poder |  | AAAAMMDD
96 | 376 | 12 | An | Declaración representantes legales entidad - 2 - Notaría
97 | 388 | 36 | An | Declaración representantes legales entidad - 3 - Nombre y apellidos
98 | 424 | 9 | An | Declaración representantes legales entidad - 3 - N.I.F
99 | 433 | 8 | Num | Declaración representantes legales entidad - 3 - Fecha Poder |  | AAAAMMDD
100 | 441 | 12 | An | Declaración representantes legales entidad - 3 - Notaría
101 | 453 | 21 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia
102 | 474 | 20 | An | Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
103 | 494 | 50 | An | Nombre y Apellidos de la persona de contacto para incidencias
104 | 544 | 9 | Num | Teléfono fijo de contacto para incidencias
105 | 553 | 9 | Num | Teléfono móvil de contacto para incidencias
106 | 562 | 50 | An | Dirección de correo electrónico para incidencias
107 | 612 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
108 | 625 | 10 | An | Identificador de fin de Registro. | OBLIGATORIO | </T200010>
Total: |  | 634
NOTA: Los importes son de 15 enteros (o N + 14) y 2 decimales

# DP200002

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo |  | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. |  | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. |  | Constante "200"
3 | 6 | 3 | An | C | Página. |  | Constante "020"
4 | 9 | 1 | An | C | Fin de identificador de modelo y página. |  | Constante ">"
5 | 10 | 1 | An | C | Indicador de página complementaria. |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 11 | 9 | An | C | A. Relación de administradores .1 - N.I.F.
7 | 20 | 1 | A | C | A. Relación de administradores. 1 - F/J |  | "F" o "J"
8 | 21 | 1 | Num | C | A. Relación de administradores. 1 - RPTE. |  | ( "0", "1")
9 | 22 | 40 | An | C | A. Relación de administradores. 1 - Apellidos y nombre / Razón social
10 | 62 | 17 | An | C | A. Relación de administradores. 1 - Domicilio fiscal
11 | 79 | 2 | An | C | A. Relación de administradores .1 - Código Provincial
12 | 81 | 9 | An | C | A. Relación de administradores. 2 - N.I.F.
13 | 90 | 1 | A | C | A. Relación de administradores. 2 - F/J |  | "F" o "J"
14 | 91 | 1 | Num | C | A. Relación de administradores. 2 - RPTE. |  | ( "0", "1")
15 | 92 | 40 | An | C | A. Relación de administradores. 2 - Apellidos y nombre / Razón social
16 | 132 | 17 | An | C | A. Relación de administradores. 2 - Domicilio fiscal
17 | 149 | 2 | An | C | A. Relación de administradores. 2 - Código Provincial
18 | 151 | 9 | An | C | A. Relación de administradores. 3 - N.I.F.
19 | 160 | 1 | A | C | A. Relación de administradores. 3 - F/J |  | "F" o "J"
20 | 161 | 1 | Num | C | A. Relación de administradores. 3 - RPTE. |  | ( "0", "1")
21 | 162 | 40 | An | C | A. Relación de administradores. 3 - Apellidos y nombre / Razón social
22 | 202 | 17 | An | C | A. Relación de administradores. 3 - Domicilio fiscal
23 | 219 | 2 | An | C | A. Relación de administradores. 3 - Código Provincial
24 | 221 | 9 | An | C | A. Relación de administradores. 4 - N.I.F.
25 | 230 | 1 | A | C | A. Relación de administradores. 4 - F/J |  | "F" o "J"
26 | 231 | 1 | Num | C | A. Relación de administradores. 4 - RPTE. |  | ( "0", "1")
27 | 232 | 40 | An | C | A. Relación de administradores. 4 - Apellidos y nombre / Razón social
28 | 272 | 17 | An | C | A. Relación de administradores. 4 - Domicilio fiscal
29 | 289 | 2 | An | C | A. Relación de administradores. 4 - Código Provincial
30 | 291 | 9 | An | C | A. Relación de administradores. 5 - N.I.F.
31 | 300 | 1 | A | C | A. Relación de administradores. 5 - F/J |  | "F" o "J"
32 | 301 | 1 | Num | C | A. Relación de administradores. 5 - RPTE. |  | ( "0", "1")
33 | 302 | 40 | An | C | A. Relación de administradores. 5 -  Apellidos y nombre / Razón social
34 | 342 | 17 | An | C | A. Relación de administradores. 5 - Domicilio fiscal
35 | 359 | 2 | An | C | A. Relación de administradores. 5 - Código Provincial
36 | 361 | 9 | An | C | A. Relación de administradores. 6 - N.I.F.
37 | 370 | 1 | A | C | A. Relación de administradores. 6 - F/J |  | "F" o "J"
38 | 371 | 1 | Num | C | A. Relación de administradores. 6 - RPTE. |  | ( "0", "1")
39 | 372 | 40 | An | C | A. Relación de administradores. 6 - Apellidos y nombre / Razón social
40 | 412 | 17 | An | C | A. Relación de administradores. 6 - Domicilio fiscal
41 | 429 | 2 | An | C | A. Relación de administradores. 6 - Código Provincial
42 | 431 | 15 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada - N.I.F.
43 | 446 | 30 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada - Nombre o razón social
44 | 476 | 2 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada - Código provincia / país
45 | 478 | 5 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la declarante - Porcentaje de participación
46 | 483 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la declarante - Valor nominal total de la participación
47 | 500 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
48 | 517 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
49 | 534 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - a) Corrección de valor pérdidas y ganancias ejercicio
50 | 551 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - b) Reversión de pérdidas por deterioro de valores (D.T. 16ªLIS)
51 | 568 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - c) Eliminación del deterioro contable incluido en P y G (art.13.2b) LIS)
52 | 585 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - d) Efecto corrección valorativa en la BI del ejercicio
53 | 602 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - e) Saldo de correcciones fiscales (art. 12.3 RDL 4/2004) pendientes a fin de ejercicio
54 | 619 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales participada - Capital
55 | 636 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales participada - Reservas y otras partidas de fondos propios
56 | 653 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales participada - Otras partidas del patrimonio neto
57 | 670 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales participada - Resultado del último ejercicio
58 | 687 | 15 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada - N.I.F.
59 | 702 | 30 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada - Nombre o razón social
60 | 732 | 2 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada - Código provincia / país
61 | 734 | 5 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la declarante - Porcentaje de participación
62 | 739 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la declarante - Valor nominal total de la participación
63 | 756 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
64 | 773 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
65 | 790 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - a) Corrección de valor pérdidas y ganancias ejercicio
66 | 807 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - b) Reversión de pérdidas por deterioro de valores (D.T. 16ªLIS)
67 | 824 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - c) Eliminación del deterioro contable incluido en P y G (art.13.2b) LIS)
68 | 841 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - d) Efecto corrección valorativa en la BI del ejercicio
69 | 858 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - e) Saldo de correcciones fiscales (art. 12.3 RDL 4/2004) pendientes a fin de ejercicio
70 | 875 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales participada - Capital
71 | 892 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales participada - Reservas y otras partidas de fondos propios
72 | 909 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales participada - Otras partidas del patrimonio neto
73 | 926 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales participada - Resultado del último ejercicio
74 | 943 | 15 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada - N.I.F.
75 | 958 | 30 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada - Nombre o razón social
76 | 988 | 2 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada - Código provincia / país
77 | 990 | 5 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la declarante - Porcentaje de participación
78 | 995 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la declarante - Valor nominal total de la participación
79 | 1012 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
80 | 1029 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
81 | 1046 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - a) Corrección de valor pérdidas y ganancias ejercicio
82 | 1063 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - b) Reversión de pérdidas por deterioro de valores (D.T. 16ªLIS)
83 | 1080 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - c) Eliminación del deterioro contable incluido en P y G (art.13.2b) LIS)
84 | 1097 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - d) Efecto corrección valorativa en la BI del ejercicio
85 | 1114 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - e) Saldo de correcciones fiscales (art. 12.3 RDL 4/2004) pendientes a fin de ejercicio
86 | 1131 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales participada - Capital
87 | 1148 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales participada - Reservas y otras partidas de fondos propios
88 | 1165 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales participada - Otras partidas del patrimonio neto
89 | 1182 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales participada - Resultado del último ejercicio
90 | 1199 | 15 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos participada - N.I.F.
91 | 1214 | 30 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos participada - Nombre o razón social
92 | 1244 | 2 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos participada - Código provincia / país
93 | 1246 | 5 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos de la declarante - Porcentaje de participación
94 | 1251 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos de la declarante - Valor nominal total de la participación
95 | 1268 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
96 | 1285 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
97 | 1302 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones valorativas - a) Corrección de valor pérdidas y ganancias ejercicio
98 | 1319 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones valorativas - b) Reversión de pérdidas por deterioro de valores (D.T. 16ªLIS)
99 | 1336 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones valorativas - c) Eliminación del deterioro contable incluido en P y G (art.13.2b) LIS)
100 | 1353 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones valorativas - d) Efecto corrección valorativa en la BI del ejercicio
101 | 1370 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones valorativas - e) Saldo de correcciones fiscales (art. 12.3 RDL 4/2004) pendientes a fin de ejercicio
102 | 1387 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos adicionales participada - Capital
103 | 1404 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos adicionales participada - Reservas y otras partidas de fondos propios
104 | 1421 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos adicionales participada - Otras partidas del patrimonio neto
105 | 1438 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos adicionales participada - Resultado del último ejercicio
106 | 1455 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - N.I.F.
107 | 1470 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - RPTE. |  | ( "0", "1")
108 | 1471 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - F/J |  | "F" o "J"
109 | 1472 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Apellidos y nombre / Razón social
110 | 1509 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Código provincia / país
111 | 1511 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Nominal
112 | 1528 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - % Particip.
113 | 1533 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - N.I.F.
114 | 1548 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - RPTE. |  | ( "0", "1")
115 | 1549 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - F/J |  | "F" o "J"
116 | 1550 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Apellidos y nombre / Razón social
117 | 1587 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Código provincia / país
118 | 1589 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Nominal
119 | 1606 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - % Particip.
120 | 1611 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - N.I.F.
121 | 1626 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - RPTE. |  | ( "0", "1")
122 | 1627 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - F/J. |  | "F" o "J"
123 | 1628 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - Apellidos y nombre / Razón social
124 | 1665 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - Código provincia / país
125 | 1667 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - Nominal
126 | 1684 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - % Particip.
127 | 1689 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - N.I.F.
128 | 1704 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - RPTE. |  | ( "0", "1")
129 | 1705 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - F/J. |  | "F" o "J"
130 | 1706 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - Apellidos y nombre / Razón social
131 | 1743 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - Código provincia / país
132 | 1745 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - Nominal
133 | 1762 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - % Particip.
134 | 1767 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - N.I.F.
135 | 1782 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - RPTE. |  | ( "0", "1")
136 | 1783 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - F/J. |  | "F" o "J"
137 | 1784 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Apellidos y nombre / Razón social.
138 | 1821 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Código provincia / país
139 | 1823 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Nominal
140 | 1840 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - % Particip.
141 | 1845 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - N.I.F.
142 | 1860 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - RPTE. |  | ( "0", "1")
143 | 1861 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - F/J. |  | "F" o "J"
144 | 1862 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Apellidos y nombre / Razón social
145 | 1899 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Código provincia / país
146 | 1901 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Nominal
147 | 1918 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - % Particip.
148 | 1923 | 5 | Num | C | B .Participaciones directas - B.2. Suma de  porcentajes de participación de personas o entidades en el capital de la  declarante inferiores al 5% o al 1% si se trata de valores que coticen en un mercado secundario organizado
149 | 1928 | 5 | Num | C | B. Participaciones directas - B.2. Suma de porcentajes de participaciones en situaciones especiales
150 | 1933 | 10 | An | C | Identificador de fin de Registro. | OBLIGATORIO | </T200020>
Total: |  | 1942

# DP200003

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "030"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Balance: Activo (I) - Activo - ACTIVO NO CORRIENTE [00101]
7 | 28 | 17 | N | Balance: Activo (I) - Activo - Inmovilizado intangible  [00102]
8 | 45 | 17 | N | Balance: Activo (I) - Activo - Desarrollo  [00103]
9 | 62 | 17 | N | Balance: Activo (I) - Activo - Concesiones  [00104]
10 | 79 | 17 | N | Balance: Activo (I) - Activo - Patentes, licencias, marcas y similares  [00105]
11 | 96 | 17 | N | Balance: Activo (I) - Activo - Fondo de comercio  [00106]
12 | 113 | 17 | N | Balance: Activo (I) - Activo - Aplicaciones informáticas  [00107]
13 | 130 | 17 | N | Balance: Activo (I) - Activo - Investigación  [00108]
14 | 147 | 17 | N | Balance: Activo (I) - Activo - Propiedad intelectual  [00700]
15 | 164 | 17 | N | Balance: Activo (I) - Activo - Derechos de emisión de gases de efecto invernadero [00701]
16 | 181 | 17 | N | Balance: Activo (I) - Activo - Otro inmovilizado intangible  [00109]
17 | 198 | 17 | N | Balance: Activo (I) - Activo - Resto  [00110]
18 | 215 | 17 | N | Balance: Activo (I) - Activo - Inmovilizado material  [00111]
19 | 232 | 17 | N | Balance: Activo (I) - Activo - Terrenos y construcciones  [00112]
20 | 249 | 17 | N | Balance: Activo (I) - Activo - Instalaciones técnicas y otro inmovilizado material  [00113]
21 | 266 | 17 | N | Balance: Activo (I) - Activo - Inmovilizado en curso y anticipos [00114]
22 | 283 | 17 | N | Balance: Activo (I) - Activo - Inversiones inmobiliarias [00115]
23 | 300 | 17 | N | Balance: Activo (I) - Activo - Terrenos [00116]
24 | 317 | 17 | N | Balance: Activo (I) - Activo - Construcciones [00117]
25 | 334 | 17 | N | Balance: Activo (I) - Activo - Inversiones en empresas del grupo y asociadas a largo plazo  [00118]
26 | 351 | 17 | N | Balance: Activo (I) - Activo - Instrumentos de patrimonio [00119]
27 | 368 | 17 | N | Balance: Activo (I) - Activo - Créditos a empresas [00120]
28 | 385 | 17 | N | Balance: Activo (I) - Activo - Valores representativos de deuda [00121]
29 | 402 | 17 | N | Balance: Activo (I) - Activo - Derivados [00122]
30 | 419 | 17 | N | Balance: Activo (I) - Activo - Otros activos financieros [00123]
31 | 436 | 17 | N | Balance: Activo (I) - Activo - Otras inversiones [00124]
32 | 453 | 17 | N | Balance: Activo (I) - Activo - Resto [00125]
33 | 470 | 17 | N | Balance: Activo (I) - Activo - Inversiones financieras a largo plazo [00126]
34 | 487 | 17 | N | Balance: Activo (I) - Activo - Instrumentos de patrimonio [00127]
35 | 504 | 17 | N | Balance: Activo (I) - Activo - Créditos a terceros [00128]
36 | 521 | 17 | N | Balance: Activo (I) - Activo - Valores representativos de deuda [00129]
37 | 538 | 17 | N | Balance: Activo (I) - Activo - Derivados [00130]
38 | 555 | 17 | N | Balance: Activo (I) - Activo - Otros activos financieros [00131]
39 | 572 | 17 | N | Balance: Activo (I) - Activo - Otras inversiones [00132]
40 | 589 | 17 | N | Balance: Activo (I) - Activo - Resto [00133]
41 | 606 | 17 | N | Balance: Activo (I) - Activo - Activos por impuesto diferido [00134]
42 | 623 | 17 | N | Balance: Activo (I) - Activo - Deudores comerciales no corrientes [00135]
43 | 640 | 17 | N | Balance: Activo (I) - Activo - ACTIVO CORRIENTE [00136]
44 | 657 | 17 | N | Balance: Activo (I) - Activo - Activos no corrientes mantenidos para la venta [00137]
45 | 674 | 17 | N | Balance: Activo (I) - Activo - Existencias [00138]
46 | 691 | 17 | N | Balance: Activo (I) - Activo - Comerciales  [00139]
47 | 708 | 17 | N | Balance: Activo (I) - Activo - Materias primas y otros aprovisionamientos [00140]
48 | 725 | 17 | N | Balance: Activo (I) - Activo - Productos en curso [00141]
49 | 742 | 17 | N | Balance: Activo (I) - Activo - Productos en curso - De ciclo largo de producción  [00142]
50 | 759 | 17 | N | Balance: Activo (I) - Activo - Productos en curso - De ciclo corto de producción  [00143]
51 | 776 | 17 | N | Balance: Activo (I) - Activo - Productos terminados [00144]
52 | 793 | 17 | N | Balance: Activo (I) - Activo - Productos terminados - De ciclo largo de producción  [00145]
53 | 810 | 17 | N | Balance: Activo (I) - Activo - Productos terminados - De ciclo corto de producción  [00146]
54 | 827 | 17 | N | Balance: Activo (I) - Activo - Subproductos, residuos y materiales recuperados [00147]
55 | 844 | 17 | N | Balance: Activo (I) - Activo - Anticipos a proveedores [00148]
56 | 861 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante </T200030>
Total: |  | 870

# DP200004

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. Constante "<T" . | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "040"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria. En blanco |  | En blanco
6 | 11 | 17 | N | Balance: Activo (II) - Activo - Deudores comerciales y otras cuentas a cobrar [00149]
7 | 28 | 17 | N | Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios [00150]
8 | 45 | 17 | N | Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios - Clientes por ventas y prestaciones de servicios a largo plazo [00151]
9 | 62 | 17 | N | Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios - Clientes por ventas y prestaciones de servicios a corto plazo [00152]
10 | 79 | 17 | N | Balance: Activo (II) - Activo - Clientes empresas del grupo y asociadas [00153]
11 | 96 | 17 | N | Balance: Activo (II) - Activo - Deudores varios [00154]
12 | 113 | 17 | N | Balance: Activo (II) - Activo - Personal [00155]
13 | 130 | 17 | N | Balance: Activo (II) - Activo - Activos por impuesto corriente [00156]
14 | 147 | 17 | N | Balance: Activo (II) - Activo - Otros créditos con las Administraciones Públicas [00157]
15 | 164 | 17 | N | Balance: Activo (II) - Activo - Accionistas (socios) por desembolsos exigidos [00158]
16 | 181 | 17 | N | Balance: Activo (II) - Activo - Otros deudores [00159]
17 | 198 | 17 | N | Balance: Activo (II) - Activo - Inversiones en empresas del grupo y asociadas a corto plazo [00160]
18 | 215 | 17 | N | Balance: Activo (II) - Activo - Instrumentos de patrimonio  [00161]
19 | 232 | 17 | N | Balance: Activo (II) - Activo - Créditos a empresas  [00162]
20 | 249 | 17 | N | Balance: Activo (II) - Activo - Valores representativos de deuda  [00163]
21 | 266 | 17 | N | Balance: Activo (II) - Activo - Derivados  [00164]
22 | 283 | 17 | N | Balance: Activo (II) - Activo - Otros activos financieros  [00165]
23 | 300 | 17 | N | Balance: Activo (II) - Activo - Otras inversiones  [00166]
24 | 317 | 17 | N | Balance: Activo (II) - Activo - Resto  [00167]
25 | 334 | 17 | N | Balance: Activo (II) - Activo - Inversiones financieras a corto plazo  [00168]
26 | 351 | 17 | N | Balance: Activo (II) - Activo - Instrumentos de patrimonio  [00169]
27 | 368 | 17 | N | Balance: Activo (II) - Activo - Créditos a empresas  [00170]
28 | 385 | 17 | N | Balance: Activo (II) - Activo - Valores representativos de deuda [00171]
29 | 402 | 17 | N | Balance: Activo (II) - Activo - Derivados [00172]
30 | 419 | 17 | N | Balance: Activo (II) - Activo - Otros activos financieros [00173]
31 | 436 | 17 | N | Balance: Activo (II) - Activo - Otras inversiones [00174]
32 | 453 | 17 | N | Balance: Activo (II) - Activo - Resto [00175]
33 | 470 | 17 | N | Balance: Activo (II) - Activo - Periodificaciones a corto plazo [00176]
34 | 487 | 17 | N | Balance: Activo (II) - Activo - Efectivo y otros activos líquidos equivalentes [00177]
35 | 504 | 17 | N | Balance: Activo (II) - Activo - Tesorería [00178]
36 | 521 | 17 | N | Balance: Activo (II) - Activo - Otros activos líquidos equivalentes [00179]
37 | 538 | 17 | N | Balance: Activo (II) - Activo - TOTAL ACTIVO [00180]
38 | 555 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante </T200040>
Total: |  | 564

# DP200005

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "050"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - PATRIMONIO NETO [00185]
7 | 28 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Fondos propios [00186]
8 | 45 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital [00187]
9 | 62 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital escriturado [00188]
10 | 79 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital no exigido [00189]
11 | 96 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Prima de emisión [00190]
12 | 113 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reservas [00191]
13 | 130 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Legal y estatutarias [00192]
14 | 147 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras reservas [00193]
15 | 164 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reserva de revalorización [00702]
16 | 181 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reserva de capitalización  [01001]
17 | 198 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reserva de nivelación   [01002]
18 | 215 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Acciones y participaciones en patrimonio propias [00194]
19 | 232 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultados de ejercicios anteriores [00195]
20 | 249 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Remanente [00196]
21 | 266 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultados negativos de ejercicios anteriores [00197]
22 | 283 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras aportaciones de socios [00198]
23 | 300 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultado del ejercicio [00199]
24 | 317 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Dividendo a cuenta [00200]
25 | 334 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros instrumentos de patrimonio neto [00201]
26 | 351 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Ajustes por cambios de valor [00202]
27 | 368 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Activos financieros disponibles para la venta [00203]
28 | 385 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Operaciones de cobertura [00204]
29 | 402 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Activos no corrientes y pasivos vinculados [00205]
30 | 419 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Diferencia de conversión [00206]
31 | 436 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros  [00207]
32 | 453 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Ajustes en patrimonio neto [00208]
33 | 470 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Subvenciones, donaciones y legados recibidos [00209]
34 | 487 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - PASIVO NO CORRIENTE [00210]
35 | 504 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Provisiones a largo plazo  [00211]
36 | 521 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Obligaciones por prestaciones a largo plazo al personal  [00212]
37 | 538 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Actuaciones medioambientales  [00213]
38 | 555 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Provisiones por reestructuración  [00214]
39 | 572 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras provisiones  [00215]
40 | 589 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deudas a largo plazo  [00216]
41 | 606 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Obligaciones y otros valores negociables  [00217]
42 | 623 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deudas con entidades de crédito  [00218]
43 | 640 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Acreedores por arrendamiento financiero  [00219]
44 | 657 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Derivados  [00220]
45 | 674 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros pasivos financieros [00221]
46 | 691 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras deudas a largo plazo [00222]
47 | 708 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deudas con empresas del grupo y asociadas a largo plazo [00223]
48 | 725 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Pasivos por impuesto diferido [00224]
49 | 742 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Periodificaciones a largo plazo [00225]
50 | 759 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Acreedores comerciales no corrientes [00226]
51 | 776 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deuda con características especiales a largo plazo [00227]
52 | 793 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200050>"
Total: |  | 802

# DP200006

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "060"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - PASIVO CORRIENTE [00228]
7 | 28 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Pasivos vinculados con activos no corrientes [00229]
8 | 45 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Provisiones a corto plazo [00230]
9 | 62 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Provisiones por derechos emisión de gases de efecto invernadero [00703]
10 | 79 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras provisiones [00704]
11 | 96 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas a corto plazo [00231]
12 | 113 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Obligaciones y otros valores negociables [00232]
13 | 130 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas con entidades de crédito [00233]
14 | 147 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Acreedores por arrendamiento financiero [00234]
15 | 164 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Derivados [00235]
16 | 181 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otros pasivos financieros [00236]
17 | 198 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras deudas a corto plazo [00237]
18 | 215 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas con empresas del grupo y asociadas a corto plazo [00238]
19 | 232 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Acreedores comerciales y otras cuentas a pagar [00239]
20 | 249 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores [00240]
21 | 266 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores - Proveedores a largo plazo [00241]
22 | 283 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores - Proveedores a corto plazo [00242]
23 | 300 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores, empresas del grupo y asociadas [00243]
24 | 317 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Acreedores varios [00244]
25 | 334 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Personal (remuneraciones pendientes de pago) [00245]
26 | 351 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Pasivos por impuesto corriente [00246]
27 | 368 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras deudas con las Administraciones Públicas [00247]
28 | 385 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Anticipos de clientes [00248]
29 | 402 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otros acreedores [00249]
30 | 419 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Periodificaciones a corto plazo [00250]
31 | 436 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deuda con características especiales a corto plazo  [00251]
32 | 453 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - TOTAL PATRIMONIO NETO Y PASIVO [00252]
33 | 470 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200060>"
Total: |  | 479

# DP200007

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "070"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Importe neto de la cifra de negocios [00255]
7 | 28 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ventas [00256]
8 | 45 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Prestaciones de servicios [00257]
9 | 62 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas -  Ingresos carácter financiero sociedades holding [00705]
10 | 79 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas -  Ingresos carácter financiero sociedades holding  - De participaciones en instrumentos patrimonio [00706]
11 | 96 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas -  Ingresos carácter financiero sociedades holding  - De valores negociables y otros instrumentos financieros [00707]
12 | 113 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas -  Ingresos carácter financiero sociedades holding  - Resto [00708]
13 | 130 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Variación de existencias de productos terminados 
y en curso de fabricación  [00258]
14 | 147 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Trabajos realizados por la empresa para su activo [00259]
15 | 164 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Aprovisionamientos [00260]
16 | 181 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Consumo de mercaderías [00261]
17 | 198 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Compras de mercaderías [00760]
18 | 215 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Variación de existencias  [00761]
19 | 232 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Consumo de materias primas y otras materias consumibles [00262]
20 | 249 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Compras de materias primas y otras materias consumibles [00762]
21 | 266 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Variación de materias primas y otras materias consumibles [00763]
22 | 283 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Trabajos realizados por otras empresas [00263]
23 | 300 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro de mercaderías, materias primas [00264]
24 | 317 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros ingresos de explotación [00265]
25 | 334 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente [00266]
26 | 351 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente - Ingresos por arrendamientos [00267]
27 | 368 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente - Resto [00268]
28 | 385 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Subvenciones de explotación incorporadas 
 al resultado del ejercicio  [00269]
29 | 402 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Gastos de personal  [00270]
30 | 419 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Sueldos, salarios y asimilados [00271]
31 | 436 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Indemnizaciones [00273]
32 | 453 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Seguridad Social a cargo de la empresa [00274]
33 | 470 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Retribuciones a largo plazo por sistemas de aportación o prestación definitiva  [00275]
34 | 487 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Retribuciones mediante instrumentos de patrimonio [00276]
35 | 504 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros gastos sociales [00277]
36 | 521 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Provisiones [00278]
37 | 538 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros gastos de explotación [00279]
38 | 555 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Servicios exteriores [00280]
39 | 572 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Tributos [00281]
40 | 589 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Pérdidas, deterioro y variación de provisiones por operaciones comerciales [00282]
41 | 606 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros gastos de gestión corriente [00283]
42 | 623 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Gastos por emisión de gases de efecto invernadero [00709]
43 | 640 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Amortización del inmovilizado [00284]
44 | 657 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Imputación de subvenciones de inmovilizado no financiero y otras [00285]
45 | 674 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Excesos de provisiones [00286]
46 | 691 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y resultado por enajenaciones del inmovilizado [00287]
47 | 708 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas [00288]
48 | 725 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas - Deterioros [00289]
49 | 742 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas - Reversión de deterioros [00290]
50 | 759 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras [00291]
51 | 776 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras - Beneficios [00292]
52 | 793 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas [00293]
53 | 810 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y resultados por enajenaciones del inmovilizado de las sociedades holding [00710]
54 | 827 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Diferencia negativa de combinaciones de negocio [00294]
55 | 844 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros resultados [00295]
56 | 861 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - RESULTADO DE EXPLOTACION [00296]
57 | 878 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200070>"
Total: |  | 887

# DP200008

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "080"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos financieros [00297]
7 | 28 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio [00298]
8 | 45 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio - En empresas del grupo y asociadas [00299]
9 | 62 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio - En terceros [00300]
10 | 79 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos financieros  [00301]
11 | 96 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos financieros  - De empresas del grupo y asociadas  [00302]
12 | 113 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos financieros  - De terceros  [00303]
13 | 130 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Imputación de subvenciones, donaciones y legados  de carácter financiero  [00304]
14 | 147 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Gastos financieros [00305]
15 | 164 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por deudas con empresas del grupo y asociadas [00306]
16 | 181 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por deudas con terceros [00307]
17 | 198 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por actualización de provisiones [00308]
18 | 215 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Variación de valor razonable en instrumentos financieros [00309]
19 | 232 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Cartera de negociación y otros [00310]
20 | 249 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Imputación por activos financieros disponibles para la venta  [00311]
21 | 266 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Diferencias de cambio [00312]
22 | 283 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioro y resultado por enajenaciones de instrumentos financieros   [00313]
23 | 300 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas [00314]
24 | 317 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Deterioros, empresas del grupo, asociadas y vinculadas [00315]
25 | 334 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Deterioros, otras empresas [00316]
26 | 351 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Reversión de deterioros, empresas del grupo, asociadas y vinculadas [00317]
27 | 368 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Reversión de deterioros, otras empresas [00318]
28 | 385 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras [00319]
29 | 402 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Beneficios, empresas del grupo, asociadas y vinculadas [00320]
30 | 419 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Beneficios, otras empresas [00321]
31 | 436 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas, empresas del grupo, asociadas y vinculadas  [00322]
32 | 453 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas, otras empresas  [00323]
33 | 470 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Otros ingresos y gastos de carácter financiero [00329]
34 | 487 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Incorporación al activo de gastos financieros [00330]
35 | 504 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Ingresos financieros derivados de convenios de acreedores [00331]
36 | 521 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resto de ingresos y gastos [00332]
37 | 538 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO FINANCIERO [00324]
38 | 555 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO ANTES DE IMPUESTOS [00325]
39 | 572 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Impuestos sobre beneficios  [00326]
40 | 589 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO DEL EJERCICIO PROCEDENTE DE OPERACIONES CONTINUADAS [00327]
41 | 606 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones interrumpidas - RESULTADO DEL EJERCICIO PROCEDENTE DE OPERACIONES INTERRUMPIDAS NETO DE IMPUESTOS [00328]
42 | 623 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones interrumpidas - RESULTADO DE LA CUENTA DE PÉRDIDAS Y GANANCIAS [00500]
43 | 640 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200080>"
Total: |  | 649

# DP200009

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "090"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Estado de cambios patrimonio neto (I) - Resultado de la cuenta de pérdidas y ganancias  [00500]
7 | 28 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por valoración de instrumentos financieros  [00336]
8 | 45 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Activos financieros disponibles para la venta [00337]
9 | 62 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Otros ingresos/gastos [00338]
10 | 79 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por coberturas de flujos de efectivo [00339]
11 | 96 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Subvenciones, donaciones y legados recibidos [00340]
12 | 113 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por ganancias y pérdidas actuariales y otros ajustes  [00341]
13 | 130 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por activos no corrientes y pasivos vinculados, mantenidos para la venta   [00342]
14 | 147 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Diferencias de conversión [00343]
15 | 164 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Efecto impositivo [00344]
16 | 181 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Total ingresos y gastos imputados en el patrimonio neto [00345]
17 | 198 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por valoración de instrumentos financieros [00346]
18 | 215 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Activos financieros disponibles para la venta [00347]
19 | 232 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Otros ingresos/gastos [00348]
20 | 249 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por coberturas de flujos de efectivo [00349]
21 | 266 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Subvenciones, donaciones y legados recibidos [00350]
22 | 283 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por activos no corrientes y pasivos vinculados , mantenidos para la venta  [00351]
23 | 300 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Diferencias de conversión [00352]
24 | 317 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Efecto impositivo [00353]
25 | 334 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Total transferencia a la cuenta de pérdidas y ganancias [00354]
26 | 351 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - TOTAL DE INGRESOS Y GASTOS RECONOCIDOS [00355]
27 | 368 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200090>"
Total: |  | 377

# DP200010

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "100"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Capital - Escriturado [00380]
7 | 28 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Capital - No exigido  [00381]
8 | 45 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Prima de emisión  [00382]
9 | 62 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Reservas  [00383]
10 | 79 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Acciones y participaciones en patrimonio propias  [00384]
11 | 96 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Resultados ejercicios anteriores  [00385]
12 | 113 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Otras aportaciones de socios  [00386]
13 | 130 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Capital - Escriturado  [00394]
14 | 147 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Capital - No exigido [00395]
15 | 164 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Prima de emisión [00396]
16 | 181 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Reservas [00397]
17 | 198 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Acciones y participaciones en patrimonio propias [00398]
18 | 215 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Resultados ejercicios anteriores [00399]
19 | 232 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Otras aportaciones de socios [00400]
20 | 249 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Capital - Escriturado [00408]
21 | 266 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Capital - No exigido [00409]
22 | 283 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Prima de emisión [00410]
23 | 300 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Reservas [00411]
24 | 317 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Acciones y participaciones en patrimonio propias [00412]
25 | 334 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Resultados ejercicios anteriores [00413]
26 | 351 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Otras aportaciones de socios [00414]
27 | 368 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Capital - Escriturado [00422]
28 | 385 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Capital - No exigido [00423]
29 | 402 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Prima de emisión [00424]
30 | 419 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Reservas [00425]
31 | 436 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Acciones y participaciones en patrimonio propias [00426]
32 | 453 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Resultados ejercicios anteriores [00427]
33 | 470 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Otras aportaciones socios [00428]
34 | 487 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Capital - Escriturado [00436]
35 | 504 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Capital - No exigido [00437]
36 | 521 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Prima de emisión [00438]
37 | 538 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Reservas [00439]
38 | 555 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Acciones y participaciones en patrimonio propias [00440]
39 | 572 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Resultados ejercicios anteriores [00441]
40 | 589 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Otras aportaciones de socios [00442]
41 | 606 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Capital - Escriturado [00450]
42 | 623 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Capital - No exigido [00451]
43 | 640 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Prima de emisión [00452]
44 | 657 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Reservas [00453]
45 | 674 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Acciones y participaciones en patrimonio propias [00454]
46 | 691 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Resultados ejercicios anteriores [00455]
47 | 708 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Otras aportaciones de socios [00456]
48 | 725 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Capital - Escriturado [00464]
49 | 742 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Capital - No exigido [00465]
50 | 759 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Prima de emisión [00466]
51 | 776 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Reservas [00467]
52 | 793 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Acciones y participaciones en patrimonio propias [00468]
53 | 810 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Resultados ejercicios anteriores [00469]
54 | 827 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otras aportaciones de socios [00470]
55 | 844 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Capital - Escriturado [00478]
56 | 861 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Capital - No exigido [00479]
57 | 878 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Prima de emisión [00480]
58 | 895 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Reservas [00481]
59 | 912 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Acciones y participaciones en patrimonio propias  [00482]
60 | 929 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Resultados ejercicios anteriores [00483]
61 | 946 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Otras aportaciones de socios [00484]
62 | 963 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Capital - Escriturado [00492]
63 | 980 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Capital - No exigido [00493]
64 | 997 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Prima de emisión [00494]
65 | 1014 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Reservas [00495]
66 | 1031 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Acciones y participaciones en patrimonio propias  [00496]
67 | 1048 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Resultados ejercicios anteriores [00497]
68 | 1065 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Otras aportaciones de socios [00498]
69 | 1082 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Capital - Escriturado [00506]
70 | 1099 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Capital - No exigido [00507]
71 | 1116 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Prima de emisión [00508]
72 | 1133 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Reservas [00509]
73 | 1150 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Acciones y participaciones en patrimonio propias [00510]
74 | 1167 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Resultados ejercicios anteriores [00511]
75 | 1184 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras aportaciones de socios [00512]
76 | 1201 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Capital - Escriturado [00520]
77 | 1218 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Capital - No exigido [00521]
78 | 1235 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Prima de emisión [00522]
79 | 1252 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Reservas [00523]
80 | 1269 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Acciones y participaciones en patrimonio propias  [00524]
81 | 1286 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Resultados ejercicios anteriores [00525]
82 | 1303 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Otras aportaciones de socios [00526]
83 | 1320 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Capital - Escriturado [00534]
84 | 1337 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Capital - No exigido [00535]
85 | 1354 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Prima de emisión [00536]
86 | 1371 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Reservas [00537]
87 | 1388 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Acciones y participaciones en patrimonio propias  [00538]
88 | 1405 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Resultados ejercicios anteriores [00539]
89 | 1422 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Otras aportaciones de socios [00540]
90 | 1439 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Capital - Escriturado [00548]
91 | 1456 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Capital - No exigido [00549]
92 | 1473 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Prima de emisión [00550]
93 | 1490 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Reservas [00551]
94 | 1507 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Acciones y participaciones en patrimonio propias [00552]
95 | 1524 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Resultados ejercicios anteriores [00553]
96 | 1541 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Otras aportaciones de socios [00554]
97 | 1558 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Capital - Escriturado [00562]
98 | 1575 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Capital - No exigido [00563]
99 | 1592 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Prima de emisión [00564]
100 | 1609 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Reservas [00565]
101 | 1626 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Acciones y participaciones en patrimonio propias  [00566]
102 | 1643 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Resultados ejercicios anteriores [00567]
103 | 1660 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Otras aportaciones de socios [00568]
104 | 1677 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Capital - Escriturado [00576]
105 | 1694 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Capital - No exigido [00577]
106 | 1711 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Prima de emisión [00578]
107 | 1728 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Reservas [00579]
108 | 1745 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Acciones y participaciones en patrimonio propias [00580]
109 | 1762 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Resultados ejercicios anteriores [00581]
110 | 1779 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Otras aportaciones de socios [00582]
111 | 1796 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Capital  - Escriturado [00590]
112 | 1813 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Capital  - No exigido [00591]
113 | 1830 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Prima de emisión [00592]
114 | 1847 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Reservas [00593]
115 | 1864 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Acciones y participaciones en patrimonio propias [00594]
116 | 1881 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Resultados ejercicios anteriores [00595]
117 | 1898 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Otras aportaciones de socios [00596]
118 | 1915 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Capital -  Escriturado [00604]
119 | 1932 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Capital - No exigido [00605]
120 | 1949 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Prima de emisión [00606]
121 | 1966 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Reservas [00607]
122 | 1983 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Acciones y participaciones en patrimonio propias [00608]
123 | 2000 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Resultados ejercicios anteriores [00609]
124 | 2017 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Otras aportaciones de socios [00610]
125 | 2034 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Capital - Escriturado [00618]
126 | 2051 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Capital - No exigido [00619]
127 | 2068 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Prima de emisión [00620]
128 | 2085 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Reservas [00621]
129 | 2102 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Acciones y participaciones en patrimonio propias [00622]
130 | 2119 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Resultados ejercicios anteriores [00623]
131 | 2136 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras aportaciones de socios [00624]
132 | 2153 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Capital - Escriturado [00715]
133 | 2170 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -  Capital - No exigido [00716]
134 | 2187 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Prima de emisión [00717]
135 | 2204 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -  Reservas [00718]
136 | 2221 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Acciones y participaciones en patrimonio propias [00719]
137 | 2238 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Resultados ejercicios anteriores [00720]
138 | 2255 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Otras aportaciones de socios [00721]
139 | 2272 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Capital - Escriturado [00729]
140 | 2289 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones -  Capital - No exigido [00730]
141 | 2306 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Prima de emisión [00731]
142 | 2323 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones -  Reservas [00732]
143 | 2340 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Acciones y participaciones en patrimonio propias  [00733]
144 | 2357 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Resultados ejercicios anteriores [00734]
145 | 2374 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Otras aportaciones de socios [00735]
146 | 2391 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Capital - Escriturado [00632]
147 | 2408 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Capital - No exigido [00633]
148 | 2425 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Prima de emisión [00634]
149 | 2442 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Reservas [00635]
150 | 2459 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Acciones y participaciones en patrimonio propias [00636]
151 | 2476 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Resultados ejercicios 
anteriores [00637]
152 | 2493 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Otras aportaciones de socios [00638]
153 | 2510 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200100>"
Total: |  | 2519

# DP200011

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "110"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Resultado del ejercicio [00387]
7 | 28 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Dividendo a cuenta [00388]
8 | 45 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Otros instrumentos patrimonio neto [00389]
9 | 62 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Ajustes por cambios de valor [00390]
10 | 79 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Ajustes en patrimonio neto [00391]
11 | 96 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Subvenciones, donaciones y legados recibidos [00392]
12 | 113 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Total [00393]
13 | 130 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Resultado del ejercicio [00401]
14 | 147 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Dividendo a cuenta [00402]
15 | 164 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Otros instrumentos patrimonio neto [00403]
16 | 181 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Ajustes por cambios de valor [00404]
17 | 198 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Ajustes en patrimonio neto [00405]
18 | 215 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Subvenciones, donaciones y legados recibidos [00406]
19 | 232 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Total [00407]
20 | 249 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Resultado del ejercicio [00415]
21 | 266 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Dividendo a cuenta [00416]
22 | 283 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Otros instrumentos patrimonio neto [00417]
23 | 300 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Ajustes por cambios de valor [00418]
24 | 317 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Ajustes en patrimonio neto [00419]
25 | 334 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Subvenciones, donaciones y legados recibidos [00420]
26 | 351 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Total [00421]
27 | 368 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Resultado del ejercicio [00429]
28 | 385 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Dividendo a cuenta [00430]
29 | 402 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Otros instrumentos patrimonio neto [00431]
30 | 419 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Ajustes por cambios de valor [00432]
31 | 436 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Ajustes en patrimonio neto [00433]
32 | 453 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Subvenciones, donaciones y legados recibidos [00434]
33 | 470 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Total [00435]
34 | 487 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Resultado del ejercicio [00443]
35 | 504 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Dividendo a cuenta [00444]
36 | 521 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Otros instrumentos patrimonio neto [00445]
37 | 538 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Ajustes por cambios de valor [00446]
38 | 555 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Subvenciones, donaciones y legados recibidos [00448]
39 | 572 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Total [00449]
40 | 589 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Resultado del ejercicio [00457]
41 | 606 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Dividendo a cuenta [00458]
42 | 623 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Ajustes en patrimonio neto [00461]
43 | 640 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Subvenciones, donaciones y legados recibidos [00462]
44 | 657 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Total [00463]
45 | 674 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Resultado del ejercicio [00471]
46 | 691 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Dividendo a cuenta [00472]
47 | 708 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ajustes en patrimonio neto [00475]
48 | 725 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Subvenciones, donaciones y legados recibidos [000476]
49 | 742 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Total [00477]
50 | 759 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Resultado del ejercicio [00485]
51 | 776 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Dividendo a cuenta [00486]
52 | 793 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Ajustes en patrimonio neto [00489]
53 | 810 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Subvenciones, donaciones y legados recibidos [00490]
54 | 827 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Total [00491]
55 | 844 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Resultado del ejercicio [00499]
56 | 861 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Dividendo a cuenta [00502]
57 | 878 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Ajustes en patrimonio neto [00503]
58 | 895 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Subvenciones, donaciones y legados recibidos [00504]
59 | 912 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Total [00505]
60 | 929 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Resultado del ejercicio [00513]
61 | 946 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Dividendo a cuenta [00514]
62 | 963 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otros instrumentos patrimonio neto [00515]
63 | 980 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Ajustes por cambios de valor [00516]
64 | 997 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Ajustes en patrimonio neto [00517]
65 | 1014 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Subvenciones, donaciones y legados recibidos [00518]
66 | 1031 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Total [00519]
67 | 1048 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Resultado del ejercicio [00527]
68 | 1065 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Dividendo a cuenta [00528]
69 | 1082 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Otros instrumentos patrimonio neto [00529]
70 | 1099 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Ajustes por cambios de valor [00530]
71 | 1116 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Ajustes en patrimonio neto [00531]
72 | 1133 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Subvenciones, donaciones y legados recibidos [00532]
73 | 1150 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Total [00533]
74 | 1167 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Resultado del ejercicio [00541]
75 | 1184 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Dividendo a cuenta [00542]
76 | 1201 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Otros instrumentos patrimonio neto [00543]
77 | 1218 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Ajustes por cambios de valor [00544]
78 | 1235 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Ajustes en patrimonio neto [00545]
79 | 1252 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Subvenciones, donaciones y legados recibidos [00546]
80 | 1269 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Total  [00547]
81 | 1286 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Resultado del ejercicio [00555]
82 | 1303 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Dividendo a cuenta [00556]
83 | 1320 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Otros instrumentos patrimonio neto [00557]
84 | 1337 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Ajustes por cambios de valor [00558]
85 | 1354 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Subvenciones, donaciones y legados recibidos [00560]
86 | 1371 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Total [00561]
87 | 1388 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Resultado del ejercicio [00569]
88 | 1405 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Dividendo a cuenta [00570]
89 | 1422 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Otros instrumentos patrimonio neto [00571]
90 | 1439 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Ajustes por cambio de valor [00572]
91 | 1456 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Subvenciones, donaciones y legados recibidos [00574]
92 | 1473 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Total [00575]
93 | 1490 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Resultado del ejercicio [00583]
94 | 1507 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Dividendo a cuenta [00584]
95 | 1524 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Otros instrumentos patrimonio neto [00585]
96 | 1541 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Ajustes por cambio de valor [00586]
97 | 1558 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Subvenciones, donaciones y legados recibidos [00588]
98 | 1575 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Total [00589]
99 | 1592 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Resultado del ejercicio [00597]
100 | 1609 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Dividendo a cuenta [00598]
101 | 1626 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Otros instrumentos patrimonio neto [00599]
102 | 1643 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Ajustes por cambios de valor [00600]
103 | 1660 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Subvenciones, donaciones y legados recibidos [00602]
104 | 1677 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Total [00603]
105 | 1694 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Resultado del ejercicio  [00611]
106 | 1711 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Dividendo a cuenta  [00612]
107 | 1728 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Otros instrumentos patrimonio neto  [00613]
108 | 1745 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Ajustes por cambios de valor [00614]
109 | 1762 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Ajustes en patrimonio neto [00615]
110 | 1779 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Subvenciones, donaciones y legados recibidos  [00616]
111 | 1796 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Total [00617]
112 | 1813 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Resultado del ejercicio [00625]
113 | 1830 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Dividendo a cuenta  [00626]
114 | 1847 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otros instrumentos patrimonio neto [00627]
115 | 1864 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Ajustes por cambios de valor [00628]
116 | 1881 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Ajustes en patrimonio neto [00629]
117 | 1898 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Subvenciones, donaciones y legados recibidos  [00630]
118 | 1915 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Total [00631]
119 | 1932 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Resultado del ejercicio [00722]
120 | 1949 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Dividendo a cuenta  [00723]
121 | 1966 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Otros instrumentos patrimonio neto [00724]
122 | 1983 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Ajustes por cambios de valor [00725]
123 | 2000 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Ajustes en patrimonio neto [00726]
124 | 2017 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Subvenciones, donaciones y legados recibidos  [00727]
125 | 2034 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Total [00728]
126 | 2051 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Resultado del ejercicio [00736]
127 | 2068 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Dividendo a cuenta  [00737]
128 | 2085 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Otros instrumentos patrimonio neto [00738]
129 | 2102 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Ajustes por cambios de valor [00739]
130 | 2119 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Ajustes en patrimonio neto [00740]
131 | 2136 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Subvenciones, donaciones y legados recibidos  [00741]
132 | 2153 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Total [00742]
133 | 2170 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Resultado del ejercicio [00639]
134 | 2187 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Dividendo a cuenta [00640]
135 | 2204 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Otros instrumentos patrimonio neto [00641]
136 | 2221 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Ajustes por cambios de valor [00642]
137 | 2238 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Ajustes en patrimonio neto [00643]
138 | 2255 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Subvenciones, donaciones y legados recibidos [00644]
139 | 2272 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Total [00645]
140 | 2289 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200110>"
Total: |  | 2298

# DP200012

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "120"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | N | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Resultado de la cuenta de pérdidas y ganancias [00500]
7 | 28 | 17 | N | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones por Impuesto Sociedades - Aumentos [00301]
8 | 45 | 17 | N | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones por Impuesto Sociedades - Disminuciones [00302]
9 | 62 | 17 | N | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Resultado cuenta pérdidas y ganancias antes de Impuesto Sociedades [00501]
10 | 79 | 17 | Num | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones al resultado contable referidos al grupo fiscal - Aumentos [01230]
11 | 96 | 17 | Num | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones al impuesto contable  referidos al grupo fiscal - Disminuciones [01231]
12 | 113 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cambio de criterios contables (art.11.3.2º LIS) - Aumentos [00355]
13 | 130 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cambio de criterios contables (art.11.3.2º LIS) - Disminuciones [00356]
14 | 147 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos (art.11.4 LIS) - Aumentos [00357]
15 | 164 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos (art.11.4 LIS) - Disminuciones [00358]
16 | 181 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reversión del deterioro de valor elem. patrimoniales (art. 11.6 LIS) - Aumentos [00359]
17 | 198 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reversión del deterioro de valor elem. patrimoniales (art. 11.6 LIS) - Disminuciones [00360]
18 | 215 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas negativas art. 11.9, 10 y 11 LIS - Aumentos [00225]
19 | 232 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas negativas art. 11.9, 10 y 11 LIS - Disminuciones  [00226]
20 | 249 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por rentas derivadas de operaciones  con quita o espera  (art.11.13 LIS) - Aumentos [00545]
21 | 266 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS) - Disminuciones  [00272]
22 | 283 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos  - Aumentos [00361]
23 | 300 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  - Disminuciones  [00362]
24 | 317 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Diferencias entre amortización contable y fiscal (arts. 12.1 LIS) - Aumentos [00303]
25 | 334 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Diferencias entre amortización contable y fiscal (arts. 12.1 LIS) - Disminuciones [00304]
26 | 351 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reversion del 30% importe gastos de amortiz.contable (excluidas emp.reducida dimensión)(art. 7 Ley 16/2012)  - Disminuciones  [00505]
27 | 368 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización inmovilizado afecto investigación y desarrollo (art. 12.3.b) LIS) - Aumentos [00305]
28 | 385 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización inmovilizado afecto investigación y desarrollo (art. 12.3.b) LIS) - Disminuciones [00306]
29 | 402 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización de gastos de investigación y desarrollo (art. 12.3.c) LIS) - Aumentos [00307]
30 | 419 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización de gastos de investigación y desarrollo (art. 12.3.c) LIS) - Disminuciones [00308]
31 | 436 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización inmovilizado material nuevo (art. 12.3 e) LIS) - Aumentos [01003]
32 | 453 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización inmovilizado material nuevo (art. 12.3 e) LIS)  - Disminuciones  [01004]
33 | 470 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otros supuestos de libertad de amortización  (art. 12.3 a) y d) LIS) - Aumentos [00309]
34 | 487 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otros supuestos de libertad de amortización  (art. 12.3 a) y d) LIS) - Disminuciones  [00310]
35 | 504 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización del inmovilizado intangible con vida útil definida  (DT 12.2 LIS) y armotización del art. DT 13ª.1 LIS - Aumentos [01005]
36 | 521 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización del inmovilizado intangible con vida útil definida  (art. 12.2 LIS) y armotización del art. DT 13ª.1 LIS - Diminuciones  [01006]
37 | 538 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización con mantenimiento de empleo (RDL 6/2010 y DT 13ª.2) - Aumentos [00514]
38 | 555 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización con mantenimiento de empleo (RDL 6/2010 y DT13ª.2) - Disminuciones [00509]
39 | 572 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización sin mantenimiento de empleo (RDL 13/2010 y DT 13ª.2) - Aumentos [00516]
40 | 589 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización sin mantenimiento de empleo (RDL 13/2010 y DT 13ª.2) - Disminuciones [00551]
41 | 606 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 LIS - Aumentos [00321]
42 | 623 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 LIS - Disminuciones [00322]
43 | 640 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art.13.1 LIS y provisiones y gastos - Aumentos [00415]
44 | 657 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art.13.1 LIS y provisiones y gastos  - Disminuciones [00211]
45 | 674 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Perdidas por deterioro de IM, inversiones inmob. e II, incluido fondo comercio - Aumentos [00331]
46 | 691 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Perdidas por deterioro de IM, inversiones inmob. e II, incluido fondo comercio - Disminuciones [00332]
47 | 708 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS y DT 16ª.1 y 2 LIS) - Aumentos [00325]
48 | 725 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Ajustes por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS y DT 16ª.1 y 2 LIS) - Disminuciones [00326]
49 | 742 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valores representativos de deuda  (art. 13.2 c) LIS y DT 15ª LIS) - Aumentos [00327]
50 | 759 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y DT 15ª LIS) - Disminuciones [00328]
51 | 776 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Deducción del intangible de vida útil indefinida (art. 13.3 LIS) - Aumentos [00333]
52 | 793 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Deducción del intangible de vida útil indefinida (art. 13.3 LIS) - Disminuciones [00334]
53 | 810 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Aplicac. limite del art. 11.12 LIS a las perdidas por deterioro del art. 13.1 LIS y provisiones y gastos - Aumentos [00416]
54 | 827 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Aplicac. limite del art. 11.12 LIS a las perdidas por deterioro del art. 13.1 LIS y provisiones y gastos - Disminuciones [00543]
55 | 844 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Gastos y provisiones por pensiones no afectos por el art. 11.12 LIS  - Aumentos [00335]
56 | 861 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Provisiones y gastos por pensiones no afectos por el art. 11.12 LIS  - Aumentos [00336]
57 | 878 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337]
58 | 895 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338]
59 | 912 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Subvenciones públic.incluidas en el resultado ejercicio no integrable en BI (art. 14.8 LIS) - Disminuciones [00368]
60 | 929 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Gastos por donativos y liberalidades (art. 15 e) LIS) - Aumentos [00339]
61 | 946 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Operaciones realizadas con paraísos fiscales (art. 15 g) LIS) - Aumentos [00341]
62 | 963 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Operaciones realizadas con paraísos fiscales (art. 15 g) LIS) - Disminuciones [00342]
63 | 980 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Gastos financieros derivados de deudas  y operaciones con entidades del grupo - Aumentos [00508]
64 | 997 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Gastos correspondientes a operac. realizadas con personas o entid. vinculadas  - Aumentos [01009]
65 | 1014 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Gastos correspondientes a operac. realizadas con personas o entid. vinculadas  - Disminuciones [01010]
66 | 1031 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Otros gastos no deducibles (arts. 15 a), c), d), f) e i) LIS) - Aumentos  [00343]
67 | 1048 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Ajustes por la limitación en la deduc. en gastos financieros (art. 16 LIS) - Aumentos  [00363]
68 | 1065 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Ajustes por la limitación en la deduc. en gastos financieros (art. 16 LIS) - Disminuciones  [00364]
69 | 1082 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Revalorizaciones contables (art. 17.1  LIS) - Aumentos [00345]
70 | 1099 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Revalorizaciones contables (art. 17.1  LIS) - Disminuciones [00346]
71 | 1116 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - SICAV: Reducciones de capital y distribución de la prima de emisión  (art. 17.6 LIS) - Aumentos [00371]
72 | 1133 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Transmisiónes lucrativas y societarias: aplicación del valor normal de mercado (art. 17.4 LIS)  - Aumentos [00347]
73 | 1150 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Transmisiónes lucrativas y societarias: aplicación del valor normal de mercado  (art. 17.4 LIS)  - Disminuciones [00348]
74 | 1167 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones vinculadas: aplicación del valor normal de mercado (art. 18 LIS)  - Aumentos [01011]
75 | 1184 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones vinculadas: aplicación del valor normal de mercado (art. 18 LIS)  - Disminuciones  [01012]
76 | 1201 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cambios de residencia y otras operaciones del art.19 LIS - Aumentos [01013]
77 | 1218 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cambios de residencia y otras operaciones del art.19 LIS - Disminuciones  [01014]
78 | 1235 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Efectos de la valoración contable diferente a la fiscal (art. 20 LIS) - Aumentos [01015]
79 | 1252 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Efectos de la valoración contable diferente a la fiscal (art. 20 LIS) - Disminuciones  [01016]
80 | 1269 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Exención por doble imposición sobre dividendos y rentas deriv.de transm.de valores ent.resid. y no residentes - Aumentos [00369]
81 | 1286 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Exención por doble imposición sobre dividendos y rentas deriv.de transm.de valores ent.resid. y no residentes - Disminuciones  [00370]
82 | 1303 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Exención de rentas en el extranjero  (art. 22 LIS) - Aumentos [00256]
83 | 1320 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Exención de rentas en el extranjero (art. 22 LIS) - Disminuciones  [00278]
84 | 1337 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Reducción de ingresos procedentes de determinados activos intangibles (art. 23 LIS) - Disminuciones  [00372]
85 | 1354 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Obra benéfico-social de las cajas de ahorro y fundaciones  bancarias (art. 24 LIS) - Aumentos [00373]
86 | 1371 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Obra benéfico-social de las cajas de ahorro y fundaciones  bancarias  (art. 24 LIS) - Disminuciones  [00374]
87 | 1388 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Impuesto extranjero soportado por el contribuyente, no deducible por afectar a rentas con deducc. doble imp. - Aumentos [00340]
88 | 1405 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Impuesto extranjero sobre beneficios con cargo a los cuales se pagan los dividendos objeto deducc.doble imp.internac. - Aumentos [00351]
89 | 1422 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Agrupación de interés económico (Cap. II Tit. VII LIS)  - Aumentos [00375]
90 | 1439 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Agrupación de interés económico   (Cap. II Tit. VII LIS) - Disminuciones  [00376]
91 | 1456 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Unión temporal de empresas, ajustes del art. 45.1 LIS  - Aumentos [01320]
92 | 1473 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias -  Unión temporal de empresas, ajustes del art. 45.1 LIS  - Disminuciones  [01321]
93 | 1490 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por rentas exentas de UTE  que opera en el extranjero  -  Aumentos [00184]
94 | 1507 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por rentas exentas de UTE  que opera en el extranjero - Disminuciones  [00544]
95 | 1524 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por participar en el extranjero en formulas colaborac. a las UTES  -  Aumentos [01022]
96 | 1541 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por participar en el extranjero en formulas colaborac. a las UTES  -  Disminuciones [01023]
97 | 1558 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por criterios de imputación temporal (art. 46.2 LIS)  - Aumentos [01018]
98 | 1575 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por criterios de imputación temporal (art. 46.2 LIS) - Disminuciones  [01019]
99 | 1592 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - BI negativas generadas dentro del grupo fiscal por la entidad transmitida y que hayan sido compensadas  - Aumentos [01275]
100 | 1609 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - BI negativas generadas dentro del grupo fiscal por la entidad transmitida y que hayan sido compensadas - Disminuciones  [01276]
101 | 1626 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Soc. y fondos de capital-riesgo y soc. desarrollo industrial regional  (cap.IV, titulo VII LIS)  - Aumentos [00377]
102 | 1643 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Soc. y fondos de capital-riesgo y soc. desarrollo industrial regional (cap.IV, titulo VII LIS) - Disminuciones [00378]
103 | 1660 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Valoración bienes y derechos. Régimen especial operaciones reestructuración (cap.VII, titulo VII LIS) - Aumentos [00379]
104 | 1677 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Valoración bienes y derechos. Régimen especial operaciones reestructuración (cap.VII, titulo VII LIS) - Disminuciones [00380]
105 | 1694 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Minería e hidrocarburos: factor agotamiento (arts. 91 y 95 LIS) - Aumentos [00381]
106 | 1711 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Minería e hidrocarburos: factor agotamiento (arts. 91 y 95 LIS) - Disminuciones [00382]
107 | 1728 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Hidrocarburos: Amortización inversiones intangibles  y gastos de investigación (art. 99 LIS) - Aumentos [00383]
108 | 1745 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Hidrocarburos: Amortización inversiones intangibles y gastos de investigación (art. 99 LIS) - Disminuciones [00384]
109 | 1762 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Transparencia Fiscal internacional (art. 100 LIS) - Aumentos [00387]
110 | 1779 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Transparencia Fiscal internacional (art. 100 LIS) - Disminuciones [00388]
111 | 1796 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200120>"
Total: |  | 1805

# DP200013

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "130"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311]
7 | 28 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312]
8 | 45 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS)  - Aumentos [00313]
9 | 62 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS) - disminuciones  [00314]
10 | 79 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323]
11 | 96 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324]
12 | 113 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Arrendamiento financiero: régimen especial  (art. 106 LIS)- Aumentos [00317]
13 | 130 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Arrendamiento financiero: régimen especial (art. 106 LIS) - Disminuciones [00318]
14 | 147 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen fiscal entidades de tenencia valores extranjeros - Aumentos [00385]
15 | 164 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen fiscal entidades de tenencia valores extranjeros - Disminuciones [00386]
16 | 181 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389]
17 | 198 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390]
18 | 215 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Montes vecinales en mano común  (cap. XV, título VII LIS) - disminuciones [00396]
19 | 232 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen entidades navieras en función del tonelaje (cap. XVI del titulo VII LIS) - Aumentos [00397]
20 | 249 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen entidades navieras en función del tonelaje (cap. XVI del titulo VII LIS) - Disminuciones [00398]
21 | 266 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Aportaciones y colaborac. A favor entidad sin fines lucrativos - Aumentos [00250]
22 | 283 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Aportaciones y colaborac. A favor entidad sin fines lucrativos - Disminuciones [00251]
23 | 300 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391]
24 | 317 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392]
25 | 334 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Cooperativas: Fondo de reserva obligatorio (Ley 20/1990) - Disminuciones [00400]
26 | 351 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reservas inversiones en Canarias (Ley 19/1994) - Aumentos [00403]
27 | 368 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reservas inversiones en Canarias (Ley 19/1994) - Disminuciones [00404]
28 | 385 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención transmisión bienes inmuebles (DA 6ª LIS)- Aumentos [00518]
29 | 402 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención transmisión bienes inmuebles (DA 6ª LIS) - Disminuciones  [00519]
30 | 419 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos (DT 1ª LIS) - Aumentos [00510]
31 | 436 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos (DT 1ª LIS) - Disminuciones  [00512]
32 | 453 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Adquisición de participaciones en entidades no residentes  (DT 14ª LIS) - Aumentos [00329]
33 | 470 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Adquisición de participaciones en entidades no residentes  (DT 14ª LIS) - Disminuciones [00330]
34 | 487 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reinversión de beneficios extraordinarios (DT 24ª LIS) - Aumentos [00365]
35 | 504 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reinversión de beneficios extraordinarios (DT 24ª LIS)  - Disminuciones [01026]
36 | 521 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Entidades rég. atribución rentas constituidas extranjero, presencia territorio español - Aumentos [00409]
37 | 538 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Entidades rég. atribución rentas constituidas extranjero, presencia territorio español - Disminuciones [00410]
38 | 555 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Correcciones específicas entidades sometidas normativa foral - Aumentos [00411]
39 | 572 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Correcciones específicas entidades sometidas normativa foral - Disminuciones [00412]
40 | 589 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Eliminaciones pdte. de incorporar sdes.que dejen de pertenecer a un grupo - Aumentos [01027]
41 | 606 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Eliminaciones pdte. de incorporar sdes.que dejen de pertenecer a un grupo - Disminuciones  [01028]
42 | 623 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413]
43 | 640 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414]
44 | 657 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Total correcciones al resultado cta. pérdidas y ganancias - Aumentos [00417]
45 | 674 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Total correcciones al resultado cta. pérdidas y ganancias - Disminuciones [00418]
46 | 691 | 17 | N | Liquidación II -  Entidades navieras en función del tonelaje - B.I. actividades o rentas en régimen general  [00578]
47 | 708 | 17 | N | Liquidación II -  Entidades navieras en función del tonelaje - B.I. derivada del régimen especial  [00579]
48 | 725 | 17 | N | Liquidación II -  Entidades que forman parte de grupos de consolidac.fiscal -  B.I. indiv.a integrar por entidades que forman parte del grupo - [01029]
49 | 742 | 17 | N | Liquidación II -  Entidades que forman parte de grupos de consolidac.fiscal - Eliminaciones e incorporaciones  correspondientes a la entidad -  [01030]
50 | 759 | 17 | N | Liquidación II -  Entidades que forman parte de grupos de consolidac.fiscal - Entigración individual de las dotaciones del art. 11.12 LIS -  [01031]
51 | 776 | 17 | N | Liquidación II -  Base imponible - B.I. antes de la compensación de bases imponibles negativas [00550]
52 | 793 | 17 | N | Liquidación II -  Base imponible - Reserva de capitalización   [01032]
53 | 810 | 17 | Num | Liquidación II -  Base imponible - Compensación de bases imponibles negativas períodos anteriores  [00547]
54 | 827 | 17 | N | Liquidación II -  Base imponible - Base imponible  [00552]
55 | 844 | 17 | N | Liquidación II -  Base Imponible  - Entidades Reducida dimensión - Reserva de nivelación - Aumentos  [01033]
56 | 861 | 17 | N | Liquidación II -  Base Imponible  - Entidades Reducida dimensión - Reserva de nivelación - Disminuciones  [01034]
57 | 878 | 17 | N | Liquidación II -  Base Imponible  - Entidades Reducida dimensión - Base imponible despues de la reserva de nivelación - Disminuciones  [01330]
58 | 895 | 17 | N | Liquidación II -  Base imponible - Sólo sociedades cooperativas - Resultados cooperativos - Disminuciones [00553]
59 | 912 | 17 | N | Liquidación II -  Base imponible - Sólo sociedades cooperativas - Resultados extracooperativos - Disminuciones [00554]
60 | 929 | 17 | N | Liquidación II -  Base imponible - Agrupaciones españolas interés economico y UTES - Socios residentes - Disminuciones [00555]
61 | 946 | 17 | N | Liquidación II -  Base imponible - Agrupaciones españolas interés economico y UTES - Socios no residentes - Disminuciones [00556]
62 | 963 | 17 | N | Liquidación II -  Base imponible - Sólo entidades ZEC - B.I. a tipo de gravamen especial: Actividades sector industrial - Disminuciones [00559]
63 | 980 | 17 | N | Liquidación II -  Base imponible - Sólo entidades ZEC - B.I. a tipo de gravamen especial: resto de actividades  - Disminuciones [01035]
64 | 997 | 17 | N | Liquidación II -  Base imponible - Sólo SOCIMIS - Parte B.I. del periodo impositivo que tributa al tipo general - Disminuciones [00520]
65 | 1014 | 17 | N | Liquidación II -  Base imponible - Sólo SOCIMIS - Parte B.I. del periodo impositivo que tributa al tipo del 0% - Disminuciones  [00521]
66 | 1031 | 17 | N | Liquidación II -  Base imponible - Rentas correspondientes a quitas por acuerdo con acreedores no vinculados (DT 34ª g) LIS) - Disminuciones   [00545]
67 | 1048 | 17 | N | Liquidación II -  Base imponible - Rentas correspondientes a quitas por acuerdo con acreedores no vinculados de cooperativas (DT 8ª Ley 20/1990) - disminuciones [00593]
68 | 1065 | 4 | Num | Liquidación II -  Tipo de gravamen - Tipo de gravamen [00558]
69 | 1069 | 17 | N | Liquidación II -  Sólo sociedades cooperativas - Cuota íntegra previa [00560]
70 | 1086 | 17 | N | Liquidación II -  Sólo sociedades cooperativas - Pérdidas por deterioro del art.12.2 LIS y provisiones y gastos - Aumentos  [00210]
71 | 1103 | 17 | N | Liquidación II -  Sólo sociedades cooperativas - Pérdidas por deterioro del art.12.2 LIS y provisiones y gastos - Disminuciones  [00480]
72 | 1120 | 17 | N | Liquidación II -  Sólo sociedades cooperativas - Aplicación del límite del art.11.12 LIS a las perdidas por deterioro del art. 13.1 LIS  y provisiones y gastos  - Aumentos  [00408]
73 | 1137 | 17 | N | Liquidación II -  Sólo sociedades cooperativas - Aplicación del límite del art.11.12 LIS a las perdidas por deterioro del art. 13.1 LIS  y provisisones y gastos  - Disminuciones   [01037]
74 | 1154 | 17 | Num | Liquidación II -  Sólo sociedades cooperativas - Compensación de cuotas por pérdidas de cooperativas [00561]
75 | 1171 | 17 | N | Liquidación II -  Sólo sociedades cooperativas - Reserva de nivelación convertido en cuotas (solo entidades del art. 101 LIS)  - Aumentos  [01285]
76 | 1188 | 17 | N | Liquidación II -  Sólo sociedades cooperativas - Reserva de nivelación convertido en cuotas (solo entidades del art. 101 LIS)   - Disminuciones   [01286]
77 | 1205 | 17 | N | Liquidación II -  Sólo sociedades cooperativas - Cuota íntegra previa después de la reserva de nivelación - Disminuciones   [01331]
78 | 1222 | 10 | An | Identificador de fin de registro | OBLIGATORIO
Total: |  | 1231 |  |  |  | Constante "</T200130>"

# DP200014

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "140"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria. En blanco |  | En blanco
6 | 11 | 17 | N | Liquidación III - Cuota íntegra - Cuota íntegra  [00562]
7 | 28 | 17 | Num | Liquidación III - Cuota íntegra - Incremento por incumplimiento reserva de nivelación   [01038]
8 | 45 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificación por rentas obtenidas en Ceuta y Melilla (art. 33 LIS)  [00567]
9 | 62 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificación por prestación de servicios (art. 34 LIS)  [00568]
10 | 79 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificación rendimientos por venta de bienes corporales producidos en Canarias  [00563]
11 | 96 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones sociedades cooperativas  [00566]
12 | 113 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones entidades dedicadas al arrendamiento de viviendas [00576]
13 | 130 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Otras bonificaciones  [00569]
14 | 147 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. interna de períodos anteriores aplicada en el ejercicio (art. 30 RDL 4/ 2004)   [00570]
15 | 164 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. interna (DT 23,1 LIS)   [01280]
16 | 181 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición  - D.I. internacional de periodos anteriores aplicada en el ejercicio (art. 31 y 32 RDL 4/ 2004)  [00572]
17 | 198 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición  - D.I. internacional periodos anteriores aplicada en el ejercicio (art. 31 y 32 LIS)  [00571]
18 | 215 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición  - D.I. internacional generada y aplicada en el ejercicio actual(art. 31 y 32 LIS)  [00573]
19 | 232 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición  - Transparencia fiscal internacional (art. 100.11 LIS)  [00575]
20 | 249 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición  - D.I. interna intersocietaria al 5/10 % (cooperativas) [00577]
21 | 266 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones empresas navieras en Canarias  (art. 76 Ley 19/1994)  [00581]
22 | 283 | 17 | N | Liquidación III - Bonificaciones/Deducciones doble imposición - Cuota íntegra ajustada positiva [00582]
23 | 300 | 17 | Num | Liquidación III - Otras deducciones - Apoyo fiscal a la inversión y otras deducciones  [00583]
24 | 317 | 17 | Num | Liquidación III - Otras deducciones - Deducción DT 24.7 L.I.S. art.42 y art. 36 ter Ley 43/95  [00585]
25 | 334 | 17 | Num | Liquidación III - Otras deducciones - Deducciones DT 24.1 LIS D.T. 8ª  RDL 4/2004  [00584]
26 | 351 | 17 | Num | Liquidación III - Otras deducciones - Deducciones con límite del Capítulo IV Título VI RDL 4/2004 y LIS  [00588]
27 | 368 | 17 | Num | Liquidación III - Otras deducciones - Deducciones por producc. Cinematograf. Extranjeras (art. 36.2 LIS)  [01039]
28 | 385 | 17 | Num | Liquidación III - Otras deducciones - Deducción donaciones a entidades sin fines de lucro [00565]
29 | 402 | 17 | Num | Liquidación III - Otras deducciones - Deducciones inversión Canarias (Ley 20/1991) [00590]
30 | 419 | 17 | Num | Liquidación III - Otras deducciones - Deducciones especifícas de las entidades sometidas a normativa foral [00399]
31 | 436 | 17 | Num | Liquidación III - Otras deducciones - Deducciones excluidas de límite I+D [00082]
32 | 453 | 17 | Num | Liquidación III - Otras deducciones - Deducciones por reversión de medidas temporales  DT 37ª.1 LIS [01040]
33 | 470 | 17 | Num | Liquidación III - Otras deducciones - Deducciones por reversión de medidas temporales  DT 37ª.2 LIS [01041]
34 | 487 | 17 | N | Liquidación III - Otras deducciones - Cuota líquida positiva [00592]
35 | 504 | 17 | Num | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Retenciones e ingresos a cuenta/pagos a cuenta participaciones I.I.C. [00595]
36 | 521 | 17 | Num | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Ret. e ingr. a cuenta/pagos a cuenta participaciones I.I.C. imputadas por agrup. de interés economico y UTES [00596]
37 | 538 | 17 | Num | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Retenciones sobre premios loterías y apuestas [00597]
38 | 555 | 17 | N | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Cuota del ejercicio a ingresar o a devolver - Estado [00599]
39 | 572 | 17 | N | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Cuota del ejercicio a ingresar o a devolver - D. Forales/Navarra (Totales)  [00600]
40 | 589 | 17 | Num | Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 1er. pago fraccionado - Estado [00601]
41 | 606 | 17 | Num | Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 1er. Pago fraccionado - D. Forales/Navarra (Totales) [00602]
42 | 623 | 17 | Num | Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 2er. Pago fraccionado - Estado [00603]
43 | 640 | 17 | Num | Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 2er. Pago fraccionado -  D. Forales/Navarra (Totales) [00604]
44 | 657 | 17 | Num | Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 3er. Pago fraccionado - Estado [00605]
45 | 674 | 17 | Num | Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 3er. Pago fraccionado - D. Forales/Navarra (Totales) [00606]
46 | 691 | 17 | N | Liquidación III - Pagos fraccionados/Cuota diferencial - Cuota diferencial  - Estado [00611]
47 | 708 | 17 | N | Liquidación III - Pagos fraccionados/Cuota diferencial - Cuota diferencial  - D. Forales/Navarra (Totales) [00612]
48 | 725 | 17 | Num | Liquidación III - Líquido a ingresar o a devolver - Incremento por pérdida beneficios fiscales períodos anteriores  - Estado [00615]
49 | 742 | 17 | Num | Liquidación III - Líquido a ingresar o a devolver - Incremento por pérdida beneficios fiscales períodos anteriores  - D. Forales/Navarra (Totales) [00616]
50 | 759 | 17 | Num | Liquidación III - Líquido a ingresar o a devolver - Incremento por incumplimiento de requisitos SOCIMI  -  Estado [00633]
51 | 776 | 17 | Num | Liquidación III - Líquido a ingresar o a devolver - Incremento por incumplimiento de requisitos SOCIMI  -  D. Forales/Navarra (Totales) [00642]
52 | 793 | 17 | Num | Liquidación III - Líquido a ingresar o a devolver - Intereses de demora  - Estado [00617]
53 | 810 | 17 | Num | Liquidación III - Líquido a ingresar o a devolver - Intereses de demora  - D. Forales/Navarra (Totales) [00618]
54 | 827 | 17 | N | Liquidación III - Líquido a ingresar o a devolver - Importe ingreso/devolución efectuada de la declaración originaria  - Estado [00619]
55 | 844 | 17 | N | Liquidación III - Líquido a ingresar o a devolver - Importe ingreso/devolución efectuada de la declaración originaria  - D. Forales/Navarra (Totales) [00620]
56 | 861 | 17 | Num | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Abono deducciones I+D+i por insuficiencia de cuota (opción art. 44.2 RDL 4/2004 y art. 39.2 LIS) - Estado  [00083]
57 | 878 | 17 | Num | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Abono deducciones I+D+i por insuficiencia de cuota (opción art. 44.2 RDL 4/2004 y art. 39.2 LIS) - D. Forales/Navarra (Totales)  [01332]
58 | 895 | 17 | Num | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Abono deducciones por producciones extranjeras (art. 36.2 LIS)  - TOTAL (Estado + D. Forales/Navarra)  [01200]
59 | 912 | 17 | Num | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Abono deducciones por producciones extranjeras (art. 36.2 LIS) - Estado  [01042]
60 | 929 | 17 | Num | Liquidación III - Cuota del ejercicio a ingresar o a devolver - Abono deducciones por producciones extranjeras (art. 36.2 LIS)  -  D. Forales/Navarra [01333]
61 | 946 | 17 | N | Liquidación III - Líquido a ingresar o a devolver  - Estado [00621]
62 | 963 | 17 | N | Liquidación III - Líquido a ingresar o a devolver  - D. Forales/Navarra (Totales) [00622]
63 | 980 | 17 | N | Liquidación III - Abono por conversión de activos por impuesto diferido en credito exigible frente a la admon.tribut. (art. 130 LIS)  Estado  [01020]
64 | 997 | 17 | N | Liquidación III - Abono por conversión de activos por impuesto diferido en credito exigible frente a la admon.tribut. (art. 130 LIS)  D. Forales/Navarra (Totales)  [001043]
65 | 1014 | 17 | N | Liquidación III - Compensación por conversión de activos por impuesto diferido en credito exigible frente a la admon.tribut. (art. 130 LIS)  Estado  [01021]
66 | 1031 | 17 | N | Liquidación III - Compensación por conversión de activos por impuesto diferido en credito exigible frente a la admon.tribut. (art. 130 LIS)  D. Forales/Navarra (Totales)  [001044]
67 | 1048 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200140>"
Total: |  | 1057

# DP200015

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. Constante "<T" . Campo OBLIGATORIO | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "150"
4 | 9 | 1 | An | Fin de identificador de modelo. Constante: ">" .Campo OBLIGATORIO | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | Num | Detalle compensación bases imponibles negativas - 1997 - Pendiente aplicación a principio del período [00640]
7 | 28 | 17 | Num | Detalle compensación bases imponibles negativas - 1997 - Aplicado en esta liquidación [00641]
8 | 45 | 17 | Num | Detalle compensación bases imponibles negativas - 1997 - Pendiente aplicación en períodos futuros [00548]
9 | 62 | 17 | Num | Detalle compensación bases imponibles negativas - 1998 - Pendiente aplicación a principio del período [00643]
10 | 79 | 17 | Num | Detalle compensación bases imponibles negativas - 1998 - Aplicado en esta liquidación [00644]
11 | 96 | 17 | Num | Detalle compensación bases imponibles negativas - 1998 - Pendiente aplicación en períodos futuros [00645]
12 | 113 | 17 | Num | Detalle compensación bases imponibles negativas - 1999 - Pendiente aplicación a principio del período [00646]
13 | 130 | 17 | Num | Detalle compensación bases imponibles negativas - 1999 - Aplicado en esta liquidación [00647]
14 | 147 | 17 | Num | Detalle compensación bases imponibles negativas - 1999 - Pendiente aplicación en períodos futuros [00648]
15 | 164 | 17 | Num | Detalle compensación bases imponibles negativas - 2000 - Pendiente aplicación a principio del período [00649]
16 | 181 | 17 | Num | Detalle compensación bases imponibles negativas - 2000 - Aplicado en esta liquidación [00650]
17 | 198 | 17 | Num | Detalle compensación bases imponibles negativas - 2000 - Pendiente aplicación en períodos futuros [00651]
18 | 215 | 17 | Num | Detalle compensación bases imponibles negativas - 2001 - Pendiente aplicación a principio del período [00652]
19 | 232 | 17 | Num | Detalle compensación bases imponibles negativas - 2001 - Aplicado en esta liquidación [00653]
20 | 249 | 17 | Num | Detalle compensación bases imponibles negativas - 2001 - Pendiente aplicación en períodos futuros [00654]
21 | 266 | 17 | Num | Detalle compensación bases imponibles negativas - 2002 - Pendiente aplicación a principio del período [00655]
22 | 283 | 17 | Num | Detalle compensación bases imponibles negativas - 2002 - Aplicado en esta liquidación [00656]
23 | 300 | 17 | Num | Detalle compensación bases imponibles negativas - 2002 - Pendiente aplicación en períodos futuros [00657]
24 | 317 | 17 | Num | Detalle compensación bases imponibles negativas - 2003 - Pendiente aplicación a principio del período [00658]
25 | 334 | 17 | Num | Detalle compensación bases imponibles negativas - 2003 - Aplicado en esta liquidación [00659]
26 | 351 | 17 | Num | Detalle compensación bases imponibles negativas - 2003 - Pendiente aplicación en períodos futuros [00660]
27 | 368 | 17 | Num | Detalle compensación bases imponibles negativas - 2004 - Pendiente aplicación a principio del período [00661]
28 | 385 | 17 | Num | Detalle compensación bases imponibles negativas - 2004 - Aplicado en esta liquidación [00662]
29 | 402 | 17 | Num | Detalle compensación bases imponibles negativas - 2004 - Pendiente aplicación en períodos futuros [00663]
30 | 419 | 17 | Num | Detalle compensación bases imponibles negativas - 2005 - Pendiente aplicación a principio del período [00664]
31 | 436 | 17 | Num | Detalle compensación bases imponibles negativas - 2005 - Aplicado en esta liquidación [00665]
32 | 453 | 17 | Num | Detalle compensación bases imponibles negativas - 2005 - Pendiente aplicación en períodos futuros [00666]
33 | 470 | 17 | Num | Detalle compensación bases imponibles negativas - 2006 - Pendiente aplicación a principio del período [00667]
34 | 487 | 17 | Num | Detalle compensación bases imponibles negativas - 2006 - Aplicado en esta liquidación [00668]
35 | 504 | 17 | Num | Detalle compensación bases imponibles negativas - 2006 - Pendiente aplicación en períodos futuros [00669]
36 | 521 | 17 | Num | Detalle compensación bases imponibles negativas - 2007 - Pendiente aplicación a principio del período [00743]
37 | 538 | 17 | Num | Detalle compensación bases imponibles negativas - 2007 - Aplicado en esta liquidación [00747]
38 | 555 | 17 | Num | Detalle compensación bases imponibles negativas - 2007 - Pendiente aplicación en períodos futuros [00748]
39 | 572 | 17 | Num | Detalle compensación bases imponibles negativas - 2008 - Pendiente aplicación a principio del período [00275]
40 | 589 | 17 | Num | Detalle compensación bases imponibles negativas - 2008 - Aplicado en esta liquidación [00276]
41 | 606 | 17 | Num | Detalle compensación bases imponibles negativas - 2008 - Pendiente aplicación en períodos futuros [00277]
42 | 623 | 17 | Num | Detalle compensación bases imponibles negativas - 2009 - Pendiente de aplicación a principio del período [00608]
43 | 640 | 17 | Num | Detalle compensación bases imponibles negativas - 2009 - Aplicado en esta liquidación [00609]
44 | 657 | 17 | Num | Detalle compensación bases imponibles negativas - 2009 - Pendiente aplicación en períodos futuros [00610]
45 | 674 | 17 | Num | Detalle compensación bases imponibles negativas - 2010 - Pendiente aplicación a principio del período [00704]
46 | 691 | 17 | Num | Detalle compensación bases imponibles negativas - 2010 - Aplicado en esta liquidación [00705]
47 | 708 | 17 | Num | Detalle compensación bases imponibles negativas - 2010 - Pendiente aplicación en períodos futuros [00706]
48 | 725 | 17 | Num | Detalle compensación bases imponibles negativas - 2011 - Pendiente aplicación a principio del período [00013]
49 | 742 | 17 | Num | Detalle compensación bases imponibles negativas - 2011 - Aplicado en esta liquidación [00014]
50 | 759 | 17 | Num | Detalle compensación bases imponibles negativas - 2011 - Pendiente aplicación en períodos futuros [00015]
51 | 776 | 17 | Num | Detalle compensación bases imponibles negativas - 2012 - Pendiente aplicación a principio del período  [00725]
52 | 793 | 17 | Num | Detalle compensación bases imponibles negativas - 2012 - Aplicado en esta liquidación [00726]
53 | 810 | 17 | Num | Detalle compensación bases imponibles negativas - 2012 - Pendiente aplicación en períodos futuros [00727]
54 | 827 | 17 | Num | Detalle compensación bases imponibles negativas - 2013  - Pendiente aplicación a principio del período  [00534]
55 | 844 | 17 | Num | Detalle compensación bases imponibles negativas - 2013  - Aplicado en esta liquidación [00535]
56 | 861 | 17 | Num | Detalle compensación bases imponibles negativas - 2013 - Pendiente aplicación en períodos futuros [00536]
57 | 878 | 17 | Num | Detalle compensación bases imponibles negativas - 2014   - Pendiente aplicación a principio del período  [00607]
58 | 895 | 17 | Num | Detalle compensación bases imponibles negativas - 2014   - Aplicado en esta liquidación [00675]
59 | 912 | 17 | Num | Detalle compensación bases imponibles negativas - 2014  - Pendiente aplicación en períodos futuros [00699]
60 | 929 | 17 | Num | Detalle compensación bases imponibles negativas - 2015(*)  - Pendiente aplicación a principio del período  [01045]
61 | 946 | 17 | Num | Detalle compensación bases imponibles negativas - 2015(*)  - Aplicado en esta liquidación [01046]
62 | 963 | 17 | Num | Detalle compensación bases imponibles negativas - 2015(*)  - Pendiente aplicación en períodos futuros [01047]
63 | 980 | 17 | Num | Detalle compensación bases imponibles negativas - TOTAL - Pendiente aplicación a principio del período [00670]
64 | 997 | 17 | Num | Detalle compensación bases imponibles negativas - TOTAL - Aplicado en esta liquidación [00547]
65 | 1014 | 17 | Num | Detalle compensación bases imponibles negativas - TOTAL - Pendiente de aplicación en períodos futuros [00671]
66 | 1031 | 17 | Num | Detalle compensación bases imponibles negativas - 2015   - Pendiente aplicación a principio del período  [01048]
67 | 1048 | 17 | Num | Detalle compensación bases imponibles negativas - 2015  - Pendiente aplicación en períodos futuros [01049]
68 | 1065 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - Deducción pendiente [00104]
69 | 1082 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - Tipo gravamen período generación [00105]
70 | 1086 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - 2015 Deducción pendiente [00846]
71 | 1103 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - Aplicado en esta liquidación [00847]
72 | 1120 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - Deducción pendiente [00106]
73 | 1137 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - Tipo gravamen período generación [00107]
74 | 1141 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - 2015 Deducción pendiente [00282]
75 | 1158 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - Aplicado en esta liquidación [00283]
76 | 1175 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - Pendiente aplic. en períodos futuros [00284]
77 | 1192 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - Deducción pendiente [00108]
78 | 1209 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - Tipo gravamen período generación [00109]
79 | 1213 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - 2015 Deducción pendiente [00702]
80 | 1230 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - Aplicado en esta liquidación [00703]
81 | 1247 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - Pendiente aplic. en períodos futuros [00707]
82 | 1264 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - Deducción pendiente [00110]
83 | 1281 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - Tipo gravamen período generación [00111]
84 | 1285 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - 2015 Deducción pendiente [00071]
85 | 1302 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - Aplicado en esta liquidación [00187]
86 | 1319 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - Pendiente aplic. en períodos futuros [00300]
87 | 1336 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - Deducción pendiente [00112]
88 | 1353 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - Tipo gravamen período generación [113]
89 | 1357 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - 2015 Deducción pendiente [00025]
90 | 1374 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - Aplicado en esta liquidación [00026]
91 | 1391 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - Pendiente aplic. en períodos futuros [00027]
92 | 1408 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - Deducción pendiente [00114]
93 | 1425 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - Tipo gravamen período generación [00115]
94 | 1429 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - 2015 Deducción pendiente [00714]
95 | 1446 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - Aplicado en esta liquidación [00715]
96 | 1463 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - Pendiente aplic. en períodos futuros [00716]
97 | 1480 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014 - Deducción pendiente [00735]
98 | 1497 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014 - Tipo gravamen período generación [00920]
99 | 1501 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014 - 2015 Deducción pendiente [00736]
100 | 1518 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014 - Aplicado en esta liquidación [00737]
101 | 1535 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014  - Pendiente aplic. en períodos futuros [00738]
102 | 1552 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - Total - Deducción pendiente [00116]
103 | 1569 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - Total - 2015 Deducción pendiente [00117]
104 | 1586 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - Total -  Aplicado en esta liquidación [00570]
105 | 1603 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - Total -  Pendiente aplic. en períodos futuros [00118]
106 | 1620 | 7 | Num | Deducciones doble imposición interna - Tipo de gravamen 2015  [00103]
107 | 1627 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - Deducción pendiente   [00153]
108 | 1644 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - Tipo gravamen período generación [00728]
109 | 1648 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - 2015 Deducción pendiente [00637]
110 | 1665 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - Aplicado en esta liquidación [00638]
111 | 1682 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - Deducción pendiente [00154]
112 | 1699 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - Tipo gravamen período generación [00729]
113 | 1703 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - 2015 Deducción pendiente [00849]
114 | 1720 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - Aplicado en esta liquidación [00894]
115 | 1737 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - Pendiente aplic. en períodos futuros [00197]
116 | 1754 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - Deducción pendiente  [00155]
117 | 1771 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - Tipo gravamen período generación [00730]
118 | 1775 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - 2015 Deducción pendiente [00285]
119 | 1792 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - Aplicado en esta liquidación [00286]
120 | 1809 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - Pendiente aplic. en períodos futuros [00287]
121 | 1826 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - Deducción pendiente   [00156]
122 | 1843 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - Tipo gravamen período generación [00731]
123 | 1847 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - 2015 Deducción pendiente [00825]
124 | 1864 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - Aplicado en esta liquidación [00826]
125 | 1881 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - Pendiente aplic. en períodos futuros [00827]
126 | 1898 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009 - Deducción pendiente   [00157]
127 | 1915 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009 - Tipo gravamen período generación [00732]
128 | 1919 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009 - 2015 Deducción pendiente [00001]
129 | 1936 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009 - Aplicado en esta liquidación [00002]
130 | 1953 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009- Pendiente aplic. en períodos futuros [00003]
131 | 1970 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- Deducción pendiente   [00158]
132 | 1987 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- Tipo gravamen período generación [00733]
133 | 1991 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- 2015 Deducción pendiente [00028]
134 | 2008 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- Aplicado en esta liquidación [00029]
135 | 2025 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- Pendiente aplic. en períodos futuros [00030]
136 | 2042 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - Deducción pendiente   [00159]
137 | 2059 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - Tipo gravamen período generación [00734]
138 | 2063 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - 2015 Deducción pendiente [00717]
139 | 2080 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - Aplicado en esta liquidación [00718]
140 | 2097 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - Pendiente aplic. en períodos futuros [00719]
141 | 2114 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - Deducción pendiente   [00720]
142 | 2131 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - Tipo gravamen período generación [00721]
143 | 2135 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - 2015 Deducción pendiente [00722]
144 | 2152 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - Aplicado en esta liquidación [00723]
145 | 2169 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - Pendiente aplic. en períodos futuros [00724]
146 | 2186 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2013 - Deducción pendiente   [00739]
147 | 2203 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2013 - Tipo gravamen período generación [00921]
148 | 2207 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2013 - 2015 Deducción pendiente [00740]
149 | 2224 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2013 - Aplicado en esta liquidación [00741]
150 | 2241 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2013 - Pendiente aplic. en períodos futuros [00742]
151 | 2258 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2014 - Deducción pendiente   [00134]
152 | 2275 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2014 - Tipo gravamen período generación [00926]
153 | 2279 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2014 - 2015 Deducción pendiente [00135]
154 | 2296 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2014 - Aplicado en esta liquidación [00136]
155 | 2313 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004  - DI internacional 2014 - Pendiente aplic. en períodos futuros [00137]
156 | 2330 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - Total - Deducción pendiente   [00160]
157 | 2347 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - Total - 2015 Deducción pendiente [00161]
158 | 2364 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - Total - Aplicado en esta liquidación [00572]
159 | 2381 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - Total  - Deducción pendiente ejercicios futuros [00162]
160 | 2398 | 7 | Num | Deducciones doble imposición internacional RDL 4/2004 - Tipo de gravamen 2015  [00103]
161 | 2405 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 (*) - Deducción pendiente [01054]
162 | 2422 | 4 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 (*) - Tipo gravamen período generación  [01050]
163 | 2426 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 (*) - 2015 Deducción pendiente [01051]
164 | 2443 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 (*) -  Aplicado en esta liquidación [01052]
165 | 2460 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 (*)  -  Pendiente aplic. en períodos futuros [01053]
166 | 2477 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2015 (*)  -  Deducción pendiente  [00131]
167 | 2494 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2015 (*)  -  2015 Deducción pendiente [00132]
168 | 2511 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2015 (*)  -  Aplicado en esta liquidación [00571]
169 | 2528 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2015 (*) -  Pendiente aplic. en períodos futuros [00133]
170 | 2545 | 7 | Num | Deducciones doble imposición internacional LIS - Tipo de gravamen 2015  [00103]
171 | 2552 | 17 | Num | Deducciones doble imposición internacional LIS - DI juridic.Imp.soportado por el contribuyente (art.31 LIS) -  Deducción generada  [00163]
172 | 2569 | 17 | Num | Deducciones doble imposición internacional LIS - DI juridic.Imp.soportado por el contribuyente (art. 31 LIS) -  Aplicado en esta liquidación  [00165]
173 | 2586 | 17 | Num | Deducciones doble imposición internacional LIS - DI juridic.Imp.soportado por el contribuyente (art. 31 LIS) -  Pendiente aplic. en períodos futuros  [00166]
174 | 2603 | 17 | Num | Deducciones doble imposición internacional LIS - DI economica Dividendos y part. en beneficios (art.32 LIS) -  Deducción generada  [00167]
175 | 2620 | 17 | Num | Deducciones doble imposición internacional LIS - DI economica Dividendos y part. en beneficios (art.32 LIS) -  Aplicado en esta liquidación  [00169]
176 | 2637 | 17 | Num | Deducciones doble imposición internacional LIS - DI economica Dividendos y part. en beneficios (art.32 LIS) -  Pendiente aplic. en períodos futuros  [00170]
177 | 2654 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2015 - Deducción generada   [00171]
178 | 2671 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2015 - Aplicado en esta liquidación [00573]
179 | 2688 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2015 - Pendiente aplic. en períodos futuros [00174]
180 | 2705 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200150>"
Total: |  | 2714

# DP200016

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página.  Campo OBLIGATORIO | OBLIGATORIO | Constante "160"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria. |  | En blanco
6 | 11 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 36 ter Ley 43 / 1995.  2002 - Deducción pendiente/generada [00835]
7 | 28 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 36 ter Ley 43 / 1995.  2002 - Aplicado en esta liquidación [00836]
8 | 45 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 36 ter Ley 43 / 1995.  2002 - Pendiente aplicación en periodos futuros [00837]
9 | 62 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 36 ter Ley 43 / 1995.  2003 - Deducción pendiente/generada [00838]
10 | 79 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 36 ter Ley 43 / 1995.  2003 - Aplicado en esta liquidación [00839]
11 | 96 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 36 ter Ley 43 / 1995.  2003 - Pendiente aplicación en periodos futuros [00840]
12 | 113 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2004- Deducción pendiente/generada [00932]
13 | 130 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2004 - Aplicado en esta liquidación [00933]
14 | 147 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2004 - Pendiente aplicación en periodos futuros [00934]
15 | 164 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2005 - Deducción pendiente/generada [00297]
16 | 181 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2005 - Aplicado en esta liquidación [00298]
17 | 198 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2005 - Pendiente aplicación en periodos futuros [00299]
18 | 215 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2006 - Deducción pendiente/generada [00090]
19 | 232 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2006 - Aplicado en esta liquidación [00091]
20 | 249 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2006 - Pendiente aplicación en periodos futuros [00092]
21 | 266 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2007 - Deducción pendiente/generada [00004]
22 | 283 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2007 - Aplicado en esta liquidación [00005]
23 | 300 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2007 - Pendiente aplicación en periodos futuros [00006]
24 | 317 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2008 - Deducción pendiente/generada [00031]
25 | 334 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2008 - Aplicado en esta liquidación [00032]
26 | 351 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2008 - Pendiente aplicación en periodos futuros [00033]
27 | 368 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2009 - Deducción pendiente/generada [00022]
28 | 385 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2009 - Aplicado en esta liquidación [00023]
29 | 402 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2009 - Pendiente aplicación en periodos futuros [00024]
30 | 419 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2010 - Deducción pendiente/generada [00040]
31 | 436 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2010 - Aplicado en esta liquidación [00041]
32 | 453 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2010 - Pendiente aplicación en periodos futuros [042]
33 | 470 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004  2011 - Deducción pendiente/generada [00138]
34 | 487 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2011 - Aplicado en esta liquidación [00139]
35 | 504 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2011 - Pendiente aplicación en periodos futuros [00140]
36 | 521 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2012 - Deducción pendiente/generada [00141]
37 | 538 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2012 - Aplicado en esta liquidación [00142]
38 | 555 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004  2012 - Pendiente aplicación en periodos futuros [00143]
39 | 572 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2013 - Deducción pendiente/generada [00188]
40 | 589 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2013 - Aplicado en esta liquidación [00189]
41 | 606 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2013 - Pendiente aplicación en periodos futuros [00190]
42 | 623 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2014 - Deducción pendiente/generada [00803]
43 | 640 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2014 - Aplicado en esta liquidación [00804]
44 | 657 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2014 - Pendiente aplicación en periodos futuros [00805]
45 | 674 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015 (*) - Deducción pendiente/generada [01055]
46 | 691 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015 (*) - Aplicado en esta liquidación [01056]
47 | 708 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015 (*) - Pendiente aplicación en periodos futuros [01057]
48 | 725 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015  - Deducción pendiente/generada [00700]
49 | 742 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015 - Aplicado en esta liquidación [00708]
50 | 759 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015 - Pendiente aplicación en periodos futuros [00709]
51 | 776 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Total Deducc. Art. 36 ter Ley 43 / 1995 y 42 RDL 4/2004 y 24ª.7 LIS  - Deducción pendiente/generada [00841]
52 | 793 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Total Deducc. Art. 36 ter Ley 43 / 1995 y 42 RDL 4/2004 y 24ª.7 LIS  -  Aplicado en esta liquidación [00585]
53 | 810 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Total Deducc. Art. 36 ter Ley 43 / 1995 y 42 RDL 4/2004 y 24ª.7 LIS  -  Pendiente aplicación en periodos futuros [00843]
54 | 827 | 17 | Num | Deducciones DT 24ª.1 LIS  - 2010 Periodificación - Deducción pendiente/generada [00749]
55 | 844 | 17 | Num | Deducciones DT 24ª.1 LIS -  2010 Periodificación - Aplicado en esta liquidación [00750]
56 | 861 | 17 | Num | Deducciones DT 24ª.1 LIS  - 2011 Periodificación - Deducción pendiente/generada [00752]
57 | 878 | 17 | Num | Deducciones DT 24ª.1 LIS - 2011 Periodificación - Aplicado en esta liquidación [00753]
58 | 895 | 17 | Num | Deducciones DT 24ª.1 LIS - 2011 Periodificación - Pendiente de aplicación en periodos futuros [00754]
59 | 912 | 17 | Num | Deducciones DT 24ª.1 LIS - 2012 Periodificación - Deducción pendiente/generada [00755]
60 | 929 | 17 | Num | Deducciones DT 24ª.1 LIS - 2012 Periodificación - Aplicado en esta liquidación [00756]
61 | 946 | 17 | Num | Deducciones DT 24ª.1 LIS - 2012 Periodificación - Pendiente de aplicación en periodos futuros [00757]
62 | 963 | 17 | Num | Deducciones DT 24ª.1 LIS - 2013 Periodificación - Deducción pendiente/generada [00758]
63 | 980 | 17 | Num | Deducciones DT 24ª.1 LIS - 2013 Periodificación - Aplicado en esta liquidación [00759]
64 | 997 | 17 | Num | Deducciones DT 24ª.1 LIS - 2013 Periodificación - Pendiente de aplicación en periodos futuros [00760]
65 | 1014 | 17 | Num | Deducciones DT 24ª.1 LIS - 2014 Periodificación - Deducción pendiente/generada [00761]
66 | 1031 | 17 | Num | Deducciones DT 24ª.1 LIS - 2014 Periodificación - Aplicado en esta liquidación [00762]
67 | 1048 | 17 | Num | Deducciones DT 24ª.1 LIS - 2014 Periodificación - Pendiente de aplicación en periodos futuros [00763]
68 | 1065 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015 (*) Periodificación - Deducción pendiente/generada [00744]
69 | 1082 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015(*) Periodificación - Aplicado en esta liquidación [00745]
70 | 1099 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015(*) Periodificación - Pendiente de aplicación en periodos futuros [00746]
71 | 1116 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015 Periodificación - Deducción pendiente/generada [00779]
72 | 1133 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015 Periodificación - Aplicado en esta liquidación [00783]
73 | 1150 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015 Periodificación - Pendiente de aplicación en periodos futuros [00784]
74 | 1167 | 17 | Num | Deducciones DT 24ª.1 LIS - Total deducciones DT octava LIS  -  Deducción pendiente/generada [00764]
75 | 1184 | 17 | Num | Deducciones DT 24ª.1 LIS - Total deducciones DT octava LIS  - Aplicado en esta liquidación [00584]
76 | 1201 | 17 | Num | Deducciones DT 24ª.1 LIS  - Total deducciones DT octava LIS  - Pendiente de aplicación en periodos futuros [00765]
77 | 1218 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2010 - Deducción pendiente/generada [00854]
78 | 1235 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2010 - Aplicado en esta liquidación [00855]
79 | 1252 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2011- Deducción pendiente/generada [00857]
80 | 1269 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2011 - Aplicado en esta liquidación [00858]
81 | 1286 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2011 - Pendiente de aplicación en periodos futuros [00859]
82 | 1303 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2012 - Deducción pendiente/generada [00860]
83 | 1320 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2012 - Aplicado en esta liquidación [00861]
84 | 1337 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2012 - Pendiente de aplicación en periodos futuros [00862]
85 | 1354 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2013 - Deducción pendiente/generada [00863]
86 | 1371 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2013 - Aplicado en esta liquidación [00864]
87 | 1388 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2013 - Pendiente de aplicación en periodos futuros [00865]
88 | 1405 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2014 - Deducción pendiente/generada [00883]
89 | 1422 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2014 - Aplicado en esta liquidación [00884]
90 | 1439 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2014 - Pendiente de aplicación en periodos futuros [00885]
91 | 1456 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 (*) - Deducción pendiente/generada [00785]
92 | 1473 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 (*) - Aplicado en esta liquidación [00789]
93 | 1490 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 (*) - Pendiente de aplicación en periodos futuros [00790]
94 | 1507 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 - Deducción pendiente/generada [00852]
95 | 1524 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 - Aplicado en esta liquidación [00853]
96 | 1541 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 - Pendiente de aplicación en periodos futuros [00856]
97 | 1558 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 1997 - Deducción pendiente/generada [00088]
98 | 1575 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 1997 - Aplicado en esta liquidación [00564]
99 | 1592 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 1998 - Deducción pendiente/generada [00194]
100 | 1609 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 1998 - Aplicado en esta liquidación [00195]
101 | 1626 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 1998 - Pendiente de aplicación en periodos futuros [00196]
102 | 1643 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 1999 - Deducción pendiente/generada  [00868]
103 | 1660 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 1999 - Aplicado en esta liquidación [00869]
104 | 1677 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 1999 - Pendiente de aplicación en periodos futuros [00834]
105 | 1694 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2000 - Deducción pendiente/generada [00871]
106 | 1711 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2000 - Aplicado en esta liquidación [00872]
107 | 1728 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2000 - Pendiente de aplicación en periodos futuros [00873]
108 | 1745 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2001 - Deducción pendiente/generada [00874]
109 | 1762 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2001 - Aplicado en esta liquidación [00875]
110 | 1779 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2001 - Pendiente de aplicación en periodos futuros [00876]
111 | 1796 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2002 - Deducción pendiente/generada [00877]
112 | 1813 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2002 - Aplicado en esta liquidación [00878]
113 | 1830 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2002 - Pendiente de aplicación en periodos futuros [00879]
114 | 1847 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2003 - Deducción pendiente/generada [00880]
115 | 1864 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2003 - Aplicado en esta liquidación [00881]
116 | 1881 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2003 - Pendiente de aplicación en periodos futuros [00882]
117 | 1898 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2004 - Deducción pendiente/generada [00866]
118 | 1915 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2004 - Aplicado en esta liquidación [00867]
119 | 1932 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2004 - Pendiente de aplicación en periodos futuros [00870]
120 | 1949 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2005 - Deducción pendiente/generada [00939]
121 | 1966 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2005 - Aplicado en esta liquidación [00940]
122 | 1983 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2005 - Pendiente de aplicación en periodos futuros [00941]
123 | 2000 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2006 - Deducción pendiente/generada [00191]
124 | 2017 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2006 - Aplicado en esta liquidación [00192]
125 | 2034 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2006 - Pendiente de aplicación en periodos futuros [00193]
126 | 2051 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2007 - Deducción pendiente/generada  [00613]
127 | 2068 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2007 - Aplicado en esta liquidación [00614]
128 | 2085 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2007 - Pendiente de aplicación en periodos futuros [00701]
129 | 2102 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2008 - Deducción pendiente/generada [00200]
130 | 2119 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2008 - Aplicado en esta liquidación [00257]
131 | 2136 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2008 - Pendiente de aplicación en periodos futuros [00011]
132 | 2153 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2009 - Deducción pendiente/generada [00037]
133 | 2170 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2009 - Aplicado en esta liquidación [00038]
134 | 2187 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2009 - Pendiente de aplicación en periodos futuros [00039]
135 | 2204 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2010 - Deducción pendiente/generada [00044]
136 | 2221 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2010 - Aplicado en esta liquidación [00045]
137 | 2238 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2010 - Pendiente de aplicación en periodos futuros [00046]
138 | 2255 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2011 - Deducción pendiente/generada [00528]
139 | 2272 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2011 - Aplicado en esta liquidación [00529]
140 | 2289 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2011 - Pendiente de aplicación en periodos futuros [00530]
141 | 2306 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2012 - Deducción pendiente/generada [00144]
142 | 2323 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2012 - Aplicado en esta liquidación [00145]
143 | 2340 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2012 - Pendiente de aplicación en periodos futuros [00146]
144 | 2357 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2013 - Deducción pendiente/generada [00147]
145 | 2374 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2013 - Aplicado en esta liquidación [00148]
146 | 2391 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2013 - Pendiente de aplicación en periodos futuros [00149]
147 | 2408 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2014  - Deducción pendiente/generada [00240]
148 | 2425 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2014  - Aplicado en esta liquidación [00241]
149 | 2442 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2014  - Pendiente de aplicación en periodos futuros [00242]
150 | 2459 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015 (*) - Deducción pendiente/generada [01058]
151 | 2476 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015 (*) - Aplicado en esta liquidación [01059]
152 | 2493 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015 (*) - Pendiente de aplicación en periodos futuros [01060]
153 | 2510 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015  - Deducción pendiente/generada [00791]
154 | 2527 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015  - Aplicado en esta liquidación [00802]
155 | 2544 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015  - Pendiente de aplicación en periodos futuros [00806]
156 | 2561 | 17 | Num | Total deducciones inversiónes en  Canarias (Ley 20/1991) - Deducción pendiente/generada [00886]
157 | 2578 | 17 | Num | Total deducciones inversiónes en  Canarias (Ley 20/1991) - Aplicado en esta liquidación [00590]
158 | 2595 | 17 | Num | Total deducciones inversiónes en  Canarias (Ley 20/1991) - Pendiente de aplicación en periodos futuros [00887]
159 | 2612 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200160>"
Total: |  | 2621

# DP200017

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "170"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | Num | Deducc. para  incentivar determ.actividades - 1997 Suma deducciones - Deducción pendiente/generada [01061]
7 | 28 | 17 | Num | Deducc. para  incentivar determ.actividades - 1997 Suma deducciones - Aplicado en esta liquidación [01062]
8 | 45 | 17 | Num | Deducc. para  incentivar determ.actividades - 1998 Suma deducciones - Deducción pendiente/generada [00768]
9 | 62 | 17 | Num | Deducc. para  incentivar determ.actividades - 1998 Suma deducciones - Aplicado en esta liquidación [00769]
10 | 79 | 17 | Num | Deducc. para  incentivar determ.actividades - 1998 Suma deducciones - Pendiente de aplicación en periodos futuros [00770]
11 | 96 | 17 | Num | Deducc. para  incentivar determ.actividades - 1999 Suma deducciones - Deducción pendiente/generada [00774]
12 | 113 | 17 | Num | Deducc. para  incentivar determ.actividades - 1999 Suma deducciones - Aplicado en esta liquidación [00775]
13 | 130 | 17 | Num | Deducc. para  incentivar determ.actividades - 1999 Suma deducciones - Pendiente de aplicación en periodos futuros [00776]
14 | 147 | 17 | Num | Deducc. para  incentivar determ.actividades - 2000 Suma deducciones - Deducción pendiente/generada [00780]
15 | 164 | 17 | Num | Deducc. para  incentivar determ.actividades - 2000 Suma deducciones - Aplicado en esta liquidación [00781]
16 | 181 | 17 | Num | Deducc. para  incentivar determ.actividades - 2000 Suma deducciones - Pendiente de aplicación en periodos futuros [00782]
17 | 198 | 17 | Num | Deducc. para  incentivar determ.actividades - 2001 Suma deducciones - Deducción pendiente/generada [00786]
18 | 215 | 17 | Num | Deducc. para  incentivar determ.actividades - 2001 Suma deducciones - Aplicado en esta liquidación [00787]
19 | 232 | 17 | Num | Deducc. para  incentivar determ.actividades - 2001 Suma deducciones - Pendiente de aplicación en periodos futuros [00788]
20 | 249 | 17 | Num | Deducc. para  incentivar determ.actividades - 2002 Suma deducciones - Deducción pendiente/generada [00766]
21 | 266 | 17 | Num | Deducc. para  incentivar determ.actividades - 2002 Suma deducciones - Aplicado en esta liquidación [00767]
22 | 283 | 17 | Num | Deducc. para  incentivar determ.actividades - 2002 Suma deducciones - Pendiente de aplicación en periodos futuros [00833]
23 | 300 | 17 | Num | Deducc. para  incentivar determ.actividades - 2003 Suma deducciones - Deducción pendiente/generada [00198]
24 | 317 | 17 | Num | Deducc. para  incentivar determ.actividades - 2003 Suma deducciones - Aplicado en esta liquidación [00896]
25 | 334 | 17 | Num | Deducc. para  incentivar determ.actividades - 2003 Suma deducciones - Pendiente de aplicación en periodos futuros [00897]
26 | 351 | 17 | Num | Deducc. para  incentivar determ.actividades - 2004 Suma deducciones - Deducción pendiente/generada [00288]
27 | 368 | 17 | Num | Deducc. para  incentivar determ.actividades - 2004 Suma deducciones - Aplicado en esta liquidación [00289]
28 | 385 | 17 | Num | Deducc. para  incentivar determ.actividades - 2004 Suma deducciones - Pendiente de aplicación en periodos futuros [00290]
29 | 402 | 17 | Num | Deducc. para  incentivar determ.actividades - 2005 Suma deducciones - Deducción pendiente/generada [00466]
30 | 419 | 17 | Num | Deducc. para  incentivar determ.actividades - 2005 Suma deducciones - Aplicado en esta liquidación [00467]
31 | 436 | 17 | Num | Deducc. para  incentivar determ.actividades - 2005 Suma deducciones - Pendiente de aplicación en periodos futuros [00468]
32 | 453 | 17 | Num | Deducc. para  incentivar determ.actividades - 2006 Suma deducciones - Deducción pendiente/generada [00061]
33 | 470 | 17 | Num | Deducc. para  incentivar determ.actividades - 2006 Suma deducciones - Aplicado en esta liquidación [00498]
34 | 487 | 17 | Num | Deducc. para  incentivar determ.actividades - 2006 Suma deducciones - Pendiente de aplicación en periodos futuros [00586]
35 | 504 | 17 | Num | Deducc. para  incentivar determ.actividades - 2007 Suma deducciones - Deducción pendiente/generada [00472]
36 | 521 | 17 | Num | Deducc. para  incentivar determ.actividades - 2007 Suma deducciones - Aplicado en esta liquidación [00473]
37 | 538 | 17 | Num | Deducc. para  incentivar determ.actividades - 2007 Suma deducciones - Pendiente de aplicación en periodos futuros [00478]
38 | 555 | 17 | Num | Deducc. para  incentivar determ.actividades - 2008 Suma deducciones - Deducción pendiente/generada [00180]
39 | 572 | 17 | Num | Deducc. para  incentivar determ.actividades - 2008 Suma deducciones - Aplicado en esta liquidación [00181]
40 | 589 | 17 | Num | Deducc. para  incentivar determ.actividades - 2008 Suma deducciones - Pendiente de aplicación en periodos futuros [00182]
41 | 606 | 17 | Num | Deducc. para  incentivar determ.actividades - 2009 Suma deducciones - Deducción pendiente/generada [00531]
42 | 623 | 17 | Num | Deducc. para  incentivar determ.actividades - 2009 Suma deducciones - Aplicado en esta liquidación [00532]
43 | 640 | 17 | Num | Deducc. para  incentivar determ.actividades - 2009 Suma deducciones - Pendiente de aplicación en periodos futuros [00533]
44 | 657 | 17 | Num | Deducc. para  incentivar determ.actividades - 2010 Suma deducciones - Deducción pendiente/generada [00945]
45 | 674 | 17 | Num | Deducc. para  incentivar determ.actividades - 2010 Suma deducciones - Aplicado en esta liquidación [00946]
46 | 691 | 17 | Num | Deducc. para  incentivar determ.actividades - 2010 Suma deducciones - Pendiente de aplicación en periodos futuros [00947]
47 | 708 | 17 | Num | Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Deducción pendiente/generada [00960]
48 | 725 | 17 | Num | Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Aplicado en esta liquidación [00961]
49 | 742 | 17 | Num | Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Pendiente de aplicación en periodos futuros [00962]
50 | 759 | 17 | Num | Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Deducción pendiente/generada [00183]
51 | 776 | 17 | Num | Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Aplicado en esta liquidación [00185]
52 | 793 | 17 | Num | Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Pendiente de aplicación en periodos futuros [00186]
53 | 810 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Suma deducciones - Deducción pendiente/generada [00966]
54 | 827 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Suma deducciones - Aplicado en esta liquidación [00967]
55 | 844 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Suma deducciones - Pendiente de aplicación en periodos futuros [00968]
56 | 861 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Investigación y desarrollo - Deducción pendiente/generada [00457]
57 | 878 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Investigación y desarrollo - Aplicado en esta liquidación [00458]
58 | 895 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Investigación y desarrollo - Pendiente de aplicación en periodos futuros [00459]
59 | 912 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Innovación tecnológica - Deducción pendiente/generada [00460]
60 | 929 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Innovación tecnológica - Aplicado en esta liquidación [00461]
61 | 946 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Innovación tecnológica - Pendiente de aplicación en periodos futuros [00462]
62 | 963 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Suma deducciones - Deducción pendiente/generada [01063]
63 | 980 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Suma deducciones - Aplicado en esta liquidación [01064]
64 | 997 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Suma deducciones - Pendiente de aplicación en periodos futuros [01065]
65 | 1014 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Investigación y desarrollo - Deducción pendiente/generada [01066]
66 | 1031 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Investigación y desarrollo - Aplicado en esta liquidación [01067]
67 | 1048 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Investigación y desarrollo - Pendiente de aplicación en periodos futuros [01068]
68 | 1065 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Innovación tecnológica - Deducción pendiente/generada [01069]
69 | 1082 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Innovación tecnológica - Aplicado en esta liquidación [01070]
70 | 1099 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Innovación tecnológica - Pendiente de aplicación en periodos futuros [01071]
71 | 1116 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Suma deducciones - Deducción pendiente/generada [00813]
72 | 1133 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Suma deducciones - Aplicado en esta liquidación [00814]
73 | 1150 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Suma deducciones - Pendiente de aplicación en periodos futuros [00815]
74 | 1167 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Deducción pendiente/generada  [00986]
75 | 1184 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Aplicado en esta liquidación  [00810]
76 | 1201 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Pendiente de aplicación en periodos futuros [00507]
77 | 1218 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Deducción pendiente/generada [00557]
78 | 1235 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Aplicado en esta liquidación [00591]
79 | 1252 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Pendiente de aplicación en periodos futuros [00594]
80 | 1269 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Deducción creación empleo trabajadores discapacidad - Deducción pendiente/generada [00795]
81 | 1286 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Deducción creación empleo trabajadores discapacidad - Aplicado en esta liquidación [00796]
82 | 1303 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Deducción creación empleo trabajadores discapacidad - Pendiente de aplicación en periodos futuros [00797]
83 | 1320 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Deducción pendiente/generada [00798]
84 | 1337 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Aplicado en esta liquidación [00799]
85 | 1354 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Pendiente de aplicación en periodos futuros [00800]
86 | 1371 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Deducción pendiente/generada [00096]
87 | 1388 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Aplicado en esta liquidación [00698]
88 | 1405 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Pendiente de aplicación en periodos futuros [00713]
89 | 1422 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Deducción por invers.beneficios - Deducción pendiente/generada [00549]
90 | 1439 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Deducción por invers.beneficios - Aplicado en esta liquidación [00888]
91 | 1456 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Deducción por invers.beneficios - Pendiente de aplicación en periodos futuros [00889]
92 | 1473 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Produc. cinematográficas españolas - Deducción pendiente/generada [00807]
93 | 1490 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Produc. cinematográficas españolas - Aplicado en esta liquidación [00808]
94 | 1507 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Produc. cinematográficas españolas - Pendiente de aplicación en periodos futuros [00809]
95 | 1524 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Espectáculos en vivo artes escenicas y musicales - Deducción pendiente/generada [01075]
96 | 1541 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Espectáculos en vivo artes escenicas y musicales -  Aplicado en esta liquidación [01076]
97 | 1558 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Espectáculos en vivo artes escenicas y musicales - Pendiente de aplicación en periodos futuros [01077]
98 | 1575 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Creación empleo contratación menores de 30  - Deducción pendiente/generada [00963]
99 | 1592 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Creación empleo contratación menores de 30 -  Aplicado en esta liquidación [00964]
100 | 1609 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Creación empleo contratación menores de 30  - Pendiente de aplicación en periodos futuros [00965]
101 | 1626 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Creación empleo contratación desempleados con prestación desempleo - Deducción pendiente/generada [00931]
102 | 1643 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Creación empleo contratación desempleados con prestación desempleo - Aplicado en esta liquidación [00502]
103 | 1660 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Creación empleo contratación desempleados con prestación desempleo - Pendiente de aplicación en periodos futuros [00751]
104 | 1677 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Invers. en territorio Africa Occidental y gastos publicidad - Deducción pendiente/generada [01078]
105 | 1694 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Invers. en territorio Africa Occidental y gastos publicidad - Aplicado en esta liquidación [01079]
106 | 1711 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Invers. en territorio Africa Occidental y gastos publicidad - Pendiente de aplicación en periodos futuros [01080]
107 | 1728 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa "El árbol es vida" - Deducción pendiente/generada  [00070]
108 | 1745 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa "El árbol es vida" - Aplicado en esta liquidación  [00072]
109 | 1762 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa "El árbol es vida" - Pendiente de aplicación en periodos futuros  [00073]
110 | 1779 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Plan Director recuperación Patrimonio Cultural Lorca - Deducción pendiente/generada [00078]
111 | 1796 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Plan Director recuperación Patrimonio Cultural Lorca - Aplicado en esta liquidación [00079]
112 | 1813 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Plan Director recuperación Patrimonio Cultural Lorca - Pendiente de aplicación en periodos futuros [00080]
113 | 1830 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Universiada de Invierno Granada 2015 - Deducción pendiente/generada [00085]
114 | 1847 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Universiada de Invierno Granada 2015 - Aplicado en esta liquidación [00086]
115 | 1864 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Universiada de Invierno Granada 2015 - Pendiente de aplicación en periodos futuros [00087]
116 | 1881 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Campeonato Mundo Ciclismo Carretera Ponferrada 2014 - Deducción pendiente/generada [00093]
117 | 1898 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Campeonato Mundo Ciclismo Carretera Ponferrada 2014 - Aplicado en esta liquidación [00057]
118 | 1915 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Campeonato Mundo Ciclismo Carretera Ponferrada 2014 - Pendiente de aplicación en periodos futuros [00058]
119 | 1932 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona World Jumping Challenge - Deducción pendiente/generada [00207]
120 | 1949 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona World Jumping Challenge - Aplicado en esta liquidación [00208]
121 | 1966 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona World Jumping Challenge - Pendiente de aplicación en periodos futuros [00209]
122 | 1983 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 3ª Edición Barcelona World Race - Deducción pendiente/generada [00216]
123 | 2000 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 3ª Edición Barcelona World Race - Aplicado en esta liquidación [00217]
124 | 2017 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 3ª Edición Barcelona World Race - Pendiente de aplicación en periodos futuros [00218]
125 | 2034 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa preparación deportistas españoles juegos "Río de Janeiro 2016"  - Deducción pendiente/generada [00204]
126 | 2051 | 17 | Num | Deducc. para  incentivar determ.actividades - 2015 Programa preparación deportistas españoles juegos "Río de Janeiro 2016"  - Aplicado en esta liquidación [00205]
127 | 2068 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa preparación deportistas españoles juegos "Río de Janeiro 2016"  - Pendiente de aplicación en periodos futuros [00206]
128 | 2085 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 VIII Centenario Peregrinación San Francisco de Asís a Santiago de Compostela  - Deducción pendiente/generada [00219]
129 | 2102 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  VIII Centenario Peregrinación San Francisco de Asís a Santiago de Compostela  - Aplicado en esta liquidación [00220]
130 | 2119 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  VIII Centenario Peregrinación San Francisco de Asís a Santiago de Compostela  - Pendiente de aplicación en periodos futuros [00221]
131 | 2136 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 V Centenario del Nacimiento Santa Teresa de Jesús en el año 2015  - Deducción pendiente/generada [00228]
132 | 2153 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 V Centenario del Nacimiento Santa Teresa de Jesús en el año 2015  - Aplicado en esta liquidación [00229]
133 | 2170 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 V Centenario del Nacimiento Santa Teresa de Jesús en el año 2015  - Pendiente de aplicación en periodos futuros [00230]
134 | 2187 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Alicante 2014 - Deducción pendiente/generada [00237]
135 | 2204 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Alicante 2014 - Aplicado en esta liquidación [00238]
136 | 2221 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Alicante 2014 - Pendiente de aplicación en periodos futuros [00239]
137 | 2238 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Donostia/San Sebastián, Capital Europea de la Cultura 2016 - Deducción pendiente/generada [00007]
138 | 2255 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Donostia/San Sebastián, Capital Europea de la Cultura 2016 - Aplicado en esta liquidación [00012]
139 | 2272 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Donostia/San Sebastián, Capital Europea de la Cultura 2016 - Pendiente de aplicación en periodos futuros [00016]
140 | 2289 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Expo Milán 2015 - Deducción pendiente/generada [00199]
141 | 2306 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Expo Milán 2015 - Aplicado en esta liquidación [00292]
142 | 2323 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Expo Milán 2015 - Pendiente de aplicación en periodos futuros [00293]
143 | 2340 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Madrid Horse Week - Deducción pendiente/generada [00419]
144 | 2357 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Madrid Horse Week - Aplicado en esta liquidación [00422]
145 | 2374 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  Madrid Horse Week - Pendiente de aplicación en periodos futuros [00423]
146 | 2391 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  III Centenario de la Real Academia Española - Deducción pendiente/generada [00424]
147 | 2408 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  III Centenario de la Real Academia Española - Aplicado en esta liquidación [00425]
148 | 2425 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  III Centenario de la Real Academia Española - Pendiente de aplicación en periodos futuros [00428]
149 | 2442 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  A Coruña 2015-120 años después - Deducción pendiente/generada [00429]
150 | 2459 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  A Coruña 2015-120 años después - Aplicado en esta liquidación [00430]
151 | 2476 | 17 | Num | Deducc. para incentivar determ.actividades - 2015  A Coruña 2015-120 años después - Pendiente de aplicación en periodos futuros [00431]
152 | 2493 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 IV Centenario de la segunda parte de El Quijote - Deducción pendiente/generada [00432]
153 | 2510 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 IV Centenario de la segunda parte de El Quijote - Aplicado en esta liquidación [00433]
154 | 2527 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 IV Centenario de la segunda parte de El Quijote - Pendiente de aplicación en periodos futuros [00434]
155 | 2544 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 World Challenge LFP/ 85 Aniversario de la Liga - Deducción pendiente/generada [00435]
156 | 2561 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 World Challenge LFP/ 85 Aniversario de la Liga - Aplicado en esta liquidación [00436]
157 | 2578 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 World Challenge LFP/ 85 Aniversario de la Liga - Pendiente de aplicación en periodos futuros [00437]
158 | 2595 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Juegos del Mediterráneo de 2017 - Deducción pendiente/generada [00438]
159 | 2612 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Juegos del Mediterráneo de 2017 - Aplicado en esta liquidación [00439]
160 | 2629 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Juegos del Mediterráneo de 2017 - Pendiente de aplicación en periodos futuros [00440]
161 | 2646 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 200 Anivers. Teatro Real y el Vigésimo Anivers.de la reapertura del Teatro Real  - Deducción pendiente/generada [01081]
162 | 2663 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 200 Anivers. Teatro Real y el Vigésimo Anivers.de la reapertura del Teatro Real  - Aplicado en esta liquidación [01082]
163 | 2680 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 200 Anivers. Teatro Real y el Vigésimo Anivers.de la reapertura del Teatro Real  - Pendiente de aplicación en periodos futuros [01083]
164 | 2697 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 IV Centenario de la muerto de Miguel de Cervantes  -  Deducción pendiente/generada [01084]
165 | 2714 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 IV Centenario de la muerto de Miguel de Cervantes  -  Aplicado en esta liquidación [01085]
166 | 2731 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 IV Centenario de la muerto de Miguel de Cervantes  -  Pendiente de aplicación en periodos futuros [01086]
167 | 2748 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 VIII Centenario de la Universidad de Salamanca  -  Deducción pendiente/generada [01087]
168 | 2765 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 VIII Centenario de la Universidad de Salamanca  -  Aplicado en esta liquidación [01088]
169 | 2782 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 VIII Centenario de la Universidad de Salamanca  -  Pendiente de aplicación en periodos futuros [01089]
170 | 2799 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa Jerez, Capital mundial del Motoliclismo -  Deducción pendiente/generada [01090]
171 | 2816 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa Jerez, Capital mundial del Motoliclismo -  Aplicado en esta liquidación [01091]
172 | 2833 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa Jerez, Capital mundial del Motoliclismo - Pendiente de aplicación en periodos futuros [01092]
173 | 2850 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Cantabria 2017, Liébana Año Jubilar  -  Deducción pendiente/generada [01093]
174 | 2867 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Cantabria 2017, Liébana Año Jubilar  -  Aplicado en esta liquidación [01094]
175 | 2884 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Cantabria 2017, Liébana Año Jubilar  -  Pendiente de aplicación en periodos futuros [01095]
176 | 2901 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa Universo Mujer  -  Deducción pendiente/generada [01096]
177 | 2918 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa Universo Mujer  -  Aplicado en esta liquidación [01097]
178 | 2935 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Programa Universo Mujer  -  Pendiente de aplicación en periodos futuros [01098]
179 | 2952 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 60 Anivers. Fundación de la Escuela de Organiz. Industrial  -  Deducción pendiente/generada [01099]
180 | 2969 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 60 Anivers. Fundación de la Escuela de Organiz. Industrial  -  Aplicado en esta liquidación [01100]
181 | 2986 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 60 Anivers. Fundación de la Escuela de Organiz. Industrial  -  Pendiente de aplicación en periodos futuros [01101]
182 | 3003 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Encuentro Mundial en Las Estrellas 2017  -  Deducción pendiente/generada [01102]
183 | 3020 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Encuentro Mundial en Las Estrellas 2017  -  Aplicado en esta liquidación [01103]
184 | 3037 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Encuentro Mundial en Las Estrellas 2017  -  Pendiente de aplicación en periodos futuros [01104]
185 | 3054 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200170>"
Total: |  | 3063

# DP200018

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "180"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona Mobile World Capital - Deducción pendiente/generada [01105]
7 | 28 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona Mobile World Capital - Aplicado en esta liquidación [01106]
8 | 45 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona Mobile World Capital - Pendiente de aplicación en periodos futuros [01107]
9 | 62 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Año internacional de la luz y de las tecnolog.basadas en la luz - Deducción pendiente/generada [01108]
10 | 79 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Año internacional de la luz y de las tecnolog.basadas en la luz - Aplicado en esta liquidación [01109]
11 | 96 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Año internacional de la luz y de las tecnolog.basadas en la luz - Pendiente de aplicación en periodos futuros [01110]
12 | 113 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 ORC Barcelona World Championship 2015 - Deducción pendiente/generada [01111]
13 | 130 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 ORC Barcelona World Championship 2015 - Aplicado en esta liquidación [01112]
14 | 147 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 ORC Barcelona World Championship 2015 - Pendiente de aplicación en periodos futuros [01113]
15 | 164 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona Equestrian Challenge - Deducción pendiente/generada [01114]
16 | 181 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona Equestrian Challenge - Aplicado en esta liquidación [01115]
17 | 198 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Barcelona Equestrian Challenge - Pendiente de aplicación en periodos futuros [01116]
18 | 215 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Women´s Hockey World League Round 3 Events 2015  - Deducción pendiente/generada [01117]
19 | 232 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Women´s Hockey World League Round 3 Events 2015  -  Aplicado en esta liquidación [01118]
20 | 249 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Women´s Hockey World League Round 3 Events 2015  - Pendiente de aplicación en periodos futuros [01119]
21 | 266 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Centenario de la Real Federación Andaluza de Fútbol 2015  - Deducción pendiente/generada [01120]
22 | 283 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Centenario de la Real Federación Andaluza de Fútbol 2015  -  Aplicado en esta liquidación [01121]
23 | 300 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Centenario de la Real Federación Andaluza de Fútbol 2015  - Pendiente de aplicación en periodos futuros [01122]
24 | 317 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Diferimiento Deducciones Cap.IV tit VI Ley 43/95 RDL 4/2004 y LIS - Deducción pendiente/generada [00828]
25 | 334 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Diferimiento Deducciones Cap.IV tit VI Ley 43/95 RDL 4/2004 y LIS - Aplicado en esta liquidación [00829]
26 | 351 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Diferimiento Deducciones Cap.IV tit VI Ley 43/95 RDL 4/2004 y LIS - Pendiente de aplicación en periodos futuros [00830]
27 | 368 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés público - Deducción pendiente/generada [00634]
28 | 385 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés público - Aplicado en esta liquidación [00635]
29 | 402 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés público - Pendiente de aplicación en periodos futuros [00636]
30 | 419 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones Cap.IV Tít.VI Ley 43/95, RDL 4/2004 y LIS - Deducción pendiente/generada [00831]
31 | 436 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones Cap.IV Tít.VI Ley 43/95, RDL 4/2004 y LIS - Aplicado en esta liquidación [00588]
32 | 453 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones Cap.IV Tít.VI Ley 43/95, RDL 4/2004 y LIS - Pendiente de aplicación en periodos futuros [00832]
33 | 470 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Deducción pendiente/generada [00918]
34 | 487 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Deducción reducida [00919]
35 | 504 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Aplicado en esta liquidación [00574]
36 | 521 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Importe abonado por insuficiencia de cuota [00580]
37 | 538 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Deducción pendiente/generada [00589]
38 | 555 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Deducción reducida [00976]
39 | 572 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Aplicado en esta liquidación [00977]
40 | 589 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Importe abonado por insuficiencia de cuota [00978]
41 | 606 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Deducción pendiente/generada [00822]
42 | 623 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Deducción reducida [00823]
43 | 640 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Aplicado en esta liquidación [00824]
44 | 657 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Importe abonado por insuficiencia de cuota [00231]
45 | 674 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Deducción pendiente/generada [00232]
46 | 691 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Deducción reducida [00233]
47 | 708 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Aplicado en esta liquidación [00850]
48 | 725 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Importe abonado por insuficiencia de cuota [00851]
49 | 742 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Deducción pendiente/generada [01123]
50 | 759 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Deducción reducida [01124]
51 | 776 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Aplicado en esta liquidación [01125]
52 | 793 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Importe abonado por insuficiencia de cuota [01126]
53 | 810 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Deducción pendiente/generada [01127]
54 | 827 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Deducción reducida [01128]
55 | 844 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Aplicado en esta liquidación [01129]
56 | 861 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Importe abonado por insuficiencia de cuota [01130]
57 | 878 | 17 | Num | Deducciones I+D+i excluidas de límite - Total - Deducción pendiente/generada [00517]
58 | 895 | 17 | Num | Deducciones I+D+i excluidas de límite - Total - Deducción reducida [00081]
59 | 912 | 17 | Num | Deducciones I+D+i excluidas de límite - Total - Aplicado en esta liquidación [00082]
60 | 929 | 17 | Num | Deducciones I+D+i excluidas de límite - Total - Importe abonado por insuficiencia de cuota [01234]
61 | 946 | 17 | Num | Deducción donativos entidades sin fines lucro - 2005 - Deducción pendiente/generada [00929]
62 | 963 | 17 | Num | Deducción donativos entidades sin fines lucro - 2005 - Aplicado en esta liquidación [00930]
63 | 980 | 17 | Num | Deducción donativos entidades sin fines lucro - 2006 - Deducción pendiente/generada [00942]
64 | 997 | 17 | Num | Deducción donativos entidades sin fines lucro - 2006 - Aplicado en esta liquidación [00943]
65 | 1014 | 17 | Num | Deducción donativos entidades sin fines lucro - 2006 - Pendiente de aplicación en periodos futuros [00944]
66 | 1031 | 17 | Num | Deducción donativos entidades sin fines lucro - 2007 - Deducción pendiente/generada [00294]
67 | 1048 | 17 | Num | Deducción donativos entidades sin fines lucro - 2007 - Aplicado en esta liquidación [00295]
68 | 1065 | 17 | Num | Deducción donativos entidades sin fines lucro - 2007 - Pendiente de aplicación en periodos futuros [00296]
69 | 1082 | 17 | Num | Deducción donativos entidades sin fines lucro - 2008 - Deducción pendiente/generada [00066]
70 | 1099 | 17 | Num | Deducción donativos entidades sin fines lucro - 2008 - Aplicado en esta liquidación [00074]
71 | 1116 | 17 | Num | Deducción donativos entidades sin fines lucro - 2008 - Pendiente de aplicación en periodos futuros [00084]
72 | 1133 | 17 | Num | Deducción donativos entidades sin fines lucro - 2009 - Deducción pendiente/generada [00008]
73 | 1150 | 17 | Num | Deducción donativos entidades sin fines lucro - 2009 - Aplicado en esta liquidación [00009]
74 | 1167 | 17 | Num | Deducción donativos entidades sin fines lucro - 2009 - Pendiente de aplicación en periodos futuros [00010]
75 | 1184 | 17 | Num | Deducción donativos entidades sin fines lucro - 2010 - Deducción pendiente/generada [00034]
76 | 1201 | 17 | Num | Deducción donativos entidades sin fines lucro - 2010 - Aplicado en esta liquidación [00035]
77 | 1218 | 17 | Num | Deducción donativos entidades sin fines lucro - 2010 - Pendiente de aplicación en periodos futuros [00036]
78 | 1235 | 17 | Num | Deducción donativos entidades sin fines lucro - 2011 - Deducción pendiente/generada [00201]
79 | 1252 | 17 | Num | Deducción donativos entidades sin fines lucro - 2011 - Aplicado en esta liquidación [00202]
80 | 1269 | 17 | Num | Deducción donativos entidades sin fines lucro - 2011 - Pendiente de aplicación en periodos futuros [00203]
81 | 1286 | 17 | Num | Deducción donativos entidades sin fines lucro - 2012 - Deducción pendiente/generada [00904]
82 | 1303 | 17 | Num | Deducción donativos entidades sin fines lucro - 2012 - Aplicado en esta liquidación [00905]
83 | 1320 | 17 | Num | Deducción donativos entidades sin fines lucro - 2012 - Pendiente de aplicación en periodos futuros [00906]
84 | 1337 | 17 | Num | Deducción donativos entidades sin fines lucro - 2013 - Deducción pendiente/generada [00990]
85 | 1354 | 17 | Num | Deducción donativos entidades sin fines lucro - 2013 - Aplicado en esta liquidación [00991]
86 | 1371 | 17 | Num | Deducción donativos entidades sin fines lucro - 2013 - Pendiente de aplicación en periodos futuros [00992]
87 | 1388 | 17 | Num | Deducción donativos entidades sin fines lucro - 2014 - Deducción pendiente/generada [00997]
88 | 1405 | 17 | Num | Deducción donativos entidades sin fines lucro - 2014 - Aplicado en esta liquidación [00998]
89 | 1422 | 17 | Num | Deducción donativos entidades sin fines lucro - 2014 - Pendiente de aplicación en periodos futuros [00999]
90 | 1439 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Deducción pendiente/generada [00246]
91 | 1456 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Aplicado en esta liquidación [00247]
92 | 1473 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Pendiente de aplicación en periodos futuros [00248]
93 | 1490 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Deducción pendiente/generada [00993]
94 | 1507 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Aplicado en esta liquidación [00994]
95 | 1524 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Pendiente de aplicación en periodos futuros [00995]
96 | 1541 | 17 | Num | Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro - Deducción pendiente/generada [00598]
97 | 1558 | 17 | Num | Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro - Aplicado en esta liquidación [00565]
98 | 1575 | 17 | Num | Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro - Pendiente de aplicación en periodos futuros [00895]
99 | 1592 | 17 | Num | Deducción donativos entidades sin fines lucro - Donaciones del período impositivo efectuadas a entidades sin fines de lucro [00974]
100 | 1609 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Base deducción [01162]
101 | 1626 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe generado/pendiente ppio periodo [01163]
102 | 1643 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe aplicado [01164]
103 | 1660 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe pendiente [01165]
104 | 1677 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Base deducción [01166]
105 | 1694 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe generado/pendiente ppio periodo [01167]
106 | 1711 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe aplicado [01168]
107 | 1728 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe pendiente [01169]
108 | 1745 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Base deducción [01170]
109 | 1762 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe generado/pendiente ppio periodo [01171]
110 | 1779 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe aplicado [01040]
111 | 1796 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe pendiente [01173]
112 | 1813 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe pendiente [01174]
113 | 1830 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe generado/pendiente ppio periodo [01175]
114 | 1847 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe aplicado [01176]
115 | 1864 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe pendiente [01177]
116 | 1881 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Base deducción [01178]
117 | 1898 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe generado/pendiente ppio periodo [01179]
118 | 1915 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe aplicado [01180]
119 | 1932 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe pendiente [01181]
120 | 1949 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Base deducción [01182]
121 | 1966 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe generado/pendiente ppio periodo [01183]
122 | 1983 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe aplicado [01041]
123 | 2000 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe pendiente [01185]
124 | 2017 | 17 | Num | Reserva Capitalización - 2015  - Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo [01131]
125 | 2034 | 17 | Num | Reserva Capitalización - 2015  - Reducción B.I. aplicada  [01132]
126 | 2051 | 17 | Num | Reserva Capitalización - 2015  -  Reducción B.I. pdte. de aplicar en períodos futuros [01133]
127 | 2068 | 17 | Num | Reserva Capitalización - 2015  - Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo [01134]
128 | 2085 | 17 | Num | Reserva Capitalización - 2015  - Reduccion B.I. aplicada  [01135]
129 | 2102 | 17 | Num | Reserva Capitalización - 2015  Reducción B.I. pdte. De aplicar en períodos futuros [01136]
130 | 2119 | 17 | Num | Reserva Capitalización - Total  - Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo [01137]
131 | 2136 | 17 | Num | Reserva Capitalización - Total  - Reduccion B.I. aplicada  [01032]
132 | 2153 | 17 | Num | Reserva Capitalización - Total -  Reducción B.I. pdte. de aplicar en períodos futuros [01139]
133 | 2170 | 17 | Num | Reserva Capitalización dotada en el ejercicio  [01140]
134 | 2187 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200180>"
Total: |  | 2196

# DP200019

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "190"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01141]
7 | 28 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe adicionado base imponible en periodo [01142]
8 | 45 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe pendiente adicionar en periodos futuros [01143]
9 | 62 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01144]
10 | 79 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe adicionado base imponible en periodo [01145]
11 | 96 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe pendiente adicionar en periodos futuros [01146]
12 | 113 | 17 | Num | Reserva de nivelación - Reducción base imponible - Total - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01147]
13 | 130 | 17 | Num | Reserva de nivelación - Reducción base imponible - Total - Importe adicionado base imponible en periodo [01148]
14 | 147 | 17 | Num | Reserva de nivelación - Reducción base imponible - Total - Importe pendiente adicionar en periodos futuros [01149]
15 | 164 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015  - Importe reserva a dotar [01150]
16 | 181 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015  - Importe reserva dotada [01151]
17 | 198 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015  - Importe reserva pendiente dotación [01152]
18 | 215 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015  - Reserva dispuesta [01153]
19 | 232 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015  - Importe reserva a dotar [01154]
20 | 249 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015  - Importe reserva dotada [01155]
21 | 266 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015  - Importe reserva pendiente dotación [01156]
22 | 283 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015  - Reserva dispuesta [01157]
23 | 300 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Total  - Importe reserva a dotar [01158]
24 | 317 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Total  - Importe reserva dotada [01159]
25 | 334 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Total  - Importe reserva pendiente dotación [01160]
26 | 351 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Total  - Reserva dispuesta [01161]
27 | 368 | 17 | Num | Aplicación de resultados - Base de reparto - Pérdidas y ganancias [00650]
28 | 385 | 17 | Num | Aplicación de resultados - Base de reparto - Remanente [00651]
29 | 402 | 17 | Num | Aplicación de resultados - Base de reparto - Reservas [00652]
30 | 419 | 17 | Num | Aplicación de resultados - Base de reparto - Total [00653]
31 | 436 | 17 | Num | Aplicación de resultados - Aplicación - A reservas [00654]
32 | 453 | 17 | Num | Aplicación de resultados - Aplicación - A reservas - Reservas de capitalización [01270]
33 | 470 | 17 | Num | Aplicación de resultados - Aplicación - A reservas - Reserva de nivelación [01271]
34 | 487 | 17 | Num | Aplicación de resultados - Aplicación - Intereses aportaciones al capital (Cooperativas) [00655]
35 | 504 | 17 | Num | Aplicación de resultados - Aplicación - A dividendos [00656]
36 | 521 | 17 | Num | Aplicación de resultados - Aplicación - A dotación O.S. (Cajas de ahorro y fundaciones bancarias) [00658]
37 | 538 | 17 | Num | Aplicación de resultados - Aplicación - A F.R.O y dotaciones voluntarias al F.E.P (Cooperativas) [00659]
38 | 555 | 17 | Num | Aplicación de resultados - Aplicación - A retornos cooperativos (Cooperativas) [00660]
39 | 572 | 17 | Num | Aplicación de resultados - Aplicación - Partícipes (IIC) [00662]
40 | 589 | 17 | Num | Aplicación de resultados - Aplicación - A remanente y otros [00664]
41 | 606 | 17 | Num | Aplicación de resultados - Aplicación - A compensación de pérdidas de ejercicios anteriores [00665]
42 | 623 | 17 | Num | Aplicación de resultados - Aplicación - Total [00666]
43 | 640 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correcciones permanentes - Del ejercicio - Aumentos
44 | 657 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correcciones permanentes - Del ejercicio - Disminuciones
45 | 674 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Del ejercicio - Aumentos
46 | 691 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Del ejercicio - Disminuciones
47 | 708 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Saldo pendiente - Aumentos futuros
48 | 725 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Saldo pendiente - Disminuciones futuras
49 | 742 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Amortizaciones - Del ejercicio - Aumentos
50 | 759 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Amortizaciones - Del ejercicio - Disminuciones
51 | 776 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Amortizaciones - Saldo pendiente - Aumentos futuros
52 | 793 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Amortizaciones - Saldo pendiente - Disminuciones futuras
53 | 810 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Deterioros valor - Del ejercicio - Aumentos
54 | 827 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Deterioros valor - Del ejercicio - Disminuciones
55 | 844 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Deterioros valor - Saldo pendiente - Aumentos futuros
56 | 861 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Deterioros valor - Saldo pendiente - Disminuciones futuras
57 | 878 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Pensiones -  Del ejercicio - Aumentos
58 | 895 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Pensiones -  Del ejercicio - Disminuciones
59 | 912 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Pensiones -  Saldo pendiente - Aumentos futuros
60 | 929 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Pensiones -  Saldo pendiente - Disminuciones futuras
61 | 946 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Fondo de comercio - Del ejercicio - Aumentos
62 | 963 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Fondo de comercio - Del ejercicio - Disminuciones
63 | 980 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Fondo de comercio - Saldo pendiente - Aumentos futuros
64 | 997 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Fondo de comercio - Saldo pendiente - Disminuciones futuras
65 | 1014 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Resto - Aumentos
66 | 1031 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Resto - Disminuciones
67 | 1048 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Resto - Saldo pendiente - Aumentos futuros
68 | 1065 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Resto - Saldo pendiente - Disminuciones futuras
69 | 1082 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Del ejercicio - Aumentos
70 | 1099 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Del ejercicio - Disminuciones
71 | 1116 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Saldo pendiente - Aumentos futuros
72 | 1133 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Saldo pendiente - Disminuciones futuras
73 | 1150 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Amortizaciones - Del ejercicio - Aumentos
74 | 1167 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Amortizaciones - Del ejercicio - Disminuciones
75 | 1184 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Amortizaciones - Saldo pendiente - Aumentos futuros
76 | 1201 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Amortizaciones - Saldo pendiente - Disminuciones futuras
77 | 1218 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Deterioros valor - Del ejercicio - Aumentos
78 | 1235 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Deterioros valor - Del ejercicio - Disminuciones
79 | 1252 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Deterioros valor - Saldo pendiente - Aumentos futuros
80 | 1269 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Deterioros valor - Saldo pendiente - Disminuciones futuras
81 | 1286 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Pensiones - Del ejercicio - Aumentos
82 | 1303 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Pensiones - Del ejercicio - Disminuciones
83 | 1320 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Pensiones - Saldo pendiente - Aumentos futuros
84 | 1337 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Pensiones - Saldo pendiente - Disminuciones futuras
85 | 1354 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Fondo de comercio - Del ejercicio - Aumentos
86 | 1371 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Fondo de comercio - Del ejercicio - Disminuciones
87 | 1388 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Fondo de comercio - Saldo pendiente - Aumentos futuros
88 | 1405 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Fondo de comercio - Saldo pendiente - Disminuciones futuras
89 | 1422 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Resto - Del ejercicio - Aumentos
90 | 1439 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Resto - Del ejercicio - Disminuciones
91 | 1456 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Resto - Saldo pendiente - Aumentos futuros
92 | 1473 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Resto - Saldo pendiente - Disminuciones futuras
93 | 1490 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de pérdidas y ganancias - Del ejercicio - Aumentos  [00417]
94 | 1507 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de pérdidas y ganancias - Del ejercicio - Disminuciones [00418]
95 | 1524 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de pérdidas y ganancias - Saldo pendiente - Aumentos futuros
96 | 1541 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de pérdidas y ganancias - Saldo pendiente - Disminuciones futuras
97 | 1558 | 22 | An | Presentación de documentación previa en la sede electrónica. NRS Anexo III (Ajustes y deducciones)
98 | 1580 | 22 | An | Presentación de documentación previa en la sede electrónica. Nº Justificante ident.declarac.informativa de ayudas Régimen económico y Fiscal de Canarias
99 | 1602 | 22 | An | Presentación de documentación previa en la sede electrónica. NRS Anexo IV (Personal investigador)
100 | 1624 | 22 | An | Presentación de documentación previa en la sede electrónica. NRS Anexo V
101 | 1646 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200190>"
Total: |  | 1655

# DP200020

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "200"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS  -  a) Gastos financieros período impositivo derivados por adquisicion de partic.  (sin signo)    [01240]
7 | 28 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS  -  b) límite adicional a la deducc. de gastos financieros (sin signo)   [01241]
8 | 45 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS  -  c1) Gastos financieros período imposit. deducibles tras aplicac. límite art. 16.5 y/o 83 LIS   [01242]
9 | 62 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS  -  c2) Gastos financieros período imposit. no deducibles tras aplicac. límite art. 16.5 y/o 83 LIS   [01243]
10 | 79 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS  -  d) Gastos financieros pendientes de deducir en período ant. afectados por art. 16.5 y/o 83 LIS   [01244]
11 | 96 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  e) Gastos financieros del período no afectados por art. 16.5, 67 b) y/o 83 LIS (sin signo)   [01245]
12 | 113 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  f) Gastos financieros del período imposit. [01246]
13 | 130 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  g) Ingresos financieros del  período impos. derivados de la cesión a terceros de capitales propios   [01247]
14 | 147 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  h) Gastos financieros netos del período impositivo   [01248]
15 | 164 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  i) Límite a la deducción de gastos financieros netos   [01249]
16 | 181 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  i1) Resultado de explotación (signo igual a Cta.de Pérd. y Gan)   [01250]
17 | 198 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  i2) Amortización del inmovilizado (signo igual a Cta.de Pérd. y Gan)   [01251]
18 | 215 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  i3) Imputación de subvenciones de inmovilizado no financiero y otras (signo igual a Cta.de Pérd. y Gan)   [01252]
19 | 232 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  i4) Deterioro y resultado por enajenaciones del inmovilizado (signo igual a Cta.de Pérd. y Gan)   [01253]
20 | 249 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  i5) Ingresos financieros de participaciones en instrumentos de patrimonio (signo igual a Cta.de Pérd. y Gan)   [01254]
21 | 266 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  j) Adición por límite beneficio operativo no aplicado en los cinco ejercicios anteriores  [01255]
22 | 283 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  k1) Gastos financieros netos del período impositivo deducibles  [01256]
23 | 300 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  k2) Gastos financieros netos del período impositivo no deducibles   [01257]
24 | 317 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  l) Gastos financieros pendientes de deducir en períodos imposit.anteriores por art 16.5 y/o 83 LIS deducibles tras aplicar los 2 límites    [01258]
25 | 334 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  m) Gastos financieros pendientes de deducir de períodos impositivos anteriores no afectados por art 16.5 y/o 83 LIS aplicados   [01259]
26 | 351 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS  -  Total gastos financieros del período impositivo no deducibles  [01260]
27 | 368 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2012 - Pendiente aplicación a principio del período - Resto  [01188]
28 | 385 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2012 - Aplicado en esta liquidación  [01189]
29 | 402 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2012 - Pendiente aplicación en períodos futuros - Resto  [01191]
30 | 419 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2013 - Pendiente aplicación a principio del período - Resto  [01193]
31 | 436 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2013 - Aplicado en esta liquidación  [01194]
32 | 453 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2013 - Pendiente aplicación en períodos futuros - Resto  [01196]
33 | 470 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2014 - Pendiente aplicación a principio del período - Resto  [01198]
34 | 487 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2014 - Aplicado en esta liquidación  [01199]
35 | 504 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2014 - Pendiente aplicación en períodos futuros - Resto  [01201]
36 | 521 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2015 (*) - Pendiente aplicación a principio del período - Por límite  [01202]
37 | 538 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2015 (*) - Pendiente aplicación a principio del período - Resto  [01203]
38 | 555 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2015 (*) - Aplicado en esta liquidación  [01204]
39 | 572 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2015 (*) - Pendiente aplicación en períodos futuros - Por límite  [01205]
40 | 589 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2015 (*) - Pendiente aplicación en períodos futuros - Resto  [01206]
41 | 606 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2015 (**) - Aplicado en esta liquidación  [01209]
42 | 623 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2015 (**) - Pendiente aplicación en períodos futuros - Por límite  [01210]
43 | 640 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2015 (**) - Pendiente aplicación en períodos futuros - Resto  [01211]
44 | 657 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Total - Pendiente aplicación a principio del período - Por límite  [01212]
45 | 674 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Total - Pendiente aplicación a principio del período - Resto  [01213]
46 | 691 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Total - Aplicado en esta liquidación  [01214]
47 | 708 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Total - Pendiente aplicación en períodos futuros - Por límite  [01215]
48 | 725 | 17 | Num | Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Total - Pendiente aplicación en períodos futuros - Resto  [01216]
49 | 742 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2012 - Pendiente aplicación a principio del período [00890]
50 | 759 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2012 - Aplicado en esta liquidación [00891]
51 | 776 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2012 - Pendiente aplicación períodos futuros  [00892]
52 | 793 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013 - Pendiente aplicación a principio del período [00503]
53 | 810 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013 - Aplicado en esta liquidación [00522]
54 | 827 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013 - Pendiente aplicación períodos futuros  [00523]
55 | 844 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2014 - Pendiente aplicación a principio del período [00273]
56 | 861 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2014 - Aplicado en esta liquidación [00274]
57 | 878 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2014 - Pendiente aplicación períodos futuros  [00537]
58 | 895 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Pendiente aplicación a principio del período [00955]
59 | 912 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Aplicado en esta liquidación [00956]
60 | 929 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Pendiente aplicación períodos futuros  [00957]
61 | 946 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Pendiente aplicación a principio del período [01217]
62 | 963 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Aplicado en esta liquidación [01218]
63 | 980 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Pendiente aplicación períodos futuros  [01219]
64 | 997 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Total - Pendiente aplicación a principio del período [00538]
65 | 1014 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Total - Aplicado en esta liquidación [00539]
66 | 1031 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Total - Pendiente aplicación períodos futuros  [00546]
67 | 1048 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2011 - Pendiente aplicación a principio del período [00893]
68 | 1065 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2011 - Ingresado en esta liquidación [00173]
69 | 1082 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2011 - Conversión [00958]
70 | 1099 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2011 - Pendiente de integración  [00898]
71 | 1116 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2012 - Pendiente aplicación a principio del período [00899]
72 | 1133 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2012 - Ingresado en esta liquidación [00227]
73 | 1150 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2012 - Conversión [00959]
74 | 1167 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2012 - Pendiente de integración  [00917]
75 | 1184 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2013 - Pendiente aplicación a principio del período [00948]
76 | 1201 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2013 - Ingresado en esta liquidación [00291]
77 | 1218 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2013 - Conversión [00979]
78 | 1235 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2013 - Pendiente de integración  [00949]
79 | 1252 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2014 - Pendiente aplicación a principio del período [00950]
80 | 1269 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2014 - Ingresado en esta liquidación [00951]
81 | 1286 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2014 - Conversión [00980]
82 | 1303 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2014  - Pendiente de integración  [00952]
83 | 1320 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2015  - Pendiente aplicación a principio del período [00981]
84 | 1337 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2015  - Ingresado en esta liquidación [00982]
85 | 1354 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2015  - Conversión [00983]
86 | 1371 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2015  - Pendiente de integración  [00984]
87 | 1388 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2015  - Pendiente aplicación a principio del período [01220]
88 | 1405 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2015  - Ingresado en esta liquidación [01221]
89 | 1422 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2015  - Conversión [01222]
90 | 1439 | 17 | Num | Dotaciones deterioro créditos u otros activos - Ejercicio generación 2015  - Pendiente de integración  [01223]
91 | 1456 | 17 | Num | Dotaciones deterioro créditos u otros activos - Total  - Pendiente aplicación a principio del período [00953]
92 | 1473 | 17 | Num | Dotaciones deterioro créditos u otros activos - Total  - Ingresado en esta liquidación [00344]
93 | 1490 | 17 | Num | Dotaciones deterioro créditos u otros activos - Total  - Conversión [00985]
94 | 1507 | 17 | Num | Dotaciones deterioro créditos u otros activos - Total  - Pendiente de integración  [00954]
95 | 1524 | 17 | Num | Dotaciones deterioro créditos u otros activos - Conversión activos impuesto diferido - Importe crédito exigible [00393]
96 | 1541 | 17 | Num | Dotaciones deterioro créditos u otros activos - Conversión activos impuesto diferido - Opciones: Abono [00150]
97 | 1558 | 17 | Num | Dotaciones deterioro créditos u otros activos - Conversión activos impuesto diferido - Opciones: Compensación [00506]
98 | 1575 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200200>"
Total: |  | 1584

# DP200021

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo |  | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | C | Página. | OBLIGATORIO | Constante "210"
4 | 9 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | C | Indicador de página complementaria |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 11 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. Descripción de la operación
7 | 31 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. Persona o entidad
8 | 51 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. F/J |  | F - J
9 | 52 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. Clave país/territorio
10 | 54 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. Importe
11 | 71 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. Descripción de la operación
12 | 91 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. Persona o entidad
13 | 111 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. F/J |  | F - J
14 | 112 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. Clave país/territorio
15 | 114 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. Importe
16 | 131 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3. Descripción de la operación
17 | 151 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3. Persona o entidad
18 | 171 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3. F/J |  | F - J
19 | 172 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3. Clave país/territorio
20 | 174 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3. Importe
21 | 191 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. Descripción de la operación
22 | 211 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. Persona o entidad
23 | 231 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. F/J |  | F - J
24 | 232 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. Clave país/territorio
25 | 234 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. Importe
26 | 251 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. Descripción de la operación
27 | 271 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. Persona o entidad
28 | 291 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. F/J |  | F - J
29 | 292 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. Clave país/territorio
30 | 294 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. Importe
31 | 311 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. Descripción de la operación
32 | 331 | 20 | An | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. Persona o entidad
33 | 351 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. F/J |  | F - J
34 | 352 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. Clave país/territorio
35 | 354 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. Importe
36 | 371 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. Tipo |  | A - B - C
37 | 372 | 23 | An | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. Entidad participada
38 | 395 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. Clave país/territorio
39 | 397 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. Valor adquisición
40 | 414 | 5 | Num | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. % participación
41 | 419 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. Tipo |  | A - B - C
42 | 420 | 23 | An | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. Entidad participada
43 | 443 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. Clave país/territorio
44 | 445 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. Valor adquisición
45 | 462 | 5 | Num | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. % participación
46 | 467 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. Tipo |  | A - B - C
47 | 468 | 23 | An | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. Entidad participada
48 | 491 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. Clave país/territorio
49 | 493 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. Valor adquisición
50 | 510 | 5 | Num | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. % participación
51 | 515 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. Tipo |  | A - B - C
52 | 516 | 23 | An | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. Entidad participada
53 | 539 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. Clave país/territorio
54 | 541 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. Valor adquisición
55 | 558 | 5 | Num | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. % participación
56 | 563 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. Tipo |  | A - B - C
57 | 564 | 23 | An | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. Entidad participada
58 | 587 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. Clave país/territorio
59 | 589 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. Valor adquisición
60 | 606 | 5 | Num | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. % participación
61 | 611 | 1 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. Tipo |  | A - B - C
62 | 612 | 23 | An | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. Entidad participada
63 | 635 | 2 | A | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. Clave país/territorio
64 | 637 | 17 | N | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. Valor adquisición
65 | 654 | 5 | Num | C | Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. % participación
66 | 659 | 17 | N |  | Comunicación importe neto cifra negocios - Grupos de sociedades. Importe neto cifra negocios [00987]
67 | 676 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [1]
68 | 685 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [2]
69 | 694 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [3]
70 | 703 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [4]
71 | 712 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [5]
72 | 721 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [6]
73 | 730 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [7]
74 | 739 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [8]
75 | 748 | 9 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [9]
76 | 757 | 17 | N |  | Comunicación importe neto cifra negocios - No residentes más de un establecimiento. Importe neto [00988]
77 | 774 | 3 | Num |  | Comunicación importe neto cifra negocios - No residentes más de un establecimiento. Nº establecimientos
78 | 777 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los establecimientos permanentes [1]
79 | 786 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los establecimientos permanentes [2]
80 | 795 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los establecimientos permanentes [3]
81 | 804 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los establecimientos permanentes [4]
82 | 813 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los establecimientos permanentes [5]
83 | 822 | 17 | N |  | Comunicación importe neto cifra negocios - Entidades de crédito, aseguradoras, I.I.C. y sociedades de garantía recíproca - Importe neto de la cifra de negocios ejercicio 2015  [00989]
84 | 839 | 4 | Num |  | Rég. Entidades navieras en función del tonelaje. Nº de buques  [N1]
85 | 843 | 17 | Num |  | Rég. Entidades navieras en función del tonelaje. Base imponible resultante de  aplicar la escala [00630]
86 | 860 | 17 | Num |  | Rég. Entidades navieras en función del tonelaje. Importe rentas generadas en trasmisiones de buques [00631]
87 | 877 | 17 | Num |  | Rég. Entidades navieras en función del tonelaje. Compensación bases imponibles negativas períodos anteriores [00632]
88 | 894 | 17 | Num |  | Rég. Entidades navieras en función del tonelaje. Base imponible resultante de la aplicación del régimen [00579]
89 | 911 | 10 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T200210>"
Total: |  | 920

# DP200022

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo |  | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An |  | Página. | OBLIGATORIO | Constante "220"
4 | 9 | 1 | An |  | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An |  | Indicador de página complementaria |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 11 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2011 - Importe dotación [00089]
7 | 28 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2011 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00094]
8 | 45 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2011 - Inversiones previstas C D art. 27.4 Ley 19/94 [00095]
9 | 62 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2012 - Importe dotación [00097]
10 | 79 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2012 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00098]
11 | 96 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2012 - Inversiones previstas C D art. 27.4 Ley 19/94 [00047]
12 | 113 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2012 - Pendiente materializar [00048]
13 | 130 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2013 - Importe dotación [00524]
14 | 147 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2013 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00525]
15 | 164 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2013 - Inversiones previstas C D art. 27.4 Ley 19/94 [00526]
16 | 181 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2013 - Pendiente materializar [00527]
17 | 198 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2014 - Importe dotación [00922]
18 | 215 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2014 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00923]
19 | 232 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2014 - Inversiones previstas C D art. 27.4 Ley 19/94 [00924]
20 | 249 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2014 - Pendiente materializar [00925]
21 | 266 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2015 - Importe dotación [00927]
22 | 283 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2015 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00928]
23 | 300 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2015 - Inversiones previstas C D art. 27.4 Ley 19/94 [00938]
24 | 317 | 17 | Num |  | Rég. especial reserva inversiones Canarias - RIC 2015 - Pendiente materializar [00996]
25 | 334 | 17 | Num |  | Rég. especial reserva inversiones Canarias - Invers. anticipadas futuras dotaciones RIC en 2015 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00020]
26 | 351 | 17 | Num |  | Rég. especial reserva inversiones Canarias - Invers. anticipadas futuras dotaciones RIC en 2015 - Inversiones previstas C y D art. 27.4 Ley 19/94 [00021]
27 | 368 | 15 | An | C | Operaciones con personas o entidades vinculadas - Nº identificación matriz
28 | 383 | 40 | An | C | Operaciones con personas o entidades vinculadas - Razón social (matriz)
29 | 423 | 15 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. NIF
30 | 438 | 1 | A | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. F/J
31 | 439 | 40 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Apellidos y nombre / Razón social
32 | 479 | 2 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Código provincia/país
33 | 481 | 1 | A | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Tipo vinculación |  | A a H
34 | 482 | 17 | N | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Importe operación
35 | 499 | 15 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. NIF
36 | 514 | 1 | A | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. F/J
37 | 515 | 40 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Apellidos y nombre / Razón social
38 | 555 | 2 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Código provincia/país
39 | 557 | 1 | A | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Tipo vinculación |  | A a H
40 | 558 | 17 | N | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Importe operación
41 | 575 | 15 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. NIF
42 | 590 | 1 | A | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. F/J
43 | 591 | 40 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Apellidos y nombre / Razón social
44 | 631 | 2 | An | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Código provincia/país
45 | 633 | 1 | A | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Tipo vinculación |  | A a H
46 | 634 | 17 | N | C | Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Importe operación
47 | 651 | 15 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. NIF
48 | 666 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. F/J
49 | 667 | 40 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Apellidos y nombre/Razón social
50 | 707 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Tipo vinculación |  | A a H
51 | 708 | 2 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Código provincia/país
52 | 710 | 2 | Num | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Tipo operación |  | 1 a 11
53 | 712 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Ingreso/Pago |  | "I" "P"
54 | 713 | 2 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Método valoración |  | 1a 1b 1c 1d 1e(*)
55 | 715 | 17 | N | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Importe operación
56 | 732 | 15 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. NIF
57 | 747 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. F/J
58 | 748 | 40 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Apellidos y nombre/Razón social
59 | 788 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Tipo vinculación |  | A a H
60 | 789 | 2 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Código provincia/país
61 | 791 | 2 | Num | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Tipo operación |  | 1 a 11
62 | 793 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Ingreso/Pago |  | "I" "P"
63 | 794 | 2 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Método valoración |  | 1a 1b 1c 1d 1e(*)
64 | 796 | 17 | N | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Importe operación
65 | 813 | 15 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. NIF
66 | 828 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. F/J
67 | 829 | 40 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Apellidos y nombre/Razón social
68 | 869 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Tipo vinculación |  | A a H
69 | 870 | 2 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Código provincia/país
70 | 872 | 2 | Num | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Tipo operación |  | 1 a 11
71 | 874 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Ingreso/Pago |  | "I" "P"
72 | 875 | 2 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Método valoración |  | 1a 1b 1c 1d 1e(*)
73 | 877 | 17 | N | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Importe operación
74 | 894 | 15 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. NIF
75 | 909 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. F/J
76 | 910 | 40 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Apellidos y nombre/Razón social
77 | 950 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Tipo vinculación |  | A a H
78 | 951 | 2 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Código provincia/país
79 | 953 | 2 | Num | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Tipo operación |  | 1 a 11
80 | 955 | 1 | A | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Ingreso/Pago |  | "I" "P"
81 | 956 | 2 | An | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Método valoración |  | 1a 1b 1c 1d 1e(*)
82 | 958 | 17 | Num | C | Información operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Importe operación
83 | 975 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Ingresos computables - Resultados cooperativos [C1]
84 | 992 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Ingresos computables - Resultados extracooperativos [E1]
85 | 1009 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Gastos específicos - Resultados cooperativos [C2]
86 | 1026 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Gastos específicos - Resultados extracooperativos [E2]
87 | 1043 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Gastos generales - Resultados cooperativos [C3]
88 | 1060 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Gastos generales - Resultados extracooperativos [E3]
89 | 1077 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Gastos Fondo de Educación y Promoción - Resultados cooperativos [C4]
90 | 1094 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Gastos Fondo de Educación y Promoción - Resultados extracooperativos [E4]
91 | 1111 | 17 | N |  | Rég. cooperativas - Determ. base imponible - Incrementos y disminuciones patrimoniales - Resultados extracooperativos [E5]
92 | 1128 | 17 | N |  | Rég. cooperativas - Determ. base imponible - Resultado - Resultados cooperativos [C6]
93 | 1145 | 17 | N |  | Rég. cooperativas - Determ. base imponible - Resultado - Resultados extracooperativos [E6]
94 | 1162 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Aumentos - Resultados cooperativos [C7]
95 | 1179 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Aumentos - Resultados extracooperativos [E7]
96 | 1196 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Disminuciones - Resultados cooperativos [C8]
97 | 1213 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - Disminuciones - Resultados extracooperativos [E8]
98 | 1230 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - 50% Dotación obligatoria - Resultados cooperativos [C9]
99 | 1247 | 17 | Num |  | Rég. cooperativas - Determ. base imponible - 50% Dotación obligatoria - Resultados extracooperativos [E9]
100 | 1264 | 17 | N |  | Rég. cooperativas - Determ. base imponible - Reserva inversiones Canarias - Resultados cooperativos [C10]
101 | 1281 | 17 | N |  | Rég. cooperativas - Determ. base imponible - Factor de agotamiento - Resultados cooperativos [C11]
102 | 1298 | 17 | N |  | Rég. cooperativas - Determ. base imponible - Factor de agotamiento - Resultados extracooperativos [E11]
103 | 1315 | 17 | N |  | Rég. cooperativas - Determ. base imponible - Base imponible - Resultados cooperativos [00553]
104 | 1332 | 17 | N |  | Rég. cooperativas - Determ. base imponible - Base imponible - Resultados extracooperativos [00554]
105 | 1349 | 10 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T200220>"
Total: |  | 1358
 |  |  | (*) NOTA |  | Por compatibilidad con versiones anteriores se admitirán también los valores 2a 2b

# DP200023

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo |  | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | C | Página. | OBLIGATORIO | Constante "230"
4 | 9 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | C | Indicador de página complementaria. |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 11 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2000 Pendiente aplicación al principio del periodo [00673]
7 | 28 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2000 Aplicado en esta liquidación [00674]
8 | 45 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2000 Pendiente aplicación en períodos futuros  [01224]
9 | 62 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2001 Pendiente aplicación al principio del periodo [00676]
10 | 79 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2001 Aplicado en esta liquidación [00677]
11 | 96 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2001 Pendiente aplicación en períodos futuros  [00678]
12 | 113 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2002 Pendiente aplicación al principio del periodo [00679]
13 | 130 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2002 Aplicado en esta liquidación [00680]
14 | 147 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2002 Pendiente aplicación en períodos futuros [00681]
15 | 164 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2003 Pendiente aplicación al principio del periodo [00682]
16 | 181 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2003 Aplicado en esta liquidación [00683]
17 | 198 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2003 Pendiente aplicación en períodos futuros  [00684]
18 | 215 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2004 Pendiente aplicación al principio del periodo [00685]
19 | 232 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2004 Aplicado en esta liquidación [00686]
20 | 249 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2004 Pendiente aplicación en períodos futuros  [00687]
21 | 266 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2005 Pendiente aplicación al principio del periodo [00688]
22 | 283 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2005 Aplicado en esta liquidación [00689]
23 | 300 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2005 Pendiente aplicación en períodos futuros  [00690]
24 | 317 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2006 Pendiente aplicación al principio del periodo [00691]
25 | 334 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2006 Aplicado en esta liquidación [00692]
26 | 351 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2006 Pendiente aplicación en períodos futuros  [00693]
27 | 368 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2007 Pendiente aplicación al principio del periodo [00623]
28 | 385 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2007 Aplicado en esta liquidación [00624]
29 | 402 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2007 Pendiente aplicación en períodos futuros  [00672]
30 | 419 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2008 Pendiente aplicación al principio del periodo [00279]
31 | 436 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2008 Aplicado en esta liquidación [00280]
32 | 453 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2008 Pendiente aplicación en períodos futuros  [00281]
33 | 470 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2009 Pendiente aplicación al principio del periodo [00587]
34 | 487 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2009 Aplicado en esta liquidación [00515]
35 | 504 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2009 Pendiente aplicación en períodos futuros  [00900]
36 | 521 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2010 Pendiente aplicación al principio del periodo [00059]
37 | 538 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2010 Aplicado en esta liquidación [00099]
38 | 555 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2010 Pendiente aplicación en períodos futuros  [00100]
39 | 572 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2011 Pendiente aplicación al principio del periodo [00017]
40 | 589 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2011 Aplicado en esta liquidación [00018]
41 | 606 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2011 Pendiente aplicación en períodos futuros  [00019]
42 | 623 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2012 Pendiente aplicación al principio del periodo [00772]
43 | 640 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2012 Aplicado en esta liquidación [00773]
44 | 657 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2012 Pendiente aplicación en períodos futuros  [00777]
45 | 674 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2013 Pendiente aplicación al principio del periodo [00907]
46 | 691 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2013 Aplicado en esta liquidación [00908]
47 | 708 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2013 Pendiente aplicación en períodos futuros  [00909]
48 | 725 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2014 Pendiente aplicación al principio del periodo [00910]
49 | 742 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2014 Aplicado en esta liquidación [00911]
50 | 759 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2014 Pendiente aplicación en períodos futuros  [00912]
51 | 776 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2015 (*) Pendiente aplicación al principio del periodo [00935]
52 | 793 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2015 (*) Aplicado en esta liquidación [00936]
53 | 810 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2015 (*) Pendiente aplicación en períodos futuros  [00937]
54 | 827 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. Total. Pendiente aplicación al principio del periodo [00694]
55 | 844 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. Total. Aplicado en esta liquidación [00561]
56 | 861 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. Total. Pendiente aplicación en períodos futuros  [00695]
57 | 878 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2015 Pendiente aplicación al principio del periodo [01225]
58 | 895 | 17 | Num |  | Rég. cooperativas - Detalle compensación cuotas. 2015  Pendiente aplicación en períodos futuros  [01226]
59 | 912 | 1 | A | C | Operaciones fusión, escisión, canje valores - 1. Tipo de operación
60 | 913 | 9 | An | C | Operaciones fusión, escisión, canje valores - 1. Entidad transmitente. NIF
61 | 922 | 40 | An | C | Operaciones fusión, escisión, canje valores - 1. Entidad transmitente.Denominación social
62 | 962 | 9 | An | C | Operaciones fusión, escisión, canje valores - 1. Entidad adquirente. NIF
63 | 971 | 40 | An | C | Operaciones fusión, escisión, canje valores - 1. Entidad adquirente.Denominación social
64 | 1011 | 8 | Num | C | Operaciones fusión, escisión, canje valores - 1. Fecha de los acuerdos sociales
65 | 1019 | 17 | N | C | Operaciones fusión, escisión, canje valores - 1. Valor acciones entregadas
66 | 1036 | 17 | N | C | Operaciones fusión, escisión, canje valores - 1. Valor acciones recibidas
67 | 1053 | 17 | N | C | Operaciones fusión, escisión, canje valores - 1. Importe rentas no integradas en la base imponible
68 | 1070 | 1 | A | C | Operaciones fusión, escisión, canje valores - 2. Tipo de operación
69 | 1071 | 9 | An | C | Operaciones fusión, escisión, canje valores - 2. Entidad transmitente. NIF
70 | 1080 | 40 | An | C | Operaciones fusión, escisión, canje valores - 2. Entidad transmitente.Denominación social
71 | 1120 | 9 | An | C | Operaciones fusión, escisión, canje valores - 2. Entidad adquirente. NIF
72 | 1129 | 40 | An | C | Operaciones fusión, escisión, canje valores - 2. Entidad adquirente.Denominación social
73 | 1169 | 8 | Num | C | Operaciones fusión, escisión, canje valores - 2. Fecha de los acuerdos sociales
74 | 1177 | 17 | N | C | Operaciones fusión, escisión, canje valores - 2. Valor acciones entregadas
75 | 1194 | 17 | N | C | Operaciones fusión, escisión, canje valores - 2. Valor acciones recibidas
76 | 1211 | 17 | N | C | Operaciones fusión, escisión, canje valores - 2. Importe rentas no integradas en la base imponible
77 | 1228 | 1 | A | C | Operaciones fusión, escisión, canje valores - 3. Tipo de operación
78 | 1229 | 9 | An | C | Operaciones fusión, escisión, canje valores - 3. Entidad transmitente. NIF
79 | 1238 | 40 | An | C | Operaciones fusión, escisión, canje valores - 3. Entidad transmitente.Denominación social
80 | 1278 | 9 | An | C | Operaciones fusión, escisión, canje valores - 3. Entidad adquirente. NIF
81 | 1287 | 40 | An | C | Operaciones fusión, escisión, canje valores - 3. Entidad adquirente.Denominación social
82 | 1327 | 8 | Num | C | Operaciones fusión, escisión, canje valores - 3. Fecha de los acuerdos sociales
83 | 1335 | 17 | N | C | Operaciones fusión, escisión, canje valores - 3. Valor acciones entregadas
84 | 1352 | 17 | N | C | Operaciones fusión, escisión, canje valores - 3. Valor acciones recibidas
85 | 1369 | 17 | N | C | Operaciones fusión, escisión, canje valores - 3. Importe rentas no integradas en la base imponible
86 | 1386 | 10 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T200230>"
Total: |  | 1395

# DP200024

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo |  | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | C | Página. | OBLIGATORIO | Constante "240"
4 | 9 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | C | Indicador de página complementaria. |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 11 | 7 | Num |  | Agrup. interés económico y UTES - Porcentaje de imputación de bases imponibles [00060]
7 | 18 | 17 | N |  | Agrup. interés económico y UTES - Modelo de información - Resultado cuenta de pérdidas y ganancias  [00500]
8 | 35 | 17 | N |  | Agrup. interés económico y UTES - Modelo de información - Gastos financieros netos no deducidos por la entidad  [01227]
9 | 52 | 17 | N |  | Agrup. interés económico y UTES - Modelo de información - Reserva capitaliz. no aplicada por la entidad  [01228]
10 | 69 | 17 | N |  | Agrup. interés económico y UTES - Modelo de información - Base imponible [00552]
11 | 86 | 17 | N |  | Agrup. interés económico y UTES - Modelo de información - Base imponible minorada o incrementada [01330]
12 | 103 | 17 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  1. Base deducción
13 | 120 | 5 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  1. % participación
14 | 125 | 17 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  2. Base deducción
15 | 142 | 5 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  2. % participación
16 | 147 | 17 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  3. Base deducción
17 | 164 | 5 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  3. % participación
18 | 169 | 17 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  4. Base deducción
19 | 186 | 5 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  4. % participación
20 | 191 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Base bonificaciones
21 | 208 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Base de deducciones - a) Base total
22 | 225 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Base de deducciones - b) Base deducciones por inversiones
23 | 242 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Retenciones e ingresos a cuenta  [00062]
24 | 259 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Dividendos y participaciones. a) Ejercicios que no haya tributado en régimen especial
25 | 276 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Dividendos y participaciones. b) Ejercicios que haya tributado en régimen especial
26 | 293 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. NIF
27 | 302 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Rpte. | ( "0", "1")
28 | 303 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. F/J | F -J
29 | 304 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. R/X | R -X
30 | 305 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Apellidos y nombre/Razón social
31 | 339 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Código provincia/país
32 | 341 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Base imponible
33 | 358 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. % partic.
34 | 365 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. NIF
35 | 374 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Rpte. | ( "0", "1")
36 | 375 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. F/J | F -J
37 | 376 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. R/X | R -X
38 | 377 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Apellidos y nombre/Razón social
39 | 411 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Código provincia/país
40 | 413 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Base imponible
41 | 430 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. % partic.
42 | 437 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. NIF
43 | 446 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Rpte. | ( "0", "1")
44 | 447 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. F/J | F -J
45 | 448 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. R/X | R -X
46 | 449 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Apellidos y nombre/Razón social
47 | 483 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Código provincia/país
48 | 485 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Base imponible
49 | 502 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. % partic.
50 | 509 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. NIF
51 | 518 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Rpte. | ( "0", "1")
52 | 519 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. F/J | F -J
53 | 520 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. R/X | R -X
54 | 521 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Apellidos y nombre/Razón social
55 | 555 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Código provincia/país
56 | 557 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Base imponible
57 | 574 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. % partic.
58 | 581 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. NIF
59 | 590 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Rpte. | ( "0", "1")
60 | 591 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. F/J | F -J
61 | 592 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. R/X | R -X
62 | 593 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Apellidos y nombre/Razón social
63 | 627 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Código provincia/país
64 | 629 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Base imponible
65 | 646 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. % partic.
66 | 653 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. NIF
67 | 662 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Rpte. | ( "0", "1")
68 | 663 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. F/J | F -J
69 | 664 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. R/X | R -X
70 | 665 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Apellidos y nombre/Razón social
71 | 699 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Código provincia/país
72 | 701 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Base imponible
73 | 718 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. % partic.
74 | 725 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. NIF
75 | 734 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Rpte. | ( "0", "1")
76 | 735 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. F/J | F -J
77 | 736 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. R/X | R -X
78 | 737 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Apellidos y nombre/Razón social
79 | 771 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Código provincia/país
80 | 773 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Base imponible
81 | 790 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. % partic.
82 | 797 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. NIF
83 | 806 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Rpte. | ( "0", "1")
84 | 807 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. F/J | F -J
85 | 808 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. R/X | R -X
86 | 809 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Apellidos y nombre/Razón social
87 | 843 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Código provincia/país
88 | 845 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Base imponible
89 | 862 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. % partic.
90 | 869 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. NIF
91 | 878 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Rpte. | ( "0", "1")
92 | 879 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. F/J | F -J
93 | 880 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. R/X | R -X
94 | 881 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Apellidos y nombre/Razón social
95 | 915 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Código provincia/país
96 | 917 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Base imponible
97 | 934 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. % partic.
98 | 941 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. NIF
99 | 950 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Rpte. | ( "0", "1")
100 | 951 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. F/J | F -J
101 | 952 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. R/X | R -X
102 | 953 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Apellidos y nombre/Razón social
103 | 987 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Código provincia/país
104 | 989 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Base imponible
105 | 1006 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. % partic.
106 | 1013 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. NIF
107 | 1022 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. Rpte. | ( "0", "1")
108 | 1023 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. F/J | F -J
109 | 1024 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. R/X | R -X
110 | 1025 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. Apellidos y nombre/Razón social
111 | 1059 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. Código provincia/país
112 | 1061 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. Base imponible
113 | 1078 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. % partic.
114 | 1085 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Identificación.
115 | 1105 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. País residencia fiscal
116 | 1107 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Volumen operaciones
117 | 1124 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Beneficio o pérdida en el período impositivo
118 | 1141 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Suma de ajustes al resultado contable
119 | 1158 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Suma Deducciones por DI internac. períodos ant.
120 | 1175 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Identificación.
121 | 1195 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. País residencia fiscal
122 | 1197 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Volumen operaciones
123 | 1214 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Beneficio o pérdida en el período impositivo
124 | 1231 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Suma de ajustes al resultado contable
125 | 1248 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Suma Deducciones por DI internac. períodos ant.
126 | 1265 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Identificación.
127 | 1285 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. País residencia fiscal
128 | 1287 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Volumen operaciones
129 | 1304 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Beneficio o pérdida en el período impositivo
130 | 1321 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Suma de ajustes al resultado contable
131 | 1338 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Suma Deducciones por DI internac. períodos ant.
132 | 1355 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Identificación.
133 | 1375 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. País residencia fiscal
134 | 1377 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Volumen operaciones
135 | 1394 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Beneficio o pérdida en el período impositivo
136 | 1411 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Suma de ajustes al resultado contable
137 | 1428 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Suma Deducciones por DI internac. períodos ant.
138 | 1445 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Identificación.
139 | 1465 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. País residencia fiscal
140 | 1467 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Volumen operaciones
141 | 1484 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Beneficio o pérdida en el período impositivo
142 | 1501 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Suma de ajustes al resultado contable
143 | 1518 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Suma Deducciones por DI internac. períodos ant.
144 | 1535 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Identificación.
145 | 1555 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. País residencia fiscal
146 | 1557 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Volumen operaciones
147 | 1574 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Beneficio o pérdida en el período impositivo
148 | 1591 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Suma de ajustes al resultado contable
149 | 1608 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Suma Deducciones por DI internac. períodos ant.
150 | 1625 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Identificación.
151 | 1645 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. País residencia fiscal
152 | 1647 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Volumen operaciones
153 | 1664 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Beneficio o pérdida en el período impositivo
154 | 1681 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Suma de ajustes al resultado contable
155 | 1698 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Suma Deducciones por DI internac. períodos ant.
156 | 1715 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Identificación.
157 | 1735 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. País residencia fiscal
158 | 1737 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Volumen operaciones
159 | 1754 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Beneficio o pérdida en el período impositivo
160 | 1771 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Suma de ajustes al resultado contable
161 | 1788 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Suma Deducciones por DI internac. períodos ant.
162 | 1805 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Identificación.
163 | 1825 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. País residencia fiscal
164 | 1827 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Volumen operaciones
165 | 1844 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Beneficio o pérdida en el período impositivo
166 | 1861 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Suma de ajustes al resultado contable
167 | 1878 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Suma Deducciones por DI internac. períodos ant.
168 | 1895 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Identificación.
169 | 1915 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. País residencia fiscal
170 | 1917 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Volumen operaciones
171 | 1934 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Beneficio o pérdida en el período impositivo
172 | 1951 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Suma de ajustes al resultado contable
173 | 1968 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Suma Deducciones por DI internac. períodos ant.
174 | 1985 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 11. Identificación.
175 | 2005 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 11. País residencia fiscal
176 | 2007 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 11. Volumen operaciones
177 | 2024 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 11. Beneficio o pérdida en el período impositivo
178 | 2041 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 11. Suma de ajustes al resultado contable
179 | 2058 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 11. Suma Deducciones por DI internac. períodos ant.
180 | 2075 | 10 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T200240>"
Total: |  | 2084

# DP200025

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo |  | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | C | Página. | OBLIGATORIO | Constante "250"
4 | 9 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | C | Indicador de página complementaria |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 11 | 40 | An | C | Rég.transparencia fiscal internacional - 1. Nombre o razón social
7 | 51 | 40 | An | C | Rég.transparencia fiscal internacional - 1. Domicilio social
8 | 91 | 2 | An | C | Rég.transparencia fiscal internacional - 1. Clave país/territorio
9 | 93 | 17 | Num | C | Rég.transparencia fiscal internacional - 1. Importe renta [A]
10 | 110 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 1
11 | 205 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 2
12 | 300 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 3
13 | 395 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 4
14 | 490 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 5
15 | 585 | 40 | An | C | Rég.transparencia fiscal internacional - 2. Nombre o razón social
16 | 625 | 40 | An | C | Rég.transparencia fiscal internacional - 2. Domicilio social
17 | 665 | 2 | An | C | Rég.transparencia fiscal internacional - 2. Clave país/territorio
18 | 667 | 17 | Num | C | Rég.transparencia fiscal internacional - 2. Importe renta [B]
19 | 684 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 1
20 | 779 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 2
21 | 874 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 3
22 | 969 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 4
23 | 1064 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 5
24 | 1159 | 40 | An | C | Rég.transparencia fiscal internacional - 3. Nombre o razón social
25 | 1199 | 40 | An | C | Rég.transparencia fiscal internacional - 3. Domicilio social
26 | 1239 | 2 | An | C | Rég.transparencia fiscal internacional - 3. Clave país/territorio
27 | 1241 | 17 | Num | C | Rég.transparencia fiscal internacional - 3. Importe renta [C]
28 | 1258 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 1
29 | 1353 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 2
30 | 1448 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 3
31 | 1543 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 4
32 | 1638 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 5
33 | 1733 | 40 | An | C | Rég.transparencia fiscal internacional - 4. Nombre o razón social
34 | 1773 | 40 | An | C | Rég.transparencia fiscal internacional - 4. Domicilio social
35 | 1813 | 2 | An | C | Rég.transparencia fiscal internacional - 4. Clave país/territorio
36 | 1815 | 17 | Num | C | Rég.transparencia fiscal internacional - 4. Importe renta [D]
37 | 1832 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 1
38 | 1927 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 2
39 | 2022 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 3
40 | 2117 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 4
41 | 2212 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 5
42 | 2307 | 40 | An | C | Rég.transparencia fiscal internacional - 5. Nombre o razón social
43 | 2347 | 40 | An | C | Rég.transparencia fiscal internacional - 5. Domicilio social
44 | 2387 | 2 | An | C | Rég.transparencia fiscal internacional - 5. Clave país/territorio
45 | 2389 | 17 | Num | C | Rég.transparencia fiscal internacional - 5. Importe renta [E]
46 | 2406 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 1
47 | 2501 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 2
48 | 2596 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 3
49 | 2691 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 4
50 | 2786 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 5
51 | 2881 | 40 | An | C | Rég.transparencia fiscal internacional - 6. Nombre o razón social
52 | 2921 | 40 | An | C | Rég.transparencia fiscal internacional - 6. Domicilio social
53 | 2961 | 2 | An | C | Rég.transparencia fiscal internacional - 6. Clave país/territorio
54 | 2963 | 17 | Num | C | Rég.transparencia fiscal internacional - 6. Importe renta [F]
55 | 2980 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 1
56 | 3075 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 2
57 | 3170 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 3
58 | 3265 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 4
59 | 3360 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 5
60 | 3455 | 17 | Num |  | Rég.transparencia fiscal internacional - Total importe [387]
61 | 3472 | 10 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T200250>"
Total: |  | 3481

# DP200026

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "260"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen total de operaciones  [00050]
7 | 28 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en el extranjero [00051]
8 | 45 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Araba [00052]
9 | 62 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Gipuzkoa [00053]
10 | 79 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Bizkaia [00054]
11 | 96 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Convenio económico - Volumen operaciones en Navarra [00055]
12 | 113 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Territorio común [00056]
13 | 130 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Araba [00626]
14 | 135 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Gipuzkoa [00627]
15 | 140 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Bizkaia [00628]
16 | 145 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Navarra [00629]
17 | 150 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Admón.del Estado [00625]
18 | 155 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Araba [00420]
19 | 172 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Gipuzkoa [00421]
20 | 189 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Bizkaia [00426]
21 | 206 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Navarra [00427]
22 | 223 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Total [00600]
23 | 240 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Araba [00402]
24 | 257 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Gipuzkoa [00442]
25 | 274 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Bizkaia [00443]
26 | 291 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Navarra [00444]
27 | 308 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Total [00602]
28 | 325 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Araba [00445]
29 | 342 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Gipuzkoa [00446]
30 | 359 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Bizkaia [00447]
31 | 376 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Navarra [00448]
32 | 393 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Total [00604]
33 | 410 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Araba [00449]
34 | 427 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Gipuzkoa [00450]
35 | 444 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Bizkaia [00451]
36 | 461 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Navarra [00465]
37 | 478 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Total [00606]
38 | 495 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Araba [00474]
39 | 512 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Gipuzkoa [00475]
40 | 529 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Bizkaia [00476]
41 | 546 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Navarra [00477]
42 | 563 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Total [00612]
43 | 580 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Araba [00482]
44 | 597 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Gipuzkoa [00483]
45 | 614 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Bizkaia [00484]
46 | 631 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Navarra [00485]
47 | 648 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Total [00616]
48 | 665 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Araba [00913]
49 | 682 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Gipuzkoa [00914]
50 | 699 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Bizkaia [00915]
51 | 716 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Navarra [00916]
52 | 733 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Total [00642]
53 | 750 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Araba [00486]
54 | 767 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Gipuzkoa [00487]
55 | 784 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Bizkaia [00488]
56 | 801 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Navarra [00489]
57 | 818 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Total [00618]
58 | 835 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Araba [00490]
59 | 852 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Gipuzkoa [00491]
60 | 869 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Bizkaia [00492]
61 | 886 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Navarra  [00493]
62 | 903 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Total [00620]
63 | 920 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Araba [01334]
64 | 937 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Gipuzkoa [01335]
65 | 954 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Bizkaia [01336]
66 | 971 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Navarra  [01337]
67 | 988 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Total [01332]
68 | 1005 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Araba [01338]
69 | 1022 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Gipuzkoa [01339]
70 | 1039 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Bizkaia [01340]
71 | 1056 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Navarra  [01341]
72 | 1073 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Total [01333]
73 | 1090 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Araba [00494]
74 | 1107 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Gipuzkoa [00495]
75 | 1124 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Bizkaia [00496]
76 | 1141 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Navarra [00497]
77 | 1158 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Total [00622]
78 | 1175 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Araba [01300]
79 | 1192 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Gipuzkoa [01301]
80 | 1209 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Bizkaia [01302]
81 | 1226 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Navarra  [01303]
82 | 1243 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Total [01043]
83 | 1260 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Araba [01305]
84 | 1277 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Gipuzkoa [01306]
85 | 1294 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Bizkaia [01307]
86 | 1311 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Navarra  [01308]
87 | 1328 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Total [01044]
88 | 1345 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200260>"
Total: |  | 1354

# DP200027

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "270"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Caja y depósitos en bancos centrales [00101]
7 | 28 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Cartera de negociación [00102]
8 | 45 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Depósitos en entidades de crédito [00103]
9 | 62 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Crédito a la clientela [00104]
10 | 79 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [00105]
11 | 96 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Otros instrumentos de capital [00106]
12 | 113 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Derivados de negociación [00107]
13 | 130 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Otros activos financieros a valor razonable con cambios en pérdidas y ganancias [00108]
14 | 147 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Depósitos en entidades de crédito [00109]
15 | 164 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Crédito a la clientela [00110]
16 | 181 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [00111]
17 | 198 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Instrumentos de capital [00112]
18 | 215 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos financieros disponibles para la venta [00113]
19 | 232 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [00114]
20 | 249 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Instrumentos de capital [00115]
21 | 266 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inversiones crediticias [00116]
22 | 283 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Depósitos en entidades de crédito [00117]
23 | 300 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Crédito a la clientela [00118]
24 | 317 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [00119]
25 | 334 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Cartera de inversión a vencimiento [00120]
26 | 351 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Ajustes a activos financieros por macro-coberturas [00121]
27 | 368 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Derivados de cobertura [00122]
28 | 385 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos no corrientes en venta [00123]
29 | 402 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Participaciones [00124]
30 | 419 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Entidades asociadas [00125]
31 | 436 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Entidades multigrupo [00126]
32 | 453 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Entidades del grupo [00127]
33 | 470 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Contratos de seguros vinculados a pensiones [00128]
34 | 487 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activo material [00129]
35 | 504 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material [00130]
36 | 521 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material - De uso propio [00131]
37 | 538 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material - Cedido en arrendamiento operativo [00132]
38 | 555 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material - Afecto a la Obra social [00133]
39 | 572 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inversiones inmobiliarias [00134]
40 | 589 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activo intangible [00135]
41 | 606 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Fondo de comercio [00136]
42 | 623 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Otro activo intangible [00137]
43 | 640 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos fiscales [00138]
44 | 657 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Corrientes [00139]
45 | 674 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Diferidos [00140]
46 | 691 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Resto de activos [00141]
47 | 708 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Total Activo - [00142]
48 | 725 | 17 | N | Contabilidad Banco de España - Balance (I) - Información adicional - Fondos insolvencias por cobertura específica [00202]
49 | 742 | 17 | N | Contabilidad Banco de España - Balance (I) - Información adicional - Fondos insolvencias por cobertura genérica [00203]
50 | 759 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200270>"
Total: |  | 768

# DP200028

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "280"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Cartera de negociación [00143]
7 | 28 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de bancos centrales [00144]
8 | 45 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de entidades de crédito [00145]
9 | 62 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de la clientela [00146]
10 | 79 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Débitos representados por valores negociables [00147]
11 | 96 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Derivados de negociación [00148]
12 | 113 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Posiciones cortas de valores [00149]
13 | 130 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [00150]
14 | 147 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros a valor razonable con cambios en pérdidas y ganancias [00151]
15 | 164 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de bancos centrales [00152]
16 | 181 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de entidades de crédito [00153]
17 | 198 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de la clientela [00154]
18 | 215 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Débitos representados por valores negociables [00155]
19 | 232 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos subordinados [00156]
20 | 249 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [00157]
21 | 266 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos financieros a coste amortizado [00158]
22 | 283 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de bancos centrales [00159]
23 | 300 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de entidades de crédito [00160]
24 | 317 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de la clientela [00161]
25 | 334 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Débitos representados por valores negociables [00162]
26 | 351 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos subordinados [00163]
27 | 368 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [00164]
28 | 385 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Ajustes a pasivos financieros por macro-coberturas [00165]
29 | 402 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Derivados de cobertura [00166]
30 | 419 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos asociados con activos no corrientes en venta [00167]
31 | 436 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Provisiones [00168]
32 | 453 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Fondo para pensiones y obligaciones similares [00169]
33 | 470 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Provisiones para impuestos y otras contingencias legales [00170]
34 | 487 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Provisiones para riesgos y compromisos contingentes [00171]
35 | 504 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otras provisiones [00172]
36 | 521 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos fiscales [00173]
37 | 538 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Corrientes [00174]
38 | 555 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Diferidos [00175]
39 | 572 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Fondo de la Obra social [00176]
40 | 589 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Resto de pasivos [00177]
41 | 606 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Capital reembolsable a la vista [00178]
42 | 623 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Total pasivo [00179]
43 | 640 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200280>"
Total: |  | 649

# DP200029

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "290"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Fondos propios [00180]
7 | 28 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Capital/Fondo dotación [00181]
8 | 45 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto   Capital/Fondo dotación - Escriturado [00182]
9 | 62 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Capital/Fondo dotación - Menos: capital no exigido [00183]
10 | 79 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Prima de emisión [00184]
11 | 96 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reservas [00185]
12 | 113 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reservas - Reserva de revalorización [00803]
13 | 130 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reservas - Reserva de capitalización [01001]
14 | 147 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reservas - Reserva de nivelación [01002]
15 | 164 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reservas - Otras reservas [00805]
16 | 181 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros instrumentos de capital [00186]
17 | 198 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros instrumentos de capital - De instrumentos financieros compuestos [00187]
18 | 215 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros instrumentos de capital - Cuotas participativas y fondos asociados [00188]
19 | 232 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros instrumentos de capital - Resto de instrumentos de capital [00189]
20 | 249 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Menos: valores propios [00190]
21 | 266 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Resultado del ejercicio [00191]
22 | 283 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Menos: Dividendos y retribuciones [00192]
23 | 300 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Ajustes por valoración [00193]
24 | 317 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Activos financieros disponibles para la venta [00194]
25 | 334 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Coberturas de los flujos de efectivo [00195]
26 | 351 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Coberturas de inversiones netas en negocios en el extranjero [00196]
27 | 368 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Diferencias de cambio [00197]
28 | 385 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Activos no corrientes en venta [00198]
29 | 402 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Resto de ajustes por valoración [00199]
30 | 419 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Total patrimonio neto [00200]
31 | 436 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Total pasivo y patrimonio neto [00201]
32 | 453 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200290>"
Total: |  | 462

# DP200030

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "300"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Intereses y rendimientos asimilados [00204]
7 | 28 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Intereses y cargas asimiladas [00205]
8 | 45 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Remuneración de capital reembolsable a la vista [00206]
9 | 62 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Margen de intereses [00207]
10 | 79 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Rendimiento de instrumentos de capital [00208]
11 | 96 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Comisiones percibidas [00209]
12 | 113 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Comisiones pagadas [00210]
13 | 130 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Resultado de operaciones financieras  [00211]
14 | 147 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Cartera de negociación [00212]
15 | 164 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Otros instrumentos financieros a valor razonable con cambios en pérdidas y ganancias [00213]
16 | 181 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Instrumentos financieros no valorados a valor razonable con cambios en pérdidas y ganancias [00214]
17 | 198 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Otros [00215]
18 | 215 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Diferencias de cambio  [00216]
19 | 232 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Otros productos de explotación [00217]
20 | 249 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Otras cargas de explotación [00218]
21 | 266 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Margen bruto [00219]
22 | 283 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Gastos de administración [00220]
23 | 300 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Gastos de personal [00221]
24 | 317 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Otros gastos generales de admón. [00222]
25 | 334 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Amortización [00223]
26 | 351 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Dotaciones a provisiones  [00224]
27 | 368 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Pérdidas por deterioro de activos financieros  [00225]
28 | 385 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Inversiones crediticias [00226]
29 | 402 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Otros instrumentos financieros no valorados a valor razonable con cambios en pérdidas y ganancias [00227]
30 | 419 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Resultado de la actividad de explotación [00228]
31 | 436 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Pérdidas por deterioro del resto de activos  [00229]
32 | 453 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Fondo de comercio y otro activo intangible [00230]
33 | 470 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Otros activos [00231]
34 | 487 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias (pérdidas) en la baja de activos no clasificados como no corrientes en venta [00232]
35 | 504 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Diferencia negativa en combinaciones de negocios [00233]
36 | 521 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias (pérdidas) de activos no corrientes en venta no clasificados como operaciones interrumpidas [00234]
37 | 538 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Resultado antes de impuestos [00235]
38 | 555 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Impuesto sobre beneficios [00236]
39 | 572 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Dotación obligatoria a obras y fondos sociales [00237]
40 | 589 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Resultado del ejercicio procedente de operaciones continuadas [00238]
41 | 606 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Resultado de operaciones interrumpidas  [00239]
42 | 623 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Resultado del ejercicio [00500]
43 | 640 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200300>"
Total: |  | 649

# DP200031

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "310"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Resultado del ejercicio [00500]
7 | 28 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Otros ingresos y gastos reconocidos [00256]
8 | 45 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Activos financieros disponibles para la venta [00257]
9 | 62 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Ganancias (pérdidas) por valoración [00258]
10 | 79 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Importes transferidos a la cuenta de pérdidas y ganancias [00259]
11 | 96 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Otras reclasificaciones [00260]
12 | 113 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Coberturas de los flujos de efectivo [00261]
13 | 130 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Ganancias (pérdidas) por valoración [00262]
14 | 147 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Importes transferidos a la cuenta de pérdidas y ganancias [00263]
15 | 164 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Importes transferidos al valor inicial de las partidas cubiertas [00264]
16 | 181 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Otras reclasificaciones [00265]
17 | 198 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Coberturas de inversiones netas en negocios en el extranjero [00266]
18 | 215 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Ganancias (pérdidas) por valoración [00267]
19 | 232 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Importes transferidos a la cuenta de pérdidas y ganancias [00268]
20 | 249 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Otras reclasificaciones [00269]
21 | 266 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Diferencias de cambio [00270]
22 | 283 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Ganancias (pérdidas) por valoración [00271]
23 | 300 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Importes transferidos a la cuenta de pérdidas y ganancias [00272]
24 | 317 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Otras reclasificaciones [00273]
25 | 334 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Activos no corrientes en venta [00274]
26 | 351 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos.Ganancias (pérdidas) por valoración [00275]
27 | 368 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00276]
28 | 385 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Otras reclasificaciones [00277]
29 | 402 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Ganancias (pérdidas) actuariales en planes de pensiones [00278]
30 | 419 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Resto de ingresos y gastos reconocidos [00279]
31 | 436 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Impuesto sobre beneficios [00280]
32 | 453 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos - Total ingresos y gastos reconocidos [00281]
33 | 470 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200310>"
Total: |  | 479

# DP200032

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "320"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc. anterior -  Capital/fondo dotación [00282]
7 | 28 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc. anterior -Prima emisión [00283]
8 | 45 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc. anterior -Reservas [00284]
9 | 62 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc. anterior -Otros instrumentos capital [00285]
10 | 79 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc. anterior -Menos: valores propios [00286]
11 | 96 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio contable - Capital/fondo dotación [00292]
12 | 113 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio contable - Prima emisión [00293]
13 | 130 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio contable - Reservas [00294]
14 | 147 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio contable - Otros instrumentos capital [00295]
15 | 164 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio contable - Menos: valores propios [00296]
16 | 181 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores - Capital/fondo dotación  [00302]
17 | 198 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores - Prima emisión [00303]
18 | 215 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores - Reservas [00304]
19 | 232 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores - Otros instrumentos capital [00305]
20 | 249 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores - Menos: valores propios [00306]
21 | 266 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado - Capital/fondo dotación [00312]
22 | 283 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado - Prima emisión [00313]
23 | 300 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado - Reservas [00314]
24 | 317 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado - Otros instrumentos capital [00315]
25 | 334 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado - Menos: valores propios [00316]
26 | 351 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos reconocidos - Capital/fondo dotación [00322]
27 | 368 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos reconocidos - Prima emisión [00323]
28 | 385 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos reconocidos - Reservas [00324]
29 | 402 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos reconocidos - Otros instrumentos capital [00325]
30 | 419 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos reconocidos - Menos: valores propios [00326]
31 | 436 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Capital/fondo dotación [00332]
32 | 453 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Prima emisión [00333]
33 | 470 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Reservas [00334]
34 | 487 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Otros instrumentos capital [00335]
35 | 504 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Menos: valores propios [00336]
36 | 521 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/ fondo de dotación - Capital/fondo dotación [00342]
37 | 538 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/ fondo de dotación - Prima emisión [00343]
38 | 555 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/ fondo de dotación - Reservas [00344]
39 | 572 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/ fondo de dotación - Otros instrumentos capital [00345]
40 | 589 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/ fondo de dotación - Menos: valores propios [00346]
41 | 606 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital - Capital/fondo dotación [00352]
42 | 623 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital - Prima emisión [00353]
43 | 640 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital - Reservas [00354]
44 | 657 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital - Otros instrumentos capital [00355]
45 | 674 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital - Menos: valores propios [00356]
46 | 691 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos financieros en capital - Capital/fondo dotación [00362]
47 | 708 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos financieros en capital - Prima emisión [00363]
48 | 725 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos financieros en capital - Reservas [00364]
49 | 742 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos financieros en capital - Otros instrumentos capital [00365]
50 | 759 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos financieros en capital - Menos: valores propios [00366]
51 | 776 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros instrumentos de capital - Capital/fondo dotación [00372]
52 | 793 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros instrumentos de capital - Prima emisión [00373]
53 | 810 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros instrumentos de capital - Reservas [00374]
54 | 827 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros instrumentos de capital - Otros instrumentos capital [00375]
55 | 844 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros instrumentos de capital - Menos: valores propios [00376]
56 | 861 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Capital/fondo dotación [00382]
57 | 878 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Prima emisión [00383]
58 | 895 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Reservas [00384]
59 | 912 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Otros instrumentos capital [00385]
60 | 929 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Menos: valores propios [00386]
61 | 946 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Capital/fondo dotación [00392]
62 | 963 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Prima emisión [00393]
63 | 980 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Reservas [00394]
64 | 997 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Otros instrumentos capital [00395]
65 | 1014 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Menos: valores propios [00396]
66 | 1031 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Capital/fondo dotación [00402]
67 | 1048 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Prima emisión [00403]
68 | 1065 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Reservas [00404]
69 | 1082 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Otros instrumentos capital [00405]
70 | 1099 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Menos: valores propios [00406]
71 | 1116 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Capital/fondo dotación [00412]
72 | 1133 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Prima emisión [00413]
73 | 1150 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Reservas [00414]
74 | 1167 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Otros instrumentos capital [00415]
75 | 1184 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Menos: valores propios [00416]
76 | 1201 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre partidas de patrimonio neto - Capital/fondo dotación [00422]
77 | 1218 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre partidas de patrimonio neto - Prima emisión [00423]
78 | 1235 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre partidas de patrimonio neto - Reservas [00424]
79 | 1252 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre partidas de patrimonio neto - Otros instrumentos capital [00425]
80 | 1269 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre partidas de patrimonio neto - Menos: valores propios [00426]
81 | 1286 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Capital/fondo dotación [00432]
82 | 1303 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Prima emisión [00433]
83 | 1320 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Reservas [00434]
84 | 1337 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Otros instrumentos capital [00435]
85 | 1354 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Menos: valores propios [00436]
86 | 1371 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Capital/fondo dotación [00442]
87 | 1388 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Prima emisión [00443]
88 | 1405 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Reservas [00444]
89 | 1422 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Otros instrumentos capital [00445]
90 | 1439 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Menos: valores propios [00446]
91 | 1456 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con instrumentos de capital - Capital/fondo dotación [00452]
92 | 1473 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con instrumentos de capital - Prima emisión [00453]
93 | 1490 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con instrumentos de capital - Reservas [00454]
94 | 1507 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con instrumentos de capital - Otros instrumentos capital [00455]
95 | 1524 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con instrumentos de capital - Menos: valores propios [00456]
96 | 1541 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Capital/fondo dotación [00462]
97 | 1558 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Prima emisión [00463]
98 | 1575 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Reservas [00464]
99 | 1592 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Otros instrumentos capital [00465]
100 | 1609 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Menos: valores propios [00466]
101 | 1626 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Capital/fondo dotación [00472]
102 | 1643 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Prima emisión [00473]
103 | 1660 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Reservas [00474]
104 | 1677 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Otros instrumentos capital [00475]
105 | 1694 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Menos: valores propios [00476]
106 | 1711 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200320>"
Total: |  | 1720

# DP200033

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "330"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc. Anterior - Resultado ejercicio [00287]
7 | 28 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc. anterior - Menos:dividendos y retribuciones [00288]
8 | 45 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc. anterior - Total fondos propios [00289]
9 | 62 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc. anterior - Ajustes por valoración [00290]
10 | 79 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc. anterior - Total patrimonio neto [00291]
11 | 96 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio de criterio contable - Resultado ejercicio [00297]
12 | 113 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio de criterio contable - Menos:dividendos y retribuciones [00298]
13 | 130 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio de criterio contable - Total fondos propios [00299]
14 | 147 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio de criterio contable - Ajustes por valoración [00300]
15 | 164 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio de criterio contable - Total patrimonio neto [00301]
16 | 181 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores - Resultado ejercicio [00307]
17 | 198 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores - Menos:dividendos y retribuciones [00308]
18 | 215 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores - Total fondos propios [00309]
19 | 232 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores - Ajustes por valoración [00310]
20 | 249 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores - Total patrimonio neto [00311]
21 | 266 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial ajustado - Resultado ejercicio [00317]
22 | 283 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial ajustado - Menos:dividendos y retribuciones [00318]
23 | 300 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial ajustado - Total fondos propios [00319]
24 | 317 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial ajustado - Ajustes por valoración [00320]
25 | 334 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial ajustado - Total patrimonio neto [00321]
26 | 351 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y gastos reconocidos - Resultado ejercicio [00327]
27 | 368 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y gastos reconocidos - Menos:dividendos y retribuciones [00328]
28 | 385 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y gastos reconocidos - Total fondos propios [00329]
29 | 402 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y gastos reconocidos - Ajustes por valoración [00330]
30 | 419 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y gastos reconocidos - Total patrimonio neto [00331]
31 | 436 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones del patrimonio neto - Resultado ejercicio [00337]
32 | 453 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones del patrimonio neto - Menos:dividendos y retribuciones [00338]
33 | 470 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones del patrimonio neto - Total fondos propios [00339]
34 | 487 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones del patrimonio neto - Ajustes por valoración [00340]
35 | 504 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones del patrimonio neto - Total patrimonio neto [00341]
36 | 521 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de capital/ fondo de dotacion -  Resultado ejercicio [00347]
37 | 538 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de capital/ fondo de dotacion -  Menos:dividendos y retribuciones [00348]
38 | 555 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de capital/ fondo de dotacion -  Total fondos propios [00349]
39 | 572 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de capital/ fondo de dotacion -  Ajustes por valoración [00350]
40 | 589 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de capital/ fondo de dotacion -  Total patrimonio neto [00351]
41 | 606 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de capital - Resultado ejercicio [00357]
42 | 623 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de capital - Menos:dividendos y retribuciones [00358]
43 | 640 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de capital - Total fondos propios [00359]
44 | 657 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de capital - Ajustes por valoración [00360]
45 | 674 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de capital - Total patrimonio neto [00361]
46 | 691 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de pasivos financieros en capital - Resultado ejercicio [00367]
47 | 708 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de pasivos financieros en capital - Menos:dividendos y retribuciones [00368]
48 | 725 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de pasivos financieros en capital - Total fondos propios [00369]
49 | 742 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de pasivos financieros en capital - Ajustes por valoración [00370]
50 | 759 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de pasivos financieros en capital - Total patrimonio neto [00371]
51 | 776 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de otros instrumentos de capital - Resultado ejercicio [00377]
52 | 793 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de otros instrumentos de capital - Menos:dividendos y retribuciones [00378]
53 | 810 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de otros instrumentos de capital - Total fondos propios [00379]
54 | 827 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de otros instrumentos de capital - Ajustes por valoración [00380]
55 | 844 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de otros instrumentos de capital - Total patrimonio neto [00381]
56 | 861 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Resultado ejercicio [00387]
57 | 878 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Menos:dividendos y retribuciones [00388]
58 | 895 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Total fondos propios [00389]
59 | 912 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Ajustes por valoración [00390]
60 | 929 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de pasivos financieros a otros instrumentos de capital - Total patrimonio neto [00391]
61 | 946 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Resultado ejercicio [00397]
62 | 963 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Menos:dividendos y retribuciones [00398]
63 | 980 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Total fondos propios [00399]
64 | 997 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Ajustes por valoración [00400]
65 | 1014 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de otros instrumentos de capital a pasivos financieros - Total patrimonio neto [00401]
66 | 1031 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Resultado ejercicio [00407]
67 | 1048 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Menos:dividendos y retribuciones [00408]
68 | 1065 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Total fondos propios [00409]
69 | 1082 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Ajustes por valoración [00410]
70 | 1099 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de dividendos /  Remuneración a los socios - Total patrimonio neto [00411]
71 | 1116 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Resultado ejercicio [00417]
72 | 1133 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Menos:dividendos y retribuciones [00418]
73 | 1150 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Total fondos propios [00419]
74 | 1167 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Ajustes por valoración [00420]
75 | 1184 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con instrumentos de capital propio (neto) - Total patrimonio neto [00421]
76 | 1201 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre partidas de patrimonio neto -  Resultado ejercicio [00427]
77 | 1218 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre partidas de patrimonio neto -  Menos:dividendos y retribuciones [00428]
78 | 1235 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre partidas de patrimonio neto -  Total fondos propios [00429]
79 | 1252 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre partidas de patrimonio neto -  Ajustes por valoración [00430]
80 | 1269 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre partidas de patrimonio neto -  Total patrimonio neto [00431]
81 | 1286 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Resultado ejercicio [00437]
82 | 1303 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Menos:dividendos y retribuciones [00438]
83 | 1320 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Total fondos propios [00439]
84 | 1337 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Ajustes por valoración [00440]
85 | 1354 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos (reducciones) por combinaciones de negocios - Total patrimonio neto [00441]
86 | 1371 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Resultado ejercicio [00447]
87 | 1388 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Menos:dividendos y retribuciones [00448]
88 | 1405 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Total fondos propios [00449]
89 | 1422 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Ajustes por valoración [00450]
90 | 1439 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación discrecional a obras y fondos sociales - Total patrimonio neto [00451]
91 | 1456 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con instrumentos de capital - Resultado ejercicio [00457]
92 | 1473 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con instrumentos de capital - Menos:dividendos y retribuciones [00458]
93 | 1490 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con instrumentos de capital - Total fondos propios [00459]
94 | 1507 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con instrumentos de capital - Ajustes por valoración [00460]
95 | 1524 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con instrumentos de capital - Total patrimonio neto [00461]
96 | 1541 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Resultado ejercicio [00467]
97 | 1558 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Menos:dividendos y retribuciones [00468]
98 | 1575 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Total fondos propios [00469]
99 | 1592 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Ajustes por valoración [00470]
100 | 1609 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de incrementos (reducciones) de patrimonio neto - Total patrimonio neto [00471]
101 | 1626 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final - Resultado ejercicio [00477]
102 | 1643 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final - Menos:dividendos y retribuciones [00478]
103 | 1660 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final - Total fondos propios [00479]
104 | 1677 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final - Ajustes por valoración [00480]
105 | 1694 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final - Total patrimonio neto [00481]
106 | 1711 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200330>"
Total: |  | 1720

# DP200034

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "340"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Efectivo y otros activos líquidos equivalentes [00101]
7 | 28 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Activos financieros mantenidos para negociar [00102]
8 | 45 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Instrumentos de patrimonio [00103]
9 | 62 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Valores representativos de deuda [00104]
10 | 79 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Derivados [00105]
11 | 96 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros [00106]
12 | 113 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros activos financieros a valor razonable con cambios en perdidas y ganancias [00107]
13 | 130 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Instrumentos de patrimonio [00108]
14 | 147 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Valores representativos de deuda [00109]
15 | 164 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Instrumentos híbridos [00110]
16 | 181 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inversiones por cuenta de tomadores seguros vida que asuman riesgo inversión [00111]
17 | 198 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros [00112]
18 | 215 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Activos financieros disponibles para la venta [00113]
19 | 232 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Instrumentos de patrimonio [00114]
20 | 249 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Valores representativos de deuda [00115]
21 | 266 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inversiones por cuenta de tomadores seguros vida 
que asuman riesgo inversión [00116]
22 | 283 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros [00117]
23 | 300 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos y partidas a cobrar [00118]
24 | 317 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Valores representativos de deuda [00119]
25 | 334 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos [00120]
26 | 351 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos - Anticipos sobre pólizas [00121]
27 | 368 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos - Préstamos a entidades del grupo y asociadas [00122]
28 | 385 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos - Préstamos a otras partes vinculadas [00123]
29 | 402 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Depósitos en entidades de crédito [00124]
30 | 419 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Depósitos constituídos por reaseguro aceptado [00125]
31 | 436 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de seguro directo [00126]
32 | 453 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de seguro directo - Tomadores de seguro [00127]
33 | 470 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de seguro directo - Mediadores [00128]
34 | 487 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de reaseguro [00129]
35 | 504 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de coaseguro [00130]
36 | 521 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Desembolsos exigidos [00131]
37 | 538 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros créditos [00132]
38 | 555 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros créditos - Créditos con las Administraciones Públicas [00133]
39 | 572 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros créditos - Resto de créditos [00134]
40 | 589 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inversiones mantenidas hasta el vencimiento [00135]
41 | 606 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Derivados de cobertura [00136]
42 | 623 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participación del reaseguro en las provisiones técnicas [00137]
43 | 640 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Provisión para primas no consumidas [00138]
44 | 657 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Provisión de seguros de vida [00139]
45 | 674 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Provisión para prestaciones [00140]
46 | 691 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otras provisiones técnicas [00141]
47 | 708 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inmovilizado material e inversiónes inmobiliarias [00142]
48 | 725 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inmovilizado material [00143]
49 | 742 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inversiones inmobiliarias [00144]
50 | 759 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inmovilizado intangible [00145]
51 | 776 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Fondo de comercio [00146]
52 | 793 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Derechos económicos derivados carteras de pólizas adquiridas a mediadores [00147]
53 | 810 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otro activo intangible [00148]
54 | 827 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participaciones en entidades del grupo y asociadas [00149]
55 | 844 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participaciones en empresas  asociadas [00150]
56 | 861 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participaciones en empresas multigrupo [00151]
57 | 878 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participaciones en empresas del grupo [00152]
58 | 895 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200340>"
Total: |  | 904

# DP200035

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "350"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos fiscales [00153]
7 | 28 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos por impuesto corriente [00154]
8 | 45 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos por impuesto diferido [00155]
9 | 62 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Otros activos [00156]
10 | 79 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos y derechos de reembolso por retribuciones a largo plazo al personal [00157]
11 | 96 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Comisiones anticipadas y otros costes adquisición [00158]
12 | 113 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Periodificaciones [00159]
13 | 130 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Resto de activos [00160]
14 | 147 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos mantenidos para la venta [00161]
15 | 164 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  TOTAL ACTIVO [00162]
16 | 181 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200350>"
Total: |  | 190

# DP200036

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimiens permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "360"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos financieros mantenidos para negociar [00163]
7 | 28 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otros pasivos financieros a valor razonable con cambios en pérdidas y ganancias. [00164]
8 | 45 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Débitos y partidas a pagar [00165]
9 | 62 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos subordinados [00166]
10 | 79 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Depósitos recibidos por reaseguro cedido [00167]
11 | 96 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro [00168]
12 | 113 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro - Deudas con asegurados [00169]
13 | 130 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro - Deudas con mediadores [00170]
14 | 147 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas por operaciones de seguro - Deudas condicionadas [00171]
15 | 164 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas por operaciones de reaseguro [00172]
16 | 181 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas por operaciones de coaseguro [00173]
17 | 198 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Obligaciones y otros valores negociables [00174]
18 | 215 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas con entidades de crédito [00175]
19 | 232 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas por operaciones preparatorias de contratos de seguro [00176]
20 | 249 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras deudas [00177]
21 | 266 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras deudas - Deudas con las Administraciones Públicas [00178]
22 | 283 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras deudas - Otras deudas con entidades del grupo y asociadas [00179]
23 | 300 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras deudas - Resto de otras deudas [00180]
24 | 317 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Derivados de cobertura [00181]
25 | 334 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisiones técnicas [00182]
26 | 351 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisión para primas no consumidas [00183]
27 | 368 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisión para riesgos en curso [00184]
28 | 385 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida [00185]
29 | 402 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida - Provisión para primas no consumidas [00186]
30 | 419 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida - Provisión para riesgos en curso [00187]
31 | 436 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida - Provisión matemática [00188]
32 | 453 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida - Provisión seguros de vida cuando riesgo de inversión lo asuma el tomador [00189]
33 | 470 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisión para prestaciones [00190]
34 | 487 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisión para participación en beneficios y para extornos [00191]
35 | 504 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras provisiones técnicas [00192]
36 | 521 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisiones no técnicas [00193]
37 | 538 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Provisiones para impuestos y otras contingencias legales [00194]
38 | 555 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Provisión para pensiones y obligaciones similiares [00195]
39 | 572 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Provisión para pagos por convenios de liquidación [00196]
40 | 589 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Otras provisiones no técnicas [00197]
41 | 606 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos fiscales [00198]
42 | 623 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos por impuesto corriente [00199]
43 | 640 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos por impuesto diferido [00200]
44 | 657 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Resto de pasivos [00201]
45 | 674 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Periodificaciones [00202]
46 | 691 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos por asimetrías contables [00203]
47 | 708 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Comisiones y otros costes de adquisición del reaseguro cedido [00204]
48 | 725 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Otros pasivos [00205]
49 | 742 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos vinculados con activos mantenidos para la venta [00206]
50 | 759 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  TOTAL PASIVO [00207]
51 | 776 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200360>"
Total: |  | 785

# DP200037

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "370"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Fondos propios [00208]
7 | 28 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual [00209]
8 | 45 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual - Capital escriturado o fondo mutual [00210]
9 | 62 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual - (Capital no exigido) [00211]
10 | 79 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Prima de emisión o asunción [00212]
11 | 96 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas [00213]
12 | 113 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva 
de revalorización [00382]
13 | 130 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva 
de capitalización [01001]
14 | 147 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva 
de nivelación [01002]
15 | 164 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Legal y estatutarias [00214]
16 | 181 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva de estabilización [00215]
17 | 198 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Otras reservas [00216]
18 | 215 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - (Acciones propias) [00217]
19 | 232 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios anteriores [00218]
20 | 249 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios anteriores - Remanente [00219]
21 | 266 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios anteriores - (Resultados negativos de ejercicios anteriores) [00220]
22 | 283 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otras aportaciones de socios y mutualistas [00221]
23 | 300 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultado del ejercicio [00222]
24 | 317 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - (Dividendo a cuenta y reserva de estabilización a cuenta) [00223]
25 | 334 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otros instrumentos de patrimonio neto [00224]
26 | 351 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Ajustes por cambios de valor [00225]
27 | 368 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Activos financieros disponibles para la venta [00226]
28 | 385 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Operaciones de cobertura [00227]
29 | 402 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Diferencias de cambio y conversión [00228]
30 | 419 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Corrección de asimetrías contables [00229]
31 | 436 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otros ajustes [00230]
32 | 453 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Subvenciones, donaciones y legados recibidos [00231]
33 | 470 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - TOTAL PATRIMONIO NETO [00232]
34 | 487 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - TOTAL PASIVO Y PATRIMONIO NETO [00233]
35 | 504 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200370>"
Total: |  | 513

# DP200038

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "380"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas imputadas al ejercicio [00234]
7 | 28 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas [00235]
8 | 45 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas - Seguro directo [00236]
9 | 62 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas - Reaseguro aceptado [00237]
10 | 79 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas - Variación de la corrección por deterioro de las primas pendientes de cobro (+ ó -) [00238]
11 | 96 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas reaseguro cedido (-) [00239]
12 | 113 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no consumidas y para riesgos en curso (+ ó -) [00240]
13 | 130 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no consumidas y para riesgos en curso (+ ó -) - Seguro directo [00241]
14 | 147 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no consumidas y para riesgos en curso (+ ó -) - Reaseguro aceptado [00242]
15 | 164 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no consumidas, reaseguro cedido (+ ó -)  [00243]
16 | 181 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Ingresos inmovilizado material y de las inversiones [00244]
17 | 198 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Ingresos inversiones inmobiliarias [00245]
18 | 215 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Ingresos inversiones financieras [00246]
19 | 232 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Aplic. correcciones de valor por deterioro del inmovilizado material y de las inversiones [00247]
20 | 249 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Aplic. correc. valor por deterioro inmovilizado material y de inversiones - Inmovilizado material e inv.inmobiliarias [00248]
21 | 266 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Aplic. correc. valor por deterioro inmovilizado material y de inversiones - Inversiones financieras [00249]
22 | 283 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado material y de inversiones [00250]
23 | 300 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado material y de inversiones - Inmovilizado material e inversiones inmobiliarias [00251]
24 | 317 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado material y de inversiones - Inversiones financieras [00252]
25 | 334 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros ingresos técnicos [00253]
26 | 351 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Siniestralidad del ejercicio, neta de reaseguro [00254]
27 | 368 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos pagados [00255]
28 | 385 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos pagados - Seguro directo [00256]
29 | 402 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos pagados - Reaseguro aceptado [00257]
30 | 419 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos pagados - Reaseguro cedido (-)  [00258]
31 | 436 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión para prestaciones  (+ ó -) [00259]
32 | 453 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Variación provisión para prestaciones  (+ ó -) - Seguro directo  [00260]
33 | 470 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Variación provisión para prestaciones  (+ ó -) - Reaseguro aceptado [00261]
34 | 487 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Variación provisión para prestaciones  (+ ó -) - Reaseguro cedido (-)  [00262]
35 | 504 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos imputables prestaciones [00263]
36 | 521 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación otras provisiones técnicas, netas de reaseguro (+ ó -)  [00264]
37 | 538 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Participación en beneficios y extornos [00265]
38 | 555 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos por participación en beneficios y extornos [00266]
39 | 572 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión participación en beneficios y extornos (+ ó -)  [00267]
40 | 589 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos explotación netos [00268]
41 | 606 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos adquisición [00269]
42 | 623 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos administración [00270]
43 | 640 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Comisiones y participaciones en el reaseguro cedido y retrocedido  [00271]
44 | 657 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros gastos técnicos (+ ó -)  [00272]
45 | 674 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación deterioro por insolvencias (+ ó -)   [00273]
46 | 691 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación deterioro del inmovilizado  (+ ó -)  [00274]
47 | 708 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación prestaciones por convenios de liquidación de siniestros (+ ó -)  [00275]
48 | 725 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros [00276]
49 | 742 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos inmovilizado material e inversiones [00277]
50 | 759 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones [00278]
51 | 776 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones - Gastos inmovilizado material e inv.inmobiliarias [00279]
52 | 793 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones - Gastos inversiones y cuentas financieras [00280]
53 | 810 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor inmovilizado material e inversiones  [00281]
54 | 827 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor inmovilizado material e inversiones - Amortización inmovilizado material e inversiones inmobiliarias [00282]
55 | 844 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor inmovilizado material e inversiones - Deterioro inmovilizado material e inversiones inmobiliarias [00283]
56 | 861 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor inmovilizado material e inversiones - Deterioro inversiones financieras [00284]
57 | 878 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado material e inversiones [00285]
58 | 895 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado material e inversiones - Inmovilizado material e inversiones inmobiliarias [00286]
59 | 912 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado material e inversiones -Inversiones financieras [00287]
60 | 929 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Subtotal (Resultado de la cuenta técnica del seguro no vida)  [00288]
61 | 946 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200380>"
Total: |  | 955

# DP200039

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "390"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas imputadas al ejercicio, netas de reaseguro [00289]
7 | 28 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas [00290]
8 | 45 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas - Seguro directo [00291]
9 | 62 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas - Reaseguro aceptado [00292]
10 | 79 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas - Variación corrección por deterioro de las primas pendientes de cobro (+ ó -) [00293]
11 | 96 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas reaseguro cedido (-) [00294]
12 | 113 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión para primas no consumidas y riesgos en curso (+ ó -) [00295]
13 | 130 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión para primas no consumidas y riesgos en curso (+ ó -) -Seguro directo [00296]
14 | 147 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión para primas no consumidas y riesgos en curso (+ ó -) - Reaseguro aceptado [00297]
15 | 164 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida -  Variación provisión primas no consumidas, reaseguro cedido (+ ó -) [00298]
16 | 181 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inmovilizado material e inversiones [00299]
17 | 198 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inversiones inmobiliarias [00300]
18 | 215 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inversiones financieras [00301]
19 | 232 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por deterioro inmov. material e inversiones [00302]
20 | 249 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por deterioro inmov. material e inversiones - Inmovilizado material e inv. inmobiliarias [00303]
21 | 266 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por deterioro inmov. material e inversiones - Inversiones financieras [00304]
22 | 283 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización inmovilizado material e inversiones [00305]
23 | 300 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización inmovilizado material e inversiones - Inmovilizado material e inv. inmobiliarias [00306]
24 | 317 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización inmovilizado material e inversiones - Inversiones financieras [00307]
25 | 334 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Inversiones afectas a seguros el tomador asume riesgo de inversión [00308]
26 | 351 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Otros ingresos ténicos [00309]
27 | 368 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Siniestralidad del ejercicio, neta de reaseguro [00310]
28 | 385 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados [00311]
29 | 402 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados - Seguro directo [00312]
30 | 419 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados - Reaseguro aceptado [00313]
31 | 436 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados - Reaseguro cedido (-)  [00314]
32 | 453 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión prestaciones (+ ó -) [00315]
33 | 470 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión prestaciones (+ ó -) - Seguro directo  [00316]
34 | 487 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión prestaciones (+ ó -) - Reaseguro aceptado [00317]
35 | 504 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión prestaciones (+ ó -) - Reaseguro cedido [00318]
36 | 521 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos imputables prestaciones [00319]
37 | 538 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación otras provisiones técnicas [00320]
38 | 555 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida [00321]
39 | 572 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida - Seguro directo [00322]
40 | 589 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida - Reaseguro aceptado [00323]
41 | 606 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida - Reaseguro cedido  (-)  [00324]
42 | 623 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida riesgo asumen tomadores [00325]
43 | 640 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Otras provisiones técnicas [00326]
44 | 657 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Participación beneficios y extornos [00327]
45 | 674 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos participación beneficios y extornos [00328]
46 | 691 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión participación beneficios y extornos  (+ o -)  [00329]
47 | 708 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos explotación netos [00330]
48 | 725 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos adquisición [00331]
49 | 742 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos administración [00332]
50 | 759 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Comisiones y participaciones reaseguro cedido y retrocedido [00333]
51 | 776 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200390>"
Total: |  | 785

# DP200040

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "400"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Otros gastos técnicos (+ ó -) [00334]
7 | 28 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Variación deterioro por insolvencias (+ ó -) [00335]
8 | 45 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Variación deterioro del inmovilizado (+ ó -)  [00336]
9 | 62 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Otros [00337]
10 | 79 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Gastos del inmovilizado material y de las inversiones [00338]
11 | 96 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos de gestión del inmovilizado material y de las inversiones [00339]
12 | 113 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos gestión inmovilizado material e inversiones - Gastos del inmovilizado material y de las inversiones inmobiliarias [00340]
13 | 130 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos gestión inmovilizado material e inversiones - Gastos de inversiones y cuentas financieras [00341]
14 | 147 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor inmovilizado material e  inversiones [00342]
15 | 164 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor inmovilizado material e  inversiones - Amortización del inmovilizado material y de las inversiones inmobiliarias [00343]
16 | 181 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor inmovilizado material e  inversiones -Deterioro del inmovilizado material y de las inversiones inmobiliarias [00344]
17 | 198 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor inmovilizado material e  inversiones - Deterioro de  inversiones financieras [00345]
18 | 215 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Pérdidas procedentes del inmovilizado material y de las inversiones [00346]
19 | 232 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Pérdidas procedentes del inmovilizado material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [00347]
20 | 249 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Pérdidas procedentes del inmovilizado material y de las inversiones - De las inversiones financieras [00348]
21 | 266 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Gastos de inversiones afectas a seguros en los que el tomador asume el riesgo de la inversión [00349]
22 | 283 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Subtotal (Resultado de la cuenta técnica del seguro de vida) [00350]
23 | 300 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos del inmovilizado material y de las inversiones [00351]
24 | 317 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos procedentes de las inversiones inmobiliarias [00352]
25 | 334 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos procedentes de las inversiones financieras [00353]
26 | 351 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplicaciones de correcciones de valor por deterioro del  inmovilizado material y de las inversiones [00354]
27 | 368 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplic. de correc. valor por deterioro inmovilizado material e inversiones - Del inmovilizado material y de las inversiones inmobiliarias [00355]
28 | 385 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplic. de correc. valor por deterioro inmovilizado material e inversiones - De inversiones financieras [00356]
29 | 402 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Beneficios en realización del inmovilizado material y de las inversiones [00357]
30 | 419 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Beneficios en realización del inmovilizado material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [00358]
31 | 436 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Beneficios en realización del inmovilizado material y de las inversiones - De inversiones financieras [00359]
32 | 453 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos del inmovilizado material y de las inversiones [00360]
33 | 470 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones [00361]
34 | 487 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones - Gastos de inversiones y cuentas financieras [00362]
35 | 504 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones - Gastos de inversiones materiales [00363]
36 | 521 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correcciones de valor del inmovilizado material y de las inversiones [00364]
37 | 538 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e inversiones - Amortización del inmovilizado material y de las inversiones inmobiliarias [00365]
38 | 555 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e inversiones - Deterioro del inmovilizado material y de las inversiones inmobiliarias [00366]
39 | 572 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e inversiones - Deterioro de inversiones financieras [00367]
40 | 589 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado material y de las inversiones [00368]
41 | 606 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [00369]
42 | 623 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado material y de las inversiones - De las inversiones financieras [00370]
43 | 640 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Otros ingresos [00371]
44 | 657 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos por la administración de fondos de pensiones [00372]
45 | 674 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resto de ingresos [00373]
46 | 691 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Otros gastos [00374]
47 | 708 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos por la administración de fondos de pensiones [00375]
48 | 725 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resto de gastos [00376]
49 | 742 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Subtotal (resultado de la cuenta no técnica) [00377]
50 | 759 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado antes de impuestos [00378]
51 | 776 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Impuesto sobre beneficios  [00379]
52 | 793 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado procedente de operaciones continuadas [00380]
53 | 810 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado procedente de operaciones interrumpidas neto de impuestos [00381]
54 | 827 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado del ejercicio [00500]
55 | 844 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200400>"
Total: |  | 853

# DP200041

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "410"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Resultado del ejercicio [00500]
7 | 28 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otros ingresos y gastos reconocidos [00383]
8 | 45 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Activos financieros disponibles para la venta [00384]
9 | 62 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00385]
10 | 79 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00386]
11 | 96 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00387]
12 | 113 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Coberturas de los flujos de efectivo [00388]
13 | 130 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00389]
14 | 147 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00390]
15 | 164 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos al valor inicial de las partidas cubiertas [00391]
16 | 181 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00392]
17 | 198 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Coberturas de inversiones netas en negocios en el extranjero [00393]
18 | 215 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00394]
19 | 232 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00395]
20 | 249 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00396]
21 | 266 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Diferencias de cambio y conversión [00397]
22 | 283 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00398]
23 | 300 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00399]
24 | 317 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00400]
25 | 334 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Corrección de asimetrías contables [00401]
26 | 351 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00402]
27 | 368 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00403]
28 | 385 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00404]
29 | 402 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Activos mantenidos para la venta [00405]
30 | 419 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00406]
31 | 436 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00407]
32 | 453 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00408]
33 | 470 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias / (pérdidas) actuariales por retribuciones a largo plazo del personal [00409]
34 | 487 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otros ingresos y gastos reconocidos [00410]
35 | 504 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Impuesto sobre beneficios [00411]
36 | 521 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Total de ingresos y gastos reconocidos [00412]
37 | 538 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200410>"
Total: |  | 547

# DP200042

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "420"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Capital o fondo mutual escriturado [00413]
7 | 28 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Capital o fondo mutual (No exigido) [00414]
8 | 45 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Prima emisión [00415]
9 | 62 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Reservas [00416]
10 | 79 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - (Acciones en patrimonio propias) [00417]
11 | 96 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Resultados de ejercicios anteriores [00418]
12 | 113 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior -Otras aportaciones de socios o mutualistas [00419]
13 | 130 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Capital o fondo mutual escriturado [00426]
14 | 147 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Capital o fondo mutual (No exigido) [00427]
15 | 164 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Prima emisión [00428]
16 | 181 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Reservas [00429]
17 | 198 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - (Acciones en patrimonio propias) [00430]
18 | 215 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Resultados de ejercicios anteriores [00431]
19 | 232 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Otras aportaciones de socios o mutualistas [00432]
20 | 249 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores - Capital o fondo mutual escriturado [00439]
21 | 266 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores - Capital o fondo mutual (No exigido) [00440]
22 | 283 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  Prima emisión [00441]
23 | 300 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  Reservas [00442]
24 | 317 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  (Acciones en patrimonio propias) [00443]
25 | 334 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  Resultados de ejercicios anteriores [00444]
26 | 351 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  Otras aportaciones de socios o mutualistas [00445]
27 | 368 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Capital o fondo mutual escriturado [00452]
28 | 385 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Capital o fondo mutual (No exigido) [00453]
29 | 402 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Prima emisión [00454]
30 | 419 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Reservas [00455]
31 | 436 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - (Acciones en patrimonio propias) [00456]
32 | 453 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Resultados de ejercicios anteriores [00457]
33 | 470 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Otras aportaciones de socios o mutualistas [00458]
34 | 487 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Capital o fondo mutual escriturado [00465]
35 | 504 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Capital o fondo mutual (No exigido) [00466]
36 | 521 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Prima emisión [00467]
37 | 538 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Reservas [00468]
38 | 555 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - (Acciones en patrimonio propias) [00469]
39 | 572 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Resultados de ejercicios anteriores [00470]
40 | 589 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Otras aportaciones de socios o mutualistas [00471]
41 | 606 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Capital o fondo mutual escriturado [00478]
42 | 623 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Capital o fondo mutual (No exigido) [00479]
43 | 640 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Prima emisión [00480]
44 | 657 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reservas [00481]
45 | 674 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - (Acciones en patrimonio propias) [00482]
46 | 691 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Resultados de ejercicios anteriores [00483]
47 | 708 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Otras aportaciones de socios o mutualistas [00484]
48 | 725 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Capital o fondo mutual escriturado [00491]
49 | 742 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Capital o fondo mutual (No exigido) [00492]
50 | 759 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Prima emisión [00493]
51 | 776 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Reservas [00494]
52 | 793 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - (Acciones en patrimonio propias) [00495]
53 | 810 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Resultados de ejercicios anteriores [00496]
54 | 827 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Otras aportaciones de socios o mutualistas [00497]
55 | 844 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual -  Escriturado [00504]
56 | 861 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. (No exigido) [00505]
57 | 878 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. Prima emisión [00506]
58 | 895 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. Reservas [00507]
59 | 912 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. (Acciones en patrimonio propias) [00508]
60 | 929 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. Resultados de ejercicios anteriores [00509]
61 | 946 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. Otras aportaciones de socios o mutualistas [00510]
62 | 963 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Escriturado [00517]
63 | 980 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. (No exigido) [00518]
64 | 997 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Prima emisión [00519]
65 | 1014 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Reservas [00520]
66 | 1031 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. (Acciones en patrimonio propias) [00521]
67 | 1048 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Resultados de ejercicios anteriores [00522]
68 | 1065 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Otras aportaciones de socios o mutualistas [00523]
69 | 1082 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Escriturado [00530]
70 | 1099 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. (No exigido) [00531]
71 | 1116 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Prima emisión [00532]
72 | 1133 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Reservas [00533]
73 | 1150 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. (Acciones en patrimonio propias) [00534]
74 | 1167 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Resultados de ejercicios anteriores [00535]
75 | 1184 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Otras aportaciones de socios o mutualistas [00536]
76 | 1201 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). Escriturado [00543]
77 | 1218 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). (No exigido) [00544]
78 | 1235 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -  Operaciones con acciones o participaciones propias (netas). Prima emisión [00545]
79 | 1252 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). Reservas [00546]
80 | 1269 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). (Acciones en patrimonio propias) [00547]
81 | 1286 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). Resultados de ejercicios anteriores [00548]
82 | 1303 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). Otras aportaciones de socios o mutualistas [00549]
83 | 1320 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Escriturado [00556]
84 | 1337 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. (No exigido) [00557]
85 | 1354 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Prima emisión [00558]
86 | 1371 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Reservas [00559]
87 | 1388 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. (Acciones en patrimonio propias) [00560]
88 | 1405 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Resultados de ejercicios anteriores [00561]
89 | 1422 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Otras aportaciones de socios o mutualistas [00562]
90 | 1439 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Escriturado [00569]
91 | 1456 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. (No exigido) [00570]
92 | 1473 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Prima emisión [00571]
93 | 1490 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Reservas [00572]
94 | 1507 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. (Acciones en patrimonio propias) [00573]
95 | 1524 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Resultados de ejercicios anteriores [00574]
96 | 1541 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Otras aportaciones de socios o mutualistas [00575]
97 | 1558 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Escriturado [00582]
98 | 1575 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - (No exigido) [00583]
99 | 1592 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Prima emisión [00584]
100 | 1609 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Reservas [00585]
101 | 1626 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - (Acciones en patrimonio propias) [00586]
102 | 1643 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Resultados de ejercicios anteriores [0087]
103 | 1660 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras aportaciones de socios o mutualistas [00588]
104 | 1677 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Escriturado [00595]
105 | 1694 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - (No exigido) [00596]
106 | 1711 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Prima emisión [00597]
107 | 1728 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Reservas [00598]
108 | 1745 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - (Acciones en patrimonio propias) [00599]
109 | 1762 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Resultados de ejercicios anteriores [00600]
110 | 1779 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Otras aportaciones de socios o mutualistas [00601]
111 | 1796 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Escriturado [00608]
112 | 1813 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - (No exigido) [00609]
113 | 1830 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Prima emisión [00610]
114 | 1847 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Reservas [00611]
115 | 1864 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - (Acciones en patrimonio propias) [00612]
116 | 1881 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Resultados de ejercicios anteriores [00613]
117 | 1898 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Otras aportaciones de socios o mutualistas [00614]
118 | 1915 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Escriturado [00621]
119 | 1932 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - (No exigido) [00622]
120 | 1949 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Prima emisión [00623]
121 | 1966 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Reservas [00624]
122 | 1983 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - (Acciones en patrimonio propias) [00625]
123 | 2000 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Resultados de ejercicios anteriores [00626]
124 | 2017 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Otras aportaciones de socios o mutualistas [00627]
125 | 2034 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Escriturado [00634]
126 | 2051 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - (No exigido) [00635]
127 | 2068 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Prima emisión [00636]
128 | 2085 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Reservas [00637]
129 | 2102 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - (Acciones en patrimonio propias) [00638]
130 | 2119 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Resultados de ejercicios anteriores [00639]
131 | 2136 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Otras aportaciones de socios o mutualistas [00640]
132 | 2153 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200420>"
Total: |  | 2162

# DP200043

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "430"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Resultado del ejercicio [00420]
7 | 28 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - (Dividendo a cuenta) [00421]
8 | 45 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Otros instrumentos de patrimonio [00422]
9 | 62 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Ajustes por cambios de valor [00423]
10 | 79 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Subvenciones donaciones y legados recibidos [00424]
11 | 96 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Total [00425]
12 | 113 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Resultado del ejercicio [00433]
13 | 130 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - (Dividendo a cuenta) [00434]
14 | 147 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Otros instrumentos de patrimonio [00435]
15 | 164 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Ajustes por cambios de valor [00436]
16 | 181 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Subvenciones donaciones y legados recibidos [00437]
17 | 198 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Total [00438]
18 | 215 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Resultado del ejercicio [00446]
19 | 232 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - (Dividendo a cuenta) [00447]
20 | 249 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Otros instrumentos de patrimonio [00448]
21 | 266 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Ajustes por cambios de valor [00449]
22 | 283 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Subvenciones donaciones y legados recibidos [00450]
23 | 300 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Total [00451]
24 | 317 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Resultado del ejercicio [00459]
25 | 334 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - (Dividendo a cuenta) [00460]
26 | 351 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Otros instrumentos de patrimonio [00461]
27 | 368 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Ajustes por cambios de valor [00462]
28 | 385 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Subvenciones donaciones y legados recibidos [00463]
29 | 402 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Total [00464]
30 | 419 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Resultado del ejercicio [00472]
31 | 436 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - (Dividendo a cuenta) [00473]
32 | 453 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Otros instrumentos de patrimonio [00474]
33 | 470 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Ajustes por cambios de valor [00475]
34 | 487 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Subvenciones donaciones y legados recibidos [00476]
35 | 504 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Total [00477]
36 | 521 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Resultado del ejercicio [00485]
37 | 538 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (Dividendo a cuenta) [00486]
38 | 555 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otros instrumentos de patrimonio [00487]
39 | 572 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Ajustes por cambios de valor [00488]
40 | 589 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Subvenciones donaciones y legados recibidos [00489]
41 | 606 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Total [00490]
42 | 623 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Resultado del ejercicio [00498]
43 | 640 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - (Dividendo a cuenta) [00499]
44 | 657 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Otros instrumentos de patrimonio [00382]
45 | 674 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Ajustes por cambios de valor [00501]
46 | 691 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Subvenciones donaciones y legados recibidos [00502]
47 | 708 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Total [00503]
48 | 725 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Resultado del ejercicio [00511]
49 | 742 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  (Dividendo a cuenta) [00512]
50 | 759 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Otros instrumentos de patrimonio [00513]
51 | 776 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Ajustes por cambios de valor [00514]
52 | 793 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Subvenciones donaciones y legados [00515]
53 | 810 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Total [00516]
54 | 827 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Resultado del ejercicio [00524]
55 | 844 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - (Dividendo a cuenta) [00525]
56 | 861 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Otros instrumentos de patrimonio [00526]
57 | 878 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Ajustes por cambios de valor [00527]
58 | 895 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Subvenciones donaciones y legados [00528]
59 | 912 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Total [00529]
60 | 929 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Resultado del ejercicio [00537]
61 | 946 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - (Dividendo a cuenta) [00538]
62 | 963 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Otros instrumentos de patrimonio [00539]
63 | 980 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Ajustes por cambios de valor [00540]
64 | 997 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Subvenciones donaciones y legados [00541]
65 | 1014 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Total [00542]
66 | 1031 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Resultado del ejercicio [00550]
67 | 1048 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - (Dividendo a cuenta) [00551]
68 | 1065 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Otros instrumentos de patrimonio [00552]
69 | 1082 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Ajustes por cambios de valor [00553]
70 | 1099 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Subvenciones donaciones y legados [00554]
71 | 1116 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Total [00555]
72 | 1133 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Resultado del ejercicio [00563]
73 | 1150 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - (Dividendo a cuenta) [00564]
74 | 1167 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Otros instrumentos de patrimonio [00565]
75 | 1184 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Ajustes por cambios de valor [00566]
76 | 1201 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Subvenciones donaciones y legados [00567]
77 | 1218 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Total [00568]
78 | 1235 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Resultado del ejercicio [00576]
79 | 1252 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - (Dividendo a cuenta) [00577]
80 | 1269 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Otros instrumentos de patrimonio [00578]
81 | 1286 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Ajustes por cambios de valor [00579]
82 | 1303 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Subvenciones donaciones y legados [00580]
83 | 1320 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Total [00581]
84 | 1337 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Resultado del ejercicio [00589]
85 | 1354 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - (Dividendo a cuenta) [00590]
86 | 1371 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otros instrumentos de patrimonio [00591]
87 | 1388 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Ajustes por cambios de valor [00592]
88 | 1405 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Subvenciones donaciones y legados [00593]
89 | 1422 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Total [00594]
90 | 1439 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Resultado del ejercicio [00602]
91 | 1456 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - (Dividendo a cuenta) [00603]
92 | 1473 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos  basados en instrumentos de patrimonio - Otros instrumentos de patrimonio [00604]
93 | 1490 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Ajustes por cambios de valor [00605]
94 | 1507 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Subvenciones donaciones y legados [00606]
95 | 1524 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Total [00607]
96 | 1541 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Resultado del ejercicio [00615]
97 | 1558 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - (Dividendo a cuenta) [00616]
98 | 1575 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Otros instrumentos de patrimonio [00617]
99 | 1592 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Ajustes por cambios de valor [00618]
100 | 1609 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Subvenciones donaciones y legados [00619]
101 | 1626 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Total [00620]
102 | 1643 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Resultado del ejercicio [00628]
103 | 1660 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - (Dividendo a cuenta) [00629]
104 | 1677 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Otros instrumentos de patrimonio [00630]
105 | 1694 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Ajustes por cambios de valor [00631]
106 | 1711 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Subvenciones donaciones y legados [00632]
107 | 1728 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Total [00633]
108 | 1745 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Resultado del ejercicio [00641]
109 | 1762 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - (Dividendo a cuenta) [00642]
110 | 1779 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Otros instrumentos de patrimonio [00643]
111 | 1796 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Ajustes por cambios de valor [00644]
112 | 1813 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Subvenciones donaciones y legados [00645]
113 | 1830 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Total [00646]
114 | 1847 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200430>"
Total: |  | 1856

# DP200044

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "440"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Inst. inversión colectiva - Balance: Activo - Activo no corriente [00101]
7 | 28 | 17 | N | Inst. inversión colectiva - Balance: Activo - Inmovilizado intangible [00102]
8 | 45 | 17 | N | Inst. inversión colectiva - Balance: Activo - Inmovilizado material [00103]
9 | 62 | 17 | N | Inst. inversión colectiva - Balance: Activo - Inmovilizado material - Bienes muebles de uso propio [00104]
10 | 79 | 17 | N | Inst. inversión colectiva - Balance: Activo - Inmovilizado material - Mobiliario y enseres [00105]
11 | 96 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias [00106]
12 | 113 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos [00107]
13 | 130 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Inmuebles en fase de construcción [00108]
14 | 147 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Inmuebles terminados [00109]
15 | 164 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Concesiones administrativas [00110]
16 | 181 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Otros derechos reales [00111]
17 | 198 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Compromisos de compra de inmuebles [00112]
18 | 215 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Compra de opciones de compra de inmuebles [00113]
19 | 232 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Acciones en sociedades tenedoras y entidades de arrendamiento [00114]
20 | 249 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Opciones sobre la cartera de inversiones inmobiliarias [00115]
21 | 266 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Otros [00116]
22 | 283 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y derechos [00117]
23 | 300 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y derechos - Sociedades tenedoras de inmuebles [00118]
24 | 317 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y derechos - Otros [00119]
25 | 334 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Anticipos o entregas a cuenta [00120]
26 | 351 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias [00121]
27 | 368 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias - Inversiones adicionales, complementarias y rehabilitaciones en curso [00122]
28 | 385 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias - Indemnizaciones a arrendatarios [00123]
29 | 402 | 17 | N | Inst. inversión colectiva - Balance: Activo - Activos por impuesto diferido [00124]
30 | 419 | 17 | N | Inst. inversión colectiva - Balance: Activo - Activo corriente [00125]
31 | 436 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores [00126]
32 | 453 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Deudores por ventas de inmuebles [00127]
33 | 470 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Deudores por alquileres [00128]
34 | 487 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Deudores dudosos o morosos [00129]
35 | 504 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Deudores dudosos o morosos avalados o garantizados [00130]
36 | 521 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Otros deudores [00131]
37 | 538 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras [00132]
38 | 555 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior [00133]
39 | 572 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Valores representativos de deuda [00134]
40 | 589 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Instrumentos de patrimonio [00135]
41 | 606 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Instituciones de inversión colectiva [00136]
42 | 623 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Depósitos en EECC [00137]
43 | 640 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Derivados [00138]
44 | 657 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Otros [00139]
45 | 674 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior  [00140]
46 | 691 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Valores representativos de deuda [00141]
47 | 708 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Instrumentos de patrimonio [00142]
48 | 725 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Instituciones de inversión colectiva [00143]
49 | 742 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Depósitos en EECC [00144]
50 | 759 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Derivados [00145]
51 | 776 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Otros [00146]
52 | 793 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Intereses de la cartera de inversión [00147]
53 | 810 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Inversiones morosas, dudosas o en litigio [00148]
54 | 827 | 17 | N | Inst. inversión colectiva - Balance: Activo - Periodificaciones [00149]
55 | 844 | 17 | N | Inst. inversión colectiva - Balance: Activo - Tesorería [00150]
56 | 861 | 17 | N | Inst. inversión colectiva - Balance: Activo - TOTAL ACTIVO [00151]
57 | 878 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200440>"
Total: |  | 887

# DP200045

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "450"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Patrimonio atribuido a partícipes o accionistas [00152]
7 | 28 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas [00153]
8 | 45 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Capital [00154]
9 | 62 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Partícipes [00155]
10 | 79 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Prima de emisión [00156]
11 | 96 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Reservas [00157]
12 | 113 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Reservas revalorización (Ley16/2012, de 27 de diciembre) [00243]
13 | 130 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Reservas  capitalización [01001]
14 | 147 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Reservas nivelación [01002]
15 | 164 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Otras Reservas [00805]
16 | 181 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -(Acciones propias) [00158]
17 | 198 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Resultados de ejercicios anteriores [00159]
18 | 215 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Otras aportaciones de socios [00160]
19 | 232 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Resultado del ejercicio [00161]
20 | 249 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - (Dividendo a cuenta) [00162]
21 | 266 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios de valor en inmovilizado material de uso propio [00163]
22 | 283 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material [00164]
23 | 300 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material - Ajustes por plusvalías de invers. inmob. e inmovilizado material [00165]
24 | 317 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material - Ajustes por minusvalías de invers. inmob. e inmovil. material [00166]
25 | 334 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Otro patrimonio atribuido [00167]
26 | 351 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Pasivo no corriente [00168]
27 | 368 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Provisiones a largo plazo [00169]
28 | 385 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Deudas a largo plazo [00170]
29 | 402 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Pasivos por impuesto diferido [00171]
30 | 419 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Pasivo corriente [00172]
31 | 436 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Provisiones a corto plazo [00173]
32 | 453 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Deudas a corto plazo [00174]
33 | 470 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Acreedores [00175]
34 | 487 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Pasivos financieros [00176]
35 | 504 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Derivados [00177]
36 | 521 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Periodificaciones [00178]
37 | 538 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - TOTAL PATRIMONIO Y PASIVO [00179]
38 | 555 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de compromiso [00180]
39 | 572 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de compromiso - Compromisos por operaciones largas de derivados [00181]
40 | 589 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de compromiso - Compromisos por operaciones cortas de derivados [00182]
41 | 606 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Compromisos por compra de inmuebles [00183]
42 | 623 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Compromisos de venta de inmuebles [00184]
43 | 640 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Contratos de arras [00185]
44 | 657 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Derechos de compra de opciones de compra de inmuebles [00186]
45 | 674 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Importes pendientes de desembolsar por inmuebles en fase de construcción [00187]
46 | 691 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso -  Otras cuentas de riesgo y compromiso [00188]
47 | 708 | 17 | N | Inst. inversión colectiva - Cuentas de orden - TOTAL CUENTAS DE RIESGO Y COMPROMISO [00189]
48 | 725 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden [00190]
49 | 742 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Valores cedidos en préstamo por la IIC [00191]
50 | 759 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Valores aportados como garantía por la IIC [00192]
51 | 776 | 17 | N | Inst. inversión colectiva - Cuentas de orden -Otras cuentas de orden -  Valores recibidos en garantía por la IIC [00193]
52 | 793 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Capital nominal no suscrito ni en circulación (SICAV) [00194]
53 | 810 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Capital nominal no suscrito (SII) [00195]
54 | 827 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Avales recibidos [00196]
55 | 844 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Avales emitidos [00197]
56 | 861 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Indemnizaciones previstas pendientes de confirmar [00198]
57 | 878 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Pérdidas fiscales a compensar [00199]
58 | 895 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Otros [00200]
59 | 912 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Otras cuentas de orden [00201]
60 | 929 | 17 | N | Inst. inversión colectiva - Cuentas de orden - TOTAL OTRAS CUENTAS DE ORDEN [00202]
61 | 946 | 17 | N | Inst. inversión colectiva - Cuentas de orden - TOTAL CUENTAS DE ORDEN [00203]
62 | 963 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200450>"
Total: |  | 972

# DP200046

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "460"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Comisiones de descuento por suscripciones y /o reembolsos [00204]
7 | 28 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Comisiones retrocedidas [00205]
8 | 45 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Ingresos por alquiler [00206]
9 | 62 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Gastos de personal [00207]
10 | 79 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación [00208]
11 | 96 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Comisión de gestión [00209]
12 | 113 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Comisión depositario [00210]
13 | 130 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Otros [00212]
14 | 147 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultados por enajenaciones de inmovilizado [00213]
15 | 164 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias [00214]
16 | 181 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias - Incrementos de deterioro [00215]
17 | 198 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias - Reversión del deterioro [00216]
18 | 215 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. [00217]
19 | 232 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. - Resultados positivos [00218]
20 | 249 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. - Resultados negativos [00219]
21 | 266 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Compensaciones e indemnizaciones por deterioro o pérdida de invers. inmob. [00220]
22 | 283 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Amortización invers. inmob. e inmovilizado material [00221]
23 | 300 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Amortización inmovilizado material [00222]
24 | 317 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Excesos de provisiones [00223]
25 | 334 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultados por enajenaciones inmovilizado material [00224]
26 | 351 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado de explotación [00225]
27 | 368 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Ingresos financieros [00226]
28 | 385 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Gastos financieros [00227]
29 | 402 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros [00228]
30 | 419 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por operaciones cartera interior [00229]
31 | 436 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por operaciones cartera exterior [00230]
32 | 453 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por operaciones con derivados [00231]
33 | 470 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Otros [00232]
34 | 487 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Diferencias de cambio [00233]
35 | 504 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros [00234]
36 | 521 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Deterioros [00235]
37 | 538 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Resultados por operaciones cartera interior [00236]
38 | 555 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Resultados por operaciones cartera exterior [00237]
39 | 572 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Resultados por operaciones con derivados [00238]
40 | 589 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Otros [00239]
41 | 606 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado financiero [00240]
42 | 623 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado antes de impuesto [00241]
43 | 640 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Impuesto sobre beneficios [00242]
44 | 657 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - RESULTADO DEL EJERCICIO [00500]
45 | 674 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200460>"
Total: |  | 683

# DP200047

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "470"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Patrimonio inicial [00244]
7 | 28 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Saldo neto [00245]
8 | 45 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Suscripciones/puesta circ. Acciones [00246]
9 | 62 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Suscripciones/Aumentos capital [00247]
10 | 79 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Reembolsos/Recompra acciones [00248]
11 | 96 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Reembolsos/Reducciones capital [00249]
12 | 113 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Beneficios brutos distribuidos [00250]
13 | 130 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Rendimientos netos [00251]
14 | 147 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Rendimientos de gestión [00252]
15 | 164 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Alquileres [00253]
16 | 181 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Intereses [00254]
17 | 198 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Dividendos [00255]
18 | 215 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias [00256]
19 | 232 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Variación valor razonable invers. inmob. [00257]
20 | 249 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Resultados enajenaciones invers. inmob. [00258]
21 | 266 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Resultados contratos invers. inmob. rescindidos [00259]
22 | 283 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Otros derivados de las invers. inmob. [00260]
23 | 300 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Valores representativos de deuda [00261]
24 | 317 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Instrumentos de patrimonio [00262]
25 | 334 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Depósitos [00263]
26 | 351 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Instituciones inversión colectiva [00264]
27 | 368 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Derivados [00265]
28 | 385 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros valores [00266]
29 | 402 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Diferencias de cambio [00267]
30 | 419 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros rendimientos [00268]
31 | 436 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos repercutidos [00269]
32 | 453 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente [00270]
33 | 470 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión gestión sobre patrimonio [00271]
34 | 487 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión gestión sobre resultados [00272]
35 | 504 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión de depósito [00273]
36 | 521 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente [00274]
37 | 538 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Tasas por registros oficiales [00275]
38 | 555 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Admisión a cotización [00276]
39 | 572 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Difusión de valores liquidativos [00277]
40 | 589 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Otros gastos gestión corriente [00278]
41 | 606 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores [00279]
42 | 623 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Tasaciones [00280]
43 | 640 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Admón.fincas y gastos comunidad [00281]
44 | 657 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Reparación y conservación inmuebles [00282]
45 | 674 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Auditoría [00283]
46 | 691 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Servicios bancarios y similares [00284]
47 | 708 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Publicidad, propaganda y relaciones públicas [00285]
48 | 725 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Otros servicios [00286]
49 | 742 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Amortización de mobiliario y enseres [00287]
50 | 759 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Deterioros, excepto por invers. inmob. [00288]
51 | 776 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Deterioros [00289]
52 | 793 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Retenciones no recuperadas por invers. de cartera exterior [00290]
53 | 810 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Impuesto sobre beneficios [00291]
54 | 827 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gasto por compartimento [00292]
55 | 844 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros [00293]
56 | 861 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200470>"
Total: |  | 870

# DP200048

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "480"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Ingresos  [00294]
7 | 28 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones de descuento a favor de la Institución [00295]
8 | 45 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas [00296]
9 | 62 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - De intermediarios financieros [00297]
10 | 79 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - Por inversiones en otras IIC [00298]
11 | 96 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - Otras [00299]
12 | 113 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Ingreso compartimento por IB [00300]
13 | 130 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Otros [00301]
14 | 147 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Revalorización inmuebles uso propio y resultados por enajenación inmobilizado [00302]
15 | 164 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - PATRIMONIO FINAL [00303]
16 | 181 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200480>"
Total: |  | 190

# DP200049

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "490"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Tesorería  [00101]
7 | 28 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Deudores comerciales y otras cuentas a cobrar  [00102]
8 | 45 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Socios dudosos  [00103]
9 | 62 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Deudores varios  [00104]
10 | 79 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Otros créditos con las Administraciones Públicas  [00105]
11 | 96 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Socios por desembolsos exigidos  [00106]
12 | 113 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Activos por impuesto corriente  [00107]
13 | 130 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Resto de cuentas a cobrar [00108]
14 | 147 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inversiones financieras  [00109]
15 | 164 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Instrumentos de patrimonio  [00110]
16 | 181 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Valores representativos de deuda  [00111]
17 | 198 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Depósitos a plazo en entidades de crédito  [00112]
18 | 215 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Activos financieros híbridos  [00113]
19 | 232 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Derivados de cobertura  [00114]
20 | 249 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Resto de derivados [00115]
21 | 266 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inversiones en empresas del grupo y asociadas  [00116]
22 | 283 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Activos no corrientes mantenidos para la venta  [00117]
23 | 300 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inmovilizado material  [00118]
24 | 317 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Terrenos y construcciones  [00119]
25 | 334 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Instalaciones técnicas y otro inmovilizado material  [00120]
26 | 351 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inversiones inmobiliarias  [00121]
27 | 368 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inmovilizado intangible  [00122]
28 | 385 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Activos por impuesto diferido  [00123]
29 | 402 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Resto de activos  [00124]
30 | 419 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Periodificaciones  [00125]
31 | 436 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Otros activos  [00126]
32 | 453 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - TOTAL ACTIVO [00127]
33 | 470 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Acreedores comerciales y otras cuenta a pagar  [00129]
34 | 487 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Acreedores varios [00130]
35 | 504 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos por impuesto corriente [00131]
36 | 521 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Deudas [00132]
37 | 538 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Obligaciones [00133]
38 | 555 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Deudas con entidades de crédito [00134]
39 | 572 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Fianzas y depósitos recibidos  [00135]
40 | 589 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Sociedades de reafianzamiento [00136]
41 | 606 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Derivados de cobertura [00137]
42 | 623 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Resto de derivados [00138]
43 | 640 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Otras deudas [00139]
44 | 657 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos vinculados con activos no corrientes mantenidos para la venta  [00140]
45 | 674 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos por avales y garantías  [00141]
46 | 691 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Garantías financieras [00142]
47 | 708 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Resto de avales y garantías [00143]
48 | 725 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Provisiones [00144]
49 | 742 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Provisiones por avales y garantías [00145]
50 | 759 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Otras provisiones [00146]
51 | 776 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200490>"
Total: |  | 785

# DP200050

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "500"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Fondo de provisiones técnicas. Cobertura conjunto operaciones [00147]
7 | 28 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Pasivos por impuesto diferido [00148]
8 | 45 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Resto de pasivos [00149]
9 | 62 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Capital reembolsable a la vista [00150]
10 | 79 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - TOTAL PASIVO [00128]
11 | 96 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Fondos propios [00151]
12 | 113 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital [00152]
13 | 130 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito [00153]
14 | 147 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito - Socios protectores [00154]
15 | 164 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito - Socios partícipes [00155]
16 | 181 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Menos: capital no exigido [00156]
17 | 198 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Menos: capital reembolsable a la vista [00157]
18 | 215 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reservas [00158]
19 | 232 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reservas revalorización (Ley 16/2012, de 27 diciembre) [00194]
20 | 249 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reserva de capitalización [01001]
21 | 266 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reserva de nivelación [01002]
22 | 283 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Otras reservas [00805]
23 | 300 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Resultados de ejercicios anteriores [00159]
24 | 317 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Resultado del ejercicio [00160]
25 | 334 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Ajustes por cambio de valor [00161]
26 | 351 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Activos financieros disponibles para la venta [00162]
27 | 368 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Otros [00163]
28 | 385 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Fondo de provisiones técnicas. Aportaciones de terceros [00164]
29 | 402 | 17 | N | Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - TOTAL PASIVO Y PATRIMONIO NETO [00165]
30 | 419 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200500>"
Total: |  | 428

# DP200051

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "510"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Importe neto cifra de negocios [00166]
7 | 28 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos por avales y garantías  [00167]
8 | 45 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos por prestación de servicios [00168]
9 | 62 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Otros ingresos de explotación [00169]
10 | 79 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Gastos de personal [00170]
11 | 96 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Sueldos, salarios y asimilados [00171]
12 | 113 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Cargas sociales [00172]
13 | 130 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Provisiones [00173]
14 | 147 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Otros gastos de explotación [00174]
15 | 164 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Dotaciones a provisiones por avales y garantías (neto) [00175]
16 | 181 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Correciones de valor por deterioro de socios dudosos (neto) [00176]
17 | 198 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Dotaciones al fondo de provisiones técnicas. Cobertura del conjunto de operaciones (neto) 00[177]
18 | 215 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Fondo de provisiones técnicas. Aportaciones de terceros utilizadas [00178]
19 | 232 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Amortización del inmovilizado [00179]
20 | 249 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Deterioro y resultado por enajenaciones de inmovilizado [00180]
21 | 266 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Deterioro y resultado activos no corrientes en venta (neto) [00181]
22 | 283 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - RESULTADO DE EXPLOTACION [00182]
23 | 300 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos financieros [00183]
24 | 317 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - De participaciones en instrumentos de patrimonio [00184]
25 | 334 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - De valores negociables y otros instrumentos financieros [00185]
26 | 351 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Gastos financieros [00186]
27 | 368 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Variación de valor razonable en instrumentos financieros[00187]
28 | 385 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Diferencias de cambio [00188]
29 | 402 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Correcciones de valor por deterioro de instrumentos financieros[00189]
30 | 419 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado por enajenación de instrumentos financieros[00190]
31 | 436 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - RESULTADO FINANCIERO [00191]
32 | 453 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado antes de impuestos [00192]
33 | 470 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Impuestos sobre beneficios [00193]
34 | 487 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - RESULTADO DEL EJERCICIO [00500]
35 | 504 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200510>"
Total: |  | 513

# DP200052

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "520"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Resultado de la cuenta de pérdidas y ganancias [00500]
7 | 28 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Por ajustes por cambios de valor [00195]
8 | 45 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Activos financieros disponibles venta [00196]
9 | 62 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Otros [00197]
10 | 79 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Fondo provisiones técnicas. Aportaciones terceros [00198]
11 | 96 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Efecto impositivo [00199]
12 | 113 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Total ingresos gastos imputados directamente en el patrimonio neto  [00200]
13 | 130 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Por ajustes por cambio de valor  [00201]
14 | 147 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Activos financieros disponibles para venta  [00202]
15 | 164 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Otros [00203]
16 | 181 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Fondo provisiones técnicas. Aportaciones terceros [00204]
17 | 198 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Efecto impositivo [00205]
18 | 215 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Total transferencias cuenta pérdidas y ganacias  [00206]
19 | 232 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - TOTAL INGRESOS Y GASTOS RECONOCIDOS [00207]
20 | 249 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200520>"
Total: |  | 258

# DP200053

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "530"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital - Suscrito [00208]
7 | 28 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital - Menos: no exigido [00209]
8 | 45 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Saldo, final ejercicio anterior - Capital - Menos: reembolsable [00210]
9 | 62 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital - Reservas [00211]
10 | 79 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital - Resultados ejercicios anteriores [00212]
11 | 96 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Capital - Suscrito [00217]
12 | 113 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Capital - Menos: no exigido [00218]
13 | 130 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -  Ajustes por cambio de criterio - Capital - Menos: reembolsable [00219]
14 | 147 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Reservas [00220]
15 | 164 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Resultados ejercicios anteriores [00221]
16 | 181 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital -  Suscrito [00226]
17 | 198 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital -  Menos: no exigido [00227]
18 | 215 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital -  Menos: reembolsable [00228]
19 | 232 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Reservas [00229]
20 | 249 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Resultados ejercicios anteriores [00230]
21 | 266 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Capital - Suscrito [00235]
22 | 283 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Capital - Menos: no exigido [00236]
23 | 300 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Capital - Menos: reembolsable [00237]
24 | 317 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Reservas [00238]
25 | 334 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Resultados ejercicios anteriores [00239]
26 | 351 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Capital - Suscrito [00244]
27 | 368 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Capital - Menos: no exigido [00245]
28 | 385 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Capital - Menos: reembolsable [00246]
29 | 402 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Reservas [00247]
30 | 419 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Resultados ejercicios anteriores [00248]
31 | 436 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital - Suscrito [00253]
32 | 453 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital - Menos: no exigido [00254]
33 | 470 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital - Menos: reembolsable [00255]
34 | 487 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Reservas [00256]
35 | 504 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Resultados ejercicios anteriores [00257]
36 | 521 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Capital - Suscrito [00262]
37 | 538 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Capital - Menos: no exigido [00263]
38 | 555 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Capital - Menos: reembolsable [00264]
39 | 572 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Operaciones con socios -  Aumentos de capital - Reservas [00265]
40 | 589 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Resultados ejercicios anteriores [00266]
41 | 606 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Capital - Suscrito [00271]
42 | 623 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Capital - Menos: no exigido [00272]
43 | 640 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Capital - Menos: reembolsable [00273]
44 | 657 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Reservas [00274]
45 | 674 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Resultados ejercicios anteriores [00275]
46 | 691 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Capital - Suscrito [00280]
47 | 708 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Capital - Menos: no exigido [00281]
48 | 725 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Capital - Menos: reembolsable [00282]
49 | 742 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Reservas [00283]
50 | 759 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Resultados ejercicios anteriores [00284]
51 | 776 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Capital - Suscrito [00289]
52 | 793 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Capital - Menos: no exigido [00290]
53 | 810 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Capital - Menos: reembolsable [00291]
54 | 827 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Reservas [00292]
55 | 844 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Resultados ejercicios anteriores [00293]
56 | 861 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Capital - Suscrito [00298]
57 | 878 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Capital - Menos: no exigido [00299]
58 | 895 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Capital - Menos: reembolsable [00300]
59 | 912 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Reservas [00301]
60 | 929 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Resultados ejercicios anteriores [00302]
61 | 946 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital - Suscrito [00307]
62 | 963 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital - Menos: no exigido [00308]
63 | 980 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital - Menos: reembolsable [00309]
64 | 997 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Reservas [00310]
65 | 1014 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Resultados ejercicios anteriores [00311]
66 | 1031 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200530>"
Total: |  | 1040

# DP200054

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "540"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior - Resultado ejercicio [00213]
7 | 28 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior -  Ajustes cambio valor [00214]
8 | 45 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior - Fondos provisiones técnicas. Aportaciones de terceros [00215]
9 | 62 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior -  Total [00216]
10 | 79 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Resultado ejercicio [00222]
11 | 96 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Ajustes cambio valor [00223]
12 | 113 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -  Ajustes por cambio de criterio - Fondos provisiones técnicas. Aportaciones de terceros [00224]
13 | 130 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Total [00225]
14 | 147 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Resultado ejercicio [00231]
15 | 164 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Ajustes cambio valor [00232]
16 | 181 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -  Ajustes por errores - Fondos provisiones técnicas. Aportaciones de terceros [00233]
17 | 198 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Total [00234]
18 | 215 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Resultado ejercicio [00240]
19 | 232 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Ajustes cambio valor [00241]
20 | 249 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Fondos provisiones técnicas. Aportaciones de terceros [00242]
21 | 266 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Total [00243]
22 | 283 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Resultado ejercicio [00249]
23 | 300 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Ajustes cambio valor [00250]
24 | 317 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Fondos provisiones técnicas. Aportaciones de terceros [00251]
25 | 334 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Total ingresos/gastos reconocidos - Total [00252]
26 | 351 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Resultado ejercicio [00258]
27 | 368 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Ajustes cambio valor [00259]
28 | 385 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Fondos provisiones técnicas. Aportaciones de terceros [00260]
29 | 402 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Total [00261]
30 | 419 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Resultado ejercicio [00267]
31 | 436 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Ajustes cambio valor [00268]
32 | 453 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Fondos provisiones técnicas. Aportaciones de terceros [00269]
33 | 470 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Total [00270]
34 | 487 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Resultado ejercicio [00276]
35 | 504 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Ajustes cambio valor [00277]
36 | 521 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Fondos provisiones técnicas. Aportaciones de terceros [00278]
37 | 538 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Total [00279]
38 | 555 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Resultado ejercicio [00285]
39 | 572 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Ajustes cambio valor [00286]
40 | 589 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Fondos provisiones técnicas. Aportaciones de terceros [00287]
41 | 606 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Total [00288]
42 | 623 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Resultado ejercicio [00294]
43 | 640 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Ajustes cambio valor [00295]
44 | 657 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Fondos provisiones técnicas. Aportaciones de terceros [00296]
45 | 674 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Total [00297]
46 | 691 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Resultado ejercicio [00303]
47 | 708 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Ajustes cambio valor [00304]
48 | 725 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Fondos provisiones técnicas. Aportaciones de terceros [00305]
49 | 742 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Total [00306]
50 | 759 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Resultado ejercicio [00312]
51 | 776 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Ajustes cambio valor [00313]
52 | 793 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Fondos provisiones técnicas. Aportaciones de terceros [00314]
53 | 810 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Total [00315]
54 | 827 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200540>"
Total: |  | 836

# DP200DID

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.0 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2015
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 3 | An | Página. | OBLIGATORIO | Constante "DID"
4 | 9 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 10 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 11 | 1 | An | Cuenta corriente tributaria |  | "0" o "1"
7 | 12 | 4 | Num | Identificación - Ejercicio
8 | 16 | 1 | Num | Tipo de ejercicio
9 | 17 | 2 | An | Período Impositivo |  | "0A"
10 | 19 | 2 | Num | Período Impositivo inicio - Día
11 | 21 | 2 | Num | Período Impositivo inicio - Mes
12 | 23 | 2 | Num | Período Impositivo inicio - Año
13 | 25 | 2 | Num | Período Impositivo fin - Día
14 | 27 | 2 | Num | Período Impositivo fin - Mes
15 | 29 | 2 | Num | Período Impositivo fin - Año
16 | 31 | 9 | An | Identificación - NIF
17 | 40 | 40 | An | Identificación - Apellidos y nombre o Razón Social
18 | 80 | 17 | N | Liquidación - Base imponible [00552]
19 | 97 | 17 | N | Liquidación - Cuota íntegra [00562]
20 | 114 | 17 | N | Liquidación - Líquido a ingresar o a devolver Estado [00621]
21 | 131 | 17 | Num | RESERVADO AEAT
22 | 148 | 17 | Num | RESERVADO AEAT
23 | 165 | 17 | Num | RESERVADO AEAT
24 | 182 | 17 | Num | RESERVADO AEAT
25 | 199 | 1 | An | Devolución - Renuncia o por Transferencia |  | "blanco" "R","D"
26 | 200 | 17 | Num | Devolución - Importe a devolver
27 | 217 | 34 | An | Devolución - Número de cuenta IBAN
28 | 251 | 11 | An | Devolución - Código SWIFT-BIC
29 | 262 | 1 | An | Modalidad de ingreso. Uno de los siguientes valores |  | "blanco", "I" Adeudo en cuenta, "H" Efectivo, "U" Domiciliación
30 | 263 | 1 | An | RESERVADO AEAT
31 | 264 | 1 | An | RESERVADO AEAT
32 | 265 | 17 | Num | Ingreso - Importe a ingresar
33 | 282 | 34 | An | Número de cuenta IBAN
34 | 316 | 17 | N | Abono/Compensación -Abono por conversión de activos impuesto diferido - A
35 | 333 | 17 | N | Abono/Compensación -Compensación por conversión de activos impuesto diferido - C
36 | 350 | 1 | An | Cuota Cero |  | "0" o  "1"
37 | 351 | 10 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200DID>"
Total: |  | 360