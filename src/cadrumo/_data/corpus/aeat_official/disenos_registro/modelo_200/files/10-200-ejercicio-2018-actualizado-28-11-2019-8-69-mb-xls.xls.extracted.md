# DP200000

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 17 | An | Constante. <T + modelo + discriminante (*) + Ejercicio devengo + periodo + tipo + > |  | "<T200020180A0000>"
2 | 18 | 5 | An | Constante |  | "<AUX>"
3 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
4 | 93 | 4 | An | Versión del programa (**)
5 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos
6 | 101 | 9 | An | NIF Empresa Desarrollo (**)
7 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos
8 | 323 | 6 | An | Constante |  | "</AUX>"
12 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
13 | *** | 18 | An | Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > |  | "</T200020180A0000>"
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
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo y página. Constante ">". | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria. |  | En blanco
6 | 13 | 1 | An | Tipo de declaración (Ver Nota*)
7 | 14 | 9 | An | Identificación - NIF
8 | 23 | 80 | An | Identificación - Apellidos y nombre o Razón Social
9 | 103 | 4 | Num | Ejercicio
10 | 107 | 2 | An | Periodo |  | Constante 0A
11 | 109 | 4 | Num | Periodo Impositivo - Año inicio
12 | 113 | 2 | Num | Periodo Impositivo - Mes inicio
13 | 115 | 2 | Num | Periodo Impositivo - Día Inicio
14 | 117 | 4 | Num | Periodo Impositivo - Año final
15 | 121 | 2 | Num | Periodo Impositivo - Mes final
16 | 123 | 2 | Num | Periodo Impositivo - Día final
17 | 125 | 1 | Num | Identificación - Tipo de ejercicio
18 | 126 | 4 | Num | Identificación - C.N.A.E.  Actividad principal
19 | 130 | 9 | An | Identificación - Teléfono 1
20 | 139 | 9 | An | Identificación - Teléfono 2
21 | 148 | 1 | Num | Entidad sin ánimo de lucro acogida régimen fiscal Título II Ley 49/2002 [00001]
22 | 149 | 1 | Num | Entidad parcialmente exenta [00002]
23 | 150 | 1 | Num | Sociedad de inversión de capital variable o fondo de inversión de carácter financiero [00003]
24 | 151 | 1 | Num | Sociedad de inversión inmobiliaria o fondo de inversión inmobiliaria [00004]
25 | 152 | 1 | Num | Comunidades titulares de montes vecinales en mano común [00005]
26 | 153 | 1 | Num | Entidad de tenencia de valores extranjeros [00011]
27 | 154 | 1 | Num | Agrupación de interés económico española o U.T.E. [00013]
28 | 155 | 1 | Num | Agrupación europea de  interés económico [00014]
29 | 156 | 1 | Num | Cooperativa protegida [00017]
30 | 157 | 1 | Num | Cooperativa especialmente protegida [00018]
31 | 158 | 1 | Num | Resto cooperativas [00019]
32 | 159 | 1 | Num | Establecimiento permanente [00021]
33 | 160 | 1 | Num | Gran empresa [00023]
34 | 161 | 1 | Num | Entidad de crédito [00024]
35 | 162 | 1 | Num | Entidad aseguradora [00025]
36 | 163 | 1 | Num | Entidades de capital-riesgo [00031]
37 | 164 | 1 | Num | Sociedades desarrollo industrial regional [00032]
38 | 165 | 1 | Num | Sociedad de garantía recíproca o de reafianzamiento [00036]
39 | 166 | 1 | Num | Fondo de Pensiones Real Decreto Legislativo 1/2002 de 29 de noviembre [00048]
40 | 167 | 1 | Num | Mutua de seguros o Mutualidad de previsión social [00058]
41 | 168 | 1 | Num | Fondos o activos de titulización [00060]
42 | 169 | 1 | Num | Entidad patrimonial [00066]
43 | 170 | 1 | Num | Incentivos entidad de reducida dimensión ( cap XI, tít. VII LIS )  [00006]
44 | 171 | 1 | Num | Entidad ZEC [00015]
45 | 172 | 1 | Num | Régimen entidades navieras en función del tonelaje [00022]
46 | 173 | 1 | Num | Tributación conjunta Estado/Diput.Cdad.Forales [00028]
47 | 174 | 1 | Num | Entidades sometidas a normativa foral [00047]
48 | 175 | 1 | Num | Aplicación rég.especial fusiones, escisiones, aportaciones activos y canjes valores (Cap.VII, Tit. VII)  [00035]
49 | 176 | 1 | Num | Regímenes especiales de normativa foral [00049]
50 | 177 | 1 | Num | Régimen especial Canarias [00029]
51 | 178 | 1 | Num | Régimen especial minería [00033]
52 | 179 | 1 | Num | Régimen especial hidrocarburos [00034]
53 | 180 | 1 | Num | Entidad dedicada al arrend. viviendas [00038]
54 | 181 | 1 | Num | Entidad en rég. Atribuc. de rentas constituida en el extranjero con presencia en territorio español [00046]
55 | 182 | 1 | Num | SOCIMI [00012]
56 | 183 | 1 | Num | Régimen fiscal entrada SOCIMI [00064]
57 | 184 | 1 | Num | Régimen fiscal salida SOCIMI [00057]
58 | 185 | 1 | Num | Otros regímenes especiales [00020]
59 | 186 | 1 | Num | Reg.fiscal de operac.de aportación de activos a sdades. para la gestion de activos (ley 8/2012)  [00062]
60 | 187 | 1 | Num | Imputación en base imponible rentas positivas art. 100 LIS   [00007]
61 | 188 | 1 | Num | Entidad dominante de grupo fiscal [00009]
62 | 189 | 1 | Num | Entidad dependiente de grupo fiscal [00010]
63 | 190 | 1 | Num | Opción  art. 46.2  LIS  [00016]
64 | 191 | 1 | Num | Entidad  inactiva  [00026]
65 | 192 | 1 | Num | Base imponible negativa o cero [00027]
66 | 193 | 1 | Num | Transmisión elementos patrimoniales arts. 27.2.d) y 77.1 L.I.S. [00030]
67 | 194 | 1 | Num | Entidad que forma parte de un grupo mercantil (art. 42 del Cód. Comercio) [00039]
68 | 195 | 1 | Num | Obligación información DT 5ª RIS [00043]
69 | 196 | 1 | Num | Inversiones anticipadas - reserva inversiones en Canarias (art. 27.11 Ley 19/1994) [00045]
70 | 197 | 1 | Num | Tipo de gravamen reducido para entidades de nueva creción  (DT 22ª LIS) [00063]
71 | 198 | 1 | Num | Tipo gravamen reducido para entidades de nueva creación (art. 29.1 LIS)  [00071]
72 | 199 | 1 | Num | Compensación bases imponibles negativas para entidades de nueva creación (art. 26.3 LIS) [00070]
73 | 200 | 1 | Num | Opción  art. 39.2 y 39.3 LIS  [00059]
74 | 201 | 1 | Num | Bonificación personal investigador (RD 475/2014) [00065]
75 | 202 | 1 | Num | Opción régimen transitorio reducción de ingresos procedentes determinados activos intangibles [00067]
76 | 203 | 1 | Num | Extinción de entidad [00072]
77 | 204 | 1 | Num | Opción del 0,7% de la cuota íntegra para fines sociales (DA 103ª Ley 6/2018) [00073]
78 | 205 | 1 | Num | Balance 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
79 | 206 | 1 | Num | ECPN 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
80 | 207 | 1 | Num | Pérdidas y ganancias 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
81 | 208 | 1 | Num | Entidades que sin ser Instituciones de inversión colectiva utilicen los estados de cuentas aplicables a éstas [00061]
82 | 209 | 7 | An | Nº de grupo fiscal al que pertenecen las entidades  que hayan marcado las claves 00009 ó 00010  [00040] |  | Relleno a ceros por la izda.
83 | 216 | 9 | An | N.I.F. de la sociedad representante/dominante (incluida en el grupo fiscal)
84 | 225 | 15 | An | Nº identificación de la sociedad dominante (en el caso de grupos constituidos solo por entidades depend.)
85 | 240 | 9 | Num | Personal asalariado (cifra media del ejercicio) Personal fijo [00041] |  | 7enteros 2 decimales
86 | 249 | 9 | Num | Personal asalariado (cifra media del ejercicio) Personal no fijo [00042] |  | 7enteros 2 decimales
87 | 258 | 1 | Num | Declaración complementaria
88 | 259 | 13 | Num | Nº de justificante de la declaración anterior
89 | 272 | 21 | An | D. - Nombre o Razón social - Secretario del Consejo de Administración
90 | 293 | 9 | An | N.I.F. - Secretario del Consejo de Administración
91 | 302 | 8 | Num | Fecha - Contribuyentes por el I.R.N.R. |  | AAAAMMDD
92 | 310 | 36 | An | Declaración representantes legales entidad - 1 - Nombre y apellidos
93 | 346 | 9 | An | Declaración representantes legales entidad - 1 - N.I.F
94 | 355 | 8 | Num | Declaración representantes legales entidad - 1 - Fecha Poder |  | AAAAMMDD
95 | 363 | 12 | An | Declaración representantes legales entidad - 1 - Notaría
96 | 375 | 36 | An | Declaración representantes legales entidad - 2 - Nombre y apellidos
97 | 411 | 9 | An | Declaración representantes legales entidad - 2 - N.I.F
98 | 420 | 8 | Num | Declaración representantes legales entidad - 2 - Fecha Poder |  | AAAAMMDD
99 | 428 | 12 | An | Declaración representantes legales entidad - 2 - Notaría
100 | 440 | 36 | An | Declaración representantes legales entidad - 3 - Nombre y apellidos
101 | 476 | 9 | An | Declaración representantes legales entidad - 3 - N.I.F
102 | 485 | 8 | Num | Declaración representantes legales entidad - 3 - Fecha Poder |  | AAAAMMDD
103 | 493 | 12 | An | Declaración representantes legales entidad - 3 - Notaría
104 | 505 | 21 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia
105 | 526 | 20 | An | Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
106 | 546 | 50 | An | Nombre y Apellidos de la persona de contacto para incidencias
107 | 596 | 9 | Num | Teléfono fijo de contacto para incidencias
108 | 605 | 9 | Num | Teléfono móvil de contacto para incidencias
109 | 614 | 50 | An | Dirección de correo electrónico para incidencias
110 | 664 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
111 | 677 | 1 | An | Entidad ZEC que pertenece a grupo fiscal |  | Nota 1
112 | 678 | 1 | An | Modelo de estados contables que se va a cumplimentar |  | Nota 2
113 | 679 | 1 | An | SOCIMIS: Régimen fiscal de entrada-salida. Renta derivada de la transmisión de inmuebles poseídos con anterioridad a la aplicación de este régimen y otras transmisiones de participaciones y activos a las que se aplica un tipo impositivo distinto del general (Art. 12.1 c, Art. 12.1 y Art 12.2) |  | "0" o "1"
114 | 680 | 197 | An | RESERVADO PARA LA AEAT
115 | 877 | 12 | An | Identificador de fin de Registro. | OBLIGATORIO | </T20001000>
Total: |  | 888
NOTA: Los importes son de 15 enteros (o N + 14) y 2 decimales
NOTA* |  |  | El Tipo de declaración puede ser:
 |  |  |  | I (Ingreso), U (Domiciliación),  N (Negativa/Resultado cero), D (Solicitud de devolución) R (Renuncia a la devolución)
 |  |  |  | G (anotación de ingreso en CCT) V (anotación de devolución en CCT) X (Devolución por transferencia al extranjero)
Nota 1
 | No es entidad ZEC
1 | Es entidad ZEC y pertenece a grupo fiscal
2 | Es entidad ZEC y no pertenece a grupo fiscal
Nota 2: Cuando coincidan los caracteres 00003, 00004 o 00061 con los caracteres 00024, 00025 o 00036
 | No es aplicable
1 | Estados contables de entidades de crédito (00024)
2 | Estados contables de entidades aseguradoras (00025)
3 | Estados contables de sociedad de garantía recíproca (00036)
4 | Estados contables de IIC

# DP200002

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. |  | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. |  | Constante "200"
3 | 6 | 5 | An | C | Página. |  | Constante "02000"
4 | 11 | 1 | An | C | Fin de identificador de modelo y página. |  | Constante ">"
5 | 12 | 1 | An | C | Indicador de página complementaria. |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 13 | 9 | An | C | A. Relación de administradores .1 - N.I.F.
7 | 22 | 1 | A | C | A. Relación de administradores. 1 - F/J |  | "F" o "J"
8 | 23 | 1 | Num | C | A. Relación de administradores. 1 - RPTE. |  | ( "0", "1")
9 | 24 | 40 | An | C | A. Relación de administradores. 1 - Apellidos y nombre / Razón social
10 | 64 | 17 | An | C | A. Relación de administradores. 1 - Domicilio fiscal
11 | 81 | 2 | An | C | A. Relación de administradores .1 - Código Provincial
12 | 83 | 9 | An | C | A. Relación de administradores. 2 - N.I.F.
13 | 92 | 1 | A | C | A. Relación de administradores. 2 - F/J |  | "F" o "J"
14 | 93 | 1 | Num | C | A. Relación de administradores. 2 - RPTE. |  | ( "0", "1")
15 | 94 | 40 | An | C | A. Relación de administradores. 2 - Apellidos y nombre / Razón social
16 | 134 | 17 | An | C | A. Relación de administradores. 2 - Domicilio fiscal
17 | 151 | 2 | An | C | A. Relación de administradores. 2 - Código Provincial
18 | 153 | 9 | An | C | A. Relación de administradores. 3 - N.I.F.
19 | 162 | 1 | A | C | A. Relación de administradores. 3 - F/J |  | "F" o "J"
20 | 163 | 1 | Num | C | A. Relación de administradores. 3 - RPTE. |  | ( "0", "1")
21 | 164 | 40 | An | C | A. Relación de administradores. 3 - Apellidos y nombre / Razón social
22 | 204 | 17 | An | C | A. Relación de administradores. 3 - Domicilio fiscal
23 | 221 | 2 | An | C | A. Relación de administradores. 3 - Código Provincial
24 | 223 | 9 | An | C | A. Relación de administradores. 4 - N.I.F.
25 | 232 | 1 | A | C | A. Relación de administradores. 4 - F/J |  | "F" o "J"
26 | 233 | 1 | Num | C | A. Relación de administradores. 4 - RPTE. |  | ( "0", "1")
27 | 234 | 40 | An | C | A. Relación de administradores. 4 - Apellidos y nombre / Razón social
28 | 274 | 17 | An | C | A. Relación de administradores. 4 - Domicilio fiscal
29 | 291 | 2 | An | C | A. Relación de administradores. 4 - Código Provincial
30 | 293 | 9 | An | C | A. Relación de administradores. 5 - N.I.F.
31 | 302 | 1 | A | C | A. Relación de administradores. 5 - F/J |  | "F" o "J"
32 | 303 | 1 | Num | C | A. Relación de administradores. 5 - RPTE. |  | ( "0", "1")
33 | 304 | 40 | An | C | A. Relación de administradores. 5 -  Apellidos y nombre / Razón social
34 | 344 | 17 | An | C | A. Relación de administradores. 5 - Domicilio fiscal
35 | 361 | 2 | An | C | A. Relación de administradores. 5 - Código Provincial
36 | 363 | 9 | An | C | A. Relación de administradores. 6 - N.I.F.
37 | 372 | 1 | A | C | A. Relación de administradores. 6 - F/J |  | "F" o "J"
38 | 373 | 1 | Num | C | A. Relación de administradores. 6 - RPTE. |  | ( "0", "1")
39 | 374 | 40 | An | C | A. Relación de administradores. 6 - Apellidos y nombre / Razón social
40 | 414 | 17 | An | C | A. Relación de administradores. 6 - Domicilio fiscal
41 | 431 | 2 | An | C | A. Relación de administradores. 6 - Código Provincial
42 | 433 | 15 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada - N.I.F.
43 | 448 | 30 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada - Nombre o razón social
44 | 478 | 2 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada - Código provincia / país
45 | 480 | 5 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la declarante - Porcentaje de participación
46 | 485 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la declarante - Valor nominal total de la participación
47 | 502 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
48 | 519 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
49 | 536 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - a) Corrección de valor pérdidas y ganancias ejercicio
50 | 553 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - b) Reversión de pérdidas por deterioro de valores (D.T. 16ªLIS)
51 | 570 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - c) Eliminación del deterioro contable incluido en P y G (art.13.2b) LIS)
52 | 587 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - d) Pérdidas por deterioro de valores repr. de partic. en el capital o fondos propios (art. 15 k) LIS)
53 | 604 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - e) Disminución de valor originada por criterio de valor razonable (art. 15 l) LIS)
54 | 621 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - f) Efecto corrección valorativa en la BI del ejercicio
55 | 638 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones valorativas - g) Saldo de correcciones fiscales (art. 12.3 RDL 4/2004) pendientes a fin de ejercicio
56 | 655 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales participada - Capital
57 | 672 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales participada - Reservas y otras partidas de fondos propios
58 | 689 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales participada - Otras partidas del patrimonio neto
59 | 706 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales participada - Resultado del último ejercicio
60 | 723 | 15 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada - N.I.F.
61 | 738 | 30 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada - Nombre o razón social
62 | 768 | 2 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada - Código provincia / país
63 | 770 | 5 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la declarante - Porcentaje de participación
64 | 775 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la declarante - Valor nominal total de la participación
65 | 792 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
66 | 809 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
67 | 826 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - a) Corrección de valor pérdidas y ganancias ejercicio
68 | 843 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - b) Reversión de pérdidas por deterioro de valores (D.T. 16ªLIS)
69 | 860 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - c) Eliminación del deterioro contable incluido en P y G (art.13.2b) LIS)
70 | 877 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - d) Pérdidas por deterioro de valores repr. de partic. en el capital o fondos propios (art. 15 k) LIS)
71 | 894 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - e) Disminución de valor originada por criterio de valor razonable (art. 15 l) LIS)
72 | 911 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - f) Efecto corrección valorativa en la BI del ejercicio
73 | 928 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones valorativas - g) Saldo de correcciones fiscales (art. 12.3 RDL 4/2004) pendientes a fin de ejercicio
74 | 945 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales participada - Capital
75 | 962 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales participada - Reservas y otras partidas de fondos propios
76 | 979 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales participada - Otras partidas del patrimonio neto
77 | 996 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales participada - Resultado del último ejercicio
78 | 1013 | 15 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada - N.I.F.
79 | 1028 | 30 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada - Nombre o razón social
80 | 1058 | 2 | An | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada - Código provincia / país
81 | 1060 | 5 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la declarante - Porcentaje de participación
82 | 1065 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la declarante - Valor nominal total de la participación
83 | 1082 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
84 | 1099 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
85 | 1116 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - a) Corrección de valor pérdidas y ganancias ejercicio
86 | 1133 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - b) Reversión de pérdidas por deterioro de valores (D.T. 16ªLIS)
87 | 1150 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - c) Eliminación del deterioro contable incluido en P y G (art.13.2b) LIS)
88 | 1167 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - d) Pérdidas por deterioro de valores repr. de partic. en el capital o fondos propios (art. 15 k) LIS)
89 | 1184 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - e) Disminución de valor originada por criterio de valor razonable (art. 15 l) LIS)
90 | 1201 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - f) Efecto corrección valorativa en la BI del ejercicio
91 | 1218 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones valorativas - g) Saldo de correcciones fiscales (art. 12.3 RDL 4/2004) pendientes a fin de ejercicio
92 | 1235 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales participada - Capital
93 | 1252 | 17 | Num | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales participada - Reservas y otras partidas de fondos propios
94 | 1269 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales participada - Otras partidas del patrimonio neto
95 | 1286 | 17 | N | C | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales participada - Resultado del último ejercicio
96 | 1303 | 17 | Num |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Datos de la declarante - Valor nominal total de la participación [1501]
97 | 1320 | 17 | Num |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación [1502]
98 | 1337 | 17 | Num |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado [1503]
99 | 1354 | 17 | N |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Correcciones valorativas - a) Corrección de valor pérdidas y ganancias ejercicio [1504]
100 | 1371 | 17 | N |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Correcciones valorativas - b) Reversión de pérdidas por deterioro de valores (D.T. 16ªLIS) [1505]
101 | 1388 | 17 | N |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Correcciones valorativas - c) Eliminación del deterioro contable incluido en P y G (art.13.2b) LIS) [1506]
102 | 1405 | 17 | N |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Correcciones valorativas - d) Pérdidas por deterioro de valores repr. de partic. en el capital o fondos propios (art. 15 k) LIS) [1809]
103 | 1422 | 17 | N |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Correcciones valorativas - e) Disminución de valor originada por criterio de valor razonable (art. 15 l) LIS) [1810]
104 | 1439 | 17 | N |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Correcciones valorativas - f) Efecto corrección valorativa en la BI del ejercicio [1507]
105 | 1456 | 17 | N |  | B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Total - Correcciones valorativas - g) Saldo de correcciones fiscales (art. 12.3 RDL 4/2004) pendientes a fin de ejercicio [1508]
106 | 1473 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - N.I.F.
107 | 1488 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - RPTE. |  | ( "0", "1")
108 | 1489 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - F/J/Otra |  | "F", "J" o "O"
109 | 1490 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Apellidos y nombre / Razón social
110 | 1527 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Código provincia / país
111 | 1529 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Nominal
112 | 1546 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - % Particip.
113 | 1551 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - N.I.F.
114 | 1566 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - RPTE. |  | ( "0", "1")
115 | 1567 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - F/J/Otra |  | "F", "J" o "O"
116 | 1568 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Apellidos y nombre / Razón social
117 | 1605 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Código provincia / país
118 | 1607 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Nominal
119 | 1624 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - % Particip.
120 | 1629 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - N.I.F.
121 | 1644 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - RPTE. |  | ( "0", "1")
122 | 1645 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - F/J/Otra |  | "F", "J" o "O"
123 | 1646 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - Apellidos y nombre / Razón social
124 | 1683 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - Código provincia / país
125 | 1685 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - Nominal
126 | 1702 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - % Particip.
127 | 1707 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - N.I.F.
128 | 1722 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - RPTE. |  | ( "0", "1")
129 | 1723 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - F/J/Otra |  | "F", "J" o "O"
130 | 1724 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - Apellidos y nombre / Razón social
131 | 1761 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - Código provincia / país
132 | 1763 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - Nominal
133 | 1780 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - % Particip.
134 | 1785 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - N.I.F.
135 | 1800 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - RPTE. |  | ( "0", "1")
136 | 1801 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - F/J/Otra |  | "F", "J" o "O"
137 | 1802 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Apellidos y nombre / Razón social.
138 | 1839 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Código provincia / país
139 | 1841 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Nominal
140 | 1858 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - % Particip.
141 | 1863 | 15 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - N.I.F.
142 | 1878 | 1 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - RPTE. |  | ( "0", "1")
143 | 1879 | 1 | A | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - F/J/Otra |  | "F", "J" o "O"
144 | 1880 | 37 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Apellidos y nombre / Razón social
145 | 1917 | 2 | An | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Código provincia / país
146 | 1919 | 17 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Nominal
147 | 1936 | 5 | Num | C | B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - % Particip.
148 | 1941 | 5 | Num |  | B .Participaciones directas - B.2. Suma de  porcentajes de participación de personas o entidades en el capital de la  declarante inferiores al 5% o al 1% si se trata de valores que coticen en un mercado secundario organizado
149 | 1946 | 5 | Num |  | B. Participaciones directas - B.2. Suma de porcentajes de participaciones en situaciones especiales
150 | 1951 | 200 | An | C | RESERVADO PARA LA AEAT
151 | 2151 | 12 | An | C | Identificador de fin de Registro. | OBLIGATORIO | </T20002000>
Total: |  | 2162

# DP200003

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "03000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Balance: Activo (I) - Activo - ACTIVO NO CORRIENTE [00101]
7 | 30 | 17 | N | Balance: Activo (I) - Activo - Inmovilizado intangible  [00102]
8 | 47 | 17 | N | Balance: Activo (I) - Activo - Desarrollo  [00103]
9 | 64 | 17 | N | Balance: Activo (I) - Activo - Concesiones  [00104]
10 | 81 | 17 | N | Balance: Activo (I) - Activo - Patentes, licencias, marcas y similares  [00105]
11 | 98 | 17 | N | Balance: Activo (I) - Activo - Fondo de comercio  [00106]
12 | 115 | 17 | N | Balance: Activo (I) - Activo - Aplicaciones informáticas  [00107]
13 | 132 | 17 | N | Balance: Activo (I) - Activo - Investigación  [00108]
14 | 149 | 17 | N | Balance: Activo (I) - Activo - Propiedad intelectual  [00700]
15 | 166 | 17 | N | Balance: Activo (I) - Activo - Otro inmovilizado intangible  [00109]
16 | 183 | 17 | N | Balance: Activo (I) - Activo - Resto  [00110]
17 | 200 | 17 | N | Balance: Activo (I) - Activo - Inmovilizado material  [00111]
18 | 217 | 17 | N | Balance: Activo (I) - Activo - Terrenos y construcciones  [00112]
19 | 234 | 17 | N | Balance: Activo (I) - Activo - Instalaciones técnicas y otro inmovilizado material  [00113]
20 | 251 | 17 | N | Balance: Activo (I) - Activo - Inmovilizado en curso y anticipos [00114]
21 | 268 | 17 | N | Balance: Activo (I) - Activo - Inversiones inmobiliarias [00115]
22 | 285 | 17 | N | Balance: Activo (I) - Activo - Terrenos [00116]
23 | 302 | 17 | N | Balance: Activo (I) - Activo - Construcciones [00117]
24 | 319 | 17 | N | Balance: Activo (I) - Activo - Inversiones en empresas del grupo y asociadas a largo plazo  [00118]
25 | 336 | 17 | N | Balance: Activo (I) - Activo - Instrumentos de patrimonio [00119]
26 | 353 | 17 | N | Balance: Activo (I) - Activo - Créditos a empresas [00120]
27 | 370 | 17 | N | Balance: Activo (I) - Activo - Valores representativos de deuda [00121]
28 | 387 | 17 | N | Balance: Activo (I) - Activo - Derivados [00122]
29 | 404 | 17 | N | Balance: Activo (I) - Activo - Otros activos financieros [00123]
30 | 421 | 17 | N | Balance: Activo (I) - Activo - Otras inversiones [00124]
31 | 438 | 17 | N | Balance: Activo (I) - Activo - Resto [00125]
32 | 455 | 17 | N | Balance: Activo (I) - Activo - Inversiones financieras a largo plazo [00126]
33 | 472 | 17 | N | Balance: Activo (I) - Activo - Instrumentos de patrimonio [00127]
34 | 489 | 17 | N | Balance: Activo (I) - Activo - Créditos a terceros [00128]
35 | 506 | 17 | N | Balance: Activo (I) - Activo - Valores representativos de deuda [00129]
36 | 523 | 17 | N | Balance: Activo (I) - Activo - Derivados [00130]
37 | 540 | 17 | N | Balance: Activo (I) - Activo - Otros activos financieros [00131]
38 | 557 | 17 | N | Balance: Activo (I) - Activo - Otras inversiones [00132]
39 | 574 | 17 | N | Balance: Activo (I) - Activo - Resto [00133]
40 | 591 | 17 | N | Balance: Activo (I) - Activo - Activos por impuesto diferido [00134]
41 | 608 | 17 | N | Balance: Activo (I) - Activo - Deudores comerciales no corrientes [00135]
42 | 625 | 17 | N | Balance: Activo (I) - Activo - ACTIVO CORRIENTE [00136]
43 | 642 | 17 | N | Balance: Activo (I) - Activo - Activos no corrientes mantenidos para la venta [00137]
44 | 659 | 17 | N | Balance: Activo (I) - Activo - Existencias [00138]
45 | 676 | 17 | N | Balance: Activo (I) - Activo - Comerciales  [00139]
46 | 693 | 17 | N | Balance: Activo (I) - Activo - Materias primas y otros aprovisionamientos [00140]
47 | 710 | 17 | N | Balance: Activo (I) - Activo - Productos en curso [00141]
48 | 727 | 17 | N | Balance: Activo (I) - Activo - Productos en curso - De ciclo largo de producción  [00142]
49 | 744 | 17 | N | Balance: Activo (I) - Activo - Productos en curso - De ciclo corto de producción  [00143]
50 | 761 | 17 | N | Balance: Activo (I) - Activo - Productos terminados [00144]
51 | 778 | 17 | N | Balance: Activo (I) - Activo - Productos terminados - De ciclo largo de producción  [00145]
52 | 795 | 17 | N | Balance: Activo (I) - Activo - Productos terminados - De ciclo corto de producción  [00146]
53 | 812 | 17 | N | Balance: Activo (I) - Activo - Subproductos, residuos y materiales recuperados [00147]
54 | 829 | 17 | N | Balance: Activo (I) - Activo - Anticipos a proveedores [00148]
55 | 846 | 17 | N | Balance: Activo (I) - Activo - Derechos de emisión de gases de efecto invernadero [00701]
56 | 863 | 200 | An | RESERVADO PARA LA AEAT
57 | 1063 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante </T20003000>
Total: |  | 1074

# DP200004

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. Constante "<T" . | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "04000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria. En blanco |  | En blanco
6 | 13 | 17 | N | Balance: Activo (II) - Activo - Deudores comerciales y otras cuentas a cobrar [00149]
7 | 30 | 17 | N | Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios [00150]
8 | 47 | 17 | N | Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios - Clientes por ventas y prestaciones de servicios a largo plazo [00151]
9 | 64 | 17 | N | Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios - Clientes por ventas y prestaciones de servicios a corto plazo [00152]
10 | 81 | 17 | N | Balance: Activo (II) - Activo - Clientes empresas del grupo y asociadas [00153]
11 | 98 | 17 | N | Balance: Activo (II) - Activo - Deudores varios [00154]
12 | 115 | 17 | N | Balance: Activo (II) - Activo - Personal [00155]
13 | 132 | 17 | N | Balance: Activo (II) - Activo - Activos por impuesto corriente [00156]
14 | 149 | 17 | N | Balance: Activo (II) - Activo - Otros créditos con las Administraciones Públicas [00157]
15 | 166 | 17 | N | Balance: Activo (II) - Activo - Accionistas (socios) por desembolsos exigidos [00158]
16 | 183 | 17 | N | Balance: Activo (II) - Activo - Otros deudores [00159]
17 | 200 | 17 | N | Balance: Activo (II) - Activo - Inversiones en empresas del grupo y asociadas a corto plazo [00160]
18 | 217 | 17 | N | Balance: Activo (II) - Activo - Instrumentos de patrimonio  [00161]
19 | 234 | 17 | N | Balance: Activo (II) - Activo - Créditos a empresas  [00162]
20 | 251 | 17 | N | Balance: Activo (II) - Activo - Valores representativos de deuda  [00163]
21 | 268 | 17 | N | Balance: Activo (II) - Activo - Derivados  [00164]
22 | 285 | 17 | N | Balance: Activo (II) - Activo - Otros activos financieros  [00165]
23 | 302 | 17 | N | Balance: Activo (II) - Activo - Otras inversiones  [00166]
24 | 319 | 17 | N | Balance: Activo (II) - Activo - Resto  [00167]
25 | 336 | 17 | N | Balance: Activo (II) - Activo - Inversiones financieras a corto plazo  [00168]
26 | 353 | 17 | N | Balance: Activo (II) - Activo - Instrumentos de patrimonio  [00169]
27 | 370 | 17 | N | Balance: Activo (II) - Activo - Créditos a empresas  [00170]
28 | 387 | 17 | N | Balance: Activo (II) - Activo - Valores representativos de deuda [00171]
29 | 404 | 17 | N | Balance: Activo (II) - Activo - Derivados [00172]
30 | 421 | 17 | N | Balance: Activo (II) - Activo - Otros activos financieros [00173]
31 | 438 | 17 | N | Balance: Activo (II) - Activo - Otras inversiones [00174]
32 | 455 | 17 | N | Balance: Activo (II) - Activo - Resto [00175]
33 | 472 | 17 | N | Balance: Activo (II) - Activo - Periodificaciones a corto plazo [00176]
34 | 489 | 17 | N | Balance: Activo (II) - Activo - Efectivo y otros activos líquidos equivalentes [00177]
35 | 506 | 17 | N | Balance: Activo (II) - Activo - Tesorería [00178]
36 | 523 | 17 | N | Balance: Activo (II) - Activo - Otros activos líquidos equivalentes [00179]
37 | 540 | 17 | N | Balance: Activo (II) - Activo - TOTAL ACTIVO [00180]
38 | 557 | 200 | An | RESERVADO PARA LA AEAT
39 | 757 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante </T2000400>
Total: |  | 768

# DP200005

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "05000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - PATRIMONIO NETO [00185]
7 | 30 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Fondos propios [00186]
8 | 47 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital [00187]
9 | 64 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital escriturado [00188]
10 | 81 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital no exigido [00189]
11 | 98 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Prima de emisión [00190]
12 | 115 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reservas [00191]
13 | 132 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Legal y estatutarias [00192]
14 | 149 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras reservas [00193]
15 | 166 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reserva de revalorización [00702]
16 | 183 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reserva de capitalización  [01001]
17 | 200 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reserva de nivelación   [01002]
18 | 217 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Acciones y participaciones en patrimonio propias [00194]
19 | 234 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultados de ejercicios anteriores [00195]
20 | 251 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Remanente [00196]
21 | 268 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultados negativos de ejercicios anteriores [00197]
22 | 285 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras aportaciones de socios [00198]
23 | 302 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultado del ejercicio [00199]
24 | 319 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Dividendo a cuenta [00200]
25 | 336 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros instrumentos de patrimonio neto [00201]
26 | 353 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Ajustes por cambios de valor [00202]
27 | 370 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Activos financieros disponibles para la venta [00203]
28 | 387 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Operaciones de cobertura [00204]
29 | 404 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Activos no corrientes y pasivos vinculados [00205]
30 | 421 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Diferencia de conversión [00206]
31 | 438 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros  [00207]
32 | 455 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Ajustes en patrimonio neto [00208]
33 | 472 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Subvenciones, donaciones y legados recibidos [00209]
34 | 489 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - PASIVO NO CORRIENTE [00210]
35 | 506 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Provisiones a largo plazo  [00211]
36 | 523 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Obligaciones por prestaciones a largo plazo al personal  [00212]
37 | 540 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Actuaciones medioambientales  [00213]
38 | 557 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Provisiones por reestructuración  [00214]
39 | 574 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras provisiones  [00215]
40 | 591 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deudas a largo plazo  [00216]
41 | 608 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Obligaciones y otros valores negociables  [00217]
42 | 625 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deudas con entidades de crédito  [00218]
43 | 642 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Acreedores por arrendamiento financiero  [00219]
44 | 659 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Derivados  [00220]
45 | 676 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros pasivos financieros [00221]
46 | 693 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras deudas a largo plazo [00222]
47 | 710 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deudas con empresas del grupo y asociadas a largo plazo [00223]
48 | 727 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Pasivos por impuesto diferido [00224]
49 | 744 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Periodificaciones a largo plazo [00225]
50 | 761 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Acreedores comerciales no corrientes [00226]
51 | 778 | 17 | N | Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deuda con características especiales a largo plazo [00227]
52 | 795 | 200 | An | RESERVADO PARA LA AEAT
53 | 995 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20005000>"
Total: |  | 1006

# DP200006

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "06000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - PASIVO CORRIENTE [00228]
7 | 30 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Pasivos vinculados con activos no corrientes [00229]
8 | 47 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Provisiones a corto plazo [00230]
9 | 64 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Provisiones por derechos emisión de gases de efecto invernadero [00703]
10 | 81 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras provisiones [00704]
11 | 98 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas a corto plazo [00231]
12 | 115 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Obligaciones y otros valores negociables [00232]
13 | 132 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas con entidades de crédito [00233]
14 | 149 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Acreedores por arrendamiento financiero [00234]
15 | 166 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Derivados [00235]
16 | 183 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otros pasivos financieros [00236]
17 | 200 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras deudas a corto plazo [00237]
18 | 217 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas con empresas del grupo y asociadas a corto plazo [00238]
19 | 234 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Acreedores comerciales y otras cuentas a pagar [00239]
20 | 251 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores [00240]
21 | 268 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores - Proveedores a largo plazo [00241]
22 | 285 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores - Proveedores a corto plazo [00242]
23 | 302 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores, empresas del grupo y asociadas [00243]
24 | 319 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Acreedores varios [00244]
25 | 336 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Personal (remuneraciones pendientes de pago) [00245]
26 | 353 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Pasivos por impuesto corriente [00246]
27 | 370 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras deudas con las Administraciones Públicas [00247]
28 | 387 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Anticipos de clientes [00248]
29 | 404 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otros acreedores [00249]
30 | 421 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Periodificaciones a corto plazo [00250]
31 | 438 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deuda con características especiales a corto plazo  [00251]
32 | 455 | 17 | N | Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - TOTAL PATRIMONIO NETO Y PASIVO [00252]
33 | 472 | 200 | An | RESERVADO PARA LA AEAT
34 | 672 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T2000600>"
Total: |  | 683

# DP200007

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "07000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Importe neto de la cifra de negocios [00255]
7 | 30 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ventas [00256]
8 | 47 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Prestaciones de servicios [00257]
9 | 64 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos de carácter financiero de las entidades concesionarias de infraestructuras públicas [00711]
10 | 81 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas -  Ingresos carácter financiero sociedades holding [00705]
11 | 98 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas -  Ingresos carácter financiero sociedades holding  - De participaciones en instrumentos patrimonio [00706]
12 | 115 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas -  Ingresos carácter financiero sociedades holding  - De valores negociables y otros instrumentos financieros [00707]
13 | 132 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas -  Ingresos carácter financiero sociedades holding  - Resto [00708]
14 | 149 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Variación de existencias de productos terminados 
y en curso de fabricación  [00258]
15 | 166 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Trabajos realizados por la empresa para su activo [00259]
16 | 183 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Aprovisionamientos [00260]
17 | 200 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Consumo de mercaderías [00261]
18 | 217 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Compras de mercaderías [00760]
19 | 234 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Variación de existencias  [00761]
20 | 251 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Consumo de materias primas y otras materias consumibles [00262]
21 | 268 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Compras de materias primas y otras materias consumibles [00762]
22 | 285 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Variación de materias primas y otras materias consumibles [00763]
23 | 302 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Trabajos realizados por otras empresas [00263]
24 | 319 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro de mercaderías, materias primas [00264]
25 | 336 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros ingresos de explotación [00265]
26 | 353 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente [00266]
27 | 370 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente - Ingresos por arrendamientos [00267]
28 | 387 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente - Resto [00268]
29 | 404 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Subvenciones de explotación incorporadas 
 al resultado del ejercicio  [00269]
30 | 421 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Gastos de personal  [00270]
31 | 438 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Sueldos, salarios y asimilados [00271]
32 | 455 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Indemnizaciones [00273]
33 | 472 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Seguridad Social a cargo de la empresa [00274]
34 | 489 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Retribuciones a largo plazo por sistemas de aportación o prestación definitiva  [00275]
35 | 506 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Retribuciones mediante instrumentos de patrimonio [00276]
36 | 523 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros gastos sociales [00277]
37 | 540 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Provisiones [00278]
38 | 557 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros gastos de explotación [00279]
39 | 574 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Servicios exteriores [00280]
40 | 591 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Tributos [00281]
41 | 608 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Pérdidas, deterioro y variación de provisiones por operaciones comerciales [00282]
42 | 625 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros gastos de gestión corriente [00283]
43 | 642 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Gastos por emisión de gases de efecto invernadero [00709]
44 | 659 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Amortización del inmovilizado [00284]
45 | 676 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Imputación de subvenciones de inmovilizado no financiero y otras [00285]
46 | 693 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Excesos de provisiones [00286]
47 | 710 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y resultado por enajenaciones del inmovilizado [00287]
48 | 727 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas [00288]
49 | 744 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas - Deterioros [00289]
50 | 761 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas - Reversión de deterioros [00290]
51 | 778 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras [00291]
52 | 795 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras - Beneficios [00292]
53 | 812 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas [00293]
54 | 829 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y resultados por enajenaciones del inmovilizado de las sociedades holding [00710]
55 | 846 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Diferencia negativa de combinaciones de negocio [00294]
56 | 863 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros resultados [00295]
57 | 880 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - RESULTADO DE EXPLOTACION [00296]
58 | 897 | 200 | An | RESERVADO PARA LA AEAT
59 | 1097 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20007000>"
Total: |  | 1108

# DP200008

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "08000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos financieros [00297]
7 | 30 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio [00298]
8 | 47 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio - En empresas del grupo y asociadas [00299]
9 | 64 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio - En terceros [00300]
10 | 81 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos financieros  [00301]
11 | 98 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos financieros  - De empresas del grupo y asociadas  [00302]
12 | 115 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos financieros  - De terceros  [00303]
13 | 132 | 17 | N | Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Imputación de subvenciones, donaciones y legados  de carácter financiero  [00304]
14 | 149 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Gastos financieros [00305]
15 | 166 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por deudas con empresas del grupo y asociadas [00306]
16 | 183 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por deudas con terceros [00307]
17 | 200 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por actualización de provisiones [00308]
18 | 217 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Variación de valor razonable en instrumentos financieros [00309]
19 | 234 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Cartera de negociación y otros [00310]
20 | 251 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Imputación por activos financieros disponibles para la venta  [00311]
21 | 268 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Diferencias de cambio [00312]
22 | 285 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioro y resultado por enajenaciones de instrumentos financieros   [00313]
23 | 302 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas [00314]
24 | 319 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Deterioros, empresas del grupo, asociadas y vinculadas [00315]
25 | 336 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Deterioros, otras empresas [00316]
26 | 353 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Reversión de deterioros, empresas del grupo, asociadas y vinculadas [00317]
27 | 370 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Reversión de deterioros, otras empresas [00318]
28 | 387 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras [00319]
29 | 404 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Beneficios, empresas del grupo, asociadas y vinculadas [00320]
30 | 421 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Beneficios, otras empresas [00321]
31 | 438 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas, empresas del grupo, asociadas y vinculadas  [00322]
32 | 455 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas, otras empresas  [00323]
33 | 472 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Otros ingresos y gastos de carácter financiero [00329]
34 | 489 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Incorporación al activo de gastos financieros [00330]
35 | 506 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Ingresos financieros derivados de convenios de acreedores [00331]
36 | 523 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resto de ingresos y gastos [00332]
37 | 540 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO FINANCIERO [00324]
38 | 557 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO ANTES DE IMPUESTOS [00325]
39 | 574 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Impuestos sobre beneficios  [00326]
40 | 591 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO DEL EJERCICIO PROCEDENTE DE OPERACIONES CONTINUADAS [00327]
41 | 608 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones interrumpidas - RESULTADO DEL EJERCICIO PROCEDENTE DE OPERACIONES INTERRUMPIDAS NETO DE IMPUESTOS [00328]
42 | 625 | 17 | N | Cuenta de pérdidas y ganancias (II) - Operaciones interrumpidas - RESULTADO DE LA CUENTA DE PÉRDIDAS Y GANANCIAS [00500]
43 | 642 | 200 | An | RESERVADO PARA LA AEAT
44 | 842 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20008000>"
Total: |  | 853

# DP200009

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "09000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Estado de cambios patrimonio neto (I) - Resultado de la cuenta de pérdidas y ganancias  [00500]
7 | 30 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por valoración de instrumentos financieros  [00336]
8 | 47 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Activos financieros disponibles para la venta [00337]
9 | 64 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Otros ingresos/gastos [00338]
10 | 81 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por coberturas de flujos de efectivo [00339]
11 | 98 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Subvenciones, donaciones y legados recibidos [00340]
12 | 115 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por ganancias y pérdidas actuariales y otros ajustes  [00341]
13 | 132 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por activos no corrientes y pasivos vinculados, mantenidos para la venta   [00342]
14 | 149 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Diferencias de conversión [00343]
15 | 166 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Efecto impositivo [00344]
16 | 183 | 17 | N | Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Total ingresos y gastos imputados en el patrimonio neto [00345]
17 | 200 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por valoración de instrumentos financieros [00346]
18 | 217 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Activos financieros disponibles para la venta [00347]
19 | 234 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Otros ingresos/gastos [00348]
20 | 251 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por coberturas de flujos de efectivo [00349]
21 | 268 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Subvenciones, donaciones y legados recibidos [00350]
22 | 285 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por activos no corrientes y pasivos vinculados , mantenidos para la venta  [00351]
23 | 302 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Diferencias de conversión [00352]
24 | 319 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Efecto impositivo [00353]
25 | 336 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Total transferencia a la cuenta de pérdidas y ganancias [00354]
26 | 353 | 17 | N | Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - TOTAL DE INGRESOS Y GASTOS RECONOCIDOS [00355]
27 | 370 | 200 | An | RESERVADO PARA LA AEAT
28 | 570 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20009000>"
Total: |  | 581

# DP200010

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "10000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Capital - Escriturado [00380]
7 | 30 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Capital - No exigido  [00381]
8 | 47 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Prima de emisión  [00382]
9 | 64 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Reservas  [00383]
10 | 81 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Acciones y participaciones en patrimonio propias  [00384]
11 | 98 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Resultados ejercicios anteriores  [00385]
12 | 115 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo,  final del ejercicio anterior - Otras aportaciones de socios  [00386]
13 | 132 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Capital - Escriturado  [00394]
14 | 149 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Capital - No exigido [00395]
15 | 166 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Prima de emisión [00396]
16 | 183 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Reservas [00397]
17 | 200 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Acciones y participaciones en patrimonio propias [00398]
18 | 217 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Resultados ejercicios anteriores [00399]
19 | 234 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Otras aportaciones de socios [00400]
20 | 251 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Capital - Escriturado [00408]
21 | 268 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Capital - No exigido [00409]
22 | 285 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Prima de emisión [00410]
23 | 302 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Reservas [00411]
24 | 319 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Acciones y participaciones en patrimonio propias [00412]
25 | 336 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Resultados ejercicios anteriores [00413]
26 | 353 | 17 | N | Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Otras aportaciones de socios [00414]
27 | 370 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Capital - Escriturado [00422]
28 | 387 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Capital - No exigido [00423]
29 | 404 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Prima de emisión [00424]
30 | 421 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Reservas [00425]
31 | 438 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Acciones y participaciones en patrimonio propias [00426]
32 | 455 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Resultados ejercicios anteriores [00427]
33 | 472 | 17 | N | Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Otras aportaciones socios [00428]
34 | 489 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Capital - Escriturado [00436]
35 | 506 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Capital - No exigido [00437]
36 | 523 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Prima de emisión [00438]
37 | 540 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Reservas [00439]
38 | 557 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Acciones y participaciones en patrimonio propias [00440]
39 | 574 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Resultados ejercicios anteriores [00441]
40 | 591 | 17 | N | Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Otras aportaciones de socios [00442]
41 | 608 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Capital - Escriturado [00450]
42 | 625 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Capital - No exigido [00451]
43 | 642 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Prima de emisión [00452]
44 | 659 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Reservas [00453]
45 | 676 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Acciones y participaciones en patrimonio propias [00454]
46 | 693 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Resultados ejercicios anteriores [00455]
47 | 710 | 17 | N | Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Otras aportaciones de socios [00456]
48 | 727 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Capital - Escriturado [00464]
49 | 744 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Capital - No exigido [00465]
50 | 761 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Prima de emisión [00466]
51 | 778 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Reservas [00467]
52 | 795 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Acciones y participaciones en patrimonio propias [00468]
53 | 812 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Resultados ejercicios anteriores [00469]
54 | 829 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otras aportaciones de socios [00470]
55 | 846 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Capital - Escriturado [00478]
56 | 863 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Capital - No exigido [00479]
57 | 880 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Prima de emisión [00480]
58 | 897 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Reservas [00481]
59 | 914 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Acciones y participaciones en patrimonio propias  [00482]
60 | 931 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Resultados ejercicios anteriores [00483]
61 | 948 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Otras aportaciones de socios [00484]
62 | 965 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Capital - Escriturado [00492]
63 | 982 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Capital - No exigido [00493]
64 | 999 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Prima de emisión [00494]
65 | 1016 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Reservas [00495]
66 | 1033 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Acciones y participaciones en patrimonio propias  [00496]
67 | 1050 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Resultados ejercicios anteriores [00497]
68 | 1067 | 17 | N | Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Otras aportaciones de socios [00498]
69 | 1084 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Capital - Escriturado [00506]
70 | 1101 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Capital - No exigido [00507]
71 | 1118 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Prima de emisión [00508]
72 | 1135 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Reservas [00509]
73 | 1152 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Acciones y participaciones en patrimonio propias [00510]
74 | 1169 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Resultados ejercicios anteriores [00511]
75 | 1186 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras aportaciones de socios [00512]
76 | 1203 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Capital - Escriturado [00520]
77 | 1220 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Capital - No exigido [00521]
78 | 1237 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Prima de emisión [00522]
79 | 1254 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Reservas [00523]
80 | 1271 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Acciones y participaciones en patrimonio propias  [00524]
81 | 1288 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Resultados ejercicios anteriores [00525]
82 | 1305 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Otras aportaciones de socios [00526]
83 | 1322 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Capital - Escriturado [00534]
84 | 1339 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Capital - No exigido [00535]
85 | 1356 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Prima de emisión [00536]
86 | 1373 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Reservas [00537]
87 | 1390 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Acciones y participaciones en patrimonio propias  [00538]
88 | 1407 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Resultados ejercicios anteriores [00539]
89 | 1424 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital - Otras aportaciones de socios [00540]
90 | 1441 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Capital - Escriturado [00548]
91 | 1458 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Capital - No exigido [00549]
92 | 1475 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Prima de emisión [00550]
93 | 1492 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Reservas [00551]
94 | 1509 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Acciones y participaciones en patrimonio propias [00552]
95 | 1526 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Resultados ejercicios anteriores [00553]
96 | 1543 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Otras aportaciones de socios [00554]
97 | 1560 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Capital - Escriturado [00562]
98 | 1577 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Capital - No exigido [00563]
99 | 1594 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Prima de emisión [00564]
100 | 1611 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Reservas [00565]
101 | 1628 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Acciones y participaciones en patrimonio propias  [00566]
102 | 1645 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Resultados ejercicios anteriores [00567]
103 | 1662 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Otras aportaciones de socios [00568]
104 | 1679 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Capital - Escriturado [00576]
105 | 1696 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Capital - No exigido [00577]
106 | 1713 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Prima de emisión [00578]
107 | 1730 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Reservas [00579]
108 | 1747 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Acciones y participaciones en patrimonio propias [00580]
109 | 1764 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Resultados ejercicios anteriores [00581]
110 | 1781 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Otras aportaciones de socios [00582]
111 | 1798 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Capital  - Escriturado [00590]
112 | 1815 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Capital  - No exigido [00591]
113 | 1832 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Prima de emisión [00592]
114 | 1849 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Reservas [00593]
115 | 1866 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Acciones y participaciones en patrimonio propias [00594]
116 | 1883 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Resultados ejercicios anteriores [00595]
117 | 1900 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Otras aportaciones de socios [00596]
118 | 1917 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Capital -  Escriturado [00604]
119 | 1934 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Capital - No exigido [00605]
120 | 1951 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Prima de emisión [00606]
121 | 1968 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Reservas [00607]
122 | 1985 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Acciones y participaciones en patrimonio propias [00608]
123 | 2002 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Resultados ejercicios anteriores [00609]
124 | 2019 | 17 | N | Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Otras aportaciones de socios [00610]
125 | 2036 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Capital - Escriturado [00618]
126 | 2053 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Capital - No exigido [00619]
127 | 2070 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Prima de emisión [00620]
128 | 2087 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Reservas [00621]
129 | 2104 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Acciones y participaciones en patrimonio propias [00622]
130 | 2121 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Resultados ejercicios anteriores [00623]
131 | 2138 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras aportaciones de socios [00624]
132 | 2155 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Capital - Escriturado [00715]
133 | 2172 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -  Capital - No exigido [00716]
134 | 2189 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Prima de emisión [00717]
135 | 2206 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -  Reservas [00718]
136 | 2223 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Acciones y participaciones en patrimonio propias [00719]
137 | 2240 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Resultados ejercicios anteriores [00720]
138 | 2257 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Otras aportaciones de socios [00721]
139 | 2274 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Capital - Escriturado [00729]
140 | 2291 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones -  Capital - No exigido [00730]
141 | 2308 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Prima de emisión [00731]
142 | 2325 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones -  Reservas [00732]
143 | 2342 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Acciones y participaciones en patrimonio propias  [00733]
144 | 2359 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Resultados ejercicios anteriores [00734]
145 | 2376 | 17 | N | Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Otras aportaciones de socios [00735]
146 | 2393 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Capital - Escriturado [00632]
147 | 2410 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Capital - No exigido [00633]
148 | 2427 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Prima de emisión [00634]
149 | 2444 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Reservas [00635]
150 | 2461 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Acciones y participaciones en patrimonio propias [00636]
151 | 2478 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Resultados ejercicios 
anteriores [00637]
152 | 2495 | 17 | N | Estado de cambios patrimonio neto (II) - SALDO, FINAL DEL EJERCICIO - Otras aportaciones de socios [00638]
153 | 2512 | 200 | An | RESERVADO PARA LA AEAT
154 | 2712 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20010000>"
Total: |  | 2723

# DP200011

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "11000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Resultado del ejercicio [00387]
7 | 30 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Dividendo a cuenta [00388]
8 | 47 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Otros instrumentos patrimonio neto [00389]
9 | 64 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Ajustes por cambios de valor [00390]
10 | 81 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Ajustes en patrimonio neto [00391]
11 | 98 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Subvenciones, donaciones y legados recibidos [00392]
12 | 115 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Total [00393]
13 | 132 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Resultado del ejercicio [00401]
14 | 149 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Dividendo a cuenta [00402]
15 | 166 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Otros instrumentos patrimonio neto [00403]
16 | 183 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Ajustes por cambios de valor [00404]
17 | 200 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Ajustes en patrimonio neto [00405]
18 | 217 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Subvenciones, donaciones y legados recibidos [00406]
19 | 234 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Total [00407]
20 | 251 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Resultado del ejercicio [00415]
21 | 268 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Dividendo a cuenta [00416]
22 | 285 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Otros instrumentos patrimonio neto [00417]
23 | 302 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Ajustes por cambios de valor [00418]
24 | 319 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Ajustes en patrimonio neto [00419]
25 | 336 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Subvenciones, donaciones y legados recibidos [00420]
26 | 353 | 17 | N | Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Total [00421]
27 | 370 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Resultado del ejercicio [00429]
28 | 387 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Dividendo a cuenta [00430]
29 | 404 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Otros instrumentos patrimonio neto [00431]
30 | 421 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Ajustes por cambios de valor [00432]
31 | 438 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Ajustes en patrimonio neto [00433]
32 | 455 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Subvenciones, donaciones y legados recibidos [00434]
33 | 472 | 17 | N | Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Total [00435]
34 | 489 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Resultado del ejercicio [00443]
35 | 506 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Dividendo a cuenta [00444]
36 | 523 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Otros instrumentos patrimonio neto [00445]
37 | 540 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Ajustes por cambios de valor [00446]
38 | 557 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Subvenciones, donaciones y legados recibidos [00448]
39 | 574 | 17 | N | Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Total [00449]
40 | 591 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Resultado del ejercicio [00457]
41 | 608 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Dividendo a cuenta [00458]
42 | 625 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Ajustes en patrimonio neto [00461]
43 | 642 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Subvenciones, donaciones y legados recibidos [00462]
44 | 659 | 17 | N | Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Total [00463]
45 | 676 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Resultado del ejercicio [00471]
46 | 693 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Dividendo a cuenta [00472]
47 | 710 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ajustes en patrimonio neto [00475]
48 | 727 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Subvenciones, donaciones y legados recibidos [000476]
49 | 744 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Total [00477]
50 | 761 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Resultado del ejercicio [00485]
51 | 778 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Dividendo a cuenta [00486]
52 | 795 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Ajustes en patrimonio neto [00489]
53 | 812 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Subvenciones, donaciones y legados recibidos [00490]
54 | 829 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Total [00491]
55 | 846 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Resultado del ejercicio [00499]
56 | 863 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Dividendo a cuenta [00502]
57 | 880 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Ajustes en patrimonio neto [00503]
58 | 897 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Subvenciones, donaciones y legados recibidos [00504]
59 | 914 | 17 | N | Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Total [00505]
60 | 931 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Resultado del ejercicio [00513]
61 | 948 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Dividendo a cuenta [00514]
62 | 965 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otros instrumentos patrimonio neto [00515]
63 | 982 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Ajustes por cambios de valor [00516]
64 | 999 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Ajustes en patrimonio neto [00517]
65 | 1016 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Subvenciones, donaciones y legados recibidos [00518]
66 | 1033 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Total [00519]
67 | 1050 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Resultado del ejercicio [00527]
68 | 1067 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Dividendo a cuenta [00528]
69 | 1084 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Otros instrumentos patrimonio neto [00529]
70 | 1101 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Ajustes por cambios de valor [00530]
71 | 1118 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Ajustes en patrimonio neto [00531]
72 | 1135 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Subvenciones, donaciones y legados recibidos [00532]
73 | 1152 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Total [00533]
74 | 1169 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Resultado del ejercicio [00541]
75 | 1186 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Dividendo a cuenta [00542]
76 | 1203 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Otros instrumentos patrimonio neto [00543]
77 | 1220 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Ajustes por cambios de valor [00544]
78 | 1237 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Ajustes en patrimonio neto [00545]
79 | 1254 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Subvenciones, donaciones y legados recibidos [00546]
80 | 1271 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Total  [00547]
81 | 1288 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Resultado del ejercicio [00555]
82 | 1305 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Dividendo a cuenta [00556]
83 | 1322 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Otros instrumentos patrimonio neto [00557]
84 | 1339 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Ajustes por cambios de valor [00558]
85 | 1356 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Subvenciones, donaciones y legados recibidos [00560]
86 | 1373 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en patrim. neto - Total [00561]
87 | 1390 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Resultado del ejercicio [00569]
88 | 1407 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Dividendo a cuenta [00570]
89 | 1424 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Otros instrumentos patrimonio neto [00571]
90 | 1441 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Ajustes por cambio de valor [00572]
91 | 1458 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Subvenciones, donaciones y legados recibidos [00574]
92 | 1475 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos - Total [00575]
93 | 1492 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Resultado del ejercicio [00583]
94 | 1509 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Dividendo a cuenta [00584]
95 | 1526 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Otros instrumentos patrimonio neto [00585]
96 | 1543 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Ajustes por cambio de valor [00586]
97 | 1560 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Subvenciones, donaciones y legados recibidos [00588]
98 | 1577 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o participaciones propias - Total [00589]
99 | 1594 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Resultado del ejercicio [00597]
100 | 1611 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Dividendo a cuenta [00598]
101 | 1628 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Otros instrumentos patrimonio neto [00599]
102 | 1645 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Ajustes por cambios de valor [00600]
103 | 1662 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Subvenciones, donaciones y legados recibidos [00602]
104 | 1679 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr. neto de combinación de negocios - Total [00603]
105 | 1696 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Resultado del ejercicio  [00611]
106 | 1713 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Dividendo a cuenta  [00612]
107 | 1730 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Otros instrumentos patrimonio neto  [00613]
108 | 1747 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Ajustes por cambios de valor [00614]
109 | 1764 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Ajustes en patrimonio neto [00615]
110 | 1781 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Subvenciones, donaciones y legados recibidos  [00616]
111 | 1798 | 17 | N | Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o propietarios - Total [00617]
112 | 1815 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Resultado del ejercicio [00625]
113 | 1832 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Dividendo a cuenta  [00626]
114 | 1849 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otros instrumentos patrimonio neto [00627]
115 | 1866 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Ajustes por cambios de valor [00628]
116 | 1883 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Ajustes en patrimonio neto [00629]
117 | 1900 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Subvenciones, donaciones y legados recibidos  [00630]
118 | 1917 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Total [00631]
119 | 1934 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Resultado del ejercicio [00722]
120 | 1951 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Dividendo a cuenta  [00723]
121 | 1968 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Otros instrumentos patrimonio neto [00724]
122 | 1985 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Ajustes por cambios de valor [00725]
123 | 2002 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Ajustes en patrimonio neto [00726]
124 | 2019 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Subvenciones, donaciones y legados recibidos  [00727]
125 | 2036 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización - Total [00728]
126 | 2053 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Resultado del ejercicio [00736]
127 | 2070 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Dividendo a cuenta  [00737]
128 | 2087 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Otros instrumentos patrimonio neto [00738]
129 | 2104 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Ajustes por cambios de valor [00739]
130 | 2121 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Ajustes en patrimonio neto [00740]
131 | 2138 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Subvenciones, donaciones y legados recibidos  [00741]
132 | 2155 | 17 | N | Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Total [00742]
133 | 2172 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Resultado del ejercicio [00639]
134 | 2189 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Dividendo a cuenta [00640]
135 | 2206 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Otros instrumentos patrimonio neto [00641]
136 | 2223 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Ajustes por cambios de valor [00642]
137 | 2240 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Ajustes en patrimonio neto [00643]
138 | 2257 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Subvenciones, donaciones y legados recibidos [00644]
139 | 2274 | 17 | N | Estado de cambios patrimonio neto (III) - SALDO, FINAL DEL EJERCICIO - Total [00645]
140 | 2291 | 200 | An | RESERVADO PARA LA AEAT
141 | 2491 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20011000>"
Total: |  | 2502

# DP200012

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "12000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | N | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Resultado de la cuenta de pérdidas y ganancias [00500]
7 | 30 | 17 | N | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones por Impuesto Sociedades - Aumentos [00301]
8 | 47 | 17 | N | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones por Impuesto Sociedades - Disminuciones [00302]
9 | 64 | 17 | N | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Resultado cuenta pérdidas y ganancias antes de Impuesto Sociedades [00501]
10 | 81 | 17 | Num | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones al resultado contable referidos al grupo fiscal - Aumentos [01230]
11 | 98 | 17 | Num | Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones al impuesto contable  referidos al grupo fiscal - Disminuciones [01231]
12 | 115 | 1 | Num | Cifra de negocios |  | Nota 1
13 | 116 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cambio de criterios contables (art.11.3.2º LIS) - Aumentos [00355]
14 | 133 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cambio de criterios contables (art.11.3.2º LIS) - Disminuciones [00356]
15 | 150 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos (art.11.4 LIS) - Aumentos [00357]
16 | 167 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos (art.11.4 LIS) - Disminuciones [00358]
17 | 184 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reversión del deterioro de valor elem. patrimoniales (art. 11.6 LIS) - Aumentos [00359]
18 | 201 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reversión del deterioro de valor elem. patrimoniales (art. 11.6 LIS) - Disminuciones [00360]
19 | 218 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas negativas (art. 11.9 y 11.10 LIS) - Aumentos [00225]
20 | 235 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas negativas (art. 11.9 y 11.10 LIS) - Disminuciones [00226]
21 | 252 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por rentas derivadas de operaciones  con quita o espera  (art.11.13 LIS) - Aumentos [01514]
22 | 269 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por rentas derivadas de operaciones con quita o espera (art. 11.13 LIS) - Disminuciones [00272]
23 | 286 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361]
24 | 303 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcciones permanentes (excl. correcc. I. Sociedades)
25 | 320 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcciones temporarias con origen en el ejercicio - Total
26 | 337 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
27 | 354 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
28 | 371 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcciones temporarias con origen en el ejercicio - Por pensiones
29 | 388 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
30 | 405 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcciones temporarias con origen en el ejercicio - Resto
31 | 422 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcc. temporarias con origen en ejerc. anteriores - Total
32 | 439 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
33 | 456 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
34 | 473 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
35 | 490 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
36 | 507 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - otras diferencias de imputac. temporal de ingresos y gastos (art.11 LIS) - Aumentos [00361] - Correcc. temporarias con origen en ejerc. anteriores - Resto
37 | 524 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362]
38 | 541 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcciones permanentes (excl. correcc. I. Sociedades)
39 | 558 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcciones temporarias con origen en el ejercicio - Total
40 | 575 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
41 | 592 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
42 | 609 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcciones temporarias con origen en el ejercicio - Por pensiones
43 | 626 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
44 | 643 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcciones temporarias con origen en el ejercicio - Resto
45 | 660 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcc. temporarias con origen en ejerc. anteriores - Total
46 | 677 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
47 | 694 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
48 | 711 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
49 | 728 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
50 | 745 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputac. temporal de ingresos y gastos  (art.11 LIS) - Disminuciones [00362] - Correcc. temporarias con origen en ejerc. anteriores - Resto
51 | 762 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Diferencias entre amortización contable y fiscal (arts. 12.1 LIS) - Aumentos [00303]
52 | 779 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Diferencias entre amortización contable y fiscal (arts. 12.1 LIS) - Disminuciones [00304]
53 | 796 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reversion del 30% importe gastos de amortiz.contable (excluidas emp.reducida dimensión)(art. 7 Ley 16/2012) - Disminuciones [00505]
54 | 813 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización del inmovilizado intangible con vida útil definida  (DT 12.2 LIS) y armotización del art. DT 13ª.1 LIS - Aumentos [01005]
55 | 830 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización del inmovilizado intangible con vida útil definida  (art. 12.2 LIS) y armotización del art. DT 13ª.1 LIS - Diminuciones  [01006]
56 | 847 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización inmovilizado afecto investigación y desarrollo (art. 12.3.b) LIS) - Aumentos [00305]
57 | 864 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización inmovilizado afecto investigación y desarrollo (art. 12.3.b) LIS) - Disminuciones [00306]
58 | 881 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización de gastos de investigación y desarrollo (art. 12.3.c) LIS) - Aumentos [00307]
59 | 898 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización de gastos de investigación y desarrollo (art. 12.3.c) LIS) - Disminuciones [00308]
60 | 915 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización inmovilizado material nuevo (art. 12.3 e) LIS) - Aumentos [01003]
61 | 932 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización inmovilizado material nuevo (art. 12.3 e) LIS) - Disminuciones [01004]
62 | 949 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otros supuestos de libertad de amortización  (art. 12.3 a) y d) LIS) - Aumentos [00309]
63 | 966 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otros supuestos de libertad de amortización  (art. 12.3 a) y d) LIS) - Disminuciones [00310]
64 | 983 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización con mantenimiento de empleo (RDL 6/2010 y DT 13ª.2 LIS) - Aumentos [00514]
65 | 1000 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización con mantenimiento de empleo (RDL 6/2010 y DT13ª.2 LIS) - Disminuciones [00509]
66 | 1017 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización sin mantenimiento de empleo (RDL 13/2010 y DT 13ª.2 LIS) - Aumentos [00516]
67 | 1034 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización sin mantenimiento de empleo (RDL 13/2010 y DT 13ª.2 LIS) - Disminuciones [00551]
68 | 1051 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321]
69 | 1068 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcciones permanentes (excl. correcc. I. Sociedades)
70 | 1085 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcciones temporarias con origen en el ejercicio - Total
71 | 1102 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
72 | 1119 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
73 | 1136 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcciones temporarias con origen en el ejercicio - Por pensiones
74 | 1153 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
75 | 1170 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcciones temporarias con origen en el ejercicio - Resto
76 | 1187 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcc. temporarias con origen en ejerc. anteriores - Total
77 | 1204 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
78 | 1221 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
79 | 1238 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
80 | 1255 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
81 | 1272 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 lis no afectada por el art. 11.12 y DT 33ª.1 LIS - Aumentos [00321] - Correcc. temporarias con origen en ejerc. anteriores - Resto
82 | 1289 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322]
83 | 1306 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcciones permanentes (excl. correcc. I. Sociedades)
84 | 1323 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcciones temporarias con origen en el ejercicio - Total
85 | 1340 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
86 | 1357 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
87 | 1374 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcciones temporarias con origen en el ejercicio - Por pensiones
88 | 1391 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
89 | 1408 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcciones temporarias con origen en el ejercicio - Resto
90 | 1425 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcc. temporarias con origen en ejerc. anteriores - Total
91 | 1442 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
92 | 1459 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
93 | 1476 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
94 | 1493 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
95 | 1510 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art. 13.1 LIS no afectada por el art. 11.12 y DT 33ª.1 LIS - Disminuciones [00322] - Correcc. temporarias con origen en ejerc. anteriores - Resto
96 | 1527 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art.13.1 LIS y provisiones y gastos - Aumentos [00415]
97 | 1544 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro del art.13.1 LIS y provisiones y gastos - Disminuciones [00211]
98 | 1561 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Perdidas por deterioro de IM, inversiones inmob. e II, incluido fondo comercio - Aumentos [00331]
99 | 1578 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Perdidas por deterioro de IM, inversiones inmob. e II, incluido fondo comercio - Disminuciones [00332]
100 | 1595 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325]
101 | 1612 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcciones permanentes (excl. correcc. I. Sociedades)
102 | 1629 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcciones temporarias con origen en el ejercicio - Total
103 | 1646 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
104 | 1663 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
105 | 1680 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcciones temporarias con origen en el ejercicio - Por pensiones
106 | 1697 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
107 | 1714 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcciones temporarias con origen en el ejercicio - Resto
108 | 1731 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcc. temporarias con origen en ejerc. anteriores - Total
109 | 1748 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
110 | 1765 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
111 | 1782 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
112 | 1799 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
113 | 1816 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Aumentos [00325] - Correcc. temporarias con origen en ejerc. anteriores - Resto
114 | 1833 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326]
115 | 1850 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcciones permanentes (excl. correcc. I. Sociedades)
116 | 1867 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcciones temporarias con origen en el ejercicio - Total
117 | 1884 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
118 | 1901 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
119 | 1918 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcciones temporarias con origen en el ejercicio - Por pensiones
120 | 1935 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
121 | 1952 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcciones temporarias con origen en el ejercicio - Resto
122 | 1969 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcc. temporarias con origen en ejerc. anteriores - Total
123 | 1986 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
124 | 2003 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
125 | 2020 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
126 | 2037 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
127 | 2054 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios (art 13.2 b) LIS) - Disminuciones [00326] - Correcc. temporarias con origen en ejerc. anteriores - Resto
128 | 2071 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios  DT 16ª.1 y 2 LIS) - Aumentos [01518]
129 | 2088 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic.en el capital o fondos propios  DT 16ª.1 y 2 LIS) - Disminuciones [00394]
130 | 2105 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic. en el capital o fondos propios (DT 16ª.3 LIS) - Aumentos [00333]
131 | 2122 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por pérdidas por deterioro de valores repr. de partic. en el capital o fondos propios (DT 16ª.3 LIS) - Disminuciones [00334]
132 | 2139 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valores representativos de deuda  (art. 13.2 c) LIS y DT 15ª LIS) - Aumentos [00327]
133 | 2156 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valores representativos de deuda (art. 13.2 c) LIS y DT 15ª LIS) - Disminuciones [00328]
134 | 2173 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Aplicac. limite del art. 11.12 LIS a las perdidas por deterioro del art. 13.1 LIS y provisiones y gastos - Aumentos [00416]
135 | 2190 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Aplicac. limite del art. 11.12 LIS a las perdidas por deterioro del art. 13.1 LIS y provisiones y gastos - Disminuciones [00543]
136 | 2207 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos y provisiones por pensiones no afectos por el art. 11.12 LIS - Aumentos [00335]
137 | 2224 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Provisiones y gastos por pensiones no afectos por el art. 11.12 LIS - Aumentos [00336]
138 | 2241 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337]
139 | 2258 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcciones permanentes (excl. correcc. I. Sociedades)
140 | 2275 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcciones temporarias con origen en el ejercicio - Total
141 | 2292 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
142 | 2309 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
143 | 2326 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcciones temporarias con origen en el ejercicio - Por pensiones
144 | 2343 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
145 | 2360 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcciones temporarias con origen en el ejercicio - Resto
146 | 2377 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcc. temporarias con origen en ejerc. anteriores - Total
147 | 2394 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
148 | 2411 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
149 | 2428 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
150 | 2445 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
151 | 2462 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Aumentos [00337] - Correcc. temporarias con origen en ejerc. anteriores - Resto
152 | 2479 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338]
153 | 2496 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcciones permanentes (excl. correcc. I. Sociedades)
154 | 2513 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcciones temporarias con origen en el ejercicio - Total
155 | 2530 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
156 | 2547 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
157 | 2564 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcciones temporarias con origen en el ejercicio - Por pensiones
158 | 2581 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
159 | 2598 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcciones temporarias con origen en el ejercicio - Resto
160 | 2615 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcc. temporarias con origen en ejerc. anteriores - Total
161 | 2632 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
162 | 2649 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
163 | 2666 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
164 | 2683 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
165 | 2700 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles fiscalmente  (art. 14 LIS) no afectas por el art. 11.12 LIS - Disminuciones [00338] - Correcc. temporarias con origen en ejerc. anteriores - Resto
166 | 2717 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Subvenciones públic.incluidas en el resultado ejercicio no integrable en BI (art. 14.8 LIS) - Disminuciones [00368]
167 | 2734 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos no deducibles por considerarse retribución de fondos propios (art. 15 a) LIS) - Aumentos [01002]
168 | 2751 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Multas, sanciones y otros (art. 15 c) LIS) - Aumentos [01815]
169 | 2768 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas del juego (art. 15 d) LIS)  [00343]
170 | 2785 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos por donativos y liberalidades (art. 15 e) LIS) - Aumentos [00339]
171 | 2802 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos de actuaciones contrarias al ordenamiento jurídico (art. 15 f) LIS) - Aumentos [01816]
172 | 2819 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones realizadas con paraísos fiscales (art. 15 g) LIS) - Aumentos [00341]
173 | 2836 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones realizadas con paraísos fiscales (art. 15 g) LIS) - Disminuciones [00342]
174 | 2853 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos financieros derivados de deudas  y operaciones con entidades del grupo - Aumentos [00508]
175 | 2870 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos derivados de la extinción de la relación laboral o mercantil (art. 15 i) LIS) - Aumentos [01817]
176 | 2887 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos correspondientes a operac. realizadas con personas o entid. vinculadas - Aumentos [01009]
177 | 2904 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos correspondientes a operac. realizadas con personas o entid. vinculadas - Disminuciones [01010]
178 | 2921 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valores repr. de partic. en el capital o fondos propios (art. 15 k) LIS) - Aumentos [01807]
179 | 2938 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valores repr. de partic. en el capital o fondos propios (art. 15 k) LIS) - Disminuciones [01811]
180 | 2955 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Disminución de valor originada por criterio de valor razonable (art. 15 l) LIS) - Aumentos [01808]
181 | 2972 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Disminución de valor originada por criterio de valor razonable (art. 15 l) LIS) - Disminuciones [01812]
182 | 2989 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Deuda tributaria de actos jurídicos documentados (ITP y AJD) (art. 15 m) LIS) - Aumentos [01813]
183 | 3006 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Deuda tributaria de actos jurídicos documentados (ITP y AJD) (art. 15 m) LIS) - Disminuciones [01814]
184 | 3023 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por la limitación en la deduc. de gastos financieros (art. 16 LIS) - Aumentos [00363]
185 | 3040 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por la limitación en la deduc. de gastos financieros (art. 16 LIS) - Disminuciones [00364]
186 | 3057 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Revalorizaciones contables (art. 17.1  LIS) - Aumentos [00345]
187 | 3074 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Revalorizaciones contables (art. 17.1  LIS) - Disminuciones [00346]
188 | 3091 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones de aumento de capital o fondos propios por compensación de créditos (art. 17.2 LIS) - Aumentos [01818]
189 | 3108 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones de aumento de capital o fondos propios por compensación de créditos (art. 17.2 LIS) - Disminuciones [01819]
190 | 3125 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - SICAV: Reducciones de capital y distribución de la prima de emisión  (art. 17.6 LIS) - Aumentos [00371]
191 | 3142 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Transmisiónes lucrativas y societarias: aplicación del valor normal de mercado (art. 17.4 LIS) - Aumentos [00347]
192 | 3159 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Transmisiónes lucrativas y societarias: aplicación del valor normal de mercado  (art. 17.4 LIS) - Disminuciones [00348]
193 | 3176 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones vinculadas: aplicación del valor normal de mercado (art. 18 LIS) - Aumentos [01011]
194 | 3193 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones vinculadas: aplicación del valor normal de mercado (art. 18 LIS) - Disminuciones [01012]
195 | 3210 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cambios de residencia y otras operaciones del art.19 LIS - Aumentos [01013]
196 | 3227 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cambios de residencia y otras operaciones del art.19 LIS - Disminuciones [01014]
197 | 3244 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Efectos de la valoración contable diferente a la fiscal (art. 20 LIS) - Aumentos [01015]
198 | 3261 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Efectos de la valoración contable diferente a la fiscal (art. 20 LIS) - Disminuciones [01016]
199 | 3278 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre dividendos o participaciones en beneficios de entidades residentes (art. 21.1 LIS) - Disminuciones [00370]
200 | 3295 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre dividendos o participaciones en benefi cios de entidades no residentes (art. 21.1 LIS) - Disminuciones [02181]
201 | 3312 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre la renta obtenida en la transmisión de valores entidades residentes (art. 21.3 LIS) - Aumentos [02182]
202 | 3329 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre la renta obtenida en la transmisión de valores entidades residentes (art. 21.3 LIS) - Disminuciones [02183]
203 | 3346 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre la renta obtenida en la transmisión de valores entidades no residentes (art. 21.3 LIS) - Aumentos [02184]
204 | 3363 | 17 | Num | Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre la renta obtenida en la transmisión de valores entidades no residentes (art. 21.3 LIS) - Disminuciones [02185]
205 | 3380 | 200 | An | RESERVADO PARA LA AEAT
206 | 3580 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20012000>"
Total: |  | 3591
Nota 1: Cifra de negocios
1 | Contribuyente cuyo importe neto de la cifra de negocios (INCN) sea inferior a 20 millones de euros durante los doce meses anteriores a la fecha de inicio del periodo impositivo
2 | Contribuyente cuyo importe neto de la cifra de negocios (INCN) sea al menos de 20 millones de euros pero inferior a 60 millones de euros durante los doce meses anteriores a la fecha de inicio del periodo impositivo
3 | Contribuyente cuyo importe neto de la cifra de negocios (INCN) sea al menos de 60 millones de euros durante los doce meses anteriores a la fecha de inicio del periodo impositivo

# DP200013

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "13000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre la renta obtenida en los supuestos del art. 21.3 LIS distintos a transmisiones de valores entidades residentes - Aumentos [02186]
7 | 30 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre la renta obtenida en los supuestos del art. 21.3 LIS distintos a transmisiones de valores entidades residentes - Disminuciones [02187]
8 | 47 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre la renta obtenida en los supuestos del art. 21.3 LIS distintos a transmisiones de valores entidades no residentes - Aumentos [02188]
9 | 64 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención sobre la renta obtenida en los supuestos del art. 21.3 LIS distintos a transmisiones de valores entidades no residentes - Disminuciones [02189]
10 | 81 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención de rentas en el extranjero  (art. 22 LIS) - Aumentos [00256]
11 | 98 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención de rentas en el extranjero (art. 22 LIS) - Disminuciones [00278]
12 | 115 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reducción de ingresos procedentes de determinados activos intangibles (art. 23 LIS) - Aumentos [01822]
13 | 132 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reducción de ingresos procedentes de determinados activos intangibles (art. 23 LIS) - Disminuciones [00372]
14 | 149 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Obra benéfico-social de las cajas de ahorro y fundaciones  bancarias (art. 24 LIS) - Aumentos [00373]
15 | 166 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Obra benéfico-social de las cajas de ahorro y fundaciones  bancarias  (art. 24 LIS) - Disminuciones [00374]
16 | 183 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Impuesto extranjero soportado por el contribuyente, no deducible por afectar a rentas con deducc. doble imp. - Aumentos [00340]
17 | 200 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Impuesto extranjero soportado por el contribuyente, no deducible por afectar a rentas con deducc. doble imp. - Disminuciones [01589]
18 | 217 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Impuesto extranjero sobre beneficios con cargo a los cuales se pagan los dividendos objeto deducc.doble imp.internac. - Aumentos [00351]
19 | 234 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Agrupación de interés económico (Cap. II Tit. VII LIS) - Aumentos [00375]
20 | 251 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Agrupación de interés económico   (Cap. II Tit. VII LIS) - Disminuciones [00376]
21 | 268 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes del art. 45.1 LIS - Aumentos [01320]
22 | 285 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes del art. 45.1 LIS - Disminuciones [01321]
23 | 302 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por rentas exentas de UTE  que opera en el extranjero - Aumentos [00184]
24 | 319 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por rentas exentas de UTE  que opera en el extranjero - Disminuciones [00544]
25 | 336 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por participar en el extranjero en formulas colaborac. a las UTES - Aumentos [01022]
26 | 353 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por participar en el extranjero en formulas colaborac. a las UTES - Disminuciones [01023]
27 | 370 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por criterios de imputación temporal (art. 46.2 LIS) - Aumentos [01018]
28 | 387 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Unión temporal de empresas, ajustes por criterios de imputación temporal (art. 46.2 LIS) - Disminuciones [01019]
29 | 404 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - BI negativas generadas dentro del grupo fiscal por la entidad transmitida y que hayan sido compensadas - Aumentos [01275]
30 | 421 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - BI negativas generadas dentro del grupo fiscal por la entidad transmitida y que hayan sido compensadas - Disminuciones [01276]
31 | 438 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Soc. y fondos de capital-riesgo y soc. desarrollo industrial regional  (cap.IV, titulo VII LIS) - Aumentos [00377]
32 | 455 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Soc. y fondos de capital-riesgo y soc. desarrollo industrial regional (cap.IV, titulo VII LIS) - Disminuciones [00378]
33 | 472 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Valoración bienes y derechos. Régimen especial operaciones reestructuración (cap.VII, titulo VII LIS) - Aumentos [00379]
34 | 489 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Valoración bienes y derechos. Régimen especial operaciones reestructuración (cap.VII, titulo VII LIS) - Disminuciones [00380]
35 | 506 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Minería e hidrocarburos: factor agotamiento (arts. 91 y 95 LIS) - Aumentos [00381]
36 | 523 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Minería e hidrocarburos: factor agotamiento (arts. 91 y 95 LIS) - Disminuciones [00382]
37 | 540 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Hidrocarburos: Amortización inversiones intangibles  y gastos de investigación (art. 99 LIS) - Aumentos [00383]
38 | 557 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Hidrocarburos: Amortización inversiones intangibles y gastos de investigación (art. 99 LIS) - Disminuciones [00384]
39 | 574 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Transparencia fiscal internacional (art. 100 LIS) - Aumentos [00387]
40 | 591 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Transparencia fiscal internacional (art. 100 LIS) - Disminuciones [00388]
41 | 608 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311]
42 | 625 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcciones permanentes (excl. correcc. I. Sociedades)
43 | 642 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcciones temporarias con origen en el ejercicio - Total
44 | 659 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
45 | 676 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
46 | 693 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcciones temporarias con origen en el ejercicio - Por pensiones
47 | 710 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
48 | 727 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcciones temporarias con origen en el ejercicio - Resto
49 | 744 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcc. temporarias con origen en ejerc. anteriores - Total
50 | 761 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
51 | 778 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
52 | 795 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
53 | 812 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
54 | 829 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Aumentos [00311] - Correcc. temporarias con origen en ejerc. anteriores - Resto
55 | 846 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312]
56 | 863 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcciones permanentes (excl. correcc. I. Sociedades)
57 | 880 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcciones temporarias con origen en el ejercicio - Total
58 | 897 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
59 | 914 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
60 | 931 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcciones temporarias con origen en el ejercicio - Por pensiones
61 | 948 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
62 | 965 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcciones temporarias con origen en el ejercicio - Resto
63 | 982 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcc. temporarias con origen en ejerc. anteriores - Total
64 | 999 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
65 | 1016 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
66 | 1033 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
67 | 1050 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
68 | 1067 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: libertad de amortización (art. 102 LIS) - Disminuciones [00312] - Correcc. temporarias con origen en ejerc. anteriores - Resto
69 | 1084 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313]
70 | 1101 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcciones permanentes (excl. correcc. I. Sociedades)
71 | 1118 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcciones temporarias con origen en el ejercicio - Total
72 | 1135 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
73 | 1152 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
74 | 1169 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcciones temporarias con origen en el ejercicio - Por pensiones
75 | 1186 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
76 | 1203 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcciones temporarias con origen en el ejercicio - Resto
77 | 1220 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcc. temporarias con origen en ejerc. anteriores - Total
78 | 1237 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
79 | 1254 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
80 | 1271 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
81 | 1288 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
82 | 1305 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS)  - Aumentos [00313] - Correcc. temporarias con origen en ejerc. anteriores - Resto
83 | 1322 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314]
84 | 1339 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcciones permanentes (excl. correcc. I. Sociedades)
85 | 1356 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcciones temporarias con origen en el ejercicio - Total
86 | 1373 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
87 | 1390 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
88 | 1407 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcciones temporarias con origen en el ejercicio - Por pensiones
89 | 1424 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
90 | 1441 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcciones temporarias con origen en el ejercicio - Resto
91 | 1458 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcc. temporarias con origen en ejerc. anteriores - Total
92 | 1475 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
93 | 1492 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
94 | 1509 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
95 | 1526 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
96 | 1543 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: amortización acelerada (art. 103 LIS y DT 28ª LIS) - disminuciones  [00314] - Correcc. temporarias con origen en ejerc. anteriores - Resto
97 | 1560 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323]
98 | 1577 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcciones permanentes (excl. correcc. I. Sociedades)
99 | 1594 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcciones temporarias con origen en el ejercicio - Total
100 | 1611 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
101 | 1628 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
102 | 1645 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcciones temporarias con origen en el ejercicio - Por pensiones
103 | 1662 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
104 | 1679 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcciones temporarias con origen en el ejercicio - Resto
105 | 1696 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcc. temporarias con origen en ejerc. anteriores - Total
106 | 1713 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
107 | 1730 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
108 | 1747 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
109 | 1764 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
110 | 1781 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias (art. 104 LIS) - Aumentos [00323] - Correcc. temporarias con origen en ejerc. anteriores - Resto
111 | 1798 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324]
112 | 1815 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcciones permanentes (excl. correcc. I. Sociedades)
113 | 1832 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcciones temporarias con origen en el ejercicio - Total
114 | 1849 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
115 | 1866 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
116 | 1883 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcciones temporarias con origen en el ejercicio - Por pensiones
117 | 1900 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
118 | 1917 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcciones temporarias con origen en el ejercicio - Resto
119 | 1934 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcc. temporarias con origen en ejerc. anteriores - Total
120 | 1951 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
121 | 1968 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
122 | 1985 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
123 | 2002 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
124 | 2019 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas de reducida dimensión: pérdidas por deterioro créditos insolvencias  (art. 104 LIS) -  Disminuciones  [00324] - Correcc. temporarias con origen en ejerc. anteriores - Resto
125 | 2036 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Arrendamiento financiero: régimen especial  (art. 106 LIS)- Aumentos [00317]
126 | 2053 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Arrendamiento financiero: régimen especial (art. 106 LIS) - Disminuciones [00318]
127 | 2070 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen fiscal entidades de tenencia valores extranjeros - Aumentos [00385]
128 | 2087 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen fiscal entidades de tenencia valores extranjeros - Disminuciones [00386]
129 | 2104 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389]
130 | 2121 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcciones permanentes (excl. correcc. I. Sociedades)
131 | 2138 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcciones temporarias con origen en el ejercicio - Total
132 | 2155 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
133 | 2172 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
134 | 2189 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcciones temporarias con origen en el ejercicio - Por pensiones
135 | 2206 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
136 | 2223 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcciones temporarias con origen en el ejercicio - Resto
137 | 2240 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcc. temporarias con origen en ejerc. anteriores - Total
138 | 2257 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
139 | 2274 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
140 | 2291 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
141 | 2308 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
142 | 2325 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Aumentos [00389] - Correcc. temporarias con origen en ejerc. anteriores - Resto
143 | 2342 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390]
144 | 2359 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcciones permanentes (excl. correcc. I. Sociedades)
145 | 2376 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcciones temporarias con origen en el ejercicio - Total
146 | 2393 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
147 | 2410 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
148 | 2427 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcciones temporarias con origen en el ejercicio - Por pensiones
149 | 2444 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
150 | 2461 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcciones temporarias con origen en el ejercicio - Resto
151 | 2478 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcc. temporarias con origen en ejerc. anteriores - Total
152 | 2495 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
153 | 2512 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
154 | 2529 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
155 | 2546 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
156 | 2563 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente exentas (cap. XIV, título VII LIS) - Disminuciones [00390] - Correcc. temporarias con origen en ejerc. anteriores - Resto
157 | 2580 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Montes vecinales en mano común  (cap. XV, título VII LIS) - disminuciones [00396]
158 | 2597 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen entidades navieras en función del tonelaje (cap. XVI del titulo VII LIS) - Aumentos [00397]
159 | 2614 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen entidades navieras en función del tonelaje (cap. XVI del titulo VII LIS) - Disminuciones [00398]
160 | 2631 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Aportaciones y colaborac. A favor entidad sin fines lucrativos - Aumentos [00250]
161 | 2648 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Aportaciones y colaborac. A favor entidad sin fines lucrativos - Disminuciones [00251]
162 | 2665 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391]
163 | 2682 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcciones permanentes (excl. correcc. I. Sociedades)
164 | 2699 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcciones temporarias con origen en el ejercicio - Total
165 | 2716 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
166 | 2733 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
167 | 2750 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcciones temporarias con origen en el ejercicio - Por pensiones
168 | 2767 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
169 | 2784 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcciones temporarias con origen en el ejercicio - Resto
170 | 2801 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcc. temporarias con origen en ejerc. anteriores - Total
171 | 2818 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
172 | 2835 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
173 | 2852 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
174 | 2869 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
175 | 2886 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Aumentos [00391] - Correcc. temporarias con origen en ejerc. anteriores - Resto
176 | 2903 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392]
177 | 2920 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcciones permanentes (excl. correcc. I. Sociedades)
178 | 2937 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcciones temporarias con origen en el ejercicio - Total
179 | 2954 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
180 | 2971 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
181 | 2988 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcciones temporarias con origen en el ejercicio - Por pensiones
182 | 3005 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
183 | 3022 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcciones temporarias con origen en el ejercicio - Resto
184 | 3039 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcc. temporarias con origen en ejerc. anteriores - Total
185 | 3056 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
186 | 3073 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
187 | 3090 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
188 | 3107 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
189 | 3124 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Regimen fiscal entidades sin fines lucrativos (Ley 49/2002) - Disminuciones [00392] - Correcc. temporarias con origen en ejerc. anteriores - Resto
190 | 3141 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Cooperativas: Fondo de reserva obligatorio (Ley 20/1990) - Disminuciones [00400]
191 | 3158 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reservas inversiones en Canarias (Ley 19/1994) - Aumentos [00403]
192 | 3175 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reservas inversiones en Canarias (Ley 19/1994) - Disminuciones [00404]
193 | 3192 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención transmisión bienes inmuebles (DA 6ª LIS)- Aumentos [00518]
194 | 3209 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención transmisión bienes inmuebles (DA 6ª LIS) - Disminuciones  [00519]
195 | 3226 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas procedentes de transmisión de inmovilizado obtenidas por las Autoridades Portuarias (DA 68ª Ley 6/2018) - Disminuciones  [01824]
196 | 3243 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos (DT 1ª LIS) - Aumentos [00510]
197 | 3260 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos (DT 1ª LIS) - Disminuciones  [00512]
198 | 3277 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Adquisición de participaciones en entidades no residentes  (DT 14ª LIS) - Aumentos [00329]
199 | 3294 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Adquisición de participaciones en entidades no residentes  (DT 14ª LIS) - Disminuciones [00330]
200 | 3311 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reinversión de beneficios extraordinarios (DT 24ª LIS) - Aumentos [00365]
201 | 3328 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reinversión de beneficios extraordinarios (DT 24ª LIS)  - Disminuciones [01026]
202 | 3345 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por la primera aplicación de la Circular 4/2017 del Banco de España, a entidades de crédito - Aumentos [02129]
203 | 3362 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por la primera aplicación de la Circular 4/2017 del Banco de España, a entidades de crédito - Disminuciones [02130]
204 | 3379 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Entidades rég. atribución rentas constituidas extranjero, presencia territorio español - Aumentos [00409]
205 | 3396 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Entidades rég. atribución rentas constituidas extranjero, presencia territorio español - Disminuciones [00410]
206 | 3413 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Correcciones específicas entidades sometidas normativa foral - Aumentos [00411]
207 | 3430 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Correcciones específicas entidades sometidas normativa foral - Disminuciones [00412]
208 | 3447 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Eliminaciones pdte. de incorporar sdes.que dejen de pertenecer a un grupo - Aumentos [01027]
209 | 3464 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias -  Eliminaciones pdte. de incorporar sdes.que dejen de pertenecer a un grupo - Disminuciones  [01028]
210 | 3481 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413]
211 | 3498 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcciones permanentes (excl. correcc. I. Sociedades)
212 | 3515 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcciones temporarias con origen en el ejercicio - Total
213 | 3532 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
214 | 3549 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
215 | 3566 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcciones temporarias con origen en el ejercicio - Por pensiones
216 | 3583 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
217 | 3600 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcciones temporarias con origen en el ejercicio - Resto
218 | 3617 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcc. temporarias con origen en ejerc. anteriores - Total
219 | 3634 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
220 | 3651 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
221 | 3668 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
222 | 3685 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
223 | 3702 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Aumentos [00413] - Correcc. temporarias con origen en ejerc. anteriores - Resto
224 | 3719 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414]
225 | 3736 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcciones permanentes (excl. correcc. I. Sociedades)
226 | 3753 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcciones temporarias con origen en el ejercicio - Total
227 | 3770 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcciones temporarias con origen en el ejercicio - Por amortizaciones
228 | 3787 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcciones temporarias con origen en el ejercicio - Por deterioros de valor
229 | 3804 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcciones temporarias con origen en el ejercicio - Por pensiones
230 | 3821 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcciones temporarias con origen en el ejercicio - Por fondo de comercio
231 | 3838 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcciones temporarias con origen en el ejercicio - Resto
232 | 3855 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcc. temporarias con origen en ejerc. anteriores - Total
233 | 3872 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcc. temporarias con origen en ejerc. anteriores - Por amortizaciones
234 | 3889 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcc. temporarias con origen en ejerc. anteriores - Por deterioros de valor
235 | 3906 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcc. temporarias con origen en ejerc. anteriores - Por pensiones
236 | 3923 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcc. temporarias con origen en ejerc. anteriores - Por fondo de comercio
237 | 3940 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta. pérdidas y ganancias  - Disminuciones [00414] - Correcc. temporarias con origen en ejerc. anteriores - Resto
238 | 3957 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Total correcciones al resultado cta. pérdidas y ganancias - Aumentos [00417]
239 | 3974 | 17 | Num | Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Total correcciones al resultado cta. pérdidas y ganancias - Disminuciones [00418]
240 | 3991 | 17 | N | Liquidación II -  Entidades navieras en función del tonelaje - B.I. actividades o rentas en régimen general  [00578]
241 | 4008 | 17 | N | Liquidación II -  Entidades navieras en función del tonelaje - B.I. derivada del régimen especial  [00579]
242 | 4025 | 17 | N | Liquidación II -  Entidades que forman parte de grupos de consolidac.fiscal -  B.I. indiv.a integrar por entidades que forman parte del grupo - [01029]
243 | 4042 | 17 | N | Liquidación II -  Entidades que forman parte de grupos de consolidac.fiscal - Eliminaciones e incorporaciones  correspondientes a la entidad -  [01030]
244 | 4059 | 17 | N | Liquidación II -  Entidades que forman parte de grupos de consolidac.fiscal - Entigración individual de las dotaciones del art. 11.12 LIS -  [01031]
245 | 4076 | 17 | N | Liquidación II -  Base imponible - B.I. antes de la compensación de bases imponibles negativas [00550]
246 | 4093 | 17 | N | Liquidación II -  Base imponible - Parte de la base imponible del período impositivo que tributa al tipo general (antes de compensación de bases imponibles negativas)
247 | 4110 | 17 | N | Liquidación II -  Base imponible - Parte de la base imponible del período impositivo que tributa al tipo del 0% (antes de compensación de bases imponibles negativas)
248 | 4127 | 17 | N | Liquidación II -  Base imponible - Reserva de capitalización [01032]
249 | 4144 | 17 | Num | Liquidación II -  Base imponible - Compensación de bases imponibles negativas períodos anteriores  [00547]
250 | 4161 | 17 | N | Liquidación II -  Base imponible - Base imponible  [00552]
251 | 4178 | 17 | N | Liquidación II -  Base Imponible  - Entidades Reducida dimensión - Reserva de nivelación - Aumentos  [01033]
252 | 4195 | 17 | N | Liquidación II -  Base Imponible  - Entidades Reducida dimensión - Reserva de nivelación - Disminuciones  [01034]
253 | 4212 | 200 | An | RESERVADO PARA LA AEAT
254 | 4412 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20013000>"
Total: |  | 4423

# DP200014

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "14000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria. En blanco |  | En blanco
6 | 13 | 17 | N | Liquidación III - Base Imponible - Entidades Reducida dimensión - Base imponible después de la reserva de nivelación - Disminuciones  [01330]
7 | 30 | 17 | N | Liquidación III - Base imponible - Sólo sociedades cooperativas - Resultados cooperativos - Disminuciones [00553]
8 | 47 | 17 | N | Liquidación III - Base imponible - Sólo sociedades cooperativas - Resultados extracooperativos - Disminuciones [00554]
9 | 64 | 17 | N | Liquidación III - Base imponible - Agrupaciones españolas interés economico y UTES - Socios residentes - Disminuciones [00555]
10 | 81 | 17 | N | Liquidación III - Base imponible - Agrupaciones españolas interés economico y UTES - Socios no residentes - Disminuciones [00556]
11 | 98 | 17 | N | Liquidación III - Base imponible - Sólo entidades ZEC - Base imponible a tipo de gravamen especial - Disminuciones [00559]
12 | 115 | 17 | N | Liquidación III - Base imponible - Sólo SOCIMIS - Parte B.I. del periodo impositivo que tributa al tipo general - Disminuciones [00520]
13 | 132 | 17 | N | Liquidación III - Base imponible - Sólo SOCIMIS - Parte B.I. del periodo impositivo que tributa al tipo del 0% - Disminuciones  [00521]
14 | 149 | 17 | N | Liquidación III - Base imponible - Rentas correspondientes a quitas por acuerdo con acreedores no vinculados (art. 26.1 LIS) - Disminuciones   [00545]
15 | 166 | 17 | N | Liquidación III - Base imponible - Rentas correspondientes a la reversión de deterioros (DT 16ª.8 LIS) - Disminuciones [01509]
16 | 183 | 4 | Num | Liquidación III - Tipo de gravamen - Tipo de gravamen [00558]
17 | 187 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Cuota íntegra previa [00560]
18 | 204 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Pérdidas por deterioro del art.13.1 LIS y provisiones y gastos - Aumentos [00210]
19 | 221 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Pérdidas por deterioro del art.13.1 LIS y provisiones y gastos - Disminuciones [00480]
20 | 238 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Aplicación del límite del art.11.12 LIS a las perdidas por deterioro del art. 13.1 LIS  y provisiones y gastos - Aumentos [00408]
21 | 255 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Aplicación del límite del art.11.12 LIS a las perdidas por deterioro del art. 13.1 LIS  y provisisones y gastos - Disminuciones [01037]
22 | 272 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Rentas corresp. a quitas por acuerdo con acreedores no vinculados cooperativas (a nivel cuota) (D.A. 8ª Ley 20/1990) - Disminuciones [00593]
23 | 289 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Rentas correspondientes a la reversión de deterioros cooperativas (a nivel cuota) (DT 16ª.8 LIS) [01510]
24 | 306 | 17 | Num | Liquidación III - Sólo sociedades cooperativas - Compensación de cuotas por pérdidas de cooperativas [00561]
25 | 323 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Reserva de nivelación convertido en cuotas (solo entidades del art. 101 LIS) - Aumentos [01285]
26 | 340 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Reserva de nivelación convertido en cuotas (solo entidades del art. 101 LIS) - Disminuciones [01286]
27 | 357 | 17 | N | Liquidación III - Sólo sociedades cooperativas - Cuota íntegra previa después de la reserva de nivelación - Disminuciones [01331]
28 | 374 | 17 | N | Liquidación III - Cuota íntegra - Cuota íntegra [00562]
29 | 391 | 17 | Num | Liquidación III - Cuota íntegra - Incremento por incumplimiento reserva de nivelación [01038]
30 | 408 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificación por rentas obtenidas en Ceuta y Melilla (art. 33 LIS) [00567]
31 | 425 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificación por prestación de servicios (art. 34 LIS) [00568]
32 | 442 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificación rendimientos por venta de bienes corporales producidos en Canarias [00563]
33 | 459 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones sociedades cooperativas [00566]
34 | 476 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones entidades dedicadas al arrendamiento de viviendas [00576]
35 | 493 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Otras bonificaciones [00569]
36 | 510 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. interna de períodos anteriores aplicada en el ejercicio (art. 30 RDL 4/ 2004) [00570]
37 | 527 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. interna de períodos anteriores aplicada en el ejercicio (DT 23.1 LIS) [01344]
38 | 544 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. interna  generada y aplicada en el ejercicio (DT 23.1 LIS) [01280]
39 | 561 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. internacional de periodos anteriores aplicada en el ejercicio (art. 31 y 32 RDL 4/ 2004) [00572]
40 | 578 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. internacional periodos anteriores aplicada en el ejercicio (art. 31 y 32 LIS) [00571]
41 | 595 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. internacional generada y aplicada en el ejercicio actual(art. 31 y 32 LIS) [00573]
42 | 612 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - Transparencia fiscal internacional (art. 100.101 LIS) [00575]
43 | 629 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. interna intersocietaria al 5/10 % (cooperativas) [00577]
44 | 646 | 17 | Num | Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones empresas navieras en Canarias  (art. 76 Ley 19/1994) [00581]
45 | 663 | 17 | N | Liquidación III - Bonificaciones/Deducciones doble imposición - Cuota íntegra ajustada positiva [00582]
46 | 680 | 17 | Num | Liquidación III - Otras deducciones - Apoyo fiscal a la inversión y otras deducciones [00583]
47 | 697 | 17 | Num | Liquidación III - Otras deducciones - Deducción DT 24.7 L.I.S. art.42 y art. 36 ter Ley 43/95 [00585]
48 | 714 | 17 | Num | Liquidación III - Otras deducciones - Deducciones DT 24.1 LIS D.T. 8ª  RDL 4/2004 [00584]
49 | 731 | 17 | Num | Liquidación III - Otras deducciones - Deducciones con límite del Capítulo IV Título VI RDL 4/2004 y LIS [00588]
50 | 748 | 17 | Num | Liquidación III - Otras deducciones - Deducciones por producc. Cinematograf. Extranjeras (art. 36.2 LIS) [01039]
51 | 765 | 17 | Num | Liquidación III - Otras deducciones - Deducción donaciones a entidades sin fines de lucro [00565]
52 | 782 | 17 | Num | Liquidación III - Otras deducciones - Deducciones inversión Canarias (Ley 20/1991) [00590]
53 | 799 | 17 | Num | Liquidación III - Otras deducciones - Deducciones especifícas de las entidades sometidas a normativa foral [00399]
54 | 816 | 17 | Num | Liquidación III - Otras deducciones - Deducciones excluidas de límite I+D [00082]
55 | 833 | 17 | Num | Liquidación III - Otras deducciones - Deducciones por reversión de medidas temporales  DT 37ª.1 LIS [01040]
56 | 850 | 17 | Num | Liquidación III - Otras deducciones - Deducciones por reversión de medidas temporales  DT 37ª.2 LIS [01041]
57 | 867 | 17 | N | Liquidación III - Otras deducciones - Cuota líquida positiva [00592]
58 | 884 | 17 | Num | Deducciones sujetas a límite. Régimen Canarias. Excluidas deducciones I+D+i de la página 17. Deducción generada en el período impositivo. Investigación y desarrollo [C]
59 | 901 | 17 | Num | Deducciones sujetas a límite. Régimen Canarias. Excluidas deducciones I+D+i de la página 17. Deducción generada en el período impositivo. Innovación tecnológica [D]
60 | 918 | 166 | An | RESERVADO PARA LA AEAT
61 | 1084 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20014000>"
Total: |  | 1095

# DP200014B

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "14B00"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria. En blanco |  | En blanco
6 | 13 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por rendimientos del capital mobiliario - Efectuados a la entidad [01785]
7 | 30 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por rendimientos del capital mobiliario - Imputados por AIEs y UTEs [01786]
8 | 47 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por arrendamientos de inmuebles urbanos - Efectuados a la entidad [01787]
9 | 64 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por arrendamientos de inmuebles urbanos - Imputados por AIEs y UTEs [01788]
10 | 81 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por rendimientos del capital mobiliario atribuidas por entidades en atribución de rentas - Efectuados a la entidad [01789]
11 | 98 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por rendimientos del capital mobiliario atribuidas por entidades en atribución de rentas - Imputados por AIEs y UTEs [01790]
12 | 115 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por arrendamientos de inmuebles urbanos atribuidas por entidades en atribución de rentas - Efectuados a la entidad [01791]
13 | 132 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por arrendamientos de inmuebles urbanos atribuidas por entidades en atribución de rentas - Imputados por AIEs y UTEs [01792]
14 | 149 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por otros conceptos diferentes a los rendimientos del capital mobiliario o a los arrendamientos de inmuebles urbanos atribuidas por entidades en atribución de rentas - Efectuados a la entidad [01793]
15 | 166 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por otros conceptos diferentes a los rendimientos del capital mobiliario o a los arrendamientos de inmuebles urbanos atribuidas por entidades en atribución de rentas - Imputados por AIEs y UTEs [01794]
16 | 183 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones e ingresos a cuenta participaciones IIC - Efectuados a la entidad [01795]
17 | 200 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones e ingresos a cuenta participaciones IIC - Imputados por AIEs y UTEs [01796]
18 | 217 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones sobre los premios de determinadas loterías y apuestas - Efectuados a la entidad [00597]
19 | 234 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones sobre los premios de determinadas loterías y apuestas - Imputados por AIEs y UTEs [01797]
20 | 251 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por otros conceptos NO incluidos en las casillas anteriores - Efectuados a la entidad [01798]
21 | 268 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Retenciones por otros conceptos NO incluidos en las casillas anteriores - Imputados por AIEs y UTEs [01799]
22 | 285 | 17 | N | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Cuota del ejercicio a ingresar o a devolver - Estado [00599]
23 | 302 | 17 | N | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Cuota del ejercicio a ingresar o a devolver - D. Forales/Navarra (Totales)  [00600]
24 | 319 | 17 | Num | Liquidación IV - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 1er. pago fraccionado - Estado [00601]
25 | 336 | 17 | Num | Liquidación IV - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 1er. Pago fraccionado - D. Forales/Navarra (Totales) [00602]
26 | 353 | 17 | Num | Liquidación IV - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 2er. Pago fraccionado - Estado [00603]
27 | 370 | 17 | Num | Liquidación IV - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 2er. Pago fraccionado -  D. Forales/Navarra (Totales) [00604]
28 | 387 | 17 | Num | Liquidación IV - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 3er. Pago fraccionado - Estado [00605]
29 | 404 | 17 | Num | Liquidación IV - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 3er. Pago fraccionado - D. Forales/Navarra (Totales) [00606]
30 | 421 | 17 | N | Liquidación IV - Pagos fraccionados/Cuota diferencial - Cuota diferencial  - Estado [00611]
31 | 438 | 17 | N | Liquidación IV - Pagos fraccionados/Cuota diferencial - Cuota diferencial  - D. Forales/Navarra (Totales) [00612]
32 | 455 | 17 | Num | Liquidación IV - Líquido a ingresar o a devolver - Incremento por pérdida beneficios fiscales períodos anteriores  - Estado [00615]
33 | 472 | 17 | Num | Liquidación IV - Líquido a ingresar o a devolver - Incremento por pérdida beneficios fiscales períodos anteriores  - D. Forales/Navarra (Totales) [00616]
34 | 489 | 17 | Num | Liquidación IV - Líquido a ingresar o a devolver - Incremento por incumplimiento de requisitos SOCIMI  -  Estado [00633]
35 | 506 | 17 | Num | Liquidación IV - Líquido a ingresar o a devolver - Incremento por incumplimiento de requisitos SOCIMI  -  D. Forales/Navarra (Totales) [00642]
36 | 523 | 17 | Num | Liquidación IV - Líquido a ingresar o a devolver - Intereses de demora  - Estado [00617]
37 | 540 | 17 | Num | Liquidación IV - Líquido a ingresar o a devolver - Intereses de demora  - D. Forales/Navarra (Totales) [00618]
38 | 557 | 17 | N | Liquidación IV - Líquido a ingresar o a devolver - Importe ingreso/devolución efectuada de la declaración originaria  - Estado [00619]
39 | 574 | 17 | N | Liquidación IV - Líquido a ingresar o a devolver - Importe ingreso/devolución efectuada de la declaración originaria  - D. Forales/Navarra (Totales) [00620]
40 | 591 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Abono deducciones I+D+i por insuficiencia de cuota - Total  [01234]
41 | 608 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Abono deducciones I+D+i por insuficiencia de cuota - Estado  [00083]
42 | 625 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Abono deducciones I+D+i por insuficiencia de cuota  - D. Forales/Navarra (Totales)  [01332]
43 | 642 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Abono deducciones por producciones cinematográficas extranjeras  - Total  [01200]
44 | 659 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Abono deducciones por producciones cinematográficas extranjeras - Estado  [01042]
45 | 676 | 17 | Num | Liquidación IV - Cuota del ejercicio a ingresar o a devolver - Abono deducciones por producciones  cinematográficas extranjeras  -  D. Forales/Navarra [01333]
46 | 693 | 17 | N | Liquidación IV - Líquido a ingresar o a devolver  - Estado [00621]
47 | 710 | 17 | N | Liquidación IV - Líquido a ingresar o a devolver  - D. Forales/Navarra (Totales) [00622]
48 | 727 | 17 | N | Liquidación IV - Abono por conversión de activos por impuesto diferido en crédito exigible frente a la admon.tribut. (art. 130 LIS)  -  Total  [00150]
49 | 744 | 17 | N | Liquidación IV - Abono por conversión de activos por impuesto diferido en crédito exigible frente a la admon.tribut. (art. 130 LIS)  -  Estado  [01020]
50 | 761 | 17 | N | Liquidación IV - Abono por conversión de activos por impuesto diferido en crédito exigible frente a la admon.tribut. (art. 130 LIS)  - D. Forales/Navarra (Totales)  [001043]
51 | 778 | 17 | N | Liquidación IV - Compensación por conversión de activos por impuesto diferido en crédito exigible frente a la admon.tribut. (art. 130 LIS)  - Total  [00506]
52 | 795 | 17 | N | Liquidación IV - Compensación por conversión de activos por impuesto diferido en crédito exigible frente a la admon.tribut. (art. 130 LIS)  - Estado  [01021]
53 | 812 | 17 | N | Liquidación IV - Compensación por conversión de activos por impuesto diferido en crédito exigible frente a la admon.tribut. (art. 130 LIS)  - D. Forales/Navarra (Totales)  [001044]
54 | 829 | 34 | An | RESERVADO PARA LA AEAT
55 | 863 | 166 | An | RESERVADO PARA LA AEAT
56 | 1029 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20014B00>"
Total: |  | 1040

# DP200015

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. Constante "<T" . Campo OBLIGATORIO | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "15000"
4 | 11 | 1 | An | Fin de identificador de modelo. Constante: ">" .Campo OBLIGATORIO | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | Num | Detalle compensación bases imponibles negativas - 1997 - Pendiente aplicación a principio del período/generada en el período [00640]
7 | 30 | 17 | Num | Detalle compensación bases imponibles negativas - 1997 - Aplicado en esta liquidación [00641]
8 | 47 | 17 | Num | Detalle compensación bases imponibles negativas - 1997 - Pendiente aplicación en períodos futuros [00548]
9 | 64 | 17 | Num | Detalle compensación bases imponibles negativas - 1998 - Pendiente aplicación a principio del período/generada en el período [00643]
10 | 81 | 17 | Num | Detalle compensación bases imponibles negativas - 1998 - Aplicado en esta liquidación [00644]
11 | 98 | 17 | Num | Detalle compensación bases imponibles negativas - 1998 - Pendiente aplicación en períodos futuros [00645]
12 | 115 | 17 | Num | Detalle compensación bases imponibles negativas - 1999 - Pendiente aplicación a principio del período/generada en el período [00646]
13 | 132 | 17 | Num | Detalle compensación bases imponibles negativas - 1999 - Aplicado en esta liquidación [00647]
14 | 149 | 17 | Num | Detalle compensación bases imponibles negativas - 1999 - Pendiente aplicación en períodos futuros [00648]
15 | 166 | 17 | Num | Detalle compensación bases imponibles negativas - 2000 - Pendiente aplicación a principio del período/generada en el período [00649]
16 | 183 | 17 | Num | Detalle compensación bases imponibles negativas - 2000 - Aplicado en esta liquidación [00650]
17 | 200 | 17 | Num | Detalle compensación bases imponibles negativas - 2000 - Pendiente aplicación en períodos futuros [00651]
18 | 217 | 17 | Num | Detalle compensación bases imponibles negativas - 2001 - Pendiente aplicación a principio del período/generada en el período [00652]
19 | 234 | 17 | Num | Detalle compensación bases imponibles negativas - 2001 - Aplicado en esta liquidación [00653]
20 | 251 | 17 | Num | Detalle compensación bases imponibles negativas - 2001 - Pendiente aplicación en períodos futuros [00654]
21 | 268 | 17 | Num | Detalle compensación bases imponibles negativas - 2002 - Pendiente aplicación a principio del período/generada en el período [00655]
22 | 285 | 17 | Num | Detalle compensación bases imponibles negativas - 2002 - Aplicado en esta liquidación [00656]
23 | 302 | 17 | Num | Detalle compensación bases imponibles negativas - 2002 - Pendiente aplicación en períodos futuros [00657]
24 | 319 | 17 | Num | Detalle compensación bases imponibles negativas - 2003 - Pendiente aplicación a principio del período/generada en el período [00658]
25 | 336 | 17 | Num | Detalle compensación bases imponibles negativas - 2003 - Aplicado en esta liquidación [00659]
26 | 353 | 17 | Num | Detalle compensación bases imponibles negativas - 2003 - Pendiente aplicación en períodos futuros [00660]
27 | 370 | 17 | Num | Detalle compensación bases imponibles negativas - 2004 - Pendiente aplicación a principio del período/generada en el período [00661]
28 | 387 | 17 | Num | Detalle compensación bases imponibles negativas - 2004 - Aplicado en esta liquidación [00662]
29 | 404 | 17 | Num | Detalle compensación bases imponibles negativas - 2004 - Pendiente aplicación en períodos futuros [00663]
30 | 421 | 17 | Num | Detalle compensación bases imponibles negativas - 2005 - Pendiente aplicación a principio del período/generada en el período [00664]
31 | 438 | 17 | Num | Detalle compensación bases imponibles negativas - 2005 - Aplicado en esta liquidación [00665]
32 | 455 | 17 | Num | Detalle compensación bases imponibles negativas - 2005 - Pendiente aplicación en períodos futuros [00666]
33 | 472 | 17 | Num | Detalle compensación bases imponibles negativas - 2006 - Pendiente aplicación a principio del período/generada en el período [00667]
34 | 489 | 17 | Num | Detalle compensación bases imponibles negativas - 2006 - Aplicado en esta liquidación [00668]
35 | 506 | 17 | Num | Detalle compensación bases imponibles negativas - 2006 - Pendiente aplicación en períodos futuros [00669]
36 | 523 | 17 | Num | Detalle compensación bases imponibles negativas - 2007 - Pendiente aplicación a principio del período/generada en el período [00743]
37 | 540 | 17 | Num | Detalle compensación bases imponibles negativas - 2007 - Aplicado en esta liquidación [00747]
38 | 557 | 17 | Num | Detalle compensación bases imponibles negativas - 2007 - Pendiente aplicación en períodos futuros [00748]
39 | 574 | 17 | Num | Detalle compensación bases imponibles negativas - 2008 - Pendiente aplicación a principio del período/generada en el período [00275]
40 | 591 | 17 | Num | Detalle compensación bases imponibles negativas - 2008 - Aplicado en esta liquidación [00276]
41 | 608 | 17 | Num | Detalle compensación bases imponibles negativas - 2008 - Pendiente aplicación en períodos futuros [00277]
42 | 625 | 17 | Num | Detalle compensación bases imponibles negativas - 2009 - Pendiente de aplicación a principio del período/generada en el período [00608]
43 | 642 | 17 | Num | Detalle compensación bases imponibles negativas - 2009 - Aplicado en esta liquidación [00609]
44 | 659 | 17 | Num | Detalle compensación bases imponibles negativas - 2009 - Pendiente aplicación en períodos futuros [00610]
45 | 676 | 17 | Num | Detalle compensación bases imponibles negativas - 2010 - Pendiente aplicación a principio del período/generada en el período [00704]
46 | 693 | 17 | Num | Detalle compensación bases imponibles negativas - 2010 - Aplicado en esta liquidación [00705]
47 | 710 | 17 | Num | Detalle compensación bases imponibles negativas - 2010 - Pendiente aplicación en períodos futuros [00706]
48 | 727 | 17 | Num | Detalle compensación bases imponibles negativas - 2011 - Pendiente aplicación a principio del período/generada en el período [00013]
49 | 744 | 17 | Num | Detalle compensación bases imponibles negativas - 2011 - Aplicado en esta liquidación [00014]
50 | 761 | 17 | Num | Detalle compensación bases imponibles negativas - 2011 - Pendiente aplicación en períodos futuros [00015]
51 | 778 | 17 | Num | Detalle compensación bases imponibles negativas - 2012 - Pendiente aplicación a principio del período/generada en el período [00725]
52 | 795 | 17 | Num | Detalle compensación bases imponibles negativas - 2012 - Aplicado en esta liquidación [00726]
53 | 812 | 17 | Num | Detalle compensación bases imponibles negativas - 2012 - Pendiente aplicación en períodos futuros [00727]
54 | 829 | 17 | Num | Detalle compensación bases imponibles negativas - 2013 - Pendiente aplicación a principio del período/generada en el período [00534]
55 | 846 | 17 | Num | Detalle compensación bases imponibles negativas - 2013 - Aplicado en esta liquidación [00535]
56 | 863 | 17 | Num | Detalle compensación bases imponibles negativas - 2013 - Pendiente aplicación en períodos futuros [00536]
57 | 880 | 17 | Num | Detalle compensación bases imponibles negativas - 2014 - Pendiente aplicación a principio del período/generada en el período [00607]
58 | 897 | 17 | Num | Detalle compensación bases imponibles negativas - 2014 - Aplicado en esta liquidación [00675]
59 | 914 | 17 | Num | Detalle compensación bases imponibles negativas - 2014 - Pendiente aplicación en períodos futuros [00699]
60 | 931 | 17 | Num | Detalle compensación bases imponibles negativas - 2015 - Pendiente aplicación a principio del período/generada en el período [01045]
61 | 948 | 17 | Num | Detalle compensación bases imponibles negativas - 2015 - Aplicado en esta liquidación [01046]
62 | 965 | 17 | Num | Detalle compensación bases imponibles negativas - 2015 - Pendiente aplicación en períodos futuros [01047]
63 | 982 | 17 | Num | Detalle compensación bases imponibles negativas - 2016 - Pendiente aplicación a principio del período/generada en el período [01519]
64 | 999 | 17 | Num | Detalle compensación bases imponibles negativas - 2016 - Aplicado en esta liquidación [01520]
65 | 1016 | 17 | Num | Detalle compensación bases imponibles negativas - 2016 - Pendiente aplicación en períodos futuros [01521]
66 | 1033 | 17 | Num | Detalle compensación bases imponibles negativas - 2017 - Pendiente aplicación a principio del período/generada en el período [01592]
67 | 1050 | 17 | Num | Detalle compensación bases imponibles negativas - 2017 - Aplicado en esta liquidación [01593]
68 | 1067 | 17 | Num | Detalle compensación bases imponibles negativas - 2017 - Pendiente aplicación en períodos futuros [01594]
69 | 1084 | 17 | Num | Detalle compensación bases imponibles negativas - 2018(*) - Pendiente aplicación a principio del período/generada en el período [01825]
70 | 1101 | 17 | Num | Detalle compensación bases imponibles negativas - 2018(*) - Aplicado en esta liquidación [01826]
71 | 1118 | 17 | Num | Detalle compensación bases imponibles negativas - 2018(*) - Pendiente aplicación en períodos futuros [01827]
72 | 1135 | 17 | Num | Detalle compensación bases imponibles negativas - TOTAL - Pendiente aplicación a principio del período/generada en el período [00670]
73 | 1152 | 17 | Num | Detalle compensación bases imponibles negativas - TOTAL - Aplicado en esta liquidación [00547]
74 | 1169 | 17 | Num | Detalle compensación bases imponibles negativas - TOTAL - Pendiente de aplicación en períodos futuros [00671]
75 | 1186 | 17 | Num | Detalle compensación bases imponibles negativas - 2018 - Pendiente aplicación a principio del período/generada en el período [01048]
76 | 1203 | 17 | Num | Detalle compensación bases imponibles negativas - 2018 - Pendiente aplicación en períodos futuros [01049]
77 | 1220 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - Deducción pendiente [00104]
78 | 1237 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - Tipo gravamen período generación [00105]
79 | 1241 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - 2018 - Deducción pendiente [00846]
80 | 1258 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - Aplicado en esta liquidación [00847]
81 | 1275 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2008 - Pendiente aplic en períodos futuros [00848]
82 | 1292 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - Deducción pendiente [00106]
83 | 1309 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - Tipo gravamen período generación [00107]
84 | 1313 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - 2018 - Deducción pendiente [00282]
85 | 1330 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - Aplicado en esta liquidación [00283]
86 | 1347 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2009 - Pendiente aplic. en períodos futuros [00284]
87 | 1364 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - Deducción pendiente [00108]
88 | 1381 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - Tipo gravamen período generación [00109]
89 | 1385 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - 2018 - Deducción pendiente [00702]
90 | 1402 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - Aplicado en esta liquidación [00703]
91 | 1419 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2010 - Pendiente aplic. en períodos futuros [00707]
92 | 1436 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - Deducción pendiente [00110]
93 | 1453 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - Tipo gravamen período generación [00111]
94 | 1457 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - 2018 - Deducción pendiente [00071]
95 | 1474 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - Aplicado en esta liquidación [00187]
96 | 1491 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2011 - Pendiente aplic. en períodos futuros [00300]
97 | 1508 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - Deducción pendiente [00112]
98 | 1525 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - Tipo gravamen período generación [113]
99 | 1529 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - 2018 - Deducción pendiente [00025]
100 | 1546 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - Aplicado en esta liquidación [00026]
101 | 1563 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2012 - Pendiente aplic. en períodos futuros [00027]
102 | 1580 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - Deducción pendiente [00114]
103 | 1597 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - Tipo gravamen período generación [00115]
104 | 1601 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - 2018 - Deducción pendiente [00714]
105 | 1618 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - Aplicado en esta liquidación [00715]
106 | 1635 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2013 - Pendiente aplic. en períodos futuros [00716]
107 | 1652 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014 - Deducción pendiente [00735]
108 | 1669 | 4 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014 - Tipo gravamen período generación [00920]
109 | 1673 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014 - 2018 - Deducción pendiente [00736]
110 | 1690 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014 - Aplicado en esta liquidación [00737]
111 | 1707 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - DI interna 2014  - Pendiente aplic. en períodos futuros [00738]
112 | 1724 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - Total - Deducción pendiente [00116]
113 | 1741 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - Total - 2018 - Deducción pendiente [00117]
114 | 1758 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - Total -  Aplicado en esta liquidación [00570]
115 | 1775 | 17 | Num | Deducciones doble imposición interna RDL 4/2004 - Total -  Pendiente aplic. en períodos futuros [00118]
116 | 1792 | 7 | Num | Deducciones doble imposición interna - Tipo de gravamen 2018  [00103]
117 | 1799 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2015 - Deducción pendiente [00101]
118 | 1816 | 4 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2015 - Tipo gravamen período generación [00102]
119 | 1820 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2015 - 2018 - Deducción pendiente [00119]
120 | 1837 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2015 - Aplicado en esta liquidación [00120]
121 | 1854 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2015  - Pendiente aplic. en períodos futuros [00121]
122 | 1871 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2016 - Deducción pendiente [00122]
123 | 1888 | 4 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2016 - Tipo gravamen período generación [00123]
124 | 1892 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2016 - 2018 - Deducción pendiente [00124]
125 | 1909 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2016 - Aplicado en esta liquidación [00125]
126 | 1926 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2016 - Pendiente aplic. en períodos futuros [00126]
127 | 1943 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2017 - Deducción pendiente [01595]
128 | 1960 | 4 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2017 - Tipo gravamen período generación [1596]
129 | 1964 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2017 - 2018 - Deducción pendiente [01597]
130 | 1981 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2017 - Aplicado en esta liquidación [01598]
131 | 1998 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2017 - Pendiente aplic. en períodos futuros [01599]
132 | 2015 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2018(*) - Deducción pendiente [01828]
133 | 2032 | 4 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2018(*) - Tipo gravamen período generación [1829]
134 | 2036 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2018(*) - 2018 - Deducción pendiente [01830]
135 | 2053 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2018(*) - Aplicado en esta liquidación [01831]
136 | 2070 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2018(*)  - Pendiente aplic. en períodos futuros [01832]
137 | 2087 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - Total - Deducción pendiente [01342]
138 | 2104 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - Total - 2018 - Deducción pendiente [01343]
139 | 2121 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - Total -  Aplicado en esta liquidación [01344]
140 | 2138 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - Total -  Pendiente aplic. en períodos futuros [01345]
141 | 2155 | 7 | Num | Deducciones doble imposición interna (DT 23.1 LIS) -  Tipo de gravamen 2018  [00103]
142 | 2162 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2018 - Deducción generada [00127]
143 | 2179 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2018 - Aplicado en esta liquidación [00128]
144 | 2196 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - DI interna 2018  - Pendiente aplic. en períodos futuros [00129]
145 | 2213 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - Total - Deducción generada [01346]
146 | 2230 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - Total - Aplicado en esta liquidación [01280]
147 | 2247 | 17 | Num | Deducciones doble imposición interna (DT 23.1 LIS) - Total  - Pendiente aplic. en períodos futuros [01347]
148 | 2264 | 200 | An | RESERVADO PARA LA AEAT
149 | 2464 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20015000>"
Total: |  | 2475

# DP200016

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página.  Campo OBLIGATORIO | OBLIGATORIO | Constante "16000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - Deducción pendiente  [00153]
7 | 30 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - Tipo gravamen período generación [00728]
8 | 34 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - 2018 Deducción pendiente [00637]
9 | 51 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - Aplicado en esta liquidación [00638]
10 | 68 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2005 - Pendiente aplic. en períodos futuros [00639]
11 | 85 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - Deducción pendiente [00154]
12 | 102 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - Tipo gravamen período generación [00729]
13 | 106 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - 2018 Deducción pendiente [00849]
14 | 123 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - Aplicado en esta liquidación [00894]
15 | 140 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2006 - Pendiente aplic. en períodos futuros [00197]
16 | 157 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - Deducción pendiente [00155]
17 | 174 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - Tipo gravamen período generación [00730]
18 | 178 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - 2018 Deducción pendiente [00285]
19 | 195 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - Aplicado en esta liquidación [00286]
20 | 212 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2007 - Pendiente aplic. en períodos futuros [00287]
21 | 229 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - Deducción pendiente  [00156]
22 | 246 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - Tipo gravamen período generación [00731]
23 | 250 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - 2018 Deducción pendiente [00825]
24 | 267 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - Aplicado en esta liquidación [00826]
25 | 284 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2008 - Pendiente aplic. en períodos futuros [00827]
26 | 301 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009 - Deducción pendiente  [00157]
27 | 318 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009 - Tipo gravamen período generación [00732]
28 | 322 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009 - 2018 Deducción pendiente [00001]
29 | 339 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009 - Aplicado en esta liquidación [00002]
30 | 356 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2009- Pendiente aplic. en períodos futuros [00003]
31 | 373 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- Deducción pendiente  [00158]
32 | 390 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- Tipo gravamen período generación [00733]
33 | 394 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- 2018 Deducción pendiente [00028]
34 | 411 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- Aplicado en esta liquidación [00029]
35 | 428 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2010- Pendiente aplic. en períodos futuros [00030]
36 | 445 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - Deducción pendiente  [00159]
37 | 462 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - Tipo gravamen período generación [00734]
38 | 466 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - 2018 Deducción pendiente [00717]
39 | 483 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - Aplicado en esta liquidación [00718]
40 | 500 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2011 - Pendiente aplic. en períodos futuros [00719]
41 | 517 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - Deducción pendiente  [00720]
42 | 534 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - Tipo gravamen período generación [00721]
43 | 538 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - 2018 Deducción pendiente [00722]
44 | 555 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - Aplicado en esta liquidación [00723]
45 | 572 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2012 - Pendiente aplic. en períodos futuros [00724]
46 | 589 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2013 - Deducción pendiente  [00739]
47 | 606 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2013 - Tipo gravamen período generación [00921]
48 | 610 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2013 - 2018 Deducción pendiente [00740]
49 | 627 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2013 - Aplicado en esta liquidación [00741]
50 | 644 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2013 - Pendiente aplic. en períodos futuros [00742]
51 | 661 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2014 - Deducción pendiente  [00134]
52 | 678 | 4 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2014 - Tipo gravamen período generación [00926]
53 | 682 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2014 - 2018 Deducción pendiente [00135]
54 | 699 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2014 - Aplicado en esta liquidación [00136]
55 | 716 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - DI internacional 2014 - Pendiente aplic. en períodos futuros [00137]
56 | 733 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - Total - Deducción pendiente  [00160]
57 | 750 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - Total - 2018 Deducción pendiente [00161]
58 | 767 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - Total - Aplicado en esta liquidación [00572]
59 | 784 | 17 | Num | Deducciones doble imposición internacional RDL 4/2004 - Total- Pendiente aplic. en períodos futuros [00162]
60 | 801 | 7 | Num | Deducciones doble imposición internacional RDL 4/2004 - Tipo de gravamen 2018 [00103]
61 | 808 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 - Deducción pendiente [01054]
62 | 825 | 4 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 - Tipo gravamen período generación [01050]
63 | 829 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 - 2018 Deducción pendiente [01051]
64 | 846 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 - Aplicado en esta liquidación [01052]
65 | 863 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional 2015 - Pendiente aplic. en períodos futuros [01053]
66 | 880 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2016 - Deducción pendiente [01348]
67 | 897 | 4 | Num | Deducciones doble imposición internacional LIS - DI internacional  2016 - Tipo gravamen período generación [01349]
68 | 901 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2016 - 2018 Deducción pendiente [01350]
69 | 918 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2016 - Aplicado en esta liquidación [01351]
70 | 935 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2016 - Pendiente aplic. en períodos futuros [01352]
71 | 952 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2017 - Deducción pendiente [01770]
72 | 969 | 4 | Num | Deducciones doble imposición internacional LIS - DI internacional  2017 - Tipo gravamen período generación [01771]
73 | 973 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2017 - 2018 Deducción pendiente [01772]
74 | 990 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2017 - Aplicado en esta liquidación [01773]
75 | 1007 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2017 - Pendiente aplic. en períodos futuros [01774]
76 | 1024 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2018(*) - Deducción pendiente [01833]
77 | 1041 | 4 | Num | Deducciones doble imposición internacional LIS - DI internacional  2018(*) - Tipo gravamen período generación [01834]
78 | 1045 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2018(*) - 2018 Deducción pendiente [01835]
79 | 1062 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2018(*) - Aplicado en esta liquidación [01836]
80 | 1079 | 17 | Num | Deducciones doble imposición internacional LIS - DI internacional  2018(*) - Pendiente aplic. en períodos futuros [01837]
81 | 1096 | 17 | Num | Deducciones doble imposición internacional LIS - Total - Deducción pendiente [00131]
82 | 1113 | 17 | Num | Deducciones doble imposición internacional LIS - Total - 2018 Deducción pendiente [00132]
83 | 1130 | 17 | Num | Deducciones doble imposición internacional LIS - Total - Aplicado en esta liquidación [00571]
84 | 1147 | 17 | Num | Deducciones doble imposición internacional LIS - Total - Pendiente aplic. en períodos futuros [00133]
85 | 1164 | 7 | Num | Deducciones doble imposición internacional LIS - Tipo de gravamen 2018 [00103]
86 | 1171 | 17 | Num | Deducciones doble imposición internacional LIS - DI juridic.Imp.soportado por el contribuyente (art.31 LIS) - Deducción generada [00163]
87 | 1188 | 17 | Num | Deducciones doble imposición internacional LIS - DI juridic.Imp.soportado por el contribuyente (art. 31 LIS) - Aplicado en esta liquidación [00165]
88 | 1205 | 17 | Num | Deducciones doble imposición internacional LIS - DI juridic.Imp.soportado por el contribuyente (art. 31 LIS) - Pendiente aplic. en períodos futuros [00166]
89 | 1222 | 17 | Num | Deducciones doble imposición internacional LIS - DI economica Dividendos y part. en beneficios (art.32 LIS) - Deducción generada [00167]
90 | 1239 | 17 | Num | Deducciones doble imposición internacional LIS - DI economica Dividendos y part. en beneficios (art.32 LIS) - Aplicado en esta liquidación [00169]
91 | 1256 | 17 | Num | Deducciones doble imposición internacional LIS - DI economica Dividendos y part. en beneficios (art.32 LIS) - Pendiente aplic. en períodos futuros [00170]
92 | 1273 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2018 - Deducción generada  [00171]
93 | 1290 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2018 - Aplicado en esta liquidación [00573]
94 | 1307 | 17 | Num | Deducciones doble imposición internacional LIS - Total 2018 - Pendiente aplic. en períodos futuros [00174]
95 | 1324 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 36 ter Ley 43 / 1995.  2003 - Deducción pendiente/generada [00838]
96 | 1341 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 36 ter Ley 43 / 1995.  2003 - Aplicado en esta liquidación [00839]
97 | 1358 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2004 - Deducción pendiente/generada [00932]
98 | 1375 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2004 - Aplicado en esta liquidación [00933]
99 | 1392 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2004 - Pendiente aplicación en periodos futuros [00934]
100 | 1409 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2005 - Deducción pendiente/generada [00297]
101 | 1426 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2005 - Aplicado en esta liquidación [00298]
102 | 1443 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2005 - Pendiente aplicación en periodos futuros [00299]
103 | 1460 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2006 - Deducción pendiente/generada [00090]
104 | 1477 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2006 - Aplicado en esta liquidación [00091]
105 | 1494 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2006 - Pendiente aplicación en periodos futuros [00092]
106 | 1511 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2007 - Deducción pendiente/generada [00004]
107 | 1528 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2007 - Aplicado en esta liquidación [00005]
108 | 1545 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2007 - Pendiente aplicación en periodos futuros [00006]
109 | 1562 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2008 - Deducción pendiente/generada [00031]
110 | 1579 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2008 - Aplicado en esta liquidación [00032]
111 | 1596 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2008 - Pendiente aplicación en periodos futuros [00033]
112 | 1613 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2009 - Deducción pendiente/generada [00022]
113 | 1630 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2009 - Aplicado en esta liquidación [00023]
114 | 1647 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2009 - Pendiente aplicación en periodos futuros [00024]
115 | 1664 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2010 - Deducción pendiente/generada [00040]
116 | 1681 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2010 - Aplicado en esta liquidación [00041]
117 | 1698 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2010 - Pendiente aplicación en periodos futuros [042]
118 | 1715 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2011 - Deducción pendiente/generada [00138]
119 | 1732 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2011 - Aplicado en esta liquidación [00139]
120 | 1749 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2011 - Pendiente aplicación en periodos futuros [00140]
121 | 1766 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2012 - Deducción pendiente/generada [00141]
122 | 1783 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2012 - Aplicado en esta liquidación [00142]
123 | 1800 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2012 - Pendiente aplicación en periodos futuros [00143]
124 | 1817 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2013 - Deducción pendiente/generada [00188]
125 | 1834 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2013 - Aplicado en esta liquidación [00189]
126 | 1851 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2013 - Pendiente aplicación en periodos futuros [00190]
127 | 1868 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2014 - Deducción pendiente/generada [00803]
128 | 1885 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2014 - Aplicado en esta liquidación [00804]
129 | 1902 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. Art. 42 RDL 4/2004 2014 - Pendiente aplicación en periodos futuros [00805]
130 | 1919 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015 - Deducción pendiente/generada [01055]
131 | 1936 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015 - Aplicado en esta liquidación [01056]
132 | 1953 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2015 - Pendiente aplicación en periodos futuros [01057]
133 | 1970 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2016 - Deducción pendiente/generada [00700]
134 | 1987 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2016 - Aplicado en esta liquidación [00708]
135 | 2004 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2016 - Pendiente aplicación en periodos futuros [00709]
136 | 2021 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2017 - Deducción pendiente/generada [01353]
137 | 2038 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2017 - Aplicado en esta liquidación [01354]
138 | 2055 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2017 - Pendiente aplicación en periodos futuros [01355]
139 | 2072 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2018(*) - Deducción pendiente/generada [01775]
140 | 2089 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2018(*) - Aplicado en esta liquidación [01776]
141 | 2106 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2018(*) - Pendiente aplicación en periodos futuros [01777]
142 | 2123 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2018 - Deducción pendiente/generada [01838]
143 | 2140 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2018 - Aplicado en esta liquidación [01839]
144 | 2157 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Deducc. DT 24ª.7 LIS 2018 - Pendiente aplicación en periodos futuros [01840]
145 | 2174 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Total Deducc. Art. 36 ter Ley 43 / 1995 y 42 RDL 4/2004 y 24ª.7 LIS- Deducción pendiente/generada [00841]
146 | 2191 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Total Deducc. Art. 36 ter Ley 43 / 1995 y 42 RDL 4/2004 y 24ª.7 LIS-  Aplicado en esta liquidación [00585]
147 | 2208 | 17 | Num | Deducc. Disposic.Transit. 24ª.7 LIS - Total Deducc. Art. 36 ter Ley 43 / 1995 y 42 RDL 4/2004 y 24ª.7 LIS-  Pendiente aplicación en periodos futuros [00843]
148 | 2225 | 200 | An | RESERVADO PARA LA AEAT
149 | 2425 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20016000>"
Total: |  | 2436

# DP200016B

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página.  Campo OBLIGATORIO | OBLIGATORIO | Constante "16B00"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria. |  | En blanco
6 | 13 | 17 | Num | Deducciones DT 24ª.1 LIS - 2013 Periodificación - Deducción pendiente/generada [00749]
7 | 30 | 17 | Num | Deducciones DT 24ª.1 LIS - 2013 Periodificación - Aplicado en esta liquidación [00750]
8 | 47 | 17 | Num | Deducciones DT 24ª.1 LIS - 2014 Periodificación - Deducción pendiente/generada [00752]
9 | 64 | 17 | Num | Deducciones DT 24ª.1 LIS - 2014 Periodificación - Aplicado en esta liquidación [00753]
10 | 81 | 17 | Num | Deducciones DT 24ª.1 LIS - 2014 Periodificación - Pendiente de aplicación en periodos futuros [00754]
11 | 98 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015 Periodificación - Deducción pendiente/generada [00755]
12 | 115 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015 Periodificación - Aplicado en esta liquidación [00756]
13 | 132 | 17 | Num | Deducciones DT 24ª.1 LIS - 2015 Periodificación - Pendiente de aplicación en periodos futuros [00757]
14 | 149 | 17 | Num | Deducciones DT 24ª.1 LIS - 2016 Periodificación - Deducción pendiente/generada [00758]
15 | 166 | 17 | Num | Deducciones DT 24ª.1 LIS - 2016 Periodificación - Aplicado en esta liquidación [00759]
16 | 183 | 17 | Num | Deducciones DT 24ª.1 LIS - 2016 Periodificación - Pendiente de aplicación en periodos futuros [00760]
17 | 200 | 17 | Num | Deducciones DT 24ª.1 LIS - 2017 Periodificación - Deducción pendiente/generada [00761]
18 | 217 | 17 | Num | Deducciones DT 24ª.1 LIS - 2017 Periodificación - Aplicado en esta liquidación [00762]
19 | 234 | 17 | Num | Deducciones DT 24ª.1 LIS - 2017 Periodificación - Pendiente de aplicación en periodos futuros [00763]
20 | 251 | 17 | Num | Deducciones DT 24ª.1 LIS - 2018(*) Periodificación - Deducción pendiente/generada [00744]
21 | 268 | 17 | Num | Deducciones DT 24ª.1 LIS - 2018(*) Periodificación - Aplicado en esta liquidación [00745]
22 | 285 | 17 | Num | Deducciones DT 24ª.1 LIS - 2018(*) Periodificación - Pendiente de aplicación en periodos futuros [00746]
23 | 302 | 17 | Num | Deducciones DT 24ª.1 LIS - 2018 Periodificación - Deducción pendiente/generada [00779]
24 | 319 | 17 | Num | Deducciones DT 24ª.1 LIS - 2018 Periodificación - Aplicado en esta liquidación [00783]
25 | 336 | 17 | Num | Deducciones DT 24ª.1 LIS - 2018 Periodificación - Pendiente de aplicación en periodos futuros [00784]
26 | 353 | 17 | Num | Deducciones DT 24ª.1 LIS - Total  -  Deducción pendiente/generada [00764]
27 | 370 | 17 | Num | Deducciones DT 24ª.1 LIS - Total - Aplicado en esta liquidación [00584]
28 | 387 | 17 | Num | Deducciones DT 24ª.1 LIS  - Total - Pendiente de aplicación en periodos futuros [00765]
29 | 404 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2010 - Deducción pendiente/generada [00854]
30 | 421 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2010 - Aplicado en esta liquidación [00855]
31 | 438 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2010 - Aplicado en esta liquidación [01356]
32 | 455 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2011 - Deducción pendiente/generada [00857]
33 | 472 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2011 - Aplicado en esta liquidación [00858]
34 | 489 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2011 - Pendiente de aplicación en periodos futuros [00859]
35 | 506 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2012 - Deducción pendiente/generada [00860]
36 | 523 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2012 - Aplicado en esta liquidación [00861]
37 | 540 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2012 - Pendiente de aplicación en periodos futuros [00862]
38 | 557 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2013 - Deducción pendiente/generada [00863]
39 | 574 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2013 - Aplicado en esta liquidación [00864]
40 | 591 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2013 - Pendiente de aplicación en periodos futuros [00865]
41 | 608 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2014 - Deducción pendiente/generada [00883]
42 | 625 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2014 - Aplicado en esta liquidación [00884]
43 | 642 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2014 - Pendiente de aplicación en periodos futuros [00885]
44 | 659 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 - Deducción pendiente/generada [00785]
45 | 676 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 - Aplicado en esta liquidación [00789]
46 | 693 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2015 - Pendiente de aplicación en periodos futuros [00790]
47 | 710 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2016 - Deducción pendiente/generada [01357]
48 | 727 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2016 - Aplicado en esta liquidación [01358]
49 | 744 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2016 - Pendiente de aplicación en periodos futuros [01359]
50 | 761 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2017 - Deducción pendiente/generada [01778]
51 | 778 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2017 - Aplicado en esta liquidación [01779]
52 | 795 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2017 - Pendiente de aplicación en periodos futuros [01780]
53 | 812 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2018(*) - Deducción pendiente/generada [00852]
54 | 829 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2018(*) - Aplicado en esta liquidación [00853]
55 | 846 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2018(*) - Pendiente de aplicación en periodos futuros [00856]
56 | 863 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2018 - Deducción pendiente/generada [02116]
57 | 880 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2018 - Aplicado en esta liquidación [02117]
58 | 897 | 17 | Num | Deducciones inversión Canarias - Activos fijos 2018 - Pendiente de aplicación en periodos futuros [02118]
59 | 914 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2000 - Deducción pendiente/generada  [00868]
60 | 931 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2000 - Aplicado en esta liquidación [00869]
61 | 948 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2001 - Deducción pendiente/generada [00871]
62 | 965 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2001 - Aplicado en esta liquidación [00872]
63 | 982 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2001 - Pendiente de aplicación en periodos futuros [00873]
64 | 999 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2002 - Deducción pendiente/generada [00874]
65 | 1016 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2002 - Aplicado en esta liquidación [00875]
66 | 1033 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2002 - Pendiente de aplicación en periodos futuros [00876]
67 | 1050 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2003 - Deducción pendiente/generada [00877]
68 | 1067 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2003 - Aplicado en esta liquidación [00878]
69 | 1084 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2003 - Pendiente de aplicación en periodos futuros [00879]
70 | 1101 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2004 - Deducción pendiente/generada [00880]
71 | 1118 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2004 - Aplicado en esta liquidación [00881]
72 | 1135 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2004 - Pendiente de aplicación en periodos futuros [00882]
73 | 1152 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2005 - Deducción pendiente/generada [00866]
74 | 1169 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2005 - Aplicado en esta liquidación [00867]
75 | 1186 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2005 - Pendiente de aplicación en periodos futuros [00870]
76 | 1203 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2006 - Deducción pendiente/generada [00939]
77 | 1220 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2006 - Aplicado en esta liquidación [00940]
78 | 1237 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2006 - Pendiente de aplicación en periodos futuros [00941]
79 | 1254 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2007 - Deducción pendiente/generada [00191]
80 | 1271 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2007 - Aplicado en esta liquidación [00192]
81 | 1288 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2007 - Pendiente de aplicación en periodos futuros [00193]
82 | 1305 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2008 - Deducción pendiente/generada  [00613]
83 | 1322 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2008 - Aplicado en esta liquidación [00614]
84 | 1339 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2008 - Pendiente de aplicación en periodos futuros [00701]
85 | 1356 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2009 - Deducción pendiente/generada [00200]
86 | 1373 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2009 - Aplicado en esta liquidación [00257]
87 | 1390 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2009 - Pendiente de aplicación en periodos futuros [00011]
88 | 1407 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2010 - Deducción pendiente/generada [00037]
89 | 1424 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2010 - Aplicado en esta liquidación [00038]
90 | 1441 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2010 - Pendiente de aplicación en periodos futuros [00039]
91 | 1458 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2011 - Deducción pendiente/generada [00044]
92 | 1475 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2011 - Aplicado en esta liquidación [00045]
93 | 1492 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2011 - Pendiente de aplicación en periodos futuros [00046]
94 | 1509 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2012 - Deducción pendiente/generada [00528]
95 | 1526 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2012 - Aplicado en esta liquidación [00529]
96 | 1543 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2012 - Pendiente de aplicación en periodos futuros [00530]
97 | 1560 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2013 - Deducción pendiente/generada [00144]
98 | 1577 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2013 - Aplicado en esta liquidación [00145]
99 | 1594 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2013 - Pendiente de aplicación en periodos futuros [00146]
100 | 1611 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2014 - Deducción pendiente/generada [00147]
101 | 1628 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2014 - Aplicado en esta liquidación [00148]
102 | 1645 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2014 - Pendiente de aplicación en periodos futuros [00149]
103 | 1662 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015 - Deducción pendiente/generada [00240]
104 | 1679 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015 - Aplicado en esta liquidación [00241]
105 | 1696 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2015 - Pendiente de aplicación en periodos futuros [00242]
106 | 1713 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2016 - Deducción pendiente/generada [01058]
107 | 1730 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2016 - Aplicado en esta liquidación [01059]
108 | 1747 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2016 - Pendiente de aplicación en periodos futuros [01060]
109 | 1764 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2017 - Deducción pendiente/generada [00791]
110 | 1781 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2017 - Aplicado en esta liquidación [00802]
111 | 1798 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2017 - Pendiente de aplicación en periodos futuros [00806]
112 | 1815 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2018(*) - Deducción pendiente/generada [01781]
113 | 1832 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2018(*) - Aplicado en esta liquidación [01782]
114 | 1849 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2018(*) - Pendiente de aplicación en periodos futuros [01783]
115 | 1866 | 17 | Num | Deducciones inversión Canarias - IInversiones en La Palma, La Gomera y El Hierro 2018(*) - Deducción pendiente/generada [02119]
116 | 1883 | 17 | Num | Deducciones inversión Canarias - Inversiones en La Palma, La Gomera y El Hierro 2018(*) - Aplicado en esta liquidación [02120]
117 | 1900 | 17 | Num | Deducciones inversión Canarias - Inversiones en La Palma, La Gomera y El Hierro 2018(*) - Pendiente de aplicación en periodos futuros [02121]
118 | 1917 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2018 - Deducción pendiente/generada [02122]
119 | 1934 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2018 - Aplicado en esta liquidación [02123]
120 | 1951 | 17 | Num | Deducciones inversión Canarias - Inversiones Canarias 2018 - Pendiente de aplicación en periodos futuros [02124]
121 | 1968 | 17 | Num | Deducciones inversión Canarias - IInversiones en La Palma, La Gomera y El Hierro 2018(*) - Deducción pendiente/generada [02125]
122 | 1985 | 17 | Num | Deducciones inversión Canarias - Inversiones en La Palma, La Gomera y El Hierro 2018(*) - Aplicado en esta liquidación [02126]
123 | 2002 | 17 | Num | Deducciones inversión Canarias - Inversiones en La Palma, La Gomera y El Hierro 2018(*) - Pendiente de aplicación en periodos futuros [02127]
124 | 2019 | 17 | Num | Deducciones inversión Canarias - Total - Deducción pendiente/generada [00886]
125 | 2036 | 17 | Num | Deducciones inversión Canarias - Total - Aplicado en esta liquidación [00590]
126 | 2053 | 17 | Num | Deducciones inversión Canarias - Total - Pendiente de aplicación en periodos futuros [00887]
127 | 2070 | 200 | An | RESERVADO PARA LA AEAT
128 | 2270 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20016B00>"
Total: |  | 2281

# DP200017

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "17000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Deducc. para  incentivar determ.actividades - 2000 Suma deducciones - Deducción pendiente/generada [00780]
7 | 30 | 17 | Num | Deducc. para  incentivar determ.actividades - 2000 Suma deducciones - Aplicado en esta liquidación [00781]
8 | 47 | 17 | Num | Deducc. para  incentivar determ.actividades - 2001 Suma deducciones - Deducción pendiente/generada [00786]
9 | 64 | 17 | Num | Deducc. para  incentivar determ.actividades - 2001 Suma deducciones - Aplicado en esta liquidación [00787]
10 | 81 | 17 | Num | Deducc. para  incentivar determ.actividades - 2001 Suma deducciones - Pendiente de aplicación en periodos futuros [00788]
11 | 98 | 17 | Num | Deducc. para  incentivar determ.actividades - 2002 Suma deducciones - Deducción pendiente/generada [00766]
12 | 115 | 17 | Num | Deducc. para  incentivar determ.actividades - 2002 Suma deducciones - Aplicado en esta liquidación [00767]
13 | 132 | 17 | Num | Deducc. para  incentivar determ.actividades - 2002 Suma deducciones - Pendiente de aplicación en periodos futuros [00833]
14 | 149 | 17 | Num | Deducc. para  incentivar determ.actividades - 2003 Suma deducciones - Deducción pendiente/generada [00198]
15 | 166 | 17 | Num | Deducc. para  incentivar determ.actividades - 2003 Suma deducciones - Aplicado en esta liquidación [00896]
16 | 183 | 17 | Num | Deducc. para  incentivar determ.actividades - 2003 Suma deducciones - Pendiente de aplicación en periodos futuros [00897]
17 | 200 | 17 | Num | Deducc. para  incentivar determ.actividades - 2004 Suma deducciones - Deducción pendiente/generada [00288]
18 | 217 | 17 | Num | Deducc. para  incentivar determ.actividades - 2004 Suma deducciones - Aplicado en esta liquidación [00289]
19 | 234 | 17 | Num | Deducc. para  incentivar determ.actividades - 2004 Suma deducciones - Pendiente de aplicación en periodos futuros [00290]
20 | 251 | 17 | Num | Deducc. para  incentivar determ.actividades - 2005 Suma deducciones - Deducción pendiente/generada [00466]
21 | 268 | 17 | Num | Deducc. para  incentivar determ.actividades - 2005 Suma deducciones - Aplicado en esta liquidación [00467]
22 | 285 | 17 | Num | Deducc. para  incentivar determ.actividades - 2005 Suma deducciones - Pendiente de aplicación en periodos futuros [00468]
23 | 302 | 17 | Num | Deducc. para  incentivar determ.actividades - 2006 Suma deducciones - Deducción pendiente/generada [00061]
24 | 319 | 17 | Num | Deducc. para  incentivar determ.actividades - 2006 Suma deducciones - Aplicado en esta liquidación [00498]
25 | 336 | 17 | Num | Deducc. para  incentivar determ.actividades - 2006 Suma deducciones - Pendiente de aplicación en periodos futuros [00586]
26 | 353 | 17 | Num | Deducc. para  incentivar determ.actividades - 2007 Suma deducciones - Deducción pendiente/generada [00472]
27 | 370 | 17 | Num | Deducc. para  incentivar determ.actividades - 2007 Suma deducciones - Aplicado en esta liquidación [00473]
28 | 387 | 17 | Num | Deducc. para  incentivar determ.actividades - 2007 Suma deducciones - Pendiente de aplicación en periodos futuros [00478]
29 | 404 | 17 | Num | Deducc. para  incentivar determ.actividades - 2008 Suma deducciones - Deducción pendiente/generada [00180]
30 | 421 | 17 | Num | Deducc. para  incentivar determ.actividades - 2008 Suma deducciones - Aplicado en esta liquidación [00181]
31 | 438 | 17 | Num | Deducc. para  incentivar determ.actividades - 2008 Suma deducciones - Pendiente de aplicación en periodos futuros [00182]
32 | 455 | 17 | Num | Deducc. para  incentivar determ.actividades - 2009 Suma deducciones - Deducción pendiente/generada [00531]
33 | 472 | 17 | Num | Deducc. para  incentivar determ.actividades - 2009 Suma deducciones - Aplicado en esta liquidación [00532]
34 | 489 | 17 | Num | Deducc. para  incentivar determ.actividades - 2009 Suma deducciones - Pendiente de aplicación en periodos futuros [00533]
35 | 506 | 17 | Num | Deducc. para  incentivar determ.actividades - 2010 Suma deducciones - Deducción pendiente/generada [00945]
36 | 523 | 17 | Num | Deducc. para  incentivar determ.actividades - 2010 Suma deducciones - Aplicado en esta liquidación [00946]
37 | 540 | 17 | Num | Deducc. para  incentivar determ.actividades - 2010 Suma deducciones - Pendiente de aplicación en periodos futuros [00947]
38 | 557 | 17 | Num | Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Deducción pendiente/generada [00960]
39 | 574 | 17 | Num | Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Aplicado en esta liquidación [00961]
40 | 591 | 17 | Num | Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Pendiente de aplicación en periodos futuros [00962]
41 | 608 | 17 | Num | Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Deducción pendiente/generada [00183]
42 | 625 | 17 | Num | Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Aplicado en esta liquidación [00185]
43 | 642 | 17 | Num | Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Pendiente de aplicación en periodos futuros [00186]
44 | 659 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Suma deducciones - Deducción pendiente/generada [00966]
45 | 676 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Suma deducciones - Aplicado en esta liquidación [00967]
46 | 693 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Suma deducciones - Pendiente de aplicación en periodos futuros [00968]
47 | 710 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Investigación y desarrollo - Deducción pendiente/generada [00457]
48 | 727 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Investigación y desarrollo - Aplicado en esta liquidación [00458]
49 | 744 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Investigación y desarrollo - Pendiente de aplicación en periodos futuros [00459]
50 | 761 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Innovación tecnológica - Deducción pendiente/generada [00460]
51 | 778 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Innovación tecnológica - Aplicado en esta liquidación [00461]
52 | 795 | 17 | Num | Deducc. para incentivar determ.actividades - 2013 Innovación tecnológica - Pendiente de aplicación en periodos futuros [00462]
53 | 812 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Suma deducciones - Deducción pendiente/generada [01063]
54 | 829 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Suma deducciones - Aplicado en esta liquidación [01064]
55 | 846 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Suma deducciones - Pendiente de aplicación en periodos futuros [01065]
56 | 863 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Investigación y desarrollo - Deducción pendiente/generada [01066]
57 | 880 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Investigación y desarrollo - Aplicado en esta liquidación [01067]
58 | 897 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Investigación y desarrollo - Pendiente de aplicación en periodos futuros [01068]
59 | 914 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Innovación tecnológica - Deducción pendiente/generada [01069]
60 | 931 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Innovación tecnológica - Aplicado en esta liquidación [01070]
61 | 948 | 17 | Num | Deducc. para incentivar determ.actividades - 2014 Innovación tecnológica - Pendiente de aplicación en periodos futuros [01071]
62 | 965 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Suma deducciones - Deducción pendiente/generada [00813]
63 | 982 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Suma deducciones - Aplicado en esta liquidación [00814]
64 | 999 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Suma deducciones - Pendiente de aplicación en periodos futuros [00815]
65 | 1016 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Deducción pendiente/generada  [00986]
66 | 1033 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Aplicado en esta liquidación  [00810]
67 | 1050 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Investigación y desarrollo - Pendiente de aplicación en periodos futuros [00507]
68 | 1067 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Deducción pendiente/generada [00557]
69 | 1084 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Aplicado en esta liquidación [00591]
70 | 1101 | 17 | Num | Deducc. para incentivar determ.actividades - 2015 Innovación tecnológica - Pendiente de aplicación en periodos futuros [00594]
71 | 1118 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Suma deducciones Cap. IV Tit. VI Ley 43/95, RDL 4/2004 y LIS
(excepto I+D+i) - Deducción pendiente/generada [01614]
72 | 1135 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Suma deducciones Cap. IV Tit. VI Ley 43/95, RDL 4/2004 y LIS
(excepto I+D+i) - Aplicado en esta liquidación [01615]
73 | 1152 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Suma deducciones Cap. IV Tit. VI Ley 43/95, RDL 4/2004 y LIS
(excepto I+D+i) - Pendiente de aplicación en periodos futuros [01616]
74 | 1169 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Investigación y desarrollo (CT) - Deducción pendiente/generada [01617]
75 | 1186 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Investigación y desarrollo (CT) - Aplicado en esta liquidación [01618]
76 | 1203 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Investigación y desarrollo (CT) - Pendiente de aplicación en periodos futuros [01619]
77 | 1220 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Innovación tecnológica (IT) - Deducción pendiente/generada [01620]
78 | 1237 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Innovación tecnológica (IT) - Aplicado en esta liquidación [01621]
79 | 1254 | 17 | Num | Deducc. para incentivar determ.actividades - 2016 Innovación tecnológica (IT) - Pendiente de aplicación en periodos futuros [01622]
80 | 1271 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Suma deducciones Cap. IV Tit. VI Ley 43/95, RDL 4/2004 y LIS
(excepto I+D+i) - Deducción pendiente/generada [01847]
81 | 1288 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Suma deducciones Cap. IV Tit. VI Ley 43/95, RDL 4/2004 y LIS
(excepto I+D+i) - Aplicado en esta liquidación [01848]
82 | 1305 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Suma deducciones Cap. IV Tit. VI Ley 43/95, RDL 4/2004 y LIS
(excepto I+D+i) - Pendiente de aplicación en periodos futuros [01849]
83 | 1322 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Investigación y desarrollo (CT) - Deducción pendiente/generada [01850]
84 | 1339 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Investigación y desarrollo (CT) - Aplicado en esta liquidación [01851]
85 | 1356 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Investigación y desarrollo (CT) - Pendiente de aplicación en periodos futuros [01852]
86 | 1373 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Innovación tecnológica (IT) - Deducción pendiente/generada [01853]
87 | 1390 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Innovación tecnológica (IT) - Aplicado en esta liquidación [01854]
88 | 1407 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Innovación tecnológica (IT) - Pendiente de aplicación en periodos futuros [01855]
89 | 1424 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Suma deducciones - Deducción pendiente/generada [01360]
90 | 1441 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Suma deducciones - Aplicado en esta liquidación [01361]
91 | 1458 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Suma deducciones - Pendiente de aplicación en periodos futuros [01362]
92 | 1475 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Investigación y desarrollo - Deducción pendiente/generada [01363]
93 | 1492 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Investigación y desarrollo - Aplicado en esta liquidación [01364]
94 | 1509 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Investigación y desarrollo - Pendiente de aplicación en periodos futuros [01365]
95 | 1526 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Innovación tecnológica - Deducción pendiente/generada [01366]
96 | 1543 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Innovación tecnológica - Aplicado en esta liquidación [01367]
97 | 1560 | 17 | Num | Deducc. para incentivar determ.actividades - 2018(*) Innovación tecnológica - Pendiente de aplicación en periodos futuros [01368]
98 | 1577 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Investigación y desarrollo - Deducción pendiente/generada [00798]
99 | 1594 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Investigación y desarrollo - Aplicado en esta liquidación [00799]
100 | 1611 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Investigación y desarrollo - Pendiente de aplicación en periodos futuros [00800]
101 | 1628 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Innovación tecnológica - Deducción pendiente/generada [00096]
102 | 1645 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Innovación tecnológica - Aplicado en esta liquidación [00698]
103 | 1662 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Innovación tecnológica - Pendiente de aplicación en periodos futuros [00713]
104 | 1679 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Produc. cinematográficas españolas - Deducción pendiente/generada [00807]
105 | 1696 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Produc. cinematográficas españolas - Aplicado en esta liquidación [00808]
106 | 1713 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Produc. cinematográficas españolas - Pendiente de aplicación en periodos futuros [00809]
107 | 1730 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Espectáculos en vivo artes escénicas y musicales - Deducción pendiente/generada [01075]
108 | 1747 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Espectáculos en vivo artes escénicas y musicales - Aplicado en esta liquidación [01076]
109 | 1764 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Espectáculos en vivo artes escénicas y musicales - Pendiente de aplicación en periodos futuros [01077]
110 | 1781 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Creación empleo contratación menores de 30 - Deducción pendiente/generada [00963]
111 | 1798 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Creación empleo contratación menores de 30 - Aplicado en esta liquidación [00964]
112 | 1815 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Creación empleo contratación menores de 30 - Pendiente de aplicación en periodos futuros [00965]
113 | 1832 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Creación empleo contratación desempleados con prestación desempleo - Deducción pendiente/generada [00931]
114 | 1849 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Creación empleo contratación desempleados con prestación desempleo - Aplicado en esta liquidación [00502]
115 | 1866 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Creación empleo contratación desempleados con prestación desempleo - Pendiente de aplicación en periodos futuros [00751]
116 | 1883 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deducción por creación de empleo trabaj. con discapacidad - Deducción pendiente/generada [00795]
117 | 1900 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deducción por creación de empleo trabaj. con discapacidad - Aplicado en esta liquidación [00796]
118 | 1917 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deducción por creación de empleo trabaj. con discapacidad - Pendiente de aplicación en periodos futuros [00797]
119 | 1934 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deducción por inversión en beneficios - Deducción pendiente/generada [00549]
120 | 1951 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deducción por inversión en beneficios - Aplicado en esta liquidación [00888]
121 | 1968 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deducción por inversión en beneficios - Pendiente de aplicación en periodos futuros [00889]
122 | 1985 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Gastos e inversiones de sociedades forestales - Deducción pendiente/generada [01369]
123 | 2002 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Gastos e inversiones de sociedades forestales - Aplicado en esta liquidación [01370]
124 | 2019 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Gastos e inversiones de sociedades forestales - Pendiente de aplicación en periodos futuros [01371]
125 | 2036 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Inversiones en territ. África Occidental y gastos de propaganda y publicidad (art. 27 bis Ley 19/1994) - Deducción pendiente/generada [02190]
126 | 2053 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Inversiones en territ. África Occidental y gastos de propaganda y publicidad (art. 27 bis Ley 19/1994) - Aplicado en esta liquidación [02191]
127 | 2070 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Inversiones en territ. África Occidental y gastos de propaganda y publicidad (art. 27 bis Ley 19/1994) - Pendiente de aplicación en periodos futuros [02192]
128 | 2087 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Juegos del Mediterráneo de 2018 - Deducción pendiente/generada [00438]
129 | 2104 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Juegos del Mediterráneo de 2018 - Aplicado en esta liquidación [00439]
130 | 2121 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Juegos del Mediterráneo de 2018 - Pendiente de aplicación en periodos futuros [00440]
131 | 2138 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 200 Anivers. Teatro Real y el Vigésimo Anivers.de la reapertura del Teatro Real  - Deducción pendiente/generada [01081]
132 | 2155 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 200 Anivers. Teatro Real y el Vigésimo Anivers.de la reapertura del Teatro Real  - Aplicado en esta liquidación [01082]
133 | 2172 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 200 Anivers. Teatro Real y el Vigésimo Anivers.de la reapertura del Teatro Real  - Pendiente de aplicación en periodos futuros [01083]
134 | 2189 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VIII Centenario de la Universidad de Salamanca  -  Deducción pendiente/generada [01087]
135 | 2206 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VIII Centenario de la Universidad de Salamanca  -  Aplicado en esta liquidación [01088]
136 | 2223 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VIII Centenario de la Universidad de Salamanca  -  Pendiente de aplicación en periodos futuros [01089]
137 | 2240 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Cantabria 2017, Liébana Año Jubilar  -  Deducción pendiente/generada [01093]
138 | 2257 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Cantabria 2017, Liébana Año Jubilar  -  Aplicado en esta liquidación [01094]
139 | 2274 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Cantabria 2017, Liébana Año Jubilar  -  Pendiente de aplicación en periodos futuros [01095]
140 | 2291 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Programa Universo Mujer  -  Deducción pendiente/generada [01096]
141 | 2308 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Programa Universo Mujer  -  Aplicado en esta liquidación [01097]
142 | 2325 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Programa Universo Mujer  -  Pendiente de aplicación en periodos futuros [01098]
143 | 2342 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Barcelona Equestrian Challenge  -  Deducción pendiente/generada [01114]
144 | 2359 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Barcelona Equestrian Challenge  -  Aplicado en esta liquidación [01115]
145 | 2376 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Barcelona Equestrian Challenge  -  Pendiente de aplicación en periodos futuros [01116]
146 | 2393 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Women's Hockey World League Round 3 Events  -  Deducción pendiente/generada [01117]
147 | 2410 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Women's Hockey World League Round 3 Events  -  Aplicado en esta liquidación [01118]
148 | 2427 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Women's Hockey World League Round 3 Events  -  Pendiente de aplicación en periodos futuros [01119]
149 | 2444 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 II Centenario Museo Nacional del Prado  -  Deducción pendiente/generada [01372]
150 | 2461 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 II Centenario Museo Nacional del Prado  -  Aplicado en esta liquidación [01373]
151 | 2478 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 II Centenario Museo Nacional del Prado  -  Pendiente de aplicación en periodos futuros [01374]
152 | 2495 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 20 Aniversario Reapertura Liceo de Barcelona  -  Deducción pendiente/generada [01375]
153 | 2512 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 20 Aniversario Reapertura Liceo de Barcelona  -  Aplicado en esta liquidación [01376]
154 | 2529 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 20 Aniversario Reapertura Liceo de Barcelona  -  Pendiente de aplicación en periodos futuros [01377]
155 | 2546 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Foro Iberoamericano de Ciudades  -  Deducción pendiente/generada [01378]
156 | 2563 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Foro Iberoamericano de Ciudades  -  Aplicado en esta liquidación [01379]
157 | 2580 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Foro Iberoamericano de Ciudades  -  Pendiente de aplicación en periodos futuros [01380]
158 | 2597 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan Decenio Málaga Cultura Innovadora  -  Deducción pendiente/generada [01381]
159 | 2614 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan Decenio Málaga Cultura Innovadora  -  Aplicado en esta liquidación [01382]
160 | 2631 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan Decenio Málaga Cultura Innovadora  -  Pendiente de aplicación en periodos futuros [01383]
161 | 2648 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonatos Mundo FIS Freestyle y Snowboard  -  Deducción pendiente/generada [01387]
162 | 2665 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonatos Mundo FIS Freestyle y Snowboard  -  Aplicado en esta liquidación [01388]
163 | 2682 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonatos Mundo FIS Freestyle y Snowboard  -  Pendiente de aplicación en periodos futuros [01389]
164 | 2699 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Vigésimo quinto aniversario Museo Thyssen-Bornemisza - Deducción pendiente/generada [01390]
165 | 2716 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Vigésimo quinto aniversario Museo Thyssen-Bornemisza - Aplicado en esta liquidación [01391]
166 | 2733 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Vigésimo quinto aniversario Museo Thyssen-Bornemisza - Pendiente de aplicación en periodos futuros [01392]
167 | 2750 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato Europa Waterpolo Barcelona 2018 - Deducción pendiente/generada [01393]
168 | 2767 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato Europa Waterpolo Barcelona 2018 - Aplicado en esta liquidación [01394]
169 | 2784 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato Europa Waterpolo Barcelona 2018 - Pendiente de aplicación en periodos futuros [01395]
170 | 2801 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Centenario nacimiento Camilo José Cela - Deducción pendiente/generada [01396]
171 | 2818 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Centenario nacimiento Camilo José Cela - Aplicado en esta liquidación [01397]
172 | 2835 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Centenario nacimiento Camilo José Cela - Pendiente de aplicación en periodos futuros [01398]
173 | 2852 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Caravaca de la Cruz Año Jubilar - Deducción pendiente/generada [01402]
174 | 2869 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Caravaca de la Cruz Año Jubilar - Aplicado en esta liquidación [01403]
175 | 2886 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Caravaca de la Cruz Año Jubilar - Pendiente de aplicación en periodos futuros [01404]
176 | 2903 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan 2020 apoyo al Deporte de Base - Deducción pendiente/generada [01405]
177 | 2920 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan 2020 apoyo al Deporte de Base - Aplicado en esta liquidación [01406]
178 | 2937 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan 2020 apoyo al Deporte de Base - Pendiente de aplicación en periodos futuros [01407]
179 | 2954 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Prevención de la Obesidad. Aligera tu vida - Deducción pendiente/generada [01417]
180 | 2971 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Prevención de la Obesidad. Aligera tu vida - Aplicado en esta liquidación [01418]
181 | 2988 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Prevención de la Obesidad. Aligera tu vida - Pendiente de aplicación en periodos futuros [01419]
182 | 3005 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 75 Aniversario de Willian Martin - Deducción pendiente/generada [01420]
183 | 3022 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 75 Aniversario de Willian Martin - Aplicado en esta liquidación [01421]
184 | 3039 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 75 Aniversario de Willian Martin - Pendiente de aplicación en periodos futuros [01422]
185 | 3056 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Salida vuelta al mundo a vela Alicante 2017 - Deducción pendiente/generada [01423]
186 | 3073 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Salida vuelta al mundo a vela Alicante 2017 - Aplicado en esta liquidación [01424]
187 | 3090 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Salida vuelta al mundo a vela Alicante 2017 - Pendiente de aplicación en periodos futuros [01425]
188 | 3107 | 200 | An | RESERVADO PARA LA AEAT
189 | 3307 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20017000>"
Total: |  | 3318

# DP200018

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "18000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 25 Aniversario de la Casa América (CA) - Deducción pendiente/generada [01623]
7 | 30 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 25 Aniversario de la Casa América (CA) - Aplicado en esta liquidación [01624]
8 | 47 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 25 Aniversario de la Casa América (CA) - Pendiente de aplicación en periodos futuros [01625]
9 | 64 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 4ª Edición de la Barcelona World Race (4BWR) - Deducción pendiente/generada [01626]
10 | 81 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 4ª Edición de la Barcelona World Race (4BWR) - Aplicado en esta liquidación [01627]
11 | 98 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 4ª Edición de la Barcelona World Race (4BWR) - Pendiente de aplicación en periodos futuros [01628]
12 | 115 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 World Roller Games Barcelona 2019 (RG19) - Deducción pendiente/generada [01629]
13 | 132 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 World Roller Games Barcelona 2019 (RG19) - Aplicado en esta liquidación [01630]
14 | 149 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 World Roller Games Barcelona 2019 (RG19) - Pendiente de aplicación en periodos futuros [01631]
15 | 166 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Madrid Horse Week 17/19 (HW19) - Deducción pendiente/generada [01632]
16 | 183 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Madrid Horse Week 17/19 (HW19) - Aplicado en esta liquidación [01633]
17 | 200 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Madrid Horse Week 17/19 (HW19) - Pendiente de aplicación en periodos futuros [01634]
18 | 217 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 La Liga World Challenge (LWCH) - Deducción pendiente/generada [01635]
19 | 234 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 La Liga World Challenge (LWCH) - Aplicado en esta liquidación [01636]
20 | 251 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 La Liga World Challenge (LWCH) - Pendiente de aplicación en periodos futuros [01637]
21 | 268 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 V Centenario de la expedición de la primera vuelta al mundo de Fernando de Magallanes y Juan Sebastián Elcano (EPVM) - Deducción pendiente/generada [01638]
22 | 285 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 V Centenario de la expedición de la primera vuelta al mundo de Fernando de Magallanes y Juan Sebastián Elcano (EPVM) - Aplicado en esta liquidación [01639]
23 | 302 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 V Centenario de la expedición de la primera vuelta al mundo de Fernando de Magallanes y Juan Sebastián Elcano (EPVM) - Pendiente de aplicación en periodos futuros [01640]
24 | 319 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 25 Aniversario de la declaración por la Unesco de Mérida como Patrimonio de la Humanidad (25M) - Deducción pendiente/generada [01641]
25 | 336 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 25 Aniversario de la declaración por la Unesco de Mérida como Patrimonio de la Humanidad (25M) - Aplicado en esta liquidación [01642]
26 | 353 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 25 Aniversario de la declaración por la Unesco de Mérida como Patrimonio de la Humanidad (25M) - Pendiente de aplicación en periodos futuros [01643]
27 | 370 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonatos del Mundo de Canoa 2019 (C19) - Deducción pendiente/generada [01644]
28 | 387 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonatos del Mundo de Canoa 2019 (C19) - Aplicado en esta liquidación [01645]
29 | 404 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonatos del Mundo de Canoa 2019 (C19) - Pendiente de aplicación en periodos futuros [01646]
30 | 421 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 250 Aniversario del Fuero de Población de 1767 y Fundación de las Nuevas Poblaciones de Sierra Morena y Andalucía (250F) - Deducción pendiente/generada [01647]
31 | 438 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 250 Aniversario del Fuero de Población de 1767 y Fundación de las Nuevas Poblaciones de Sierra Morena y Andalucía (250F) - Aplicado en esta liquidación [01648]
32 | 455 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 250 Aniversario del Fuero de Población de 1767 y Fundación de las Nuevas Poblaciones de Sierra Morena y Andalucía (250F) - Pendiente de aplicación en periodos futuros [01649]
33 | 472 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 IV Centenario del nacimiento de Bartolomé Esteban Murillo (BEM) - Deducción pendiente/generada [01650]
34 | 489 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 IV Centenario del nacimiento de Bartolomé Esteban Murillo (BEM) - Aplicado en esta liquidación [01651]
35 | 506 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 IV Centenario del nacimiento de Bartolomé Esteban Murillo (BEM) - Pendiente de aplicación en periodos futuros [01652]
36 | 523 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Numancia 2017 (N17) - Deducción pendiente/generada [01653]
37 | 540 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Numancia 2017 (N17) - Aplicado en esta liquidación [01654]
38 | 557 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Numancia 2017 (N17) - Pendiente de aplicación en periodos futuros [01655]
39 | 574 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 PHotoEspaña. 20 aniversario (PH20) - Deducción pendiente/generada [01656]
40 | 591 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 PHotoEspaña. 20 aniversario (PH20) - Aplicado en esta liquidación [01657]
41 | 608 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 PHotoEspaña. 20 aniversario (PH20) - Pendiente de aplicación en periodos futuros [01658]
42 | 625 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 IV Centenario de la Plaza Mayor de Madrid (PMM) - Deducción pendiente/generada [01659]
43 | 642 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 IV Centenario de la Plaza Mayor de Madrid (PMM) - Aplicado en esta liquidación [01660]
44 | 659 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 IV Centenario de la Plaza Mayor de Madrid (PMM) - Pendiente de aplicación en periodos futuros [01661]
45 | 676 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 XXX Aniversario de la Declaración de Toledo como Ciudad Patrimonio de la Humanidad (TCPH) - Deducción pendiente/generada [01662]
46 | 693 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 XXX Aniversario de la Declaración de Toledo como Ciudad Patrimonio de la Humanidad (TCPH) - Aplicado en esta liquidación [01663]
47 | 710 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 XXX Aniversario de la Declaración de Toledo como Ciudad Patrimonio de la Humanidad (TCPH) - Pendiente de aplicación en periodos futuros [01664]
48 | 727 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VII Centenario del Archivo de la Corona de Aragón (ACA) - Deducción pendiente/generada [01665]
49 | 744 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VII Centenario del Archivo de la Corona de Aragón (ACA) - Aplicado en esta liquidación [01666]
50 | 761 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VII Centenario del Archivo de la Corona de Aragón (ACA) - Pendiente de aplicación en periodos futuros [01667]
51 | 778 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Lorca, Aula de la Historia (LAH) - Deducción pendiente/generada [01668]
52 | 795 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Lorca, Aula de la Historia (LAH) - Aplicado en esta liquidación [01669]
53 | 812 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Lorca, Aula de la Historia (LAH) - Pendiente de aplicación en periodos futuros [01670]
54 | 829 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan de Fomento de la Lectura (2017-2020) (PFL) - Deducción pendiente/generada [01671]
55 | 846 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan de Fomento de la Lectura (2017-2020) (PFL) - Aplicado en esta liquidación [01672]
56 | 863 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan de Fomento de la Lectura (2017-2020) (PFL) - Pendiente de aplicación en periodos futuros [01673]
57 | 880 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan 2020 de Apoyo a los Nuevos Creadores Cinematográficos y a la conservación y difusión de la historia del cine español (NCC) - Deducción pendiente/generada [01674]
58 | 897 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan 2020 de Apoyo a los Nuevos Creadores Cinematográficos y a la conservación y difusión de la historia del cine español (NCC) - Aplicado en esta liquidación [01675]
59 | 914 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan 2020 de Apoyo a los Nuevos Creadores Cinematográficos y a la conservación y difusión de la historia del cine español (NCC) - Pendiente de aplicación en periodos futuros [01676]
60 | 931 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro (TCA) - Deducción pendiente/generada [01677]
61 | 948 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro (TCA) - Aplicado en esta liquidación [01678]
62 | 965 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 40 Aniversario del Festival Internacional de Teatro Clásico de Almagro (TCA) - Pendiente de aplicación en periodos futuros [01679]
63 | 982 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 75º Aniversario de la Escuela Diplomática (ED) - Deducción pendiente/generada [01689]
64 | 999 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 75º Aniversario de la Escuela Diplomática (ED) - Aplicado en esta liquidación [01690]
65 | 1016 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 75º Aniversario de la Escuela Diplomática (ED) - Pendiente de aplicación en periodos futuros [01691]
66 | 1033 | 17 | Num | Deducc. para incentivar determ.actividades - 2017 Teruel 2017. 800 Años de los Amantes (T17) - Deducción pendiente/generada [01692]
67 | 1050 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Teruel 2017. 800 Años de los Amantes (T17) - Aplicado en esta liquidación [01693]
68 | 1067 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Teruel 2017. 800 Años de los Amantes (T17) - Pendiente de aplicación en periodos futuros [01694]
69 | 1084 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 40 Aniversario de la Constitución Española (40CE) - Deducción pendiente/generada [01695]
70 | 1101 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 40 Aniversario de la Constitución Española (40CE) - Aplicado en esta liquidación [01696]
71 | 1118 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 40 Aniversario de la Constitución Española (40CE) - Pendiente de aplicación en periodos futuros [01697]
72 | 1135 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50º Aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya (SFIC) - Deducción pendiente/generada [01698]
73 | 1152 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50º Aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya (SFIC) - Aplicado en esta liquidación [01699]
74 | 1169 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50º Aniversario de Sitges-Festival Internacional de Cine Fantástico de Catalunya (SFIC) - Pendiente de aplicación en periodos futuros [01700]
75 | 1186 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50 Aniversario de la Universidad Autónoma de Madrid (50UA) - Deducción pendiente/generada [01701]
76 | 1203 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50 Aniversario de la Universidad Autónoma de Madrid (50UA) - Aplicado en esta liquidación [01702]
77 | 1220 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50 Aniversario de la Universidad Autónoma de Madrid (50UA) - Pendiente de aplicación en periodos futuros [01703]
78 | 1237 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Hernandiano 2017 (AH17) - Deducción pendiente/generada [01704]
79 | 1254 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Hernandiano 2017 (AH17) - Aplicado en esta liquidación [01705]
80 | 1271 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Hernandiano 2017 (AH17) - Pendiente de aplicación en periodos futuros [01706]
81 | 1288 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan Decenio Milliarium Montserrat 1025-2025 (PDMM) - Deducción pendiente/generada [01707]
82 | 1305 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan Decenio Milliarium Montserrat 1025-2025 (PDMM) - Aplicado en esta liquidación [01708]
83 | 1322 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Plan Decenio Milliarium Montserrat 1025-2025 (PDMM) - Pendiente de aplicación en periodos futuros [01709]
84 | 1339 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Programa de preparación de los deportistas españoles de los Juegos de Tokio 2020 (T20) - Deducción pendiente/generada [01800]
85 | 1356 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Programa de preparación de los deportistas españoles de los Juegos de Tokio 2020 (T20) - Aplicado en esta liquidación [01801]
86 | 1373 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Programa de preparación de los deportistas españoles de los Juegos de Tokio 2020 (T20) - Pendiente de aplicación en periodos futuros [01802]
87 | 1390 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 I Centenario Parque Nacional Ordesa y Monte Perdido (PO) - Deducción pendiente/generada [01856]
88 | 1407 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 I Centenario Parque Nacional Ordesa y Monte Perdido (PO) - Aplicado en esta liquidación [01857]
89 | 1424 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 I Centenario Parque Nacional Ordesa y Monte Perdido (PO) - Pendiente de aplicación en periodos futuros [01858]
90 | 1441 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 I Centenario Parque Nacional Picos de Europa (PE) - Deducción pendiente/generada [01859]
91 | 1458 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 I Centenario Parque Nacional Picos de Europa (PE) - Aplicado en esta liquidación [01860]
92 | 1475 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 I Centenario Parque Nacional Picos de Europa (PE) - Pendiente de aplicación en periodos futuros [01861]
93 | 1492 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50 Edición del Festival Internacional de Jazz de Barcelona (50J) - Deducción pendiente/generada [01862]
94 | 1509 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50 Edición del Festival Internacional de Jazz de Barcelona (50J) - Aplicado en esta liquidación [01863]
95 | 1526 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 50 Edición del Festival Internacional de Jazz de Barcelona (50J) - Pendiente de aplicación en periodos futuros [01864]
96 | 1543 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Centenarios del Real Sitio de Covadonga (RSC) - Deducción pendiente/generada [01865]
97 | 1560 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Centenarios del Real Sitio de Covadonga (RSC) - Aplicado en esta liquidación [01866]
98 | 1577 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Centenarios del Real Sitio de Covadonga (RSC) - Pendiente de aplicación en periodos futuros [01867]
99 | 1594 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato Mundial Junior Balonmano Masculino 2019 (BM19) - Deducción pendiente/generada [01868]
100 | 1611 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato Mundial Junior Balonmano Masculino 2019 (BM19) - Aplicado en esta liquidación [01869]
101 | 1628 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato Mundial Junior Balonmano Masculino 2019 (BM19) - Pendiente de aplicación en periodos futuros [01870]
102 | 1645 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Andalucía Valderrama Masters (AVM) - Deducción pendiente/generada [01874]
103 | 1662 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Andalucía Valderrama Masters (AVM) - Aplicado en esta liquidación [01875]
104 | 1679 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Andalucía Valderrama Masters (AVM) - Pendiente de aplicación en periodos futuros [01876]
105 | 1696 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 La Transición: 40 años de Libertad de Expresión (T) - Deducción pendiente/generada [01877]
106 | 1713 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 La Transición: 40 años de Libertad de Expresión (T) - Aplicado en esta liquidación [01878]
107 | 1730 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 La Transición: 40 años de Libertad de Expresión (T) - Pendiente de aplicación en periodos futuros [01879]
108 | 1747 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Barcelona Mobile World Capital (BMWC) - Deducción pendiente/generada [01880]
109 | 1764 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Barcelona Mobile World Capital (BMWC) - Aplicado en esta liquidación [01881]
110 | 1781 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Barcelona Mobile World Capital (BMWC) - Pendiente de aplicación en periodos futuros [01882]
111 | 1798 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Ceuta y la Legión, 100 años de unión (CL) - Deducción pendiente/generada [01883]
112 | 1815 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Ceuta y la Legión, 100 años de unión (CL) - Aplicado en esta liquidación [01884]
113 | 1832 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Ceuta y la Legión, 100 años de unión (CL) - Pendiente de aplicación en periodos futuros [01885]
114 | 1849 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019 (TMP) - Deducción pendiente/generada [01886]
115 | 1866 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019 (TMP) - Aplicado en esta liquidación [01887]
116 | 1883 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Campeonato del Mundo de Triatlón Multideporte Pontevedra 2019 (TMP) - Pendiente de aplicación en periodos futuros [01888]
117 | 1900 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Bádminton World Tour (BWT) - Deducción pendiente/generada [01889]
118 | 1917 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Bádminton World Tour (BWT) - Aplicado en esta liquidación [01890]
119 | 1934 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Bádminton World Tour (BWT) - Pendiente de aplicación en periodos futuros [01891]
120 | 1951 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Nuevas Metas (NM) - Deducción pendiente/generada [01892]
121 | 1968 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Nuevas Metas (NM) - Aplicado en esta liquidación [01893]
122 | 1985 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Nuevas Metas (NM) - Pendiente de aplicación en periodos futuros [01894]
123 | 2002 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Logroño 2021, nuestro V Centenario (L21) - Deducción pendiente/generada [01901]
124 | 2019 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Logroño 2021, nuestro V Centenario (L21) - Aplicado en esta liquidación [01902]
125 | 2036 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Logroño 2021, nuestro V Centenario (L21) - Pendiente de aplicación en periodos futuros [01903]
126 | 2053 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Santo Jacobeo 2021 (J21) - Deducción pendiente/generada [01907]
127 | 2070 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Santo Jacobeo 2021 (J21) - Aplicado en esta liquidación [01908]
128 | 2087 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Santo Jacobeo 2021 (J21) - Pendiente de aplicación en periodos futuros [01909]
129 | 2104 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VIII Centenario de la Catedral de Burgos 2021 (CB21) - Deducción pendiente/generada [01910]
130 | 2121 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VIII Centenario de la Catedral de Burgos 2021 (CB21) - Aplicado en esta liquidación [01911]
131 | 2138 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 VIII Centenario de la Catedral de Burgos 2021 (CB21) - Pendiente de aplicación en periodos futuros [01912]
132 | 2155 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deporte Inclusivo (DI) - Deducción pendiente/generada [01913]
133 | 2172 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deporte Inclusivo (DI) - Aplicado en esta liquidación [01914]
134 | 2189 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Deporte Inclusivo (DI) - Pendiente de aplicación en periodos futuros [01915]
135 | 2206 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 España, Capital del Talento Joven (E) - Deducción pendiente/generada [01919]
136 | 2223 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 España, Capital del Talento Joven (E) - Aplicado en esta liquidación [01920]
137 | 2240 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 España, Capital del Talento Joven (E) - Pendiente de aplicación en periodos futuros [01921]
138 | 2257 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Conmemoración del Centenario de la Coronación de Ntra. Sra. del Rocío (1919-2019) (CR) - Deducción pendiente/generada [01922]
139 | 2274 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Conmemoración del Centenario de la Coronación de Ntra. Sra. del Rocío (1919-2019) (CR) - Aplicado en esta liquidación [01923]
140 | 2291 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Conmemoración del Centenario de la Coronación de Ntra. Sra. del Rocío (1919-2019) (CR) - Pendiente de aplicación en periodos futuros [01924]
141 | 2308 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Traslado de la Imagen de Ntra. Sra. del Rocío desde la Aldea al
Pueblo de Almonte (TR) - Deducción pendiente/generada [01925]
142 | 2325 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Traslado de la Imagen de Ntra. Sra. del Rocío desde la Aldea al
Pueblo de Almonte (TR) - Aplicado en esta liquidación [01926]
143 | 2342 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Traslado de la Imagen de Ntra. Sra. del Rocío desde la Aldea al
Pueblo de Almonte (TR) - Pendiente de aplicación en periodos futuros [01927]
144 | 2359 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Europeo del Patrimonio Cultural (2018) (PC18) - Deducción pendiente/generada [01931]
145 | 2376 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Europeo del Patrimonio Cultural (2018) (PC18) - Aplicado en esta liquidación [01932]
146 | 2393 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Año Europeo del Patrimonio Cultural (2018) (PC18) - Pendiente de aplicación en periodos futuros [01933]
147 | 2410 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación (EN20) - Deducción pendiente/generada [01937]
148 | 2427 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación (EN20) - Aplicado en esta liquidación [01938]
149 | 2444 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Enfermedades Neurodegenerativas 2020. Año Internacional de la Investigación e Innovación (EN20) - Pendiente de aplicación en periodos futuros [01939]
150 | 2461 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Camino de la Cruz de Caravaca (CC) - Deducción pendiente/generada [01940]
151 | 2478 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Camino de la Cruz de Caravaca (CC) - Aplicado en esta liquidación [01941]
152 | 2495 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Camino de la Cruz de Caravaca (CC) - Pendiente de aplicación en periodos futuros [01942]
153 | 2512 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad (GPM) - Deducción pendiente/generada [01943]
154 | 2529 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad (GPM) - Aplicado en esta liquidación [01944]
155 | 2546 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 XXV Aniversario de la Declaración por la UNESCO del Real Monasterio de Santa María de Guadalupe como Patrimonio de la Humanidad (GPM) - Pendiente de aplicación en periodos futuros [01945]
156 | 2563 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Automobile Barcelona 2019 (AB19) - Deducción pendiente/generada [01946]
157 | 2580 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Automobile Barcelona 2019 (AB19) - Aplicado en esta liquidación [01947]
158 | 2597 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Automobile Barcelona 2019 (AB19) - Pendiente de aplicación en periodos futuros [01948]
159 | 2614 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Campeonato Mundial Balonmano Femenino 2021 (BF21) - Deducción pendiente/generada [01871]
160 | 2631 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Campeonato Mundial Balonmano Femenino 2021 (BF21) - Aplicado en esta liquidación [01872]
161 | 2648 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Campeonato Mundial Balonmano Femenino 2021 (BF21) - Pendiente de aplicación en periodos futuros [01873]
162 | 2665 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Barcelona Equestrian Challenge (3ª edición) (BE3) - Deducción pendiente/generada [01895]
163 | 2682 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Barcelona Equestrian Challenge (3ª edición) (BE3) - Aplicado en esta liquidación [01896]
164 | 2699 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Barcelona Equestrian Challenge (3ª edición) (BE3) - Pendiente de aplicación en periodos futuros [01897]
165 | 2716 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Universo Mujer II (UMII) - Deducción pendiente/generada [01898]
166 | 2733 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Universo Mujer II (UMII) - Aplicado en esta liquidación [01899]
167 | 2750 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Universo Mujer II (UMII) - Pendiente de aplicación en periodos futuros [01900]
168 | 2767 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Centenario Delibes (CD) - Deducción pendiente/generada [01904]
169 | 2784 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Centenario Delibes (CD) - Aplicado en esta liquidación [01905]
170 | 2801 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Centenario Delibes (CD) - Pendiente de aplicación en periodos futuros [01906]
171 | 2818 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Plan 2020 de Apoyo al Deporte Base II (P20-2) - Deducción pendiente/generada [01916]
172 | 2835 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Plan 2020 de Apoyo al Deporte Base II (P20-2) - Aplicado en esta liquidación [01917]
173 | 2852 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Plan 2020 de Apoyo al Deporte Base II (P20-2) - Pendiente de aplicación en periodos futuros [01918]
174 | 2869 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Camino Lebaniego (CL) - Deducción pendiente/generada [01928]
175 | 2886 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Camino Lebaniego (CL) - Aplicado en esta liquidación [01929]
176 | 2903 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Camino Lebaniego (CL) - Pendiente de aplicación en periodos futuros [01930]
177 | 2920 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Expo Dubai 2020 (D20) - Deducción pendiente/generada [01934]
178 | 2937 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Expo Dubai 2020 (D20) - Aplicado en esta liquidación [01935]
179 | 2954 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Expo Dubai 2020 (D20) - Pendiente de aplicación en periodos futuros [01936]
180 | 2971 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Resto deducciones relativas a programas de apoyo a acontecimientos de excepcional interés público - Deducción pendiente/generada [01683]
181 | 2988 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Resto deducciones relativas a programas de apoyo a acontecimientos de excepcional interés público - Aplicado en esta liquidación [01684]
182 | 3005 | 17 | Num | Deducc. para incentivar determ.actividades - 2019(****) Resto deducciones relativas a programas de apoyo a acontecimientos de excepcional interés público - Pendiente de aplicación en periodos futuros [01685]
183 | 3022 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés público - Deducción pendiente/generada [00634]
184 | 3039 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés público - Aplicado en esta liquidación [00635]
185 | 3056 | 17 | Num | Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés público - Pendiente de aplicación en periodos futuros [00636]
186 | 3073 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Diferim. deducciones Cap.IV Tít.VI Ley 43/95, RDL 4/2004 y LIS - Deducción pendiente/generada [00828]
187 | 3090 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Diferim. deducciones Cap.IV Tít.VI Ley 43/95, RDL 4/2004 y LIS - Aplicado en esta liquidación [00829]
188 | 3107 | 17 | Num | Deducc. para incentivar determ.actividades - 2018 Diferim. deducciones Cap.IV Tít.VI Ley 43/95, RDL 4/2004 y LIS - Pendiente de aplicación en periodos futuros [00830]
189 | 3124 | 17 | Num | Deducc. para incentivar determ.actividades - Total - Deducción pendiente/generada [00831]
190 | 3141 | 17 | Num | Deducc. para incentivar determ.actividades - Total - Aplicado en esta liquidación [00588]
191 | 3158 | 17 | Num | Deducc. para incentivar determ.actividades - Total - Pendiente de aplicación en periodos futuros [00832]
192 | 3175 | 200 | An | RESERVADO PARA LA AEAT
193 | 3375 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20018000>"
Total: |  | 3386

# DP200018B

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "18B00"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Deducción donativos entidades sin fines lucro - 2008 - Deducción pendiente/generada [00066]
7 | 30 | 17 | Num | Deducción donativos entidades sin fines lucro - 2008 - Aplicado en esta liquidación [00074]
8 | 47 | 17 | Num | Deducción donativos entidades sin fines lucro - 2009 - Deducción pendiente/generada [00008]
9 | 64 | 17 | Num | Deducción donativos entidades sin fines lucro - 2009 - Aplicado en esta liquidación [00009]
10 | 81 | 17 | Num | Deducción donativos entidades sin fines lucro - 2009 - Pendiente de aplicación en periodos futuros [00010]
11 | 98 | 17 | Num | Deducción donativos entidades sin fines lucro - 2010 - Deducción pendiente/generada [00034]
12 | 115 | 17 | Num | Deducción donativos entidades sin fines lucro - 2010 - Aplicado en esta liquidación [00035]
13 | 132 | 17 | Num | Deducción donativos entidades sin fines lucro - 2010 - Pendiente de aplicación en periodos futuros [00036]
14 | 149 | 17 | Num | Deducción donativos entidades sin fines lucro - 2011 - Deducción pendiente/generada [00201]
15 | 166 | 17 | Num | Deducción donativos entidades sin fines lucro - 2011 - Aplicado en esta liquidación [00202]
16 | 183 | 17 | Num | Deducción donativos entidades sin fines lucro - 2011 - Pendiente de aplicación en periodos futuros [00203]
17 | 200 | 17 | Num | Deducción donativos entidades sin fines lucro - 2012 - Deducción pendiente/generada [00904]
18 | 217 | 17 | Num | Deducción donativos entidades sin fines lucro - 2012 - Aplicado en esta liquidación [00905]
19 | 234 | 17 | Num | Deducción donativos entidades sin fines lucro - 2012 - Pendiente de aplicación en periodos futuros [00906]
20 | 251 | 17 | Num | Deducción donativos entidades sin fines lucro - 2013 - Deducción pendiente/generada [00990]
21 | 268 | 17 | Num | Deducción donativos entidades sin fines lucro - 2013 - Aplicado en esta liquidación [00991]
22 | 285 | 17 | Num | Deducción donativos entidades sin fines lucro - 2013 - Pendiente de aplicación en periodos futuros [00992]
23 | 302 | 17 | Num | Deducción donativos entidades sin fines lucro - 2014 - Deducción pendiente/generada [00997]
24 | 319 | 17 | Num | Deducción donativos entidades sin fines lucro - 2014 - Aplicado en esta liquidación [00998]
25 | 336 | 17 | Num | Deducción donativos entidades sin fines lucro - 2014 - Pendiente de aplicación en periodos futuros [00999]
26 | 353 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Deducción pendiente/generada [00246]
27 | 370 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Aplicado en esta liquidación [00247]
28 | 387 | 17 | Num | Deducción donativos entidades sin fines lucro - 2015 - Pendiente de aplicación en periodos futuros [00248]
29 | 404 | 17 | Num | Deducción donativos entidades sin fines lucro - 2016 - Deducción pendiente/generada [00993]
30 | 421 | 17 | Num | Deducción donativos entidades sin fines lucro - 2016 - Aplicado en esta liquidación [00994]
31 | 438 | 17 | Num | Deducción donativos entidades sin fines lucro - 2016 - Pendiente de aplicación en periodos futuros [00995]
32 | 455 | 17 | Num | Deducción donativos entidades sin fines lucro - 2017 - Deducción pendiente/generada [01434]
33 | 472 | 17 | Num | Deducción donativos entidades sin fines lucro - 2017 - Aplicado en esta liquidación [01435]
34 | 489 | 17 | Num | Deducción donativos entidades sin fines lucro - 2017 - Pendiente de aplicación en periodos futuros [01436]
35 | 506 | 17 | Num | Deducción donativos entidades sin fines lucro - 2018(*) - Deducción pendiente/generada [01718]
36 | 523 | 17 | Num | Deducción donativos entidades sin fines lucro - 2018(*) - Aplicado en esta liquidación [01719]
37 | 540 | 17 | Num | Deducción donativos entidades sin fines lucro - 2018(*) - Pendiente de aplicación en periodos futuros [01720]
38 | 557 | 17 | Num | Deducción donativos entidades sin fines lucro - 2018 - Deducción pendiente/generada [01950]
39 | 574 | 17 | Num | Deducción donativos entidades sin fines lucro - 2018 - Aplicado en esta liquidación [01951]
40 | 591 | 17 | Num | Deducción donativos entidades sin fines lucro - 2018 - Pendiente de aplicación en periodos futuros [01952]
41 | 608 | 17 | Num | Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro - Deducción pendiente/generada [00598]
42 | 625 | 17 | Num | Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro - Aplicado en esta liquidación [00565]
43 | 642 | 17 | Num | Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro - Pendiente de aplicación en periodos futuros [00895]
44 | 659 | 17 | Num | Deducción donativos entidades sin fines lucro - Donaciones del período impositivo efectuadas a entidades sin fines de lucro [00974]
45 | 676 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Base deducción [01166]
46 | 693 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe generado/pendiente principio periodo [01167]
47 | 710 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe aplicado [01437]
48 | 727 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2015 - Importe pendiente [01169]
49 | 744 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2016 - Base deducción [01438]
50 | 761 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2016 - Importe generado/pendiente principio periodo [01439]
51 | 778 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2016 - Importe aplicado [01440]
52 | 795 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2016 - Importe pendiente [01441]
53 | 812 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2017 - Base deducción [01442]
54 | 829 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2017 - Importe generado/pendiente principio periodo [01443]
55 | 846 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2017 - Importe aplicado [01444]
56 | 863 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2017 - Importe pendiente [01445]
57 | 880 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2018(*) - Base deducción [01721]
58 | 897 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2018(*) - Importe generado/pendiente principio periodo [01722]
59 | 914 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2018(*) - Importe aplicado [01723]
60 | 931 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2018(*) - Importe pendiente [01724]
61 | 948 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2018 - Base deducción [01953]
62 | 965 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2018 - Importe generado/pendiente principio periodo [01954]
63 | 982 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2018 - Importe aplicado [01955]
64 | 999 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - 2018 - Importe pendiente [01956]
65 | 1016 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - Total - Base deducción [01170]
66 | 1033 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - Total - Importe generado/pendiente principio periodo [01171]
67 | 1050 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - Total - Importe aplicado [01040]
68 | 1067 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 1 LIS) - Total - Importe pendiente [01173]
69 | 1084 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Base deducción [01178]
70 | 1101 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe generado/pendiente principio periodo [01179]
71 | 1118 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe aplicado [01446]
72 | 1135 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2015 - Importe pendiente [01181]
73 | 1152 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2016 - Base deducción [01447]
74 | 1169 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2016 - Importe generado/pendiente principio periodo [01448]
75 | 1186 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2016 - Importe aplicado [01449]
76 | 1203 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2016 - Importe pendiente [01450]
77 | 1220 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2017 - Base deducción [01451]
78 | 1237 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2017 - Importe generado/pendiente principio periodo [01452]
79 | 1254 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2017 - Importe aplicado [01453]
80 | 1271 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2017 - Importe pendiente [01454]
81 | 1288 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2018(*) - Base deducción [01725]
82 | 1305 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2018(*) - Importe generado/pendiente principio periodo [01726]
83 | 1322 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2018(*) - Importe aplicado [01727]
84 | 1339 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2018(*) - Importe pendiente [01728]
85 | 1356 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2018 - Base deducción [01957]
86 | 1373 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2018 - Importe generado/pendiente principio periodo [01958]
87 | 1390 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2018 - Importe aplicado [01959]
88 | 1407 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - 2018 - Importe pendiente [01960]
89 | 1424 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - Total - Base deducción [01182]
90 | 1441 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - Total - Importe generado/pendiente principio periodo [01183]
91 | 1458 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - Total - Importe aplicado [01041]
92 | 1475 | 17 | Num | Deducción por reinversión de medidas temporales (D.T.37ª. 2 LIS) - Total - Importe pendiente [01185]
93 | 1492 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01141]
94 | 1509 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe adicionado base imponible en periodo [01142]
95 | 1526 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2015 - Importe pendiente adicionar en periodos futuros [01143]
96 | 1543 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2016 - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01144]
97 | 1560 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2016 - Importe adicionado base imponible en periodo [01145]
98 | 1577 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2016 - Importe pendiente adicionar en periodos futuros [01146]
99 | 1594 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2017 - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01455]
100 | 1611 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2017 - Importe adicionado base imponible en periodo [01456]
101 | 1628 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2017 - Importe pendiente adicionar en periodos futuros [01457]
102 | 1645 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2018(*) - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01961]
103 | 1662 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2018(*) - Importe adicionado base imponible en periodo [01962]
104 | 1679 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2018(*) - Importe pendiente adicionar en periodos futuros [01963]
105 | 1696 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2018 - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01034]
106 | 1713 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2018 - Importe adicionado base imponible en periodo [01730]
107 | 1730 | 17 | Num | Reserva de nivelación - Reducción base imponible - Ejercicio generación 2018 - Importe pendiente adicionar en periodos futuros [01731]
108 | 1747 | 17 | Num | Reserva de nivelación - Reducción base imponible - Total - Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01147]
109 | 1764 | 17 | Num | Reserva de nivelación - Reducción base imponible - Total - Importe adicionado base imponible en periodo [01033]
110 | 1781 | 17 | Num | Reserva de nivelación - Reducción base imponible - Total - Importe pendiente adicionar en periodos futuros [01149]
111 | 1798 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015 - Importe reserva a dotar [01150]
112 | 1815 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015 - Importe reserva dotada [01151]
113 | 1832 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015 - Importe reserva pendiente dotación [01152]
114 | 1849 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2015 - Reserva dispuesta [01153]
115 | 1866 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2016 - Importe reserva a dotar [01154]
116 | 1883 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2016 - Importe reserva dotada [01155]
117 | 1900 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2016 - Importe reserva pendiente dotación [01156]
118 | 1917 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2016 - Reserva dispuesta [01157]
119 | 1934 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2017 - Importe reserva a dotar [01458]
120 | 1951 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2017 - Importe reserva dotada [01459]
121 | 1968 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2017 - Importe reserva pendiente dotación [01460]
122 | 1985 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2017 - Reserva dispuesta [01461]
123 | 2002 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2018(*) - Importe reserva a dotar [01732]
124 | 2019 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2018(*) - Importe reserva dotada [01733]
125 | 2036 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2018(*) - Importe reserva pendiente dotación [01734]
126 | 2053 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2018(*) - Reserva dispuesta [01735]
127 | 2070 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2018 - Importe reserva a dotar [01964]
128 | 2087 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2018 - Importe reserva dotada [01965]
129 | 2104 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2018 - Importe reserva pendiente dotación [01966]
130 | 2121 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Ejercicio generación 2018 - Reserva dispuesta [01967]
131 | 2138 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Total - Importe reserva a dotar [01158]
132 | 2155 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Total - Importe reserva dotada [01159]
133 | 2172 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Total - Importe reserva pendiente dotación [01160]
134 | 2189 | 17 | Num | Reserva de nivelación - Dotación de la reserva - Total - Reserva dispuesta [01161]
135 | 2206 | 1 | An | Deducción donativos entidades sin fines de lucro. Ley 49/2002. Indique si entre las deducciones que se van a aplicar hay actividades prioritarias de mecenazgo |  | "0" o "1"
136 | 2207 | 1 | An | Deducción donativos entidades sin fines de lucro. Ley 49/2002. Indique si en los dos períodos impositivos inmediatos anteriores hubieran realizado donaciones o aportaciones con derecho a deducción a favor de una misma entidad por importe igual o superior en cada uno de ellos, al del período impositivo anterior |  | "0" o "1"
137 | 2208 | 198 | An | RESERVADO PARA LA AEAT
138 | 2406 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20018B00>"
Total: |  | 2417

# DP200019

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "19000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Deducción pendiente/generada [00918]
7 | 30 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Deducción reducida [00919]
8 | 47 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Aplicado en esta liquidación [00574]
9 | 64 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Importe abonado por insuficiencia de cuota [00580]
10 | 81 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Deducción resto del grupo |  | Nota 1
11 | 98 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Deducción pendiente/generada [00589]
12 | 115 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Deducción reducida [00976]
13 | 132 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Aplicado en esta liquidación [00977]
14 | 149 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Importe abonado por insuficiencia de cuota [00978]
15 | 166 | 17 | Num | Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Deducción resto del grupo |  | Nota 1
16 | 183 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Deducción pendiente/generada [00822]
17 | 200 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Deducción reducida [00823]
18 | 217 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Aplicado en esta liquidación [00824]
19 | 234 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Importe abonado por insuficiencia de cuota [00231]
20 | 251 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Investigación y desarrollo - Deducción resto del grupo |  | Nota 1
21 | 268 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Deducción pendiente/generada [00232]
22 | 285 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Deducción reducida [00233]
23 | 302 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Aplicado en esta liquidación [00850]
24 | 319 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Importe abonado por insuficiencia de cuota [00851]
25 | 336 | 17 | Num | Deducciones I+D+i excluidas de límite - 2014 Innovación tecnológica - Deducción resto del grupo |  | Nota 1
26 | 353 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Deducción pendiente/generada [01123]
27 | 370 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Deducción reducida [01124]
28 | 387 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Aplicado en esta liquidación [01125]
29 | 404 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Importe abonado por insuficiencia de cuota [01126]
30 | 421 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Investigación y desarrollo - Deducción resto del grupo |  | Nota 1
31 | 438 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Deducción pendiente/generada [01127]
32 | 455 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Deducción reducida [01128]
33 | 472 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Aplicado en esta liquidación [01129]
34 | 489 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Importe abonado por insuficiencia de cuota [01130]
35 | 506 | 17 | Num | Deducciones I+D+i excluidas de límite - 2015 Innovación tecnológica - Deducción resto del grupo |  | Nota 1
36 | 523 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Investigación y desarrollo - Deducción pendiente/generada [01426]
37 | 540 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Investigación y desarrollo - Deducción reducida [01427]
38 | 557 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Investigación y desarrollo - Aplicado en esta liquidación [01428]
39 | 574 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Investigación y desarrollo - Importe abonado por insuficiencia de cuota [01429]
40 | 591 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Investigación y desarrollo - Deducción resto del grupo |  | Nota 1
41 | 608 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Innovación tecnológica - Deducción pendiente/generada [01430]
42 | 625 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Innovación tecnológica - Deducción reducida [01431]
43 | 642 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Innovación tecnológica - Aplicado en esta liquidación [01432]
44 | 659 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Innovación tecnológica - Importe abonado por insuficiencia de cuota [01433]
45 | 676 | 17 | Num | Deducciones I+D+i excluidas de límite - 2016 Innovación tecnológica - Deducción resto del grupo |  | Nota 1
46 | 693 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Investigación y desarrollo - Deducción pendiente/generada [01710]
47 | 710 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Investigación y desarrollo - Deducción reducida [01711]
48 | 727 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Investigación y desarrollo - Aplicado en esta liquidación [01712]
49 | 744 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Investigación y desarrollo - Importe abonado por insuficiencia de cuota [01713]
50 | 761 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Investigación y desarrollo - Deducción resto del grupo |  | Nota 1
51 | 778 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Innovación tecnológica - Deducción pendiente/generada [01714]
52 | 795 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Innovación tecnológica - Deducción reducida [01715]
53 | 812 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Innovación tecnológica - Aplicado en esta liquidación [01716]
54 | 829 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Innovación tecnológica - Importe abonado por insuficiencia de cuota [01717]
55 | 846 | 17 | Num | Deducciones I+D+i excluidas de límite - 2017 Innovación tecnológica - Deducción resto del grupo |  | Nota 1
56 | 863 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Investigación y desarrollo - Deducción pendiente/generada [01968]
57 | 880 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Investigación y desarrollo - Deducción reducida [01969]
58 | 897 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Investigación y desarrollo - Aplicado en esta liquidación [01970]
59 | 914 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Investigación y desarrollo - Importe abonado por insuficiencia de cuota [01971]
60 | 931 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Investigación y desarrollo - Deducción resto del grupo |  | Nota 1
61 | 948 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Innovación tecnológica - Deducción pendiente/generada [01972]
62 | 965 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Innovación tecnológica - Deducción reducida [01973]
63 | 982 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Innovación tecnológica - Aplicado en esta liquidación [01974]
64 | 999 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Innovación tecnológica - Importe abonado por insuficiencia de cuota [01975]
65 | 1016 | 17 | Num | Deducciones I+D+i excluidas de límite - 2018(*) Innovación tecnológica - Deducción resto del grupo |  | Nota 1
66 | 1033 | 17 | Num | Deducciones I+D+i excluidas de límite - Total - Deducción pendiente/generada [00517]
67 | 1050 | 17 | Num | Deducciones I+D+i excluidas de límite - Total - Deducción reducida [00081]
68 | 1067 | 17 | Num | Deducciones I+D+i excluidas de límite - Total - Aplicado en esta liquidación [00082]
69 | 1084 | 17 | Num | Deducciones I+D+i excluidas de límite - Total - Importe abonado por insuficiencia de cuota [01234]
70 | 1101 | 17 | Num | Aplicación de resultados - Base de reparto - Pérdidas y ganancias [00650]
71 | 1118 | 17 | Num | Aplicación de resultados - Base de reparto - Remanente [00651]
72 | 1135 | 17 | Num | Aplicación de resultados - Base de reparto - Reservas [00652]
73 | 1152 | 17 | Num | Aplicación de resultados - Base de reparto - Total [00653]
74 | 1169 | 17 | Num | Aplicación de resultados - Aplicación - A reservas [00654]
75 | 1186 | 17 | Num | Aplicación de resultados - Aplicación - A reservas - Reservas de capitalización [01270]
76 | 1203 | 17 | Num | Aplicación de resultados - Aplicación - A reservas - Reserva de nivelación [01271]
77 | 1220 | 17 | Num | Aplicación de resultados - Aplicación - A reservas - Otras reservas [01522]
78 | 1237 | 17 | Num | Aplicación de resultados - Aplicación - Intereses aportaciones al capital (Cooperativas) [00655]
79 | 1254 | 17 | Num | Aplicación de resultados - Aplicación - A dividendos [00656]
80 | 1271 | 17 | Num | Aplicación de resultados - Aplicación - A dotación O.S. (Cajas de ahorro y fundaciones bancarias) [00658]
81 | 1288 | 17 | Num | Aplicación de resultados - Aplicación - A F.R.O y dotaciones voluntarias al F.E.P (Cooperativas) [00659]
82 | 1305 | 17 | Num | Aplicación de resultados - Aplicación - A retornos cooperativos (Cooperativas) [00660]
83 | 1322 | 17 | Num | Aplicación de resultados - Aplicación - Partícipes (IIC) [00662]
84 | 1339 | 17 | Num | Aplicación de resultados - Aplicación - A remanente y otros [00664]
85 | 1356 | 17 | Num | Aplicación de resultados - Aplicación - A compensación de pérdidas de ejercicios anteriores [00665]
86 | 1373 | 17 | Num | Aplicación de resultados - Aplicación - Total [00666]
87 | 1390 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correcciones permanentes - Del ejercicio - Aumentos
88 | 1407 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correcciones permanentes - Del ejercicio - Disminuciones
89 | 1424 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Del ejercicio - Aumentos
90 | 1441 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Del ejercicio - Disminuciones
91 | 1458 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Saldo pendiente - Aumentos futuros
92 | 1475 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Saldo pendiente - Disminuciones futuras
93 | 1492 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Amortizaciones - Del ejercicio - Aumentos
94 | 1509 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Amortizaciones - Del ejercicio - Disminuciones
95 | 1526 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Amortizaciones - Saldo pendiente - Aumentos futuros
96 | 1543 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Amortizaciones - Saldo pendiente - Disminuciones futuras
97 | 1560 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Deterioros valor - Del ejercicio - Aumentos
98 | 1577 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Deterioros valor - Del ejercicio - Disminuciones
99 | 1594 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Deterioros valor - Saldo pendiente - Aumentos futuros
100 | 1611 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Deterioros valor - Saldo pendiente - Disminuciones futuras
101 | 1628 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Pensiones - Del ejercicio - Aumentos
102 | 1645 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Pensiones - Del ejercicio - Disminuciones
103 | 1662 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Pensiones - Saldo pendiente - Aumentos futuros
104 | 1679 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Pensiones - Saldo pendiente - Disminuciones futuras
105 | 1696 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Fondo de comercio - Del ejercicio - Aumentos
106 | 1713 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Fondo de comercio - Del ejercicio - Disminuciones
107 | 1730 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Fondo de comercio - Saldo pendiente - Aumentos futuros
108 | 1747 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Fondo de comercio - Saldo pendiente - Disminuciones futuras
109 | 1764 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Resto - Aumentos
110 | 1781 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Resto - Disminuciones
111 | 1798 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Resto - Saldo pendiente - Aumentos futuros
112 | 1815 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejercicio - Resto - Saldo pendiente - Disminuciones futuras
113 | 1832 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Del ejercicio - Aumentos
114 | 1849 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Del ejercicio - Disminuciones
115 | 1866 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Saldo pendiente - Aumentos futuros
116 | 1883 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Saldo pendiente - Disminuciones futuras
117 | 1900 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Amortizaciones - Del ejercicio - Aumentos
118 | 1917 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Amortizaciones - Del ejercicio - Disminuciones
119 | 1934 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Amortizaciones - Saldo pendiente - Aumentos futuros
120 | 1951 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Amortizaciones - Saldo pendiente - Disminuciones futuras
121 | 1968 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Deterioros valor - Del ejercicio - Aumentos
122 | 1985 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Deterioros valor - Del ejercicio - Disminuciones
123 | 2002 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Deterioros valor - Saldo pendiente - Aumentos futuros
124 | 2019 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Deterioros valor - Saldo pendiente - Disminuciones futuras
125 | 2036 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Pensiones - Del ejercicio - Aumentos
126 | 2053 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Pensiones - Del ejercicio - Disminuciones
127 | 2070 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Pensiones - Saldo pendiente - Aumentos futuros
128 | 2087 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Pensiones - Saldo pendiente - Disminuciones futuras
129 | 2104 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Fondo de comercio - Del ejercicio - Aumentos
130 | 2121 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Fondo de comercio - Del ejercicio - Disminuciones
131 | 2138 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Fondo de comercio - Saldo pendiente - Aumentos futuros
132 | 2155 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Fondo de comercio - Saldo pendiente - Disminuciones futuras
133 | 2172 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Resto - Del ejercicio - Aumentos
134 | 2189 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Resto - Del ejercicio - Disminuciones
135 | 2206 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Resto - Saldo pendiente - Aumentos futuros
136 | 2223 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc. anteriores - Resto - Saldo pendiente - Disminuciones futuras
137 | 2240 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de pérdidas y ganancias - Del ejercicio - Aumentos  [00417]
138 | 2257 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de pérdidas y ganancias - Del ejercicio - Disminuciones [00418]
139 | 2274 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de pérdidas y ganancias - Saldo pendiente - Aumentos futuros
140 | 2291 | 17 | Num | Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de pérdidas y ganancias - Saldo pendiente - Disminuciones futuras
141 | 2308 | 200 | An | RESERVADO PARA LA AEAT
142 | 2508 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20019000>"
Total: |  | 2519
Nota 1:
A cumplimentar exclusivamente por entidades que pertenezcan a grupos mercantiles (carácter 00039)

# DP200020

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "20000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS - a) Gastos financieros período impositivo derivados por adquisicion de partic. (sin signo) [01240]
7 | 30 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS - b) límite adicional a la deducc. de gastos financieros (sin signo) [01241]
8 | 47 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS - c1) Gastos financieros período imposit. deducibles tras aplicac. límite art. 16.5 y/o 83 LIS [01242]
9 | 64 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS - c2) Gastos financieros período imposit. no deducibles tras aplicac. límite art. 16.5 y/o 83 LIS [01243]
10 | 81 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.5, 67 b) o 83 LIS - d) Gastos financieros pendientes de deducir en período ant. afectados por art. 16.5 y/o 83 LIS [01244]
11 | 98 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - e) Gastos financieros del período no afectados por art. 16.5, 67 b) y/o 83 LIS (sin signo) [01245]
12 | 115 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - f) Gastos financieros del período imposit. [01246]
13 | 132 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - g) Ingresos financieros del período impos. derivados de la cesión a terceros de capitales propios [01247]
14 | 149 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - h) Gastos financieros netos del período impositivo [01248]
15 | 166 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - i) Límite a la deducción de gastos financieros netos [01249]
16 | 183 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - i1) Resultado de explotación (signo igual a Cta.de Pérd. y Gan) [01250]
17 | 200 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - i2) Amortización del inmovilizado (signo igual a Cta.de Pérd. y Gan) [01251]
18 | 217 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - i3) Imputación de subvenciones de inmovilizado no financiero y otras (signo igual a Cta.de Pérd. y Gan) [01252]
19 | 234 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - i4) Deterioro y resultado por enajenaciones del inmovilizado (signo igual a Cta.de Pérd. y Gan) [01253]
20 | 251 | 17 | N | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - i5) Ingresos financieros de participaciones en instrumentos de patrimonio (signo igual a Cta.de Pérd. y Gan) [01254]
21 | 268 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - j) Adición por límite beneficio operativo no aplicado en los cinco ejercicios anteriores [01255]
22 | 285 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - k1) Gastos financieros netos del período impositivo deducibles [01256]
23 | 302 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - k2) Gastos financieros netos del período impositivo no deducibles [01257]
24 | 319 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - l) Gastos financieros pendientes de deducir en períodos imposit.anteriores por art 16.5 y/o 83 LIS deducibles tras aplicar los 2 límites [01258]
25 | 336 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - m) Gastos financieros pendientes de deducir de períodos impositivos anteriores no afectados por art 16.5 y/o 83 LIS aplicados [01259]
26 | 353 | 17 | Num | Limitación deducibilidad gastos financieros - limite art. 16.1 y 16.2 LIS - Total gastos financieros del período impositivo no deducibles [01260]
27 | 370 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2012 - Pendiente aplicación a principio del período - Resto [01188]
28 | 387 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2012 - Aplicado en esta liquidación [01189]
29 | 404 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2012 - Pendiente aplicación en períodos futuros - Resto [01191]
30 | 421 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2013 - Pendiente aplicación a principio del período - Resto [01193]
31 | 438 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2013 - Aplicado en esta liquidación [01194]
32 | 455 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2013 - Pendiente aplicación en períodos futuros - Resto [01196]
33 | 472 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2014 - Pendiente aplicación a principio del período - Resto [01198]
34 | 489 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2014 - Aplicado en esta liquidación [01199]
35 | 506 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2014 - Pendiente aplicación en períodos futuros - Resto [01201]
36 | 523 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2015 - Pendiente aplicación a principio del período - Por límite [01202]
37 | 540 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2015 - Pendiente aplicación a principio del período - Resto [01203]
38 | 557 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2015 - Aplicado en esta liquidación [01204]
39 | 574 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2015 - Pendiente aplicación en períodos futuros - Por límite [01205]
40 | 591 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2015 - Pendiente aplicación en períodos futuros - Resto [01206]
41 | 608 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2016 - Pendiente aplicación a principio del período - Por límite [01462]
42 | 625 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2016 - Pendiente aplicación a principio del período - Resto [01463]
43 | 642 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2016 - Aplicado en esta liquidación [01209]
44 | 659 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2016 - Pendiente aplicación en períodos futuros - Por límite [01210]
45 | 676 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2016 - Pendiente aplicación en períodos futuros - Resto [01211]
46 | 693 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2017 - Pendiente aplicación a principio del período - Por límite [01736]
47 | 710 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2017 - Pendiente aplicación a principio del período - Resto [01737]
48 | 727 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2017 - Aplicado en esta liquidación [01464]
49 | 744 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2017 - Pendiente aplicación en períodos futuros - Por límite [01465]
50 | 761 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2017 - Pendiente aplicación en períodos futuros - Resto [01466]
51 | 778 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2018(*) - Pendiente aplicación a principio del período - Por límite [01977]
52 | 795 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2018(*) - Pendiente aplicación a principio del período - Resto [01978]
53 | 812 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2018(*) - Aplicado en esta liquidación [01738]
54 | 829 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2018(*) - Pendiente aplicación en períodos futuros - Por límite [01739]
55 | 846 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2018(*) - Pendiente aplicación en períodos futuros - Resto [01740]
56 | 863 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2018(**) - Aplicado en esta liquidación [01979]
57 | 880 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2018(**) - Pendiente aplicación en períodos futuros - Por límite [01980]
58 | 897 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Ejercicio generación 2018(**) - Pendiente aplicación en períodos futuros - Resto [01981]
59 | 914 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Total - Pendiente aplicación a principio del período - Por límite [01212]
60 | 931 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Total - Pendiente aplicación a principio del período - Resto [01213]
61 | 948 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Total - Aplicado en esta liquidación [01214]
62 | 965 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Total - Pendiente aplicación en períodos futuros - Por límite [01215]
63 | 982 | 17 | Num | Limitación deducibilidad gastos financieros. gastos financieros pendientes deducir - Total - Pendiente aplicación en períodos futuros - Resto [01216]
64 | 999 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013 - Pendiente aplicación a principio del período [00503]
65 | 1016 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013 - Aplicado en esta liquidación [00522]
66 | 1033 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2014 - Pendiente aplicación a principio del período [00273]
67 | 1050 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2014 - Aplicado en esta liquidación [00274]
68 | 1067 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2014 - Pendiente aplicación períodos futuros [00537]
69 | 1084 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Pendiente aplicación a principio del período [00955]
70 | 1101 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Aplicado en esta liquidación [00956]
71 | 1118 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2015 - Pendiente aplicación períodos futuros [00957]
72 | 1135 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2016 - Pendiente aplicación a principio del período [01217]
73 | 1152 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2016 - Aplicado en esta liquidación [01218]
74 | 1169 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2016 - Pendiente aplicación períodos futuros [01219]
75 | 1186 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2017 - Pendiente aplicación a principio del período [01467]
76 | 1203 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2017 - Aplicado en esta liquidación [01468]
77 | 1220 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2017 - Pendiente aplicación períodos futuros [01469]
78 | 1237 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2018(*) - Pendiente aplicación a principio del período [01741]
79 | 1254 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2018(*) - Aplicado en esta liquidación [01742]
80 | 1271 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2018(*) - Pendiente aplicación períodos futuros [01743]
81 | 1288 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2018(**) - Pendiente aplicación a principio del período [01982]
82 | 1305 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2018(**) - Aplicado en esta liquidación [01983]
83 | 1322 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2018(**) - Pendiente aplicación períodos futuros [01984]
84 | 1339 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Total - Pendiente aplicación a principio del período [00538]
85 | 1356 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Total - Aplicado en esta liquidación [00539]
86 | 1373 | 17 | Num | Pendiente adición por límite beneficio operativo no aplicado - Total - Pendiente aplicación períodos futuros [00546]
87 | 1390 | 200 | An | RESERVADO PARA LA AEAT
88 | 1590 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20020000>"
Total: |  | 1601

# DP200020B

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "20B00"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Reserva Capitalización - 2016 - Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo [01134]
7 | 30 | 17 | Num | Reserva Capitalización - 2016 - Reducción B.I. aplicada [01135]
8 | 47 | 17 | Num | Reserva Capitalización - 2017 - Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo [01470]
9 | 64 | 17 | Num | Reserva Capitalización - 2017 - Reducción B.I. aplicada [01471]
10 | 81 | 17 | Num | Reserva Capitalización - 2017 - Reducción B.I. pdte. De aplicar en períodos futuros [01472]
11 | 98 | 17 | Num | Reserva Capitalización - 2018(*) - Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo [01744]
12 | 115 | 17 | Num | Reserva Capitalización - 2018(*) - Reducción B.I. aplicada [01745]
13 | 132 | 17 | Num | Reserva Capitalización - 2018(*) - Reducción B.I. pdte. De aplicar en períodos futuros [01746]
14 | 149 | 17 | Num | Reserva Capitalización - 2018 - Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo [01985]
15 | 166 | 17 | Num | Reserva Capitalización - 2018 - Reducción B.I. aplicada [01986]
16 | 183 | 17 | Num | Reserva Capitalización - 2018 - Reducción B.I. pdte. De aplicar en períodos futuros [01987]
17 | 200 | 17 | Num | Reserva Capitalización - Total - Derecho reducir B.I. generado periodo/pendiente aplicar inicio periodo [01137]
18 | 217 | 17 | Num | Reserva Capitalización - Total - Reducción B.I. aplicada [01032]
19 | 234 | 17 | Num | Reserva Capitalización - Total - Reducción B.I. pdte. de aplicar en períodos futuros [01139]
20 | 251 | 17 | Num | Reserva Capitalización dotada en el ejercicio [01140]
21 | 268 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2007 y anteriores - Que no han cumplido condiciones deducibilidad fiscal [01473]
22 | 285 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2007 y anteriores - Que han cumplido condiciones deducibilidad fiscal [01408]
23 | 302 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2007 y anteriores - Dotaciones integradas en liquidación [01474]
24 | 319 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2007 y anteriores - Dotaciones aplicadas conversión activos imp. diferido [01475]
25 | 336 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2007 y anteriores - Que no han cumplido condiciones deducibilidad fiscal [01476]
26 | 353 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2007 y anteriores - Que han cumplido condiciones deducibilidad fiscal [01409]
27 | 370 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2008 a 2015 - Que no han cumplido condiciones deducibilidad fiscal [01477]
28 | 387 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2008 a 2015 - Que han cumplido condiciones deducibilidad fiscal [01478]
29 | 404 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2008 a 2015 - Dotaciones integradas en liquidación [01481]
30 | 421 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2008 a 2015 - Dotaciones aplicadas conversión activos imp. diferido [01482]
31 | 438 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2008 a 2015 - Que no han cumplido condiciones deducibilidad fiscal [01483]
32 | 455 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2008 a 2015 - Que han cumplido condiciones deducibilidad fiscal [01484]
33 | 472 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2016 - Que no han cumplido condiciones deducibilidad fiscal [01485]
34 | 489 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2016 - Que han cumplido condiciones deducibilidad fiscal [01486]
35 | 506 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2016 - Dotaciones integradas en liquidación [01487]
36 | 523 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2016 - Dotaciones aplicadas conversión activos imp. diferido [01488]
37 | 540 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2016 - Que no han cumplido condiciones deducibilidad fiscal [01489]
38 | 557 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2016 - Que han cumplido condiciones deducibilidad fiscal [01490]
39 | 574 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2017 - Que no han cumplido condiciones deducibilidad fiscal [01491]
40 | 591 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2017 - Que han cumplido condiciones deducibilidad fiscal [01747]
41 | 608 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2017 - Dotaciones integradas en liquidación [01748]
42 | 625 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2017 - Dotaciones aplicadas conversión activos imp. diferido [01492]
43 | 642 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2017 - Que no han cumplido condiciones deducibilidad fiscal [01493]
44 | 659 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2017 - Que han cumplido condiciones deducibilidad fiscal [01749]
45 | 676 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2018(*) - Que no han cumplido condiciones deducibilidad fiscal [01750]
46 | 693 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2018(*) - Que han cumplido condiciones deducibilidad fiscal [01988]
47 | 710 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2018(*) - Dotaciones integradas en liquidación [01989]
48 | 727 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2018(*) - Dotaciones aplicadas conversión activos imp. diferido [01751]
49 | 744 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2018(*) - Que no han cumplido condiciones deducibilidad fiscal [01752]
50 | 761 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2018(*) - Que han cumplido condiciones deducibilidad fiscal [01990]
51 | 778 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2018 - Que no han cumplido condiciones deducibilidad fiscal [01991]
52 | 795 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Ejercicio generación - 2018 - Dotaciones aplicadas conversión activos imp. diferido [01992]
53 | 812 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Ejercicio generación - 2018 - Que no han cumplido condiciones deducibilidad fiscal [01993]
54 | 829 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Total - Que no han cumplido condiciones deducibilidad fiscal [01494]
55 | 846 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Total - Que han cumplido condiciones deducibilidad fiscal [01495]
56 | 863 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Total - Dotaciones integradas en liquidación [01496]
57 | 880 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración a principio periodo - Total - Dotaciones aplicadas conversión activos imp. diferido [01497]
58 | 897 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Total - Que no han cumplido condiciones deducibilidad fiscal [01498]
59 | 914 | 17 | Num | Dotaciones deterioro créditos u otros activos - Dotaciones pendientes integración periodos futuros - Total - Que han cumplido condiciones deducibilidad fiscal [01499]
60 | 931 | 1 | Num | Reversión pérdidas deterioro valores representativos o fondos propios entidades pendientes reversión -Número periodo impositivo (*)
61 | 932 | 17 | Num | Reversión pérdidas deterioro valores representativos o fondos propios entidades pendientes reversión - Dotaciones pendientes integración a principio periodo [01515]
62 | 949 | 17 | Num | Reversión pérdidas deterioro valores representativos o fondos propios entidades pendientes reversión - Dotaciones integradas en esta liquidación DT 16ª.1 y 2 LIS [01516]
63 | 966 | 17 | Num | Reversión pérdidas deterioro valores representativos o fondos propios entidades pendientes reversión - Dotaciones integradas en esta liquidación DT 16ª.3 LIS [01585]
64 | 983 | 17 | Num | Reversión pérdidas deterioro valores representativos o fondos propios entidades pendientes reversión - Dotaciones pendientes integración en periodos futuros [01517]
65 | 1000 | 200 | An | RESERVADO PARA LA AEAT
66 | 1200 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20020B00>"
Total: |  | 1211

# DP200020C

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "20C00"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - 2007 y anteriores - Importe total AID pendiente aplicación a principio periodo  [01524]
7 | 30 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - 2007 y anteriores - AID aplicados en el periodo  [01525]
8 | 47 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - 2007 y anteriores - AID convertidos en crédito  [01526]
9 | 64 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - 2007 y anteriores - AID pendientes aplicación periodos futuros - Sin prestación patrimonial  [01527]
10 | 81 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - 2007 y anteriores - AID pendientes aplicación periodos futuros -  Importe total AID pendientes  [01528]
11 | 98 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total 2008 a 2015 - Importe total AID pendiente aplicación a principio periodo  [01529]
12 | 115 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total 2008 a 2015 - Cuota líquida positiva  [01530]
13 | 132 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total 2008 a 2015 - AID aplicados en el periodo [01590]
14 | 149 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total 2008 a 2015 - AID convertidos en crédito [01591]
15 | 166 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total 2008 a 2015 - Con prestación patrimonial [01531]
16 | 183 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total 2008 a 2015 - AID pendientes aplicación periodos futuros -  Sin prestación patrimonial [01532]
17 | 200 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total 2008 a 2015 - AID pendientes aplicación periodos futuros -  Sin prestación patrimonial. Minoración prestación exceso cuota [01533]
18 | 217 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total 2008 a 2015 - AID pendientes aplicación periodos futuros -  Importe total AID pendientes [01534]
19 | 234 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total - Importe total AID pendiente aplicación a principio periodo  [01535]
20 | 251 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total - AID aplicados en el periodo  [01536]
21 | 268 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total - AID convertidos en crédito  [01537]
22 | 285 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total - Con prestación patrimonial  [01538]
23 | 302 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total - AID pendientes aplicación periodos futuros - Sin prestación patrimonial  [01539]
24 | 319 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total - AID pendientes aplicación periodos futuros - Sin prestación patrimonial. Minoración prestación exceso cuota [01540]
25 | 336 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). DT 33ª y DA 13ª LIS - Ejercicio generación - Total - AID pendientes aplicación periodos futuros - Importe total AID pendientes [01541]
26 | 353 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - Importe total AID (art. 130.6 a) pendiente aplicación a principio periodo  [01542]
27 | 370 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - Cuota líquida positiva  [01543]
28 | 387 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible [01544]
29 | 404 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible por exceso cuota [01545]
30 | 421 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - AID pendientes aplicación a principio periodo -  Sin derecho conversión crédito exigible [01546]
31 | 438 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - AID aplicados en el periodo [01547]
32 | 455 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - AID convertidos en crédito exigible periodo [01548]
33 | 472 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible [01549]
34 | 489 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible exceso cuota [01550]
35 | 506 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2016 - AID pendientes aplicación periodos futuros - Sin derecho conversión crédito exigible [01551]
36 | 523 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - Importe total AID (art. 130.6 a) pendiente aplicación a principio periodo  [01552]
37 | 540 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - Cuota líquida positiva  [01553]
38 | 557 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible [01554]
39 | 574 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible por exceso cuota [01555]
40 | 591 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - AID pendientes aplicación a principio periodo -  Sin derecho conversión crédito exigible [01556]
41 | 608 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - AID aplicados en el periodo [01753]
42 | 625 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - AID convertidos en crédito exigible periodo [01557]
43 | 642 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible [01558]
44 | 659 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 - AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible exceso cuota [01559]
45 | 676 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2017 -  AID pendientes aplicación periodos futuros - Sin derecho conversión crédito exigible [01560]
46 | 693 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - Importe total AID (art. 130.6 a) pendiente aplicación a principio periodo  [01754]
47 | 710 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - Cuota líquida positiva  [01755]
48 | 727 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible [01756]
49 | 744 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible por exceso cuota [01757]
50 | 761 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - AID pendientes aplicación a principio periodo -  Sin derecho conversión crédito exigible [01758]
51 | 778 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - AID pendientes aplicación a principio periodo -  Sin derecho conversión crédito exigible [01994]
52 | 795 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - AID convertidos en crédito exigible periodo [01759]
53 | 812 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible [01760]
54 | 829 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible exceso cuota [01761]
55 | 846 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018(*) - AID pendientes aplicación periodos futuros - Sin derecho conversión crédito exigible [01762]
56 | 863 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - Importe total AID (art. 130.6 a) pendiente aplicación a principio periodo  [02100]
57 | 880 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - Cuota líquida positiva  [02101]
58 | 897 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible [02102]
59 | 914 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible por exceso cuota [02103]
60 | 931 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - AID pendientes aplicación a principio periodo -  Sin derecho conversión crédito exigible [02104]
61 | 948 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - AID convertidos en crédito exigible periodo [02105]
62 | 965 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible [02106]
63 | 982 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible exceso cuota [02107]
64 | 999 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - 2018 - AID pendientes aplicación periodos futuros - Sin derecho conversión crédito exigible [02108]
65 | 1016 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total - Importe total AID (art. 130.6 a) pendiente aplicación a principio periodo  [01561]
66 | 1033 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total - Cuota líquida positiva  [01562]
67 | 1050 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible [01563]
68 | 1067 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total - AID pendientes aplicación a principio periodo -  Con derecho conversión crédito exigible por exceso cuota [01564]
69 | 1084 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total - AID pendientes aplicación a principio periodo -  Sin derecho conversión crédito exigible [01565]
70 | 1101 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total -  AID aplicados en el periodo [01566]
71 | 1118 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total -  AID convertidos en crédito exigible periodo [01567]
72 | 1135 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total -  AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible [01568]
73 | 1152 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total -  AID pendientes aplicación periodos futuros - Con derecho conversión crédito exigible exceso cuota [01569]
74 | 1169 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Activos impuesto diferido (AID). Art. 130 LIS - Ejercicio generación - Total -  AID pendientes aplicación periodos futuros - Sin derecho conversión crédito exigible [01570]
75 | 1186 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Importe crédito exigible [00393]
76 | 1203 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Abono [00150]
77 | 1220 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Compensación [00506]
78 | 1237 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2016 - Exceso cuota líquida positiva pendiente a principio periodo [01571]
79 | 1254 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2016 - Exceso cuota líquida positiva aplicado periodos impositivos 2008 a 2015 [01572]
80 | 1271 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2016 - Exceso cuota líquida positiva aplicado periodos impositivos iniciados a partir 2016 [01573]
81 | 1288 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2017 - Exceso cuota líquida positiva pendiente a principio periodo [01575]
82 | 1305 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2017 - Exceso cuota líquida positiva aplicado periodos impositivos 2008 a 2015 [01576]
83 | 1322 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2017 - Exceso cuota líquida positiva aplicado periodos impositivos iniciados a partir 2016 [01577]
84 | 1339 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2017 - Exceso cuota líquida positiva pendiente aplicación periodos futuros [01578]
85 | 1356 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2018(*) - Exceso cuota líquida positiva pendiente a principio periodo [01763]
86 | 1373 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2018(*) - Exceso cuota líquida positiva aplicado periodos impositivos 2008 a 2015 [01764]
87 | 1390 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2018(*) - Exceso cuota líquida positiva aplicado periodos impositivos iniciados a partir 2016 [01765]
88 | 1407 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2018(*) - Exceso cuota líquida positiva pendiente aplicación periodos futuros [01766]
89 | 1424 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2018 - Exceso cuota líquida positiva pendiente a principio periodo [02109]
90 | 1441 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2018 - Exceso cuota líquida positiva aplicado periodos impositivos 2008 a 2015 [02110]
91 | 1458 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2018 - Exceso cuota líquida positiva aplicado periodos impositivos iniciados a partir 2016 [02111]
92 | 1475 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - 2018 - Exceso cuota líquida positiva pendiente aplicación periodos futuros [02112]
93 | 1492 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - Total - Exceso cuota líquida positiva pendiente a principio periodo [01579]
94 | 1509 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - Total - Exceso cuota líquida positiva aplicado periodos impositivos 2008 a 2015 [01580]
95 | 1526 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - Total - Exceso cuota líquida positiva aplicado periodos impositivos iniciados a partir 2016 [01581]
96 | 1543 | 17 | Num | Conversión activos impuesto diferido crédito exigible frente Admón.tributaria - Exceso cuota líquida positiva - Ejercicio generación - Total - Exceso cuota líquida positiva pendiente aplicación periodos futuros [01582]
97 | 1560 | 200 | An | RESERVADO PARA LA AEAT
98 | 1760 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20020C00>"
Total: |  | 1771

# DP200021

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | C | Página. | OBLIGATORIO | Constante "21000"
4 | 11 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | C | Indicador de página complementaria |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 13 | 17 | N |  | Comunicación importe neto cifra negocios - Grupos de sociedades. Importe neto cifra negocios [00987]
7 | 30 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [1]
8 | 45 | 5 | An | C | RESERVADO PARA LA AEAT
9 | 50 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [1]
10 | 52 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [2]
11 | 67 | 5 | An | C | RESERVADO PARA LA AEAT
12 | 72 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [2
13 | 74 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [3]
14 | 89 | 5 | An | C | RESERVADO PARA LA AEAT
15 | 94 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [3]
16 | 96 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [4]
17 | 111 | 5 | An | C | RESERVADO PARA LA AEAT
18 | 116 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [4]
19 | 118 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [5]
20 | 133 | 5 | An | C | RESERVADO PARA LA AEAT
21 | 138 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [5]
22 | 140 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [6]
23 | 155 | 5 | An | C | RESERVADO PARA LA AEAT
24 | 160 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [6]
25 | 162 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [7]
26 | 177 | 5 | An | C | RESERVADO PARA LA AEAT
27 | 182 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [7]
28 | 184 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [8]
29 | 199 | 5 | An | C | RESERVADO PARA LA AEAT
30 | 204 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [8]
31 | 206 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [9]
32 | 221 | 5 | An | C | RESERVADO PARA LA AEAT
33 | 226 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [9]
34 | 228 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [10]
35 | 243 | 5 | An | C | RESERVADO PARA LA AEAT
36 | 248 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [10]
37 | 250 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [11]
38 | 265 | 5 | An | C | RESERVADO PARA LA AEAT
39 | 270 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [11]
40 | 272 | 15 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [12]
41 | 287 | 5 | An | C | RESERVADO PARA LA AEAT
42 | 292 | 2 | An | C | Comunicación importe neto cifra negocios - Grupos de sociedades. Código país [12]
43 | 294 | 17 | N |  | Comunicación importe neto cifra negocios - No residentes más de un establecimiento permanente. Importe neto [00988]
44 | 311 | 3 | Num |  | Comunicación importe neto cifra negocios - No residentes más de un establecimiento permanente. Nº establecimientos permanentes
45 | 314 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento permanente. NIF de los establecimientos permanentes [1]
46 | 323 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento permanente. NIF de los establecimientos permanentes [2]
47 | 332 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento permanente. NIF de los establecimientos permanentes [3]
48 | 341 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento permanente. NIF de los establecimientos permanentes [4]
49 | 350 | 9 | An | C | Comunicación importe neto cifra negocios - No residentes más de un establecimiento permanente. NIF de los establecimientos permanentes [5]
50 | 359 | 17 | N |  | Comunicación importe neto cifra negocios - Entidades de crédito, aseguradoras e instituciones de inversión colectiva - Importe neto de la cifra de negocios ejercicio 2018  [00989]
51 | 376 | 4 | Num |  | Rég. Entidades navieras en función del tonelaje. Nº de buques  [N1]
52 | 380 | 17 | Num |  | Rég. Entidades navieras en función del tonelaje. Base imponible resultante de  aplicar la escala [00630]
53 | 397 | 17 | Num |  | Rég. Entidades navieras en función del tonelaje. Importe rentas generadas en trasmisiones de buques [00631]
54 | 414 | 17 | Num |  | Rég. Entidades navieras en función del tonelaje. Compensación bases imponibles negativas períodos anteriores [00632]
55 | 431 | 17 | Num |  | Rég. Entidades navieras en función del tonelaje. Base imponible resultante de la aplicación del régimen [00579]
56 | 448 | 22 | An |  | Presentación de documentación previa en la sede electrónica. Documentación presentada  Anexo III (Ajustes y deducciones)
57 | 470 | 22 | An |  | Presentación de documentación previa en la sede electrónica. Documentación presentada Anexo IV (Personal investigador)
58 | 492 | 22 | An |  | Presentación de documentación previa en la sede electrónica. Documento normalizado presentado por el Anexo V Orden HAP/871/2016 (Art. 16.4 RIS)
59 | 514 | 13 | An |  | Presentación de documentación previa en la sede electrónica. Número de justificante declaración informativa de ayudas Régimen Económico y Fiscal de Canarias
60 | 527 | 13 | An |  | Presentación de documentación previa en la sede electrónica. Número justificante autoliquidación de la prestación patrimonial por conversión de activos
61 | 540 | 200 | An | C | RESERVADO PARA LA AEAT
62 | 740 | 12 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T20021000>"
Total: |  | 751

# DP200022

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "22000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2014 - Importe dotación [00089]
7 | 30 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2014 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00094]
8 | 47 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2014 - Inversiones previstas C D art. 27.4 Ley 19/94 [00095]
9 | 64 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2015 - Importe dotación [00097]
10 | 81 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2015 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00098]
11 | 98 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2015 - Inversiones previstas C D art. 27.4 Ley 19/94 [00047]
12 | 115 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2015 - Pendiente materializar [00048]
13 | 132 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2016 - Importe dotación [00524]
14 | 149 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2016 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00525]
15 | 166 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2016 - Inversiones previstas C D art. 27.4 Ley 19/94 [00526]
16 | 183 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2016 - Pendiente materializar [00527]
17 | 200 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2017 - Importe dotación [00922]
18 | 217 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2017 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00923]
19 | 234 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2017 - Inversiones previstas C D art. 27.4 Ley 19/94 [00924]
20 | 251 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2017 - Pendiente materializar [00925]
21 | 268 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2018 - Importe dotación [00927]
22 | 285 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2018 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00928]
23 | 302 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2018 - Inversiones previstas C D art. 27.4 Ley 19/94 [00938]
24 | 319 | 17 | Num | Rég. especial reserva inversiones Canarias - RIC 2018 - Pendiente materializar [00996]
25 | 336 | 17 | Num | Rég. especial reserva inversiones Canarias - Invers. anticipadas futuras dotaciones RIC en 2018 - Inversiones previstas A B D art. 27.4 Ley 19/94 [00020]
26 | 353 | 17 | Num | Rég. especial reserva inversiones Canarias - Invers. anticipadas futuras dotaciones RIC en 2018 - Inversiones previstas C y D art. 27.4 Ley 19/94 [00021]
27 | 370 | 17 | Num | Rég. cooperativas - Determ. base imponible - Ingresos computables - Resultados cooperativos [C1]
28 | 387 | 17 | Num | Rég. cooperativas - Determ. base imponible - Ingresos computables - Resultados extracooperativos [E1]
29 | 404 | 17 | Num | Rég. cooperativas - Determ. base imponible - Gastos específicos - Resultados cooperativos [C2]
30 | 421 | 17 | Num | Rég. cooperativas - Determ. base imponible - Gastos específicos - Resultados extracooperativos [E2]
31 | 438 | 17 | Num | Rég. cooperativas - Determ. base imponible - Gastos generales imputados - Resultados cooperativos [C3]
32 | 455 | 17 | Num | Rég. cooperativas - Determ. base imponible - Gastos generales imputados - Resultados extracooperativos [E3]
33 | 472 | 17 | Num | Rég. cooperativas - Determ. base imponible - Gastos Fondo de Educación y Promoción - Resultados cooperativos [C4]
34 | 489 | 17 | Num | Rég. cooperativas - Determ. base imponible - Gastos Fondo de Educación y Promoción - Resultados extracooperativos [E4]
35 | 506 | 17 | N | Rég. cooperativas - Determ. base imponible - Incrementos y disminuciones patrimoniales - Resultados extracooperativos [E5]
36 | 523 | 17 | N | Rég. cooperativas - Determ. base imponible - Resultado - Resultados cooperativos [C6]
37 | 540 | 17 | N | Rég. cooperativas - Determ. base imponible - Resultado - Resultados extracooperativos [E6]
38 | 557 | 17 | Num | Rég. cooperativas - Determ. base imponible - Aumentos - Resultados cooperativos [C7]
39 | 574 | 17 | Num | Rég. cooperativas - Determ. base imponible - Aumentos - Resultados extracooperativos [E7]
40 | 591 | 17 | Num | Rég. cooperativas - Determ. base imponible - Disminuciones - Resultados cooperativos [C8]
41 | 608 | 17 | Num | Rég. cooperativas - Determ. base imponible - Disminuciones - Resultados extracooperativos [E8]
42 | 625 | 17 | Num | Rég. cooperativas - Determ. base imponible - 50% Dotación obligatoria - Resultados cooperativos [C9]
43 | 642 | 17 | Num | Rég. cooperativas - Determ. base imponible - 50% Dotación obligatoria - Resultados extracooperativos [E9]
44 | 659 | 17 | N | Rég. cooperativas - Determ. base imponible - Reserva inversiones Canarias - Resultados cooperativos [C10]
45 | 676 | 17 | N | Rég. cooperativas - Determ. base imponible - Factor de agotamiento - Resultados cooperativos [C11]
46 | 693 | 17 | N | Rég. cooperativas - Determ. base imponible - Factor de agotamiento - Resultados extracooperativos [E11]
47 | 710 | 17 | N | Rég. cooperativas - Determ. base imponible - Base imponible - Resultados cooperativos [00553]
48 | 727 | 17 | N | Rég. cooperativas - Determ. base imponible - Base imponible - Resultados extracooperativos [00554]
49 | 744 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2000 Pendiente aplicación al principio del periodo [00673]
50 | 761 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2000 Aplicado en esta liquidación [00674]
51 | 778 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2000 Pendiente aplicación en períodos futuros  [01224]
52 | 795 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2001 Pendiente aplicación al principio del periodo [00676]
53 | 812 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2001 Aplicado en esta liquidación [00677]
54 | 829 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2001 Pendiente aplicación en períodos futuros  [00678]
55 | 846 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2002 Pendiente aplicación al principio del periodo [00679]
56 | 863 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2002 Aplicado en esta liquidación [00680]
57 | 880 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2002 Pendiente aplicación en períodos futuros [00681]
58 | 897 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2003 Pendiente aplicación al principio del periodo [00682]
59 | 914 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2003 Aplicado en esta liquidación [00683]
60 | 931 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2003 Pendiente aplicación en períodos futuros  [00684]
61 | 948 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2004 Pendiente aplicación al principio del periodo [00685]
62 | 965 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2004 Aplicado en esta liquidación [00686]
63 | 982 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2004 Pendiente aplicación en períodos futuros  [00687]
64 | 999 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2005 Pendiente aplicación al principio del periodo [00688]
65 | 1016 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2005 Aplicado en esta liquidación [00689]
66 | 1033 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2005 Pendiente aplicación en períodos futuros  [00690]
67 | 1050 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2006 Pendiente aplicación al principio del periodo [00691]
68 | 1067 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2006 Aplicado en esta liquidación [00692]
69 | 1084 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2006 Pendiente aplicación en períodos futuros  [00693]
70 | 1101 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2007 Pendiente aplicación al principio del periodo [00623]
71 | 1118 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2007 Aplicado en esta liquidación [00624]
72 | 1135 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2007 Pendiente aplicación en períodos futuros  [00672]
73 | 1152 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2008 Pendiente aplicación al principio del periodo [00279]
74 | 1169 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2008 Aplicado en esta liquidación [00280]
75 | 1186 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2008 Pendiente aplicación en períodos futuros  [00281]
76 | 1203 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2009 Pendiente aplicación al principio del periodo [00587]
77 | 1220 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2009 Aplicado en esta liquidación [00515]
78 | 1237 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2009 Pendiente aplicación en períodos futuros  [00900]
79 | 1254 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2010 Pendiente aplicación al principio del periodo [00059]
80 | 1271 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2010 Aplicado en esta liquidación [00099]
81 | 1288 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2010 Pendiente aplicación en períodos futuros  [00100]
82 | 1305 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2011 Pendiente aplicación al principio del periodo [00017]
83 | 1322 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2011 Aplicado en esta liquidación [00018]
84 | 1339 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2011 Pendiente aplicación en períodos futuros  [00019]
85 | 1356 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2012 Pendiente aplicación al principio del periodo [00772]
86 | 1373 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2012 Aplicado en esta liquidación [00773]
87 | 1390 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2012 Pendiente aplicación en períodos futuros  [00777]
88 | 1407 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2013 Pendiente aplicación al principio del periodo [00907]
89 | 1424 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2013 Aplicado en esta liquidación [00908]
90 | 1441 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2013 Pendiente aplicación en períodos futuros  [00909]
91 | 1458 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2014 Pendiente aplicación al principio del periodo [00910]
92 | 1475 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2014 Aplicado en esta liquidación [00911]
93 | 1492 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2014 Pendiente aplicación en períodos futuros  [00912]
94 | 1509 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2015 Pendiente aplicación al principio del periodo [00935]
95 | 1526 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2015 Aplicado en esta liquidación [00936]
96 | 1543 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2015 Pendiente aplicación en períodos futuros  [00937]
97 | 1560 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2016 Pendiente aplicación al principio del periodo [01511]
98 | 1577 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2016 Aplicado en esta liquidación [01512]
99 | 1594 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2016 Pendiente aplicación en períodos futuros  [01513]
100 | 1611 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2017 Pendiente aplicación al principio del periodo [01767]
101 | 1628 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2017 Aplicado en esta liquidación [01768]
102 | 1645 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2017 Pendiente aplicación en períodos futuros  [01769]
103 | 1662 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2018(*) Pendiente aplicación al principio del periodo [02113]
104 | 1679 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2018(*) Aplicado en esta liquidación [02114]
105 | 1696 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2018(*) Pendiente aplicación en períodos futuros  [02115]
106 | 1713 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. Total. Pendiente aplicación al principio del periodo [00694]
107 | 1730 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. Total. Aplicado en esta liquidación [00561]
108 | 1747 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. Total. Pendiente aplicación en períodos futuros  [00695]
109 | 1764 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2018 Pendiente aplicación al principio del periodo [01225]
110 | 1781 | 17 | Num | Rég. cooperativas - Detalle compensación cuotas. 2018 Pendiente aplicación en períodos futuros  [01226]
111 | 1798 | 200 | An | RESERVADO PARA LA AEAT
112 | 1998 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20022000>"
Total: |  | 2009

# DP200023

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | C | Página. | OBLIGATORIO | Constante "23000"
4 | 11 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | C | Indicador de página complementaria. |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 13 | 1 | A | C | Operaciones fusión, escisión, canje valores - 1. Tipo de operación
7 | 14 | 9 | An | C | Operaciones fusión, escisión, canje valores - 1. Entidad transmitente. NIF
8 | 23 | 40 | An | C | Operaciones fusión, escisión, canje valores - 1. Entidad transmitente.Denominación social
9 | 63 | 9 | An | C | Operaciones fusión, escisión, canje valores - 1. Entidad adquirente. NIF
10 | 72 | 40 | An | C | Operaciones fusión, escisión, canje valores - 1. Entidad adquirente.Denominación social
11 | 112 | 8 | Num | C | Operaciones fusión, escisión, canje valores - 1. Fecha de los acuerdos sociales
12 | 120 | 17 | N | C | Operaciones fusión, escisión, canje valores - 1. Valor acciones entregadas
13 | 137 | 17 | N | C | Operaciones fusión, escisión, canje valores - 1. Valor acciones recibidas
14 | 154 | 17 | N | C | Operaciones fusión, escisión, canje valores - 1. Importe rentas no integradas en la base imponible
15 | 171 | 1 | A | C | Operaciones fusión, escisión, canje valores - 2. Tipo de operación
16 | 172 | 9 | An | C | Operaciones fusión, escisión, canje valores - 2. Entidad transmitente. NIF
17 | 181 | 40 | An | C | Operaciones fusión, escisión, canje valores - 2. Entidad transmitente.Denominación social
18 | 221 | 9 | An | C | Operaciones fusión, escisión, canje valores - 2. Entidad adquirente. NIF
19 | 230 | 40 | An | C | Operaciones fusión, escisión, canje valores - 2. Entidad adquirente.Denominación social
20 | 270 | 8 | Num | C | Operaciones fusión, escisión, canje valores - 2. Fecha de los acuerdos sociales
21 | 278 | 17 | N | C | Operaciones fusión, escisión, canje valores - 2. Valor acciones entregadas
22 | 295 | 17 | N | C | Operaciones fusión, escisión, canje valores - 2. Valor acciones recibidas
23 | 312 | 17 | N | C | Operaciones fusión, escisión, canje valores - 2. Importe rentas no integradas en la base imponible
24 | 329 | 1 | A | C | Operaciones fusión, escisión, canje valores - 3. Tipo de operación
25 | 330 | 9 | An | C | Operaciones fusión, escisión, canje valores - 3. Entidad transmitente. NIF
26 | 339 | 40 | An | C | Operaciones fusión, escisión, canje valores - 3. Entidad transmitente.Denominación social
27 | 379 | 9 | An | C | Operaciones fusión, escisión, canje valores - 3. Entidad adquirente. NIF
28 | 388 | 40 | An | C | Operaciones fusión, escisión, canje valores - 3. Entidad adquirente.Denominación social
29 | 428 | 8 | Num | C | Operaciones fusión, escisión, canje valores - 3. Fecha de los acuerdos sociales
30 | 436 | 17 | N | C | Operaciones fusión, escisión, canje valores - 3. Valor acciones entregadas
31 | 453 | 17 | N | C | Operaciones fusión, escisión, canje valores - 3. Valor acciones recibidas
32 | 470 | 17 | N | C | Operaciones fusión, escisión, canje valores - 3. Importe rentas no integradas en la base imponible
33 | 487 | 1 | A | C | Operaciones fusión, escisión, canje valores - 4. Tipo de operación
34 | 488 | 9 | An | C | Operaciones fusión, escisión, canje valores - 4. Entidad transmitente. NIF
35 | 497 | 40 | An | C | Operaciones fusión, escisión, canje valores - 4. Entidad transmitente.Denominación social
36 | 537 | 9 | An | C | Operaciones fusión, escisión, canje valores - 4. Entidad adquirente. NIF
37 | 546 | 40 | An | C | Operaciones fusión, escisión, canje valores - 4. Entidad adquirente.Denominación social
38 | 586 | 8 | Num | C | Operaciones fusión, escisión, canje valores - 4. Fecha de los acuerdos sociales
39 | 594 | 17 | N | C | Operaciones fusión, escisión, canje valores - 4. Valor acciones entregadas
40 | 611 | 17 | N | C | Operaciones fusión, escisión, canje valores - 4. Valor acciones recibidas
41 | 628 | 17 | N | C | Operaciones fusión, escisión, canje valores - 4. Importe rentas no integradas en la base imponible
42 | 645 | 1 | A | C | Operaciones fusión, escisión, canje valores - 5. Tipo de operación
43 | 646 | 9 | An | C | Operaciones fusión, escisión, canje valores - 5. Entidad transmitente. NIF
44 | 655 | 40 | An | C | Operaciones fusión, escisión, canje valores - 5. Entidad transmitente.Denominación social
45 | 695 | 9 | An | C | Operaciones fusión, escisión, canje valores - 5. Entidad adquirente. NIF
46 | 704 | 40 | An | C | Operaciones fusión, escisión, canje valores - 5. Entidad adquirente.Denominación social
47 | 744 | 8 | Num | C | Operaciones fusión, escisión, canje valores - 5. Fecha de los acuerdos sociales
48 | 752 | 17 | N | C | Operaciones fusión, escisión, canje valores - 5. Valor acciones entregadas
49 | 769 | 17 | N | C | Operaciones fusión, escisión, canje valores - 5. Valor acciones recibidas
50 | 786 | 17 | N | C | Operaciones fusión, escisión, canje valores - 5. Importe rentas no integradas en la base imponible
51 | 803 | 200 | An | C | RESERVADO PARA LA AEAT
52 | 1003 | 12 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T20023000>"
Total: |  | 1014

# DP200024

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | C | Página. | OBLIGATORIO | Constante "24000"
4 | 11 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | C | Indicador de página complementaria. |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 13 | 7 | Num |  | Agrup. interés económico y UTES - Porcentaje de imputación de bases imponibles [00060]
7 | 20 | 17 | N |  | Agrup. interés económico y UTES - Modelo de información - Resultado cuenta de pérdidas y ganancias  [00500]
8 | 37 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Gastos financieros netos no deducidos por la entidad  [01227]
9 | 54 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Reserva capitaliz. no aplicada por la entidad  [01228]
10 | 71 | 17 | N |  | Agrup. interés económico y UTES - Modelo de información - Base imponible [00552]
11 | 88 | 17 | N |  | Agrup. interés económico y UTES - Modelo de información - Base imponible minorada o incrementada [01330]
12 | 105 | 17 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  1. Base deducción
13 | 122 | 5 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  1. % participación
14 | 127 | 17 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  2. Base deducción
15 | 144 | 5 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  2. % participación
16 | 149 | 17 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  3. Base deducción
17 | 166 | 5 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  3. % participación
18 | 171 | 17 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  4. Base deducción
19 | 188 | 5 | Num | C | Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición  4. % participación
20 | 193 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Base bonificaciones
21 | 210 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Base de deducciones - a) Base total
22 | 227 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Base de deducciones - b) Base deducciones por inversiones
23 | 244 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Retenciones e ingresos a cuenta  [00062]
24 | 261 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Dividendos y participaciones. a) Ejercicios que no haya tributado en régimen especial
25 | 278 | 17 | Num |  | Agrup. interés económico y UTES - Modelo de información - Dividendos y participaciones. b) Ejercicios que haya tributado en régimen especial
26 | 295 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. NIF
27 | 304 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Rpte. |  | ("0", "1")
28 | 305 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. F/J/Otra |  | "F", "J" o "O"
29 | 306 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. R/X |  | "R" o "X"
30 | 307 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Apellidos y nombre/Razón social
31 | 341 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Código provincia/país
32 | 343 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Base imponible
33 | 360 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. % partic.
34 | 367 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. NIF
35 | 376 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Rpte. |  | ("0", "1")
36 | 377 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. F/J/Otra |  | "F", "J" o "O"
37 | 378 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. R/X |  | "R" o "X"
38 | 379 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Apellidos y nombre/Razón social
39 | 413 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Código provincia/país
40 | 415 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Base imponible
41 | 432 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. % partic.
42 | 439 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. NIF
43 | 448 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Rpte. |  | ("0", "1")
44 | 449 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. F/J/Otra |  | "F", "J" o "O"
45 | 450 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. R/X |  | "R" o "X"
46 | 451 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Apellidos y nombre/Razón social
47 | 485 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Código provincia/país
48 | 487 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Base imponible
49 | 504 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. % partic.
50 | 511 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. NIF
51 | 520 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Rpte. |  | ("0", "1")
52 | 521 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. F/J/Otra |  | "F", "J" o "O"
53 | 522 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. R/X |  | "R" o "X"
54 | 523 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Apellidos y nombre/Razón social
55 | 557 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Código provincia/país
56 | 559 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Base imponible
57 | 576 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. % partic.
58 | 583 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. NIF
59 | 592 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Rpte. |  | ("0", "1")
60 | 593 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. F/J/Otra |  | "F", "J" o "O"
61 | 594 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. R/X |  | "R" o "X"
62 | 595 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Apellidos y nombre/Razón social
63 | 629 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Código provincia/país
64 | 631 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Base imponible
65 | 648 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. % partic.
66 | 655 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. NIF
67 | 664 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Rpte. |  | ("0", "1")
68 | 665 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. F/J/Otra |  | "F", "J" o "O"
69 | 666 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. R/X |  | "R" o "X"
70 | 667 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Apellidos y nombre/Razón social
71 | 701 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Código provincia/país
72 | 703 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Base imponible
73 | 720 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. % partic.
74 | 727 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. NIF
75 | 736 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Rpte. |  | ("0", "1")
76 | 737 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. F/J/Otra |  | "F", "J" o "O"
77 | 738 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. R/X |  | "R" o "X"
78 | 739 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Apellidos y nombre/Razón social
79 | 773 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Código provincia/país
80 | 775 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Base imponible
81 | 792 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. % partic.
82 | 799 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. NIF
83 | 808 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Rpte. |  | ("0", "1")
84 | 809 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. F/J/Otra |  | "F", "J" o "O"
85 | 810 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. R/X |  | "R" o "X"
86 | 811 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Apellidos y nombre/Razón social
87 | 845 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Código provincia/país
88 | 847 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Base imponible
89 | 864 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. % partic.
90 | 871 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. NIF
91 | 880 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Rpte. |  | ("0", "1")
92 | 881 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. F/J/Otra |  | "F", "J" o "O"
93 | 882 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. R/X |  | "R" o "X"
94 | 883 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Apellidos y nombre/Razón social
95 | 917 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Código provincia/país
96 | 919 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Base imponible
97 | 936 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. % partic.
98 | 943 | 9 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. NIF
99 | 952 | 1 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Rpte. |  | ("0", "1")
100 | 953 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. F/J/Otra |  | "F", "J" o "O"
101 | 954 | 1 | A | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. R/X |  | "R" o "X"
102 | 955 | 34 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Apellidos y nombre/Razón social
103 | 989 | 2 | An | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Código provincia/país
104 | 991 | 17 | N | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Base imponible
105 | 1008 | 7 | Num | C | Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. % partic.
106 | 1015 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Identificación.
107 | 1035 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. País residencia fiscal
108 | 1037 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Volumen operaciones
109 | 1054 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Beneficio o pérdida en el período impositivo
110 | 1071 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Suma de ajustes al resultado contable
111 | 1088 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 1. Suma Deducciones por DI internac. períodos ant.
112 | 1105 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Identificación.
113 | 1125 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. País residencia fiscal
114 | 1127 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Volumen operaciones
115 | 1144 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Beneficio o pérdida en el período impositivo
116 | 1161 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Suma de ajustes al resultado contable
117 | 1178 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 2. Suma Deducciones por DI internac. períodos ant.
118 | 1195 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Identificación.
119 | 1215 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. País residencia fiscal
120 | 1217 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Volumen operaciones
121 | 1234 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Beneficio o pérdida en el período impositivo
122 | 1251 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Suma de ajustes al resultado contable
123 | 1268 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 3. Suma Deducciones por DI internac. períodos ant.
124 | 1285 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Identificación.
125 | 1305 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. País residencia fiscal
126 | 1307 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Volumen operaciones
127 | 1324 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Beneficio o pérdida en el período impositivo
128 | 1341 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Suma de ajustes al resultado contable
129 | 1358 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 4. Suma Deducciones por DI internac. períodos ant.
130 | 1375 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Identificación.
131 | 1395 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. País residencia fiscal
132 | 1397 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Volumen operaciones
133 | 1414 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Beneficio o pérdida en el período impositivo
134 | 1431 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Suma de ajustes al resultado contable
135 | 1448 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 5. Suma Deducciones por DI internac. períodos ant.
136 | 1465 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Identificación.
137 | 1485 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. País residencia fiscal
138 | 1487 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Volumen operaciones
139 | 1504 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Beneficio o pérdida en el período impositivo
140 | 1521 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Suma de ajustes al resultado contable
141 | 1538 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 6. Suma Deducciones por DI internac. períodos ant.
142 | 1555 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Identificación.
143 | 1575 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. País residencia fiscal
144 | 1577 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Volumen operaciones
145 | 1594 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Beneficio o pérdida en el período impositivo
146 | 1611 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Suma de ajustes al resultado contable
147 | 1628 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 7. Suma Deducciones por DI internac. períodos ant.
148 | 1645 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Identificación.
149 | 1665 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. País residencia fiscal
150 | 1667 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Volumen operaciones
151 | 1684 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Beneficio o pérdida en el período impositivo
152 | 1701 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Suma de ajustes al resultado contable
153 | 1718 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 8. Suma Deducciones por DI internac. períodos ant.
154 | 1735 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Identificación.
155 | 1755 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. País residencia fiscal
156 | 1757 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Volumen operaciones
157 | 1774 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Beneficio o pérdida en el período impositivo
158 | 1791 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Suma de ajustes al resultado contable
159 | 1808 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 9. Suma Deducciones por DI internac. períodos ant.
160 | 1825 | 20 | An | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Identificación.
161 | 1845 | 2 | A | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. País residencia fiscal
162 | 1847 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Volumen operaciones
163 | 1864 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Beneficio o pérdida en el período impositivo
164 | 1881 | 17 | N | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Suma de ajustes al resultado contable
165 | 1898 | 17 | Num | C | Agrup. interés económico y UTES - Información detalle de EP o UTE - 10. Suma Deducciones por DI internac. períodos ant.
166 | 1915 | 200 | An | C | RESERVADO PARA LA AEAT
167 | 2115 | 12 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T20024000>"
Total: |  | 2126

# DP200025

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | C | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | C | Página. | OBLIGATORIO | Constante "25000"
4 | 11 | 1 | An | C | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | C | Indicador de página complementaria |  | Blanco (No complementaria) o
"C" (Complementaria)
6 | 13 | 40 | An | C | Rég.transparencia fiscal internacional - 1. Nombre o razón social
7 | 53 | 40 | An | C | Rég.transparencia fiscal internacional - 1. Domicilio social
8 | 93 | 2 | An | C | Rég.transparencia fiscal internacional - 1. Clave país/territorio
9 | 95 | 17 | Num | C | Rég.transparencia fiscal internacional - 1. Importe renta [A]
10 | 112 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 1
11 | 207 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 2
12 | 302 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 3
13 | 397 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 4
14 | 492 | 95 | An | C | Rég.transparencia fiscal internacional - 1. Administradores. Línea 5
15 | 587 | 40 | An | C | Rég.transparencia fiscal internacional - 2. Nombre o razón social
16 | 627 | 40 | An | C | Rég.transparencia fiscal internacional - 2. Domicilio social
17 | 667 | 2 | An | C | Rég.transparencia fiscal internacional - 2. Clave país/territorio
18 | 669 | 17 | Num | C | Rég.transparencia fiscal internacional - 2. Importe renta [B]
19 | 686 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 1
20 | 781 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 2
21 | 876 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 3
22 | 971 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 4
23 | 1066 | 95 | An | C | Rég.transparencia fiscal internacional - 2. Administradores. Línea 5
24 | 1161 | 40 | An | C | Rég.transparencia fiscal internacional - 3. Nombre o razón social
25 | 1201 | 40 | An | C | Rég.transparencia fiscal internacional - 3. Domicilio social
26 | 1241 | 2 | An | C | Rég.transparencia fiscal internacional - 3. Clave país/territorio
27 | 1243 | 17 | Num | C | Rég.transparencia fiscal internacional - 3. Importe renta [C]
28 | 1260 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 1
29 | 1355 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 2
30 | 1450 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 3
31 | 1545 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 4
32 | 1640 | 95 | An | C | Rég.transparencia fiscal internacional - 3. Administradores. Línea 5
33 | 1735 | 40 | An | C | Rég.transparencia fiscal internacional - 4. Nombre o razón social
34 | 1775 | 40 | An | C | Rég.transparencia fiscal internacional - 4. Domicilio social
35 | 1815 | 2 | An | C | Rég.transparencia fiscal internacional - 4. Clave país/territorio
36 | 1817 | 17 | Num | C | Rég.transparencia fiscal internacional - 4. Importe renta [D]
37 | 1834 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 1
38 | 1929 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 2
39 | 2024 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 3
40 | 2119 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 4
41 | 2214 | 95 | An | C | Rég.transparencia fiscal internacional - 4. Administradores. Línea 5
42 | 2309 | 40 | An | C | Rég.transparencia fiscal internacional - 5. Nombre o razón social
43 | 2349 | 40 | An | C | Rég.transparencia fiscal internacional - 5. Domicilio social
44 | 2389 | 2 | An | C | Rég.transparencia fiscal internacional - 5. Clave país/territorio
45 | 2391 | 17 | Num | C | Rég.transparencia fiscal internacional - 5. Importe renta [E]
46 | 2408 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 1
47 | 2503 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 2
48 | 2598 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 3
49 | 2693 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 4
50 | 2788 | 95 | An | C | Rég.transparencia fiscal internacional - 5. Administradores. Línea 5
51 | 2883 | 40 | An | C | Rég.transparencia fiscal internacional - 6. Nombre o razón social
52 | 2923 | 40 | An | C | Rég.transparencia fiscal internacional - 6. Domicilio social
53 | 2963 | 2 | An | C | Rég.transparencia fiscal internacional - 6. Clave país/territorio
54 | 2965 | 17 | Num | C | Rég.transparencia fiscal internacional - 6. Importe renta [F]
55 | 2982 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 1
56 | 3077 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 2
57 | 3172 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 3
58 | 3267 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 4
59 | 3362 | 95 | An | C | Rég.transparencia fiscal internacional - 6. Administradores. Línea 5
60 | 3457 | 17 | Num |  | Rég.transparencia fiscal internacional - Total importe [387]
61 | 3474 | 200 | An | C | RESERVADO PARA LA AEAT
62 | 3674 | 12 | An | C | Identificador de fin de registro | OBLIGATORIO | Constante "</T20025000>"
Total: |  | 3685

# DP200026 

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "26000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen total de operaciones  [00050]
7 | 30 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en el extranjero [00051]
8 | 47 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Araba [00052]
9 | 64 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Gipuzkoa [00053]
10 | 81 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Bizkaia [00054]
11 | 98 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Convenio económico - Volumen operaciones en Navarra [00055]
12 | 115 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Territorio común [00056]
13 | 132 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Araba [00626]
14 | 137 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Gipuzkoa [00627]
15 | 142 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Bizkaia [00628]
16 | 147 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Navarra [00629]
17 | 152 | 5 | Num | Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Admón.del Estado [00625]
18 | 157 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Araba [00420]
19 | 174 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Gipuzkoa [00421]
20 | 191 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Bizkaia [00426]
21 | 208 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Navarra [00427]
22 | 225 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Total [00600]
23 | 242 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Araba [00402]
24 | 259 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Gipuzkoa [00442]
25 | 276 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Bizkaia [00443]
26 | 293 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Navarra [00444]
27 | 310 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Total [00602]
28 | 327 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Araba [00445]
29 | 344 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Gipuzkoa [00446]
30 | 361 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Bizkaia [00447]
31 | 378 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Navarra [00448]
32 | 395 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Total [00604]
33 | 412 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Araba [00449]
34 | 429 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Gipuzkoa [00450]
35 | 446 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Bizkaia [00451]
36 | 463 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Navarra [00465]
37 | 480 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Total [00606]
38 | 497 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Araba [00474]
39 | 514 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Gipuzkoa [00475]
40 | 531 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Bizkaia [00476]
41 | 548 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Navarra [00477]
42 | 565 | 17 | N | Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Total [00612]
43 | 582 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Araba [00482]
44 | 599 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Gipuzkoa [00483]
45 | 616 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Bizkaia [00484]
46 | 633 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Navarra [00485]
47 | 650 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Total [00616]
48 | 667 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Araba [00913]
49 | 684 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Gipuzkoa [00914]
50 | 701 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Bizkaia [00915]
51 | 718 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Navarra [00916]
52 | 735 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Total [00642]
53 | 752 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Araba [00486]
54 | 769 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Gipuzkoa [00487]
55 | 786 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Bizkaia [00488]
56 | 803 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Navarra [00489]
57 | 820 | 17 | Num | Tributación conjunta Estado y Adm.Forales - Intereses demora - Total [00618]
58 | 837 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Araba [00490]
59 | 854 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Gipuzkoa [00491]
60 | 871 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Bizkaia [00492]
61 | 888 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Navarra  [00493]
62 | 905 | 17 | N | Tributación conjunta Estado y Adm.Forales - Importe  ingreso/devolución declaración originaria - Total [00620]
63 | 922 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Araba [01334]
64 | 939 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Gipuzkoa [01335]
65 | 956 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Bizkaia [01336]
66 | 973 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Navarra  [01337]
67 | 990 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones I+D+i insuf. cuota - Total [01332]
68 | 1007 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Araba [01338]
69 | 1024 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Gipuzkoa [01339]
70 | 1041 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Bizkaia [01340]
71 | 1058 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Navarra  [01341]
72 | 1075 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono deducciones producciones extranjeras - Total [01333]
73 | 1092 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Araba [00494]
74 | 1109 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Gipuzkoa [00495]
75 | 1126 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Bizkaia [00496]
76 | 1143 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Navarra [00497]
77 | 1160 | 17 | N | Tributación conjunta Estado y Adm.Forales -  Líquido a ingresar o a devolver - Total [00622]
78 | 1177 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Araba [01300]
79 | 1194 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Gipuzkoa [01301]
80 | 1211 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Bizkaia [01302]
81 | 1228 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Navarra  [01303]
82 | 1245 | 17 | N | Tributación conjunta Estado y Adm.Forales - Abono por conversión activos - Total [01043]
83 | 1262 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Araba [01305]
84 | 1279 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Gipuzkoa [01306]
85 | 1296 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Bizkaia [01307]
86 | 1313 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Navarra  [01308]
87 | 1330 | 17 | N | Tributación conjunta Estado y Adm.Forales - Compensación conversión activos - Total [01044]
88 | 1347 | 200 | An | RESERVADO PARA LA AEAT
89 | 1547 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20026000>"
Total: |  | 1558

# DP200027

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "27000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Efectivo, saldos en efectivo en bancos centrales y otros depósitos a la vista [00101]
7 | 30 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos financieros mantenidos para negociar [00102]
8 | 47 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Derivados [00103]
9 | 64 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Instrumentos de patrimonio [00104]
10 | 81 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [00105]
11 | 98 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos [00106]
12 | 115 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Bancos centrales [00107]
13 | 132 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Entidades de crédito [00108]
14 | 149 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Clientela [00109]
15 | 166 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Pro memoria: prestados o entregados como garantía con derecho de venta o pignoración [00750]
16 | 183 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos financieros no destinados a negociación valorados obligatoriamente a valor razonable con cambios en resultados [02131]
17 | 200 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Instrumentos de patrimonio [02132]
18 | 217 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [02133]
19 | 234 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos [02134]
20 | 251 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Bancos centrales [02135]
21 | 268 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Entidades de crédito [02136]
22 | 285 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Clientela [02137]
23 | 302 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Pro memoria: prestados o entregados como garantía con derecho de venta o pignoración [02138]
24 | 319 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos financieros designados a valor razonable con cambios en resultados [00110]
25 | 336 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [00112]
26 | 353 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos [00113]
27 | 370 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Bancos centrales [00114]
28 | 387 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Entidades de crédito [00115]
29 | 404 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Clientela [00116]
30 | 421 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Pro memoria: prestados o entregados como garantía con derecho de venta o pignoración [00751]
31 | 438 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos financieros a valor razonable con cambios en otro resultado global [02139]
32 | 455 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Instrumentos de patrimonio [02140]
33 | 472 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [02141]
34 | 489 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos [02142]
35 | 506 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Bancos centrales [02143]
36 | 523 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Entidades de crédito [02144]
37 | 540 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Clientela [02145]
38 | 557 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Pro memoria: prestados o entregados como garantía con derecho de venta o pignoración [02146]
39 | 574 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos financieros a coste amortizado [02147]
40 | 591 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [02148]
41 | 608 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos [02149]
42 | 625 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Bancos centrales [02150]
43 | 642 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Entidades de crédito [02151]
44 | 659 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Préstamos y anticipos Clientela [02152]
45 | 676 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Pro memoria: prestados o entregados como garantía con derecho de venta o pignoración [02153]
46 | 693 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Derivados - contabilidad de coberturas [00127]
47 | 710 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Cambios del valor razonable de los elementos cubiertos de una cartera con cobertura del riesgo de tipo de interés [00128]
48 | 727 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inversiones en dependientes, negocios conjuntos y asociadas [00129]
49 | 744 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Entidades del grupo [00130]
50 | 761 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Entidades multigrupo [00131]
51 | 778 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Entidades asociadas [00132]
52 | 795 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos tangibles [00133]
53 | 812 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material [00134]
54 | 829 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - De uso propio [00135]
55 | 846 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Cedido en arrendamiento operativo [00136]
56 | 863 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Afecto a la obra social (cajas de ahorros y cooperativas de crédito) [00137]
57 | 880 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Inversiones inmobiliarias [00138]
58 | 897 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - De las cuales: cedido en arrendamiento operativo [00139]
59 | 914 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Pro memoria: prestados o entregados como garantía con derecho de venta o pignoración [00755]
60 | 931 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos intangibles [00140]
61 | 948 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Fondo de comercio [00141]
62 | 965 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Otros activos intangibles [00142]
63 | 982 | 200 | An | RESERVADO PARA LA AEAT
64 | 1182 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20027000>"
Total: |  | 1193

# DP200027B

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "27B00"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos por impuestos [00143]
7 | 30 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos por impuestos corrientes [00144]
8 | 47 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos por impuestos diferidos [00145]
9 | 64 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Otros activos [00146]
10 | 81 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Contratos de seguros vinculados a pensiones [00147]
11 | 98 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Existencias [00148]
12 | 115 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Resto de los otros activos [00149]
13 | 132 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Activos no corrientes y grupos enajenables de elementos que se han clasificado como mantenidos para la venta [00150]
14 | 149 | 17 | N | Contabilidad Banco de España - Balance (I) - Activo - Total activo [00151]
15 | 166 | 200 | An | RESERVADO PARA LA AEAT
16 | 366 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20027B00>"
Total: |  | 377

# DP200028

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "28000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos financieros mantenidos para negociar [00152]
7 | 30 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Derivados [00153]
8 | 47 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Posiciones cortas [00154]
9 | 64 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos [00155]
10 | 81 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Bancos centrales [00156]
11 | 98 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Entidades de crédito [00157]
12 | 115 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Clientela [00158]
13 | 132 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Valores representativos de deuda emitidos [00159]
14 | 149 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [00160]
15 | 166 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos financieros designados a valor razonable con cambios en resultados [00161]
16 | 183 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos [00162]
17 | 200 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Bancos centrales [00163]
18 | 217 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Entidades de crédito [00164]
19 | 234 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Clientela [00165]
20 | 251 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Valores representativos de deuda emitidos [00166]
21 | 268 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [00167]
22 | 285 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pro memoria: pasivos subordinados [00756]
23 | 302 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos financieros a coste amortizado [00168]
24 | 319 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos [00169]
25 | 336 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Bancos centrales [00170]
26 | 353 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Entidades de crédito [00171]
27 | 370 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos Clientela [00172]
28 | 387 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Valores representativos de deuda emitidos [00173]
29 | 404 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [00174]
30 | 421 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pro memoria: pasivos subordinados [00757]
31 | 438 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Derivados - contabilidad de coberturas [00175]
32 | 455 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Cambios del valor razonable de los elementos cubiertos de una cartera con cobertura del riesgo de tipo de interés [00176]
33 | 472 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Provisiones [00177]
34 | 489 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pensiones y otras obligaciones de prestaciones definidas post-empleo [00178]
35 | 506 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otras retribuciones a los empleados a largo plazo [00179]
36 | 523 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Cuestiones procesales y litigios por impuestos pendientes [00180]
37 | 540 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Compromisos y garantías concedidos [00181]
38 | 557 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Restantes provisiones [00182]
39 | 574 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos por impuestos [00183]
40 | 591 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos por impuestos corrientes [00184]
41 | 608 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos por impuestos diferidos [00185]
42 | 625 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Capital social reembolsable a la vista [00186]
43 | 642 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos [00187]
44 | 659 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - De los cuales: fondo de la obra social (solo cajas de ahorros y cooperativas de crédito) [00188]
45 | 676 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos incluidos en grupos enajenables de elementos que se han clasificado como mantenidos para la venta [00189]
46 | 693 | 17 | N | Contabilidad Banco de España - Balance (II) - Pasivo - Total pasivo [00190]
47 | 710 | 200 | An | RESERVADO PARA LA AEAT
48 | 910 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20028000>"
Total: |  | 921

# DP200029 

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "29000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Fondos propios [00191]
7 | 30 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Capital [00192]
8 | 47 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Capital desembolsado [00193]
9 | 64 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Capital no desembolsado exigido [00194]
10 | 81 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Pro memoria: capital no exigido [00758]
11 | 98 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Prima de emisión [00195]
12 | 115 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Instrumentos de patrimonio emitidos distintos del capital [00196]
13 | 132 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Componente de patrimonio neto de los instrumentos financieros compuestos [00197]
14 | 149 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros instrumentos de patrimonio emitidos [00198]
15 | 166 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros elementos de patrimonio neto [00199]
16 | 183 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Ganancias acumuladas [00200]
17 | 200 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reservas de revalorización [00201]
18 | 217 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otras reservas [00202]
19 | 234 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reserva de capitalización [00762]
20 | 251 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reserva de nivelación [00763]
21 | 268 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otras [00764]
22 | 285 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - (-) Acciones propias [00203]
23 | 302 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Resultado del ejercicio [00204]
24 | 319 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - (-) Dividendos a cuenta [00205]
25 | 336 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otro resultado global acumulado [00206]
26 | 353 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Elementos que no se reclasificarán en resultados [00207]
27 | 370 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Ganancias o (-) pérdidas actuariales en planes de pensiones de prestaciones definidas [00208]
28 | 387 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Activos no corrientes y grupos enajenables de elementos que se han clasificado como mantenidos para la venta [00209]
29 | 404 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Cambios del valor razonable de los instrumentos de patrimonio valorados a valor razonable con cambios en otro resultado global [02154]
30 | 421 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Ineficacia de las coberturas de valor razonable de los instrumentos de patrimonio valorados a valor razonable con cambios en otro resultado global [02155]
31 | 438 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Cambios del valor razonable de los instrumentos de patrimonio valorados a valor razonable con cambios en otro resultado global [elemento cubierto] [02156]
32 | 455 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Cambios del valor razonable de los instrumentos de patrimonio valorados a valor razonable con cambios en otro resultado global [instrumento de cobertura] [02157]
33 | 472 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Cambios del valor razonable de los pasivos financieros a valor razonable con cambios en resultados atribuibles a cambios en el riesgo de crédito [02158]
34 | 489 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Elementos que pueden reclasificarse en resultados [00211]
35 | 506 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Cobertura de inversiones netas en negocios en el extranjero [parte eficaz] [00212]
36 | 523 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Conversión de divisas [00213]
37 | 540 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Derivados de cobertura. Coberturas de flujos de efectivo [parte eficaz] [00214]
38 | 557 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Cambios del valor razonable de los instrumentos de deuda valorados a valor razonable con cambios en otro resultado global [02159]
39 | 574 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Instrumentos de cobertura [elementos no designados] [02160]
40 | 591 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Activos no corrientes y grupos enajenables de elementos que se han clasificado como mantenidos para la venta [00218]
41 | 608 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Total patrimonio neto [00219]
42 | 625 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Total patrimonio neto y pasivo [00220]
43 | 642 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Pro memoria: exposiciones fuera de balance [00759]
44 | 659 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Compromisos de préstamo concedidos [00760]
45 | 676 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Garantías financieras concedidas [00761]
46 | 693 | 17 | N | Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros compromisos concedidos [02161]
47 | 710 | 200 | An | RESERVADO PARA LA AEAT
48 | 910 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20029000>"
Total: |  | 921

# DP200030

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "30000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ingresos por intereses [00221]
7 | 30 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Gastos por intereses) [00222]
8 | 47 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Gastos por capital social reembolsable a la vista) [00223]
9 | 64 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - A) Margen de intereses [00224]
10 | 81 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ingresos por dividendos [00225]
11 | 98 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ingresos por comisiones [00226]
12 | 115 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Gastos por comisiones) [00227]
13 | 132 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias o (-) pérdidas al dar de baja en cuentas activos y pasivos financieros no valorados a valor razonable con cambios en resultados, netas [00228]
14 | 149 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias o (-) pérdidas por activos y pasivos financieros mantenidos para negociar, netas [00229]
15 | 166 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias o (-) pérdidas por activos financieros no destinados a negociación valorados obligatoriamente a valor razonable con cambios en resultados, netas [02162]
16 | 183 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias o (-) pérdidas por activos y pasivos financieros designados a valor razonable con cambios en resultados, netas [00230]
17 | 200 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias o (-) pérdidas resultantes de la contabilidad de coberturas, netas [00231]
18 | 217 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Diferencias de cambio [ganancia o (-) pérdida], netas [00232]
19 | 234 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Otros ingresos de explotación [00233]
20 | 251 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Otros gastos de explotación) [00234]
21 | 268 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (De los cuales: dotaciones obligatorias a fondos de la obra social) (solo cajas de ahorros y cooperativas de crédito) [00235]
22 | 285 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - B) Margen bruto [00236]
23 | 302 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Gastos de administración) [00237]
24 | 319 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Gastos de personal) [00238]
25 | 336 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Otros gastos de administración) [00239]
26 | 353 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Amortización) [00240]
27 | 370 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Provisiones o (-) reversión de provisiones) [00241]
28 | 387 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Deterioro del valor o (-) reversión del deterioro del valor de activos financieros no valorados a valor razonable con cambios en resultados y pérdidas o (-) ganancias netas por modificación) [00242]
29 | 404 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Activos financieros a valor razonable con cambios en otro resultado global) [00243]
30 | 421 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Activos financieros a coste amortizado) [00244]
31 | 438 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Deterioro del valor o (-) reversión del deterioro del valor de inversiones en dependientes, negocios conjuntos o asociadas) [00248]
32 | 455 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Deterioro del valor o (-) reversión del deterioro del valor de activos no financieros) [00249]
33 | 472 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Activos tangibles) [00250]
34 | 489 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Activos intangibles) [00251]
35 | 506 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Otros) [00252]
36 | 523 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias o (-) pérdidas al dar de baja en cuentas activos no financieros, netas [00253]
37 | 540 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Fondo de comercio negativo reconocido en resultados [00255]
38 | 557 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias o (-) pérdidas procedentes de activos no corrientes y grupos enajenables de elementos clasificados como mantenidos para la venta no admisibles como actividades interrumpidas [00256]
39 | 574 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - C) Ganancias o (-) pérdidas antes de impuestos procedentes de las actividades continuadas [00257]
40 | 591 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - (Gastos o (-) ingresos por impuestos sobre los resultados de las actividades continuadas) [00258]
41 | 608 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - D) Ganancias o (-) pérdidas después de impuestos procedentes de las actividades continuadas [00259]
42 | 625 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - Ganancias o (-) pérdidas después de impuestos procedentes de actividades interrumpidas [00260]
43 | 642 | 17 | N | Contabilidad Banco de España - Pérdidas  y ganancias - E) Resultado del ejercicio [00500]
44 | 659 | 200 | An | RESERVADO PARA LA AEAT
45 | 859 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20030000>"
Total: |  | 870

# DP200031 

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "31000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Resultado del ejercicio [00500]
7 | 30 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Otro resultado global [00263]
8 | 47 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Elementos que no se reclasificarán en resultados [00264]
9 | 64 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Ganancias o (-) pérdidas actuariales en planes de pensiones de prestaciones definidas [00265]
10 | 81 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Activos no corrientes y grupos enajenables de elementos mantenidos para la venta [00266]
11 | 98 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Cambios del valor razonable de los instrumentos de patrimonio valorados a valor razonable con cambios en otro resultado global [02163]
12 | 115 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Ganancias o (-) pérdidas resultantes de la contabilidad de coberturas de instrumentos de patrimonio valorados a valor razonable con cambios en otro resultado global, netas [02164]
13 | 132 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Cambios del valor razonable de los instrumentos de patrimonio valorados a valor razonable con cambios en otro resultado global (elemento cubierto) [02165]
14 | 149 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Cambios del valor razonable de los instrumentos de patrimonio valorados a valor razonable con cambios en otro resultado global (instrumento de cobertura) [02166]
15 | 166 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Cambios del valor razonable de los pasivos financieros a valor razonable con cambios en resultados atribuibles a cambios en el riesgo de crédito [02167]
16 | 183 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Impuesto sobre las ganancias relativo a los elementos que no se reclasificarán [00268]
17 | 200 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Elementos que pueden reclasificarse en resultados [00269]
18 | 217 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Cobertura de inversiones netas en negocios en el extranjero  [parte eficaz] [00270]
19 | 234 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Ganancias o (-) pérdidas de valor contabilizadas en el patrimonio neto [00271]
20 | 251 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Transferido a resultados [00272]
21 | 268 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Otras reclasificaciones [00273]
22 | 285 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Conversión de divisas [00274]
23 | 302 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Ganancias o (-) pérdidas por cambio de divisas contabilizadas en el patrimonio neto [00275]
24 | 319 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Transferido a resultados [00276]
25 | 336 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Otras reclasificaciones [00277]
26 | 353 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Coberturas de flujos de efectivo  [parte eficaz] [00278]
27 | 370 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Ganancias o (-) pérdidas de valor contabilizadas en el patrimonio neto [00279]
28 | 387 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Transferido a resultados [00280]
29 | 404 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Transferido al importe en libros inicial de los elementos cubiertos [00281]
30 | 421 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Otras reclasificaciones [00282]
31 | 438 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Instrumentos de cobertura [elementos no designados] [02168]
32 | 455 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Ganancias o (-) pérdidas de valor contabilizadas en el patrimonio neto [02169]
33 | 472 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Transferido a resultados [02170]
34 | 489 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Otras reclasificaciones [02171]
35 | 506 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Instrumentos de deuda a valor razonable con cambios en otro resultado global [02172]
36 | 523 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Ganancias o (-) pérdidas de valor contabilizadas en el patrimonio neto [02173]
37 | 540 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Transferido a resultados [02174]
38 | 557 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Otras reclasificaciones [02175]
39 | 574 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Activos no corrientes y grupos enajenables de elementos mantenidos para la venta [00287]
40 | 591 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Ganancias o (-) pérdidas de valor contabilizadas en el patrimonio neto [00288]
41 | 608 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Transferido a resultados [00289]
42 | 625 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Otras reclasificaciones [00290]
43 | 642 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Impuesto sobre las ganancias relativo a los elementos que pueden reclasificarse en ganancias o (-) pérdidas [00291]
44 | 659 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos Reconocidos - Resultado global total del ejercicio [00292]
45 | 676 | 200 | An | RESERVADO PARA LA AEAT
46 | 876 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20031000>"
Total: |  | 887

# DP200032

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "32000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Capital [00293]
7 | 30 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Prima de emisión [00294]
8 | 47 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Instrumentos patrimonio emitidos distintos del capital [00295]
9 | 64 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Otros elementos del patrimonio neto [00296]
10 | 81 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Ganancias acumuladas [00297]
11 | 98 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Reservas de revalorización [00298]
12 | 115 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Capital [00305]
13 | 132 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Prima de emisión [00306]
14 | 149 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Instrumentos patrimonio emitidos distintos del capital [00307]
15 | 166 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Otros elementos del patrimonio neto [00308]
16 | 183 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Ganancias acumuladas [00309]
17 | 200 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Reservas de revalorización [00310]
18 | 217 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Capital [00317]
19 | 234 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Prima de emisión [00318]
20 | 251 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Instrumentos patrimonio emitidos distintos del capital [00319]
21 | 268 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Otros elementos del patrimonio neto [00320]
22 | 285 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Ganancias acumuladas [00321]
23 | 302 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Reservas de revalorización [00322]
24 | 319 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Capital [00329]
25 | 336 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Prima de emisión [00330]
26 | 353 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Instrumentos patrimonio emitidos distintos del capital [00331]
27 | 370 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Otros elementos del patrimonio neto [00332]
28 | 387 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Ganancias acumuladas [00333]
29 | 404 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Reservas de revalorización [00334]
30 | 421 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resultado global total del ejercicio - Ganancias acumuladas [00345]
31 | 438 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resultado global total del ejercicio - Reservas de revalorización [00346]
32 | 455 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Capital [00353]
33 | 472 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Prima de emisión [00354]
34 | 489 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Instrumentos patrimonio emitidos distintos del capital [00355]
35 | 506 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Otros elementos del patrimonio neto [00356]
36 | 523 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Ganancias acumuladas [00357]
37 | 540 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Reservas de revalorización [00358]
38 | 557 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones ordinarias - Capital [00365]
39 | 574 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones ordinarias - Otros elementos del patrimonio neto [00366]
40 | 591 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones ordinarias - Ganancias acumuladas [00369]
41 | 608 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones ordinarias - Reservas de revalorización [00370]
42 | 625 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones preferentes - Capital [00377]
43 | 642 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones preferentes - Prima de emisión [00378]
44 | 659 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones preferentes - Instrumentos patrimonio emitidos distintos del capital [00379]
45 | 676 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones preferentes - Ganancias acumuladas [00381]
46 | 693 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones preferentes - Reservas de revalorización [00382]
47 | 710 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de otros instrumentos de patrimonio - Instrumentos patrimonio emitidos distintos del capital [00391]
48 | 727 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de otros instrumentos de patrimonio - Ganancias acumuladas [00393]
49 | 744 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de otros instrumentos de patrimonio - Reservas de revalorización [00394]
50 | 761 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ejercicio o vencimiento de otros instrumentos de patrimonio emitidos - Instrumentos patrimonio emitidos distintos del capital [00403]
51 | 778 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ejercicio o vencimiento de otros instrumentos de patrimonio emitidos - Ganancias acumuladas [00405]
52 | 795 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ejercicio o vencimiento de otros instrumentos de patrimonio emitidos - Reservas de revalorización [00406]
53 | 812 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de deuda en patrimonio neto - Capital [00413]
54 | 829 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de deuda en patrimonio neto - Prima de emisión [00414]
55 | 846 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de deuda en patrimonio neto - Instrumentos patrimonio emitidos distintos del capital [00415]
56 | 863 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de deuda en patrimonio neto - Otros elementos del patrimonio neto [00416]
57 | 880 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de deuda en patrimonio neto - Ganancias acumuladas [00417]
58 | 897 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducción del capital - Capital [00425]
59 | 914 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducción del capital - Prima de emisión [00426]
60 | 931 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducción del capital - Ganancias acumuladas [00429]
61 | 948 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducción del capital - Reservas de revalorización [00430]
62 | 965 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - Capital [00437]
63 | 982 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - Prima de emisión [00438]
64 | 999 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - Instrumentos patrimonio emitidos distintos del capital [00439]
65 | 1016 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - Otros elementos del patrimonio neto [00440]
66 | 1033 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - Ganancias acumuladas [00441]
67 | 1050 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - Reservas de revalorización [00442]
68 | 1067 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Compra de acciones propias - Ganancias acumuladas [00453]
69 | 1084 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Compra de acciones propias - Reservas de revalorización [00454]
70 | 1101 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Venta o cancelación de acciones propias - Ganancias acumuladas [00465]
71 | 1118 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Venta o cancelación de acciones propias - Reservas de revalorización [00466]
72 | 1135 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del patrimonio neto al pasivo - Capital [00473]
73 | 1152 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del patrimonio neto al pasivo - Prima de emisión [00474]
74 | 1169 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del patrimonio neto al pasivo - Instrumentos patrimonio emitidos distintos del capital [00475]
75 | 1186 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del patrimonio neto al pasivo - Otros elementos del patrimonio neto [00476]
76 | 1203 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del pasivo al patrimonio neto - Capital [00485]
77 | 1220 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del pasivo al patrimonio neto - Prima de emisión [00486]
78 | 1237 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del pasivo al patrimonio neto - Instrumentos patrimonio emitidos distintos del capital [00487]
79 | 1254 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del pasivo al patrimonio neto - Otros elementos del patrimonio neto [00488]
80 | 1271 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - Instrumentos patrimonio emitidos distintos del capital [00499]
81 | 1288 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - Otros elementos del patrimonio neto [00504]
82 | 1305 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - Ganancias acumuladas [00501]
83 | 1322 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - Reservas de revalorización [00502]
84 | 1339 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Capital [00509]
85 | 1356 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Prima de emisión [00510]
86 | 1373 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Instrumentos patrimonio emitidos distintos del capital [00511]
87 | 1390 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Otros elementos del patrimonio neto [00512]
88 | 1407 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Ganancias acumuladas [00513]
89 | 1424 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Reservas de revalorización [00514]
90 | 1441 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos basados en acciones - Capital [00521]
91 | 1458 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos basados en acciones - Prima de emisión [00522]
92 | 1475 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos basados en acciones - Otros elementos del patrimonio neto [00524]
93 | 1492 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - Instrumentos patrimonio emitidos distintos del capital [00535]
94 | 1509 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - Otros elementos del patrimonio neto [00536]
95 | 1526 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - Ganancias acumuladas [00537]
96 | 1543 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - Reservas de revalorización [00538]
97 | 1560 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - De los cuales: dotación discrecional a obras y fondos sociales (solo cajas de ahorros y cooperativas de crédito) - Ganancias acumuladas [00549]
98 | 1577 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Capital [00557]
99 | 1594 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Prima de emisión [00558]
100 | 1611 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Instrumentos patrimonio emitidos distintos del capital [00559]
101 | 1628 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Otros elementos del patrimonio neto [00560]
102 | 1645 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Ganancias acumuladas [00561]
103 | 1662 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Reservas de revalorización [00562]
104 | 1679 | 200 | An | RESERVADO PARA LA AEAT
105 | 1879 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20032000>"
Total: |  | 1890

# DP200033

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "33000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Otras reservas [00299]
7 | 30 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - (-) Acciones propias [00300]
8 | 47 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Resultado del ejercicio [00301]
9 | 64 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - (-) Dividendos a cuenta [00302]
10 | 81 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Otro resultado global acumulado [00303]
11 | 98 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [antes de la reexpresión] - Total [00304]
12 | 115 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Otras reservas [00311]
13 | 132 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - (-) Acciones propias [00312]
14 | 149 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Resultado del ejercicio [00313]
15 | 166 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - (-) Dividendos a cuenta [00314]
16 | 183 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Otro resultado global acumulado [00315]
17 | 200 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de la corrección de errores - Total [00316]
18 | 217 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Otras reservas [00323]
19 | 234 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - (-) Acciones propias [00324]
20 | 251 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Resultado del ejercicio [00325]
21 | 268 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - (-) Dividendos a cuenta [00326]
22 | 285 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Otro resultado global acumulado [00327]
23 | 302 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Efectos de los cambios en las políticas contables - Total [00328]
24 | 319 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Otras reservas [00335]
25 | 336 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - (-) Acciones propias [00336]
26 | 353 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Resultado del ejercicio [00337]
27 | 370 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - (-) Dividendos a cuenta [00338]
28 | 387 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Otro resultado global acumulado [00339]
29 | 404 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de apertura  [período corriente] - Total [00340]
30 | 421 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resultado global total del ejercicio - Otras reservas [00347]
31 | 438 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resultado global total del ejercicio - Resultado del ejercicio [00349]
32 | 455 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resultado global total del ejercicio - Otro resultado global acumulado [00351]
33 | 472 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resultado global total del ejercicio - Total [00352]
34 | 489 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Otras reservas [00359]
35 | 506 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - (-) Acciones propias [00360]
36 | 523 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Resultado del ejercicio [00361]
37 | 540 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - (-) Dividendos a cuenta [00362]
38 | 557 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Otro resultado global acumulado [00363]
39 | 574 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del patrimonio neto - Total [00364]
40 | 591 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones ordinarias - Otras reservas [00371]
41 | 608 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones ordinarias - Total [00376]
42 | 625 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones preferentes - Otras reservas [00383]
43 | 642 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de acciones preferentes - Total [00388]
44 | 659 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de otros instrumentos de patrimonio - Otras reservas [00395]
45 | 676 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Emisión de otros instrumentos de patrimonio - Total [00400]
46 | 693 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ejercicio o vencimiento de otros instrumentos de patrimonio emitidos - Otras reservas [00407]
47 | 710 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ejercicio o vencimiento de otros instrumentos de patrimonio emitidos - Total [00412]
48 | 727 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de deuda en patrimonio neto - Otras reservas [00419]
49 | 744 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de deuda en patrimonio neto - (-) Acciones propias [00420]
50 | 761 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de deuda en patrimonio neto - Total [00424]
51 | 778 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducción del capital - Otras reservas [00431]
52 | 795 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducción del capital - (-) Acciones propias [00432]
53 | 812 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducción del capital - Resultado del ejercicio [00433]
54 | 829 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducción del capital - Total [00436]
55 | 846 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - Otras reservas [00443]
56 | 863 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - (-) Acciones propias [00444]
57 | 880 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - (-) Dividendos a cuenta [00446]
58 | 897 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dividendos (o remuneraciones a los socios) - Total [00448]
59 | 914 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Compra de acciones propias - Otras reservas [00455]
60 | 931 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Compra de acciones propias - (-) Acciones propias [00456]
61 | 948 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Compra de acciones propias - Total [00460]
62 | 965 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Venta o cancelación de acciones propias - Otras reservas [00467]
63 | 982 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Venta o cancelación de acciones propias - (-) Acciones propias [00468]
64 | 999 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Venta o cancelación de acciones propias - Total [00472]
65 | 1016 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del patrimonio neto al pasivo - Total [00484]
66 | 1033 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de instrumentos financieros del pasivo al patrimonio neto - Total [00496]
67 | 1050 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - Otras reservas [00503]
68 | 1067 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - Resultado del ejercicio [00505]
69 | 1084 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - (-) Dividendos a cuenta [00506]
70 | 1101 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - Otro resultado global acumulado [00507]
71 | 1118 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Transferencias entre componentes del patrimonio neto - Total [00508]
72 | 1135 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Otras reservas [00515]
73 | 1152 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - (-) Acciones propias [00516]
74 | 1169 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Otro resultado global acumulado [00519]
75 | 1186 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumento o (-) disminución del patrimonio neto resultante de combinaciones de negocios - Total [00520]
76 | 1203 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos basados en acciones - (-) Acciones propias [00528]
77 | 1220 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos basados en acciones - Total [00532]
78 | 1237 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - Otras reservas [00539]
79 | 1254 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - (-) Acciones propias [00540]
80 | 1271 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - Resultado del ejercicio [00541]
81 | 1288 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - (-) Dividendos a cuenta [00542]
82 | 1305 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - Otro resultado global acumulado [00543]
83 | 1322 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otros aumentos o (-) disminuciones del patrimonio neto - Total [00544]
84 | 1339 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - De los cuales: dotación discrecional a obras y fondos sociales (solo cajas de ahorros y cooperativas de crédito) - Otras reservas [00551]
85 | 1356 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - De los cuales: dotación discrecional a obras y fondos sociales (solo cajas de ahorros y cooperativas de crédito) - Total [00556]
86 | 1373 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Otras reservas [00563]
87 | 1390 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - (-) Acciones propias [00564]
88 | 1407 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Resultado del ejercicio [00565]
89 | 1424 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - (-) Dividendos a cuenta [00566]
90 | 1441 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Otro resultado global acumulado [00567]
91 | 1458 | 17 | N | Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo de cierre (período corriente) - Total [00568]
92 | 1475 | 200 | An | RESERVADO PARA LA AEAT
93 | 1675 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20033000>"
Total: |  | 1686

# DP200034

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "34000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Efectivo y otros activos líquidos equivalentes [00101]
7 | 30 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Activos financieros mantenidos para negociar [00102]
8 | 47 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Instrumentos de patrimonio [00103]
9 | 64 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Valores representativos de deuda [00104]
10 | 81 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Derivados [00105]
11 | 98 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros [00106]
12 | 115 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros activos financieros a valor razonable con cambios en perdidas y ganancias [00107]
13 | 132 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Instrumentos de patrimonio [00108]
14 | 149 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Valores representativos de deuda [00109]
15 | 166 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Instrumentos híbridos [00110]
16 | 183 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inversiones por cuenta de tomadores seguros vida que asuman riesgo inversión [00111]
17 | 200 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros [00112]
18 | 217 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Activos financieros disponibles para la venta [00113]
19 | 234 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Instrumentos de patrimonio [00114]
20 | 251 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Valores representativos de deuda [00115]
21 | 268 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inversiones por cuenta de tomadores seguros vida 
que asuman riesgo inversión [00116]
22 | 285 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros [00117]
23 | 302 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos y partidas a cobrar [00118]
24 | 319 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Valores representativos de deuda [00119]
25 | 336 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos [00120]
26 | 353 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos - Anticipos sobre pólizas [00121]
27 | 370 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos - Préstamos a entidades del grupo y asociadas [00122]
28 | 387 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Préstamos - Préstamos a otras partes vinculadas [00123]
29 | 404 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Depósitos en entidades de crédito [00124]
30 | 421 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Depósitos constituídos por reaseguro aceptado [00125]
31 | 438 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de seguro directo [00126]
32 | 455 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de seguro directo - Tomadores de seguro [00127]
33 | 472 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de seguro directo - Mediadores [00128]
34 | 489 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de reaseguro [00129]
35 | 506 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Créditos por operaciones de coaseguro [00130]
36 | 523 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Desembolsos exigidos [00131]
37 | 540 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros créditos [00132]
38 | 557 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros créditos - Créditos con las Administraciones Públicas [00133]
39 | 574 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otros créditos - Resto de créditos [00134]
40 | 591 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inversiones mantenidas hasta el vencimiento [00135]
41 | 608 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Derivados de cobertura [00136]
42 | 625 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participación del reaseguro en las provisiones técnicas [00137]
43 | 642 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Provisión para primas no consumidas [00138]
44 | 659 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Provisión de seguros de vida [00139]
45 | 676 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Provisión para prestaciones [00140]
46 | 693 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otras provisiones técnicas [00141]
47 | 710 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inmovilizado material e inversiónes inmobiliarias [00142]
48 | 727 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inmovilizado material [00143]
49 | 744 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inversiones inmobiliarias [00144]
50 | 761 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Inmovilizado intangible [00145]
51 | 778 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Fondo de comercio [00146]
52 | 795 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Derechos económicos derivados carteras de pólizas adquiridas a mediadores [00147]
53 | 812 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Otro activo intangible [00148]
54 | 829 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participaciones en entidades del grupo y asociadas [00149]
55 | 846 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participaciones en empresas  asociadas [00150]
56 | 863 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participaciones en empresas multigrupo [00151]
57 | 880 | 17 | N | Entidades aseguradoras -  Balance - Activo (I) - Participaciones en empresas del grupo [00152]
58 | 897 | 200 | An | RESERVADO PARA LA AEAT
59 | 1097 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20034000>"
Total: |  | 1108

# DP200035

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "35000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos fiscales [00153]
7 | 30 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos por impuesto corriente [00154]
8 | 47 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos por impuesto diferido [00155]
9 | 64 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Otros activos [00156]
10 | 81 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos y derechos de reembolso por retribuciones a largo plazo al personal [00157]
11 | 98 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Comisiones anticipadas y otros costes adquisición [00158]
12 | 115 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Periodificaciones [00159]
13 | 132 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Resto de activos [00160]
14 | 149 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  Activos mantenidos para la venta [00161]
15 | 166 | 17 | N | Entidades aseguradoras -  Balance - Activo (II) -  TOTAL ACTIVO [00162]
16 | 183 | 200 | An | RESERVADO PARA LA AEAT
17 | 383 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20035000>"
Total: |  | 394

# DP200036

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimiens permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "36000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos financieros mantenidos para negociar [00163]
7 | 30 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otros pasivos financieros a valor razonable con cambios en pérdidas y ganancias. [00164]
8 | 47 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Débitos y partidas a pagar [00165]
9 | 64 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos subordinados [00166]
10 | 81 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Depósitos recibidos por reaseguro cedido [00167]
11 | 98 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro [00168]
12 | 115 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro - Deudas con asegurados [00169]
13 | 132 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro - Deudas con mediadores [00170]
14 | 149 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas por operaciones de seguro - Deudas condicionadas [00171]
15 | 166 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas por operaciones de reaseguro [00172]
16 | 183 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas por operaciones de coaseguro [00173]
17 | 200 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Obligaciones y otros valores negociables [00174]
18 | 217 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas con entidades de crédito [00175]
19 | 234 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Deudas por operaciones preparatorias de contratos de seguro [00176]
20 | 251 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras deudas [00177]
21 | 268 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras deudas - Deudas con las Administraciones Públicas [00178]
22 | 285 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras deudas - Otras deudas con entidades del grupo y asociadas [00179]
23 | 302 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras deudas - Resto de otras deudas [00180]
24 | 319 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Derivados de cobertura [00181]
25 | 336 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisiones técnicas [00182]
26 | 353 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisión para primas no consumidas [00183]
27 | 370 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisión para riesgos en curso [00184]
28 | 387 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida [00185]
29 | 404 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida - Provisión para primas no consumidas [00186]
30 | 421 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida - Provisión para riesgos en curso [00187]
31 | 438 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida - Provisión matemática [00188]
32 | 455 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provision de seguros de vida - Provisión seguros de vida cuando riesgo de inversión lo asuma el tomador [00189]
33 | 472 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisión para prestaciones [00190]
34 | 489 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisión para participación en beneficios y para extornos [00191]
35 | 506 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Otras provisiones técnicas [00192]
36 | 523 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo - Provisiones no técnicas [00193]
37 | 540 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Provisiones para impuestos y otras contingencias legales [00194]
38 | 557 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Provisión para pensiones y obligaciones similiares [00195]
39 | 574 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Provisión para pagos por convenios de liquidación [00196]
40 | 591 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Otras provisiones no técnicas [00197]
41 | 608 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos fiscales [00198]
42 | 625 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos por impuesto corriente [00199]
43 | 642 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos por impuesto diferido [00200]
44 | 659 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Resto de pasivos [00201]
45 | 676 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Periodificaciones [00202]
46 | 693 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos por asimetrías contables [00203]
47 | 710 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Comisiones y otros costes de adquisición del reaseguro cedido [00204]
48 | 727 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Otros pasivos [00205]
49 | 744 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  Pasivos vinculados con activos mantenidos para la venta [00206]
50 | 761 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) -  Pasivo -  TOTAL PASIVO [00207]
51 | 778 | 200 | An | RESERVADO PARA LA AEAT
52 | 978 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20036000>"
Total: |  | 989

# DP200037

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "37000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Fondos propios [00208]
7 | 30 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual [00209]
8 | 47 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual - Capital escriturado o fondo mutual [00210]
9 | 64 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual - (Capital no exigido) [00211]
10 | 81 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Prima de emisión o asunción [00212]
11 | 98 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas [00213]
12 | 115 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva 
de revalorización [00382]
13 | 132 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva 
de capitalización [01001]
14 | 149 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva 
de nivelación [01002]
15 | 166 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Legal y estatutarias [00214]
16 | 183 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva de estabilización [00215]
17 | 200 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Otras reservas [00216]
18 | 217 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - (Acciones propias) [00217]
19 | 234 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios anteriores [00218]
20 | 251 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios anteriores - Remanente [00219]
21 | 268 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios anteriores - (Resultados negativos de ejercicios anteriores) [00220]
22 | 285 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otras aportaciones de socios y mutualistas [00221]
23 | 302 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultado del ejercicio [00222]
24 | 319 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - (Dividendo a cuenta y reserva de estabilización a cuenta) [00223]
25 | 336 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otros instrumentos de patrimonio neto [00224]
26 | 353 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Ajustes por cambios de valor [00225]
27 | 370 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Activos financieros disponibles para la venta [00226]
28 | 387 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Operaciones de cobertura [00227]
29 | 404 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Diferencias de cambio y conversión [00228]
30 | 421 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Corrección de asimetrías contables [00229]
31 | 438 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otros ajustes [00230]
32 | 455 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Subvenciones, donaciones y legados recibidos [00231]
33 | 472 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - TOTAL PATRIMONIO NETO [00232]
34 | 489 | 17 | N | Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - TOTAL PASIVO Y PATRIMONIO NETO [00233]
35 | 506 | 200 | An | RESERVADO PARA LA AEAT
36 | 706 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20037000>"
Total: |  | 717

# DP200038

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "38000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas imputadas al ejercicio [00234]
7 | 30 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas [00235]
8 | 47 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas - Seguro directo [00236]
9 | 64 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas - Reaseguro aceptado [00237]
10 | 81 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas - Variación de la corrección por deterioro de las primas pendientes de cobro (+ ó -) [00238]
11 | 98 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas reaseguro cedido (-) [00239]
12 | 115 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no consumidas y para riesgos en curso (+ ó -) [00240]
13 | 132 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no consumidas y para riesgos en curso (+ ó -) - Seguro directo [00241]
14 | 149 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no consumidas y para riesgos en curso (+ ó -) - Reaseguro aceptado [00242]
15 | 166 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no consumidas, reaseguro cedido (+ ó -)  [00243]
16 | 183 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Ingresos inmovilizado material y de las inversiones [00244]
17 | 200 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Ingresos inversiones inmobiliarias [00245]
18 | 217 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Ingresos inversiones financieras [00246]
19 | 234 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Aplic. correcciones de valor por deterioro del inmovilizado material y de las inversiones [00247]
20 | 251 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Aplic. correc. valor por deterioro inmovilizado material y de inversiones - Inmovilizado material e inv.inmobiliarias [00248]
21 | 268 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Aplic. correc. valor por deterioro inmovilizado material y de inversiones - Inversiones financieras [00249]
22 | 285 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado material y de inversiones [00250]
23 | 302 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado material y de inversiones - Inmovilizado material e inversiones inmobiliarias [00251]
24 | 319 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado material y de inversiones - Inversiones financieras [00252]
25 | 336 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros ingresos técnicos [00253]
26 | 353 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Siniestralidad del ejercicio, neta de reaseguro [00254]
27 | 370 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos pagados [00255]
28 | 387 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos pagados - Seguro directo [00256]
29 | 404 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos pagados - Reaseguro aceptado [00257]
30 | 421 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos pagados - Reaseguro cedido (-)  [00258]
31 | 438 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión para prestaciones  (+ ó -) [00259]
32 | 455 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Variación provisión para prestaciones  (+ ó -) - Seguro directo  [00260]
33 | 472 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Variación provisión para prestaciones  (+ ó -) - Reaseguro aceptado [00261]
34 | 489 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida -  Variación provisión para prestaciones  (+ ó -) - Reaseguro cedido (-)  [00262]
35 | 506 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos imputables prestaciones [00263]
36 | 523 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación otras provisiones técnicas, netas de reaseguro (+ ó -)  [00264]
37 | 540 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Participación en beneficios y extornos [00265]
38 | 557 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos por participación en beneficios y extornos [00266]
39 | 574 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión participación en beneficios y extornos (+ ó -)  [00267]
40 | 591 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos explotación netos [00268]
41 | 608 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos adquisición [00269]
42 | 625 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos administración [00270]
43 | 642 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Comisiones y participaciones en el reaseguro cedido y retrocedido  [00271]
44 | 659 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros gastos técnicos (+ ó -)  [00272]
45 | 676 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación deterioro por insolvencias (+ ó -)   [00273]
46 | 693 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación deterioro del inmovilizado  (+ ó -)  [00274]
47 | 710 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación prestaciones por convenios de liquidación de siniestros (+ ó -)  [00275]
48 | 727 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros [00276]
49 | 744 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos inmovilizado material e inversiones [00277]
50 | 761 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones [00278]
51 | 778 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones - Gastos inmovilizado material e inv.inmobiliarias [00279]
52 | 795 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones - Gastos inversiones y cuentas financieras [00280]
53 | 812 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor inmovilizado material e inversiones  [00281]
54 | 829 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor inmovilizado material e inversiones - Amortización inmovilizado material e inversiones inmobiliarias [00282]
55 | 846 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor inmovilizado material e inversiones - Deterioro inmovilizado material e inversiones inmobiliarias [00283]
56 | 863 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor inmovilizado material e inversiones - Deterioro inversiones financieras [00284]
57 | 880 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado material e inversiones [00285]
58 | 897 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado material e inversiones - Inmovilizado material e inversiones inmobiliarias [00286]
59 | 914 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado material e inversiones -Inversiones financieras [00287]
60 | 931 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Subtotal (Resultado de la cuenta técnica del seguro no vida)  [00288]
61 | 948 | 200 | An | RESERVADO PARA LA AEAT
62 | 1148 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20038000>"
Total: |  | 1159

# DP200039

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "39000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas imputadas al ejercicio, netas de reaseguro [00289]
7 | 30 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas [00290]
8 | 47 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas - Seguro directo [00291]
9 | 64 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas - Reaseguro aceptado [00292]
10 | 81 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas - Variación corrección por deterioro de las primas pendientes de cobro (+ ó -) [00293]
11 | 98 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas reaseguro cedido (-) [00294]
12 | 115 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión para primas no consumidas y riesgos en curso (+ ó -) [00295]
13 | 132 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión para primas no consumidas y riesgos en curso (+ ó -) -Seguro directo [00296]
14 | 149 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión para primas no consumidas y riesgos en curso (+ ó -) - Reaseguro aceptado [00297]
15 | 166 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida -  Variación provisión primas no consumidas, reaseguro cedido (+ ó -) [00298]
16 | 183 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inmovilizado material e inversiones [00299]
17 | 200 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inversiones inmobiliarias [00300]
18 | 217 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inversiones financieras [00301]
19 | 234 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por deterioro inmov. material e inversiones [00302]
20 | 251 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por deterioro inmov. material e inversiones - Inmovilizado material e inv. inmobiliarias [00303]
21 | 268 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por deterioro inmov. material e inversiones - Inversiones financieras [00304]
22 | 285 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización inmovilizado material e inversiones [00305]
23 | 302 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización inmovilizado material e inversiones - Inmovilizado material e inv. inmobiliarias [00306]
24 | 319 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización inmovilizado material e inversiones - Inversiones financieras [00307]
25 | 336 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Inversiones afectas a seguros el tomador asume riesgo de inversión [00308]
26 | 353 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Otros ingresos ténicos [00309]
27 | 370 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Siniestralidad del ejercicio, neta de reaseguro [00310]
28 | 387 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados [00311]
29 | 404 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados - Seguro directo [00312]
30 | 421 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados - Reaseguro aceptado [00313]
31 | 438 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados - Reaseguro cedido (-)  [00314]
32 | 455 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión prestaciones (+ ó -) [00315]
33 | 472 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión prestaciones (+ ó -) - Seguro directo  [00316]
34 | 489 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión prestaciones (+ ó -) - Reaseguro aceptado [00317]
35 | 506 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión prestaciones (+ ó -) - Reaseguro cedido [00318]
36 | 523 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos imputables prestaciones [00319]
37 | 540 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación otras provisiones técnicas [00320]
38 | 557 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida [00321]
39 | 574 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida - Seguro directo [00322]
40 | 591 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida - Reaseguro aceptado [00323]
41 | 608 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida - Reaseguro cedido  (-)  [00324]
42 | 625 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida riesgo asumen tomadores [00325]
43 | 642 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Otras provisiones técnicas [00326]
44 | 659 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Participación beneficios y extornos [00327]
45 | 676 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos participación beneficios y extornos [00328]
46 | 693 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión participación beneficios y extornos  (+ o -)  [00329]
47 | 710 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos explotación netos [00330]
48 | 727 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos adquisición [00331]
49 | 744 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos administración [00332]
50 | 761 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Comisiones y participaciones reaseguro cedido y retrocedido [00333]
51 | 778 | 200 | An | RESERVADO PARA LA AEAT
52 | 978 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20039000>"
Total: |  | 989

# DP200040

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "40000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Otros gastos técnicos (+ ó -) [00334]
7 | 30 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Variación deterioro por insolvencias (+ ó -) [00335]
8 | 47 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Variación deterioro del inmovilizado (+ ó -)  [00336]
9 | 64 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Otros [00337]
10 | 81 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Gastos del inmovilizado material y de las inversiones [00338]
11 | 98 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos de gestión del inmovilizado material y de las inversiones [00339]
12 | 115 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos gestión inmovilizado material e inversiones - Gastos del inmovilizado material y de las inversiones inmobiliarias [00340]
13 | 132 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos gestión inmovilizado material e inversiones - Gastos de inversiones y cuentas financieras [00341]
14 | 149 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor inmovilizado material e  inversiones [00342]
15 | 166 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor inmovilizado material e  inversiones - Amortización del inmovilizado material y de las inversiones inmobiliarias [00343]
16 | 183 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor inmovilizado material e  inversiones -Deterioro del inmovilizado material y de las inversiones inmobiliarias [00344]
17 | 200 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor inmovilizado material e  inversiones - Deterioro de  inversiones financieras [00345]
18 | 217 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Pérdidas procedentes del inmovilizado material y de las inversiones [00346]
19 | 234 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Pérdidas procedentes del inmovilizado material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [00347]
20 | 251 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Pérdidas procedentes del inmovilizado material y de las inversiones - De las inversiones financieras [00348]
21 | 268 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida -  Gastos de inversiones afectas a seguros en los que el tomador asume el riesgo de la inversión [00349]
22 | 285 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Subtotal (Resultado de la cuenta técnica del seguro de vida) [00350]
23 | 302 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos del inmovilizado material y de las inversiones [00351]
24 | 319 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos procedentes de las inversiones inmobiliarias [00352]
25 | 336 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos procedentes de las inversiones financieras [00353]
26 | 353 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplicaciones de correcciones de valor por deterioro del  inmovilizado material y de las inversiones [00354]
27 | 370 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplic. de correc. valor por deterioro inmovilizado material e inversiones - Del inmovilizado material y de las inversiones inmobiliarias [00355]
28 | 387 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplic. de correc. valor por deterioro inmovilizado material e inversiones - De inversiones financieras [00356]
29 | 404 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Beneficios en realización del inmovilizado material y de las inversiones [00357]
30 | 421 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Beneficios en realización del inmovilizado material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [00358]
31 | 438 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Beneficios en realización del inmovilizado material y de las inversiones - De inversiones financieras [00359]
32 | 455 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos del inmovilizado material y de las inversiones [00360]
33 | 472 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones [00361]
34 | 489 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones - Gastos de inversiones y cuentas financieras [00362]
35 | 506 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones - Gastos de inversiones materiales [00363]
36 | 523 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correcciones de valor del inmovilizado material y de las inversiones [00364]
37 | 540 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e inversiones - Amortización del inmovilizado material y de las inversiones inmobiliarias [00365]
38 | 557 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e inversiones - Deterioro del inmovilizado material y de las inversiones inmobiliarias [00366]
39 | 574 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e inversiones - Deterioro de inversiones financieras [00367]
40 | 591 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado material y de las inversiones [00368]
41 | 608 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [00369]
42 | 625 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado material y de las inversiones - De las inversiones financieras [00370]
43 | 642 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Otros ingresos [00371]
44 | 659 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos por la administración de fondos de pensiones [00372]
45 | 676 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resto de ingresos [00373]
46 | 693 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Otros gastos [00374]
47 | 710 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos por la administración de fondos de pensiones [00375]
48 | 727 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resto de gastos [00376]
49 | 744 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Subtotal (resultado de la cuenta no técnica) [00377]
50 | 761 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado antes de impuestos [00378]
51 | 778 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Impuesto sobre beneficios  [00379]
52 | 795 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado procedente de operaciones continuadas [00380]
53 | 812 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado procedente de operaciones interrumpidas neto de impuestos [00381]
54 | 829 | 17 | N | Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado del ejercicio [00500]
55 | 846 | 200 | An | RESERVADO PARA LA AEAT
56 | 1046 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20040000>"
Total: |  | 1057

# DP200041

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "41000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Resultado del ejercicio [00500]
7 | 30 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otros ingresos y gastos reconocidos [00383]
8 | 47 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Activos financieros disponibles para la venta [00384]
9 | 64 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00385]
10 | 81 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00386]
11 | 98 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00387]
12 | 115 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Coberturas de los flujos de efectivo [00388]
13 | 132 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00389]
14 | 149 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00390]
15 | 166 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos al valor inicial de las partidas cubiertas [00391]
16 | 183 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00392]
17 | 200 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Coberturas de inversiones netas en negocios en el extranjero [00393]
18 | 217 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00394]
19 | 234 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00395]
20 | 251 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00396]
21 | 268 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Diferencias de cambio y conversión [00397]
22 | 285 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00398]
23 | 302 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00399]
24 | 319 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00400]
25 | 336 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Corrección de asimetrías contables [00401]
26 | 353 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00402]
27 | 370 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00403]
28 | 387 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00404]
29 | 404 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Activos mantenidos para la venta [00405]
30 | 421 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias y pérdidas por valoración [00406]
31 | 438 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Importes transferidos a la cuenta de pérdidas y ganancias [00407]
32 | 455 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otras reclasificaciones [00408]
33 | 472 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Ganancias / (pérdidas) actuariales por retribuciones a largo plazo del personal [00409]
34 | 489 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Otros ingresos y gastos reconocidos [00410]
35 | 506 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Impuesto sobre beneficios [00411]
36 | 523 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos -  Total de ingresos y gastos reconocidos [00412]
37 | 540 | 200 | An | RESERVADO PARA LA AEAT
38 | 740 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20041000>"
Total: |  | 751

# DP200042

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "42000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Capital o fondo mutual escriturado [00413]
7 | 30 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Capital o fondo mutual (No exigido) [00414]
8 | 47 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Prima emisión [00415]
9 | 64 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Reservas [00416]
10 | 81 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - (Acciones en patrimonio propias) [00417]
11 | 98 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Resultados de ejercicios anteriores [00418]
12 | 115 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior -Otras aportaciones de socios o mutualistas [00419]
13 | 132 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Capital o fondo mutual escriturado [00426]
14 | 149 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Capital o fondo mutual (No exigido) [00427]
15 | 166 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Prima emisión [00428]
16 | 183 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Reservas [00429]
17 | 200 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - (Acciones en patrimonio propias) [00430]
18 | 217 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Resultados de ejercicios anteriores [00431]
19 | 234 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios anteriores - Otras aportaciones de socios o mutualistas [00432]
20 | 251 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores - Capital o fondo mutual escriturado [00439]
21 | 268 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores - Capital o fondo mutual (No exigido) [00440]
22 | 285 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  Prima emisión [00441]
23 | 302 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  Reservas [00442]
24 | 319 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  (Acciones en patrimonio propias) [00443]
25 | 336 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  Resultados de ejercicios anteriores [00444]
26 | 353 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -  Otras aportaciones de socios o mutualistas [00445]
27 | 370 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Capital o fondo mutual escriturado [00452]
28 | 387 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Capital o fondo mutual (No exigido) [00453]
29 | 404 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Prima emisión [00454]
30 | 421 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Reservas [00455]
31 | 438 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - (Acciones en patrimonio propias) [00456]
32 | 455 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Resultados de ejercicios anteriores [00457]
33 | 472 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Otras aportaciones de socios o mutualistas [00458]
34 | 489 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Capital o fondo mutual escriturado [00465]
35 | 506 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Capital o fondo mutual (No exigido) [00466]
36 | 523 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Prima emisión [00467]
37 | 540 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Reservas [00468]
38 | 557 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - (Acciones en patrimonio propias) [00469]
39 | 574 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Resultados de ejercicios anteriores [00470]
40 | 591 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Otras aportaciones de socios o mutualistas [00471]
41 | 608 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Capital o fondo mutual escriturado [00478]
42 | 625 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Capital o fondo mutual (No exigido) [00479]
43 | 642 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Prima emisión [00480]
44 | 659 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reservas [00481]
45 | 676 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - (Acciones en patrimonio propias) [00482]
46 | 693 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Resultados de ejercicios anteriores [00483]
47 | 710 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Otras aportaciones de socios o mutualistas [00484]
48 | 727 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Capital o fondo mutual escriturado [00491]
49 | 744 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Capital o fondo mutual (No exigido) [00492]
50 | 761 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Prima emisión [00493]
51 | 778 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Reservas [00494]
52 | 795 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - (Acciones en patrimonio propias) [00495]
53 | 812 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Resultados de ejercicios anteriores [00496]
54 | 829 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Aumentos del capital o fondo mutual - Otras aportaciones de socios o mutualistas [00497]
55 | 846 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual -  Escriturado [00504]
56 | 863 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. (No exigido) [00505]
57 | 880 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. Prima emisión [00506]
58 | 897 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. Reservas [00507]
59 | 914 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. (Acciones en patrimonio propias) [00508]
60 | 931 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. Resultados de ejercicios anteriores [00509]
61 | 948 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Reducciones del capital o fondo mutual. Otras aportaciones de socios o mutualistas [00510]
62 | 965 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Escriturado [00517]
63 | 982 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. (No exigido) [00518]
64 | 999 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Prima emisión [00519]
65 | 1016 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Reservas [00520]
66 | 1033 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. (Acciones en patrimonio propias) [00521]
67 | 1050 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Resultados de ejercicios anteriores [00522]
68 | 1067 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto. Otras aportaciones de socios o mutualistas [00523]
69 | 1084 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Escriturado [00530]
70 | 1101 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. (No exigido) [00531]
71 | 1118 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Prima emisión [00532]
72 | 1135 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Reservas [00533]
73 | 1152 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. (Acciones en patrimonio propias) [00534]
74 | 1169 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Resultados de ejercicios anteriores [00535]
75 | 1186 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Distribución de dividendos o derramas activas. Otras aportaciones de socios o mutualistas [00536]
76 | 1203 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). Escriturado [00543]
77 | 1220 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). (No exigido) [00544]
78 | 1237 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -  Operaciones con acciones o participaciones propias (netas). Prima emisión [00545]
79 | 1254 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). Reservas [00546]
80 | 1271 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). (Acciones en patrimonio propias) [00547]
81 | 1288 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). Resultados de ejercicios anteriores [00548]
82 | 1305 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas). Otras aportaciones de socios o mutualistas [00549]
83 | 1322 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Escriturado [00556]
84 | 1339 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. (No exigido) [00557]
85 | 1356 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Prima emisión [00558]
86 | 1373 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Reservas [00559]
87 | 1390 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. (Acciones en patrimonio propias) [00560]
88 | 1407 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Resultados de ejercicios anteriores [00561]
89 | 1424 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Incremento (reducción) de patr. neto resultante de una combinación de negocios. Otras aportaciones de socios o mutualistas [00562]
90 | 1441 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Escriturado [00569]
91 | 1458 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. (No exigido) [00570]
92 | 1475 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Prima emisión [00571]
93 | 1492 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Reservas [00572]
94 | 1509 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. (Acciones en patrimonio propias) [00573]
95 | 1526 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Resultados de ejercicios anteriores [00574]
96 | 1543 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas. Otras aportaciones de socios o mutualistas [00575]
97 | 1560 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Escriturado [00582]
98 | 1577 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - (No exigido) [00583]
99 | 1594 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Prima emisión [00584]
100 | 1611 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Reservas [00585]
101 | 1628 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - (Acciones en patrimonio propias) [00586]
102 | 1645 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Resultados de ejercicios anteriores [00587]
103 | 1662 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras aportaciones de socios o mutualistas [00588]
104 | 1679 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Escriturado [00595]
105 | 1696 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - (No exigido) [00596]
106 | 1713 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Prima emisión [00597]
107 | 1730 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Reservas [00598]
108 | 1747 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - (Acciones en patrimonio propias) [00599]
109 | 1764 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Resultados de ejercicios anteriores [00600]
110 | 1781 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Otras aportaciones de socios o mutualistas [00601]
111 | 1798 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Escriturado [00608]
112 | 1815 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - (No exigido) [00609]
113 | 1832 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Prima emisión [00610]
114 | 1849 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Reservas [00611]
115 | 1866 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - (Acciones en patrimonio propias) [00612]
116 | 1883 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Resultados de ejercicios anteriores [00613]
117 | 1900 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Otras aportaciones de socios o mutualistas [00614]
118 | 1917 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Escriturado [00621]
119 | 1934 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - (No exigido) [00622]
120 | 1951 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Prima emisión [00623]
121 | 1968 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Reservas [00624]
122 | 1985 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - (Acciones en patrimonio propias) [00625]
123 | 2002 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Resultados de ejercicios anteriores [00626]
124 | 2019 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras variaciones - Otras aportaciones de socios o mutualistas [00627]
125 | 2036 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Escriturado [00634]
126 | 2053 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - (No exigido) [00635]
127 | 2070 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Prima emisión [00636]
128 | 2087 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Reservas [00637]
129 | 2104 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - (Acciones en patrimonio propias) [00638]
130 | 2121 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Resultados de ejercicios anteriores [00639]
131 | 2138 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Otras aportaciones de socios o mutualistas [00640]
132 | 2155 | 200 | An | RESERVADO PARA LA AEAT
133 | 2355 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20042000>"
Total: |  | 2366

# DP200043

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "43000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Resultado del ejercicio [00420]
7 | 30 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - (Dividendo a cuenta) [00421]
8 | 47 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Otros instrumentos de patrimonio [00422]
9 | 64 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Ajustes por cambios de valor [00423]
10 | 81 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Subvenciones donaciones y legados recibidos [00424]
11 | 98 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Total [00425]
12 | 115 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Resultado del ejercicio [00433]
13 | 132 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - (Dividendo a cuenta) [00434]
14 | 149 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Otros instrumentos de patrimonio [00435]
15 | 166 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Ajustes por cambios de valor [00436]
16 | 183 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Subvenciones donaciones y legados recibidos [00437]
17 | 200 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios anteriores - Total [00438]
18 | 217 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Resultado del ejercicio [00446]
19 | 234 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - (Dividendo a cuenta) [00447]
20 | 251 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Otros instrumentos de patrimonio [00448]
21 | 268 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Ajustes por cambios de valor [00449]
22 | 285 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Subvenciones donaciones y legados recibidos [00450]
23 | 302 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Total [00451]
24 | 319 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Resultado del ejercicio [00459]
25 | 336 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - (Dividendo a cuenta) [00460]
26 | 353 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Otros instrumentos de patrimonio [00461]
27 | 370 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Ajustes por cambios de valor [00462]
28 | 387 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Subvenciones donaciones y legados recibidos [00463]
29 | 404 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Total [00464]
30 | 421 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Resultado del ejercicio [00472]
31 | 438 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - (Dividendo a cuenta) [00473]
32 | 455 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Otros instrumentos de patrimonio [00474]
33 | 472 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Ajustes por cambios de valor [00475]
34 | 489 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Subvenciones donaciones y legados recibidos [00476]
35 | 506 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Total [00477]
36 | 523 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Resultado del ejercicio [00485]
37 | 540 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (Dividendo a cuenta) [00486]
38 | 557 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otros instrumentos de patrimonio [00487]
39 | 574 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Ajustes por cambios de valor [00488]
40 | 591 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Subvenciones donaciones y legados recibidos [00489]
41 | 608 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Total [00490]
42 | 625 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Resultado del ejercicio [00498]
43 | 642 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - (Dividendo a cuenta) [00499]
44 | 659 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Otros instrumentos de patrimonio [00382]
45 | 676 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Ajustes por cambios de valor [00501]
46 | 693 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Subvenciones donaciones y legados recibidos [00502]
47 | 710 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos de capital o fondo mutual - Total [00503]
48 | 727 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Resultado del ejercicio [00511]
49 | 744 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  (Dividendo a cuenta) [00512]
50 | 761 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Otros instrumentos de patrimonio [00513]
51 | 778 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Ajustes por cambios de valor [00514]
52 | 795 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Subvenciones donaciones y legados [00515]
53 | 812 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Reducciones del capital o fondo mutual -  Total [00516]
54 | 829 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Resultado del ejercicio [00524]
55 | 846 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - (Dividendo a cuenta) [00525]
56 | 863 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Otros instrumentos de patrimonio [00526]
57 | 880 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Ajustes por cambios de valor [00527]
58 | 897 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Subvenciones donaciones y legados [00528]
59 | 914 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Conversión de pasivos financ. en patr. neto - Total [00529]
60 | 931 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Resultado del ejercicio [00537]
61 | 948 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - (Dividendo a cuenta) [00538]
62 | 965 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Otros instrumentos de patrimonio [00539]
63 | 982 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Ajustes por cambios de valor [00540]
64 | 999 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Subvenciones donaciones y legados [00541]
65 | 1016 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-) Distribución de dividendos o derramas activas - Total [00542]
66 | 1033 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Resultado del ejercicio [00550]
67 | 1050 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - (Dividendo a cuenta) [00551]
68 | 1067 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Otros instrumentos de patrimonio [00552]
69 | 1084 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Ajustes por cambios de valor [00553]
70 | 1101 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Subvenciones donaciones y legados [00554]
71 | 1118 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Operaciones con acciones o participaciones propias (netas) - Total [00555]
72 | 1135 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Resultado del ejercicio [00563]
73 | 1152 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - (Dividendo a cuenta) [00564]
74 | 1169 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Otros instrumentos de patrimonio [00565]
75 | 1186 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Ajustes por cambios de valor [00566]
76 | 1203 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Subvenciones donaciones y legados [00567]
77 | 1220 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Incremento  (reducción) de patr. neto resultante de una combinación de negocios - Total [00568]
78 | 1237 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Resultado del ejercicio [00576]
79 | 1254 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - (Dividendo a cuenta) [00577]
80 | 1271 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Otros instrumentos de patrimonio [00578]
81 | 1288 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Ajustes por cambios de valor [00579]
82 | 1305 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Subvenciones donaciones y legados [00580]
83 | 1322 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras operaciones con socios o mutualistas - Total [00581]
84 | 1339 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Resultado del ejercicio [00589]
85 | 1356 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - (Dividendo a cuenta) [00590]
86 | 1373 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otros instrumentos de patrimonio [00591]
87 | 1390 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Ajustes por cambios de valor [00592]
88 | 1407 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Subvenciones donaciones y legados [00593]
89 | 1424 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Total [00594]
90 | 1441 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Resultado del ejercicio [00602]
91 | 1458 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - (Dividendo a cuenta) [00603]
92 | 1475 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos  basados en instrumentos de patrimonio - Otros instrumentos de patrimonio [00604]
93 | 1492 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Ajustes por cambios de valor [00605]
94 | 1509 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Subvenciones donaciones y legados [00606]
95 | 1526 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos basados en instrumentos de patrimonio - Total [00607]
96 | 1543 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Resultado del ejercicio [00615]
97 | 1560 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - (Dividendo a cuenta) [00616]
98 | 1577 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Otros instrumentos de patrimonio [00617]
99 | 1594 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Ajustes por cambios de valor [00618]
100 | 1611 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Subvenciones donaciones y legados [00619]
101 | 1628 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos entre partidas de patrimonio neto - Total [00620]
102 | 1645 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Resultado del ejercicio [00628]
103 | 1662 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - (Dividendo a cuenta) [00629]
104 | 1679 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Otros instrumentos de patrimonio [00630]
105 | 1696 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Ajustes por cambios de valor [00631]
106 | 1713 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Subvenciones donaciones y legados [00632]
107 | 1730 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras variaciones - Total [00633]
108 | 1747 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Resultado del ejercicio [00641]
109 | 1764 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - (Dividendo a cuenta) [00642]
110 | 1781 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Otros instrumentos de patrimonio [00643]
111 | 1798 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Ajustes por cambios de valor [00644]
112 | 1815 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Subvenciones donaciones y legados [00645]
113 | 1832 | 17 | N | Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Total [00646]
114 | 1849 | 200 | An | RESERVADO PARA LA AEAT
115 | 2049 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20043000>"
Total: |  | 2060

# DP200044

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "44000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Inst. inversión colectiva - Balance: Activo - Activo no corriente [00101]
7 | 30 | 17 | N | Inst. inversión colectiva - Balance: Activo - Inmovilizado intangible [00102]
8 | 47 | 17 | N | Inst. inversión colectiva - Balance: Activo - Inmovilizado material [00103]
9 | 64 | 17 | N | Inst. inversión colectiva - Balance: Activo - Inmovilizado material - Bienes muebles de uso propio [00104]
10 | 81 | 17 | N | Inst. inversión colectiva - Balance: Activo - Inmovilizado material - Mobiliario y enseres [00105]
11 | 98 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias [00106]
12 | 115 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos [00107]
13 | 132 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Inmuebles en fase de construcción [00108]
14 | 149 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Inmuebles terminados [00109]
15 | 166 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Concesiones administrativas [00110]
16 | 183 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Otros derechos reales [00111]
17 | 200 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Compromisos de compra de inmuebles [00112]
18 | 217 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Compra de opciones de compra de inmuebles [00113]
19 | 234 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Acciones en sociedades tenedoras y entidades de arrendamiento [00114]
20 | 251 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Opciones sobre la cartera de inversiones inmobiliarias [00115]
21 | 268 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y derechos - Otros [00116]
22 | 285 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y derechos [00117]
23 | 302 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y derechos - Sociedades tenedoras de inmuebles [00118]
24 | 319 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y derechos - Otros [00119]
25 | 336 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Anticipos o entregas a cuenta [00120]
26 | 353 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias [00121]
27 | 370 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias - Inversiones adicionales, complementarias y rehabilitaciones en curso [00122]
28 | 387 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias - Indemnizaciones a arrendatarios [00123]
29 | 404 | 17 | N | Inst. inversión colectiva - Balance: Activo - Activos por impuesto diferido [00124]
30 | 421 | 17 | N | Inst. inversión colectiva - Balance: Activo - Activo corriente [00125]
31 | 438 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores [00126]
32 | 455 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Deudores por ventas de inmuebles [00127]
33 | 472 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Deudores por alquileres [00128]
34 | 489 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Deudores dudosos o morosos [00129]
35 | 506 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Deudores dudosos o morosos avalados o garantizados [00130]
36 | 523 | 17 | N | Inst. inversión colectiva - Balance: Activo - Deudores - Otros deudores [00131]
37 | 540 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras [00132]
38 | 557 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior [00133]
39 | 574 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Valores representativos de deuda [00134]
40 | 591 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Instrumentos de patrimonio [00135]
41 | 608 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Instituciones de inversión colectiva [00136]
42 | 625 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Depósitos en EECC [00137]
43 | 642 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Derivados [00138]
44 | 659 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Otros [00139]
45 | 676 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior  [00140]
46 | 693 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Valores representativos de deuda [00141]
47 | 710 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Instrumentos de patrimonio [00142]
48 | 727 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Instituciones de inversión colectiva [00143]
49 | 744 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Depósitos en EECC [00144]
50 | 761 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Derivados [00145]
51 | 778 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Otros [00146]
52 | 795 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Intereses de la cartera de inversión [00147]
53 | 812 | 17 | N | Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Inversiones morosas, dudosas o en litigio [00148]
54 | 829 | 17 | N | Inst. inversión colectiva - Balance: Activo - Periodificaciones [00149]
55 | 846 | 17 | N | Inst. inversión colectiva - Balance: Activo - Tesorería [00150]
56 | 863 | 17 | N | Inst. inversión colectiva - Balance: Activo - TOTAL ACTIVO [00151]
57 | 880 | 200 | An | RESERVADO PARA LA AEAT
58 | 1080 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20044000>"
Total: |  | 1091

# DP200045

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "45000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Patrimonio atribuido a partícipes o accionistas [00152]
7 | 30 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas [00153]
8 | 47 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Capital [00154]
9 | 64 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Partícipes [00155]
10 | 81 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Prima de emisión [00156]
11 | 98 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Reservas [00157]
12 | 115 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Reservas revalorización (Ley16/2012, de 27 de diciembre) [00243]
13 | 132 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Reservas  capitalización [01001]
14 | 149 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Reservas nivelación [01002]
15 | 166 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Otras Reservas [00805]
16 | 183 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -(Acciones propias) [00158]
17 | 200 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Resultados de ejercicios anteriores [00159]
18 | 217 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Otras aportaciones de socios [00160]
19 | 234 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Resultado del ejercicio [00161]
20 | 251 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - (Dividendo a cuenta) [00162]
21 | 268 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios de valor en inmovilizado material de uso propio [00163]
22 | 285 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material [00164]
23 | 302 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material - Ajustes por plusvalías de invers. inmob. e inmovilizado material [00165]
24 | 319 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material - Ajustes por minusvalías de invers. inmob. e inmovil. material [00166]
25 | 336 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Otro patrimonio atribuido [00167]
26 | 353 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Pasivo no corriente [00168]
27 | 370 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Provisiones a largo plazo [00169]
28 | 387 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Deudas a largo plazo [00170]
29 | 404 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Pasivos por impuesto diferido [00171]
30 | 421 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Pasivo corriente [00172]
31 | 438 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Provisiones a corto plazo [00173]
32 | 455 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Deudas a corto plazo [00174]
33 | 472 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Acreedores [00175]
34 | 489 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Pasivos financieros [00176]
35 | 506 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Derivados [00177]
36 | 523 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - Periodificaciones [00178]
37 | 540 | 17 | N | Inst. inversión colectiva - Patrimonio y pasivo - TOTAL PATRIMONIO Y PASIVO [00179]
38 | 557 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de compromiso [00180]
39 | 574 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de compromiso - Compromisos por operaciones largas de derivados [00181]
40 | 591 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de compromiso - Compromisos por operaciones cortas de derivados [00182]
41 | 608 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Compromisos por compra de inmuebles [00183]
42 | 625 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Compromisos de venta de inmuebles [00184]
43 | 642 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Contratos de arras [00185]
44 | 659 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Derechos de compra de opciones de compra de inmuebles [00186]
45 | 676 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Importes pendientes de desembolsar por inmuebles en fase de construcción [00187]
46 | 693 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso -  Otras cuentas de riesgo y compromiso [00188]
47 | 710 | 17 | N | Inst. inversión colectiva - Cuentas de orden - TOTAL CUENTAS DE RIESGO Y COMPROMISO [00189]
48 | 727 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden [00190]
49 | 744 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Valores cedidos en préstamo por la IIC [00191]
50 | 761 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Valores aportados como garantía por la IIC [00192]
51 | 778 | 17 | N | Inst. inversión colectiva - Cuentas de orden -Otras cuentas de orden -  Valores recibidos en garantía por la IIC [00193]
52 | 795 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Capital nominal no suscrito ni en circulación (SICAV) [00194]
53 | 812 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Capital nominal no suscrito (SII) [00195]
54 | 829 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Avales recibidos [00196]
55 | 846 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Avales emitidos [00197]
56 | 863 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Indemnizaciones previstas pendientes de confirmar [00198]
57 | 880 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Pérdidas fiscales a compensar [00199] Aplicable a IIC financieras
58 | 897 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Pérdidas fiscales a compensar [00199] Aplicable a IIC inmobiliarias
59 | 914 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Otros [00200]
60 | 931 | 17 | N | Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Otras cuentas de orden [00201]
61 | 948 | 17 | N | Inst. inversión colectiva - Cuentas de orden - TOTAL OTRAS CUENTAS DE ORDEN [00202]
62 | 965 | 17 | N | Inst. inversión colectiva - Cuentas de orden - TOTAL CUENTAS DE ORDEN [00203]
63 | 982 | 200 | An | RESERVADO PARA LA AEAT
64 | 1182 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20045000>"
Total: |  | 1193

# DP200046

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "46000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Comisiones de descuento por suscripciones y /o reembolsos [00204]
7 | 30 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Comisiones retrocedidas [00205]
8 | 47 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Ingresos por alquiler [00206]
9 | 64 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Gastos de personal [00207]
10 | 81 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación [00208]
11 | 98 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Comisión de gestión [00209]
12 | 115 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Comisión depositario [00210]
13 | 132 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Otros [00212]
14 | 149 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultados por enajenaciones de inmovilizado [00213]
15 | 166 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias [00214]
16 | 183 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias - Incrementos de deterioro [00215]
17 | 200 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias - Reversión del deterioro [00216]
18 | 217 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. [00217]
19 | 234 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. - Resultados positivos [00218]
20 | 251 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. - Resultados negativos [00219]
21 | 268 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Compensaciones e indemnizaciones por deterioro o pérdida de invers. inmob. [00220]
22 | 285 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Amortización invers. inmob. e inmovilizado material [00221]
23 | 302 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Amortización inmovilizado material [00222]
24 | 319 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Excesos de provisiones [00223]
25 | 336 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultados por enajenaciones inmovilizado material [00224]
26 | 353 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado de explotación [00225]
27 | 370 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Ingresos financieros [00226]
28 | 387 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Gastos financieros [00227]
29 | 404 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros [00228]
30 | 421 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por operaciones cartera interior [00229]
31 | 438 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por operaciones cartera exterior [00230]
32 | 455 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por operaciones con derivados [00231]
33 | 472 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Otros [00232]
34 | 489 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Diferencias de cambio [00233]
35 | 506 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros [00234]
36 | 523 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Deterioros [00235]
37 | 540 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Resultados por operaciones cartera interior [00236]
38 | 557 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Resultados por operaciones cartera exterior [00237]
39 | 574 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Resultados por operaciones con derivados [00238]
40 | 591 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros - Otros [00239]
41 | 608 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado financiero [00240]
42 | 625 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado antes de impuesto [00241]
43 | 642 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - Impuesto sobre beneficios [00242]
44 | 659 | 17 | N | Inst. inversión colectiva - Cuenta pérdidas y ganancias - RESULTADO DEL EJERCICIO [00500]
45 | 676 | 200 | An | RESERVADO PARA LA AEAT
46 | 876 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20046000>"
Total: |  | 887

# DP200047

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "47000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Patrimonio inicial [00244]
7 | 30 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Saldo neto [00245]
8 | 47 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Suscripciones/puesta circ. Acciones [00246]
9 | 64 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Suscripciones/Aumentos capital [00247]
10 | 81 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Reembolsos/Recompra acciones [00248]
11 | 98 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Reembolsos/Reducciones capital [00249]
12 | 115 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Beneficios brutos distribuidos [00250]
13 | 132 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Rendimientos netos [00251]
14 | 149 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Rendimientos de gestión [00252]
15 | 166 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Alquileres [00253]
16 | 183 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Intereses [00254]
17 | 200 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Dividendos [00255]
18 | 217 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias [00256]
19 | 234 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Variación valor razonable invers. inmob. [00257]
20 | 251 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Resultados enajenaciones invers. inmob. [00258]
21 | 268 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Resultados contratos invers. inmob. rescindidos [00259]
22 | 285 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Otros derivados de las invers. inmob. [00260]
23 | 302 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Valores representativos de deuda [00261]
24 | 319 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Instrumentos de patrimonio [00262]
25 | 336 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Depósitos [00263]
26 | 353 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Instituciones inversión colectiva [00264]
27 | 370 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Derivados [00265]
28 | 387 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros valores [00266]
29 | 404 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Diferencias de cambio [00267]
30 | 421 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros rendimientos [00268]
31 | 438 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos repercutidos [00269]
32 | 455 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente [00270]
33 | 472 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión gestión sobre patrimonio [00271]
34 | 489 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión gestión sobre resultados [00272]
35 | 506 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión de depósito [00273]
36 | 523 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente [00274]
37 | 540 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Tasas por registros oficiales [00275]
38 | 557 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Admisión a cotización [00276]
39 | 574 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Difusión de valores liquidativos [00277]
40 | 591 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Otros gastos gestión corriente [00278]
41 | 608 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores [00279]
42 | 625 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Tasaciones [00280]
43 | 642 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Admón.fincas y gastos comunidad [00281]
44 | 659 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Reparación y conservación inmuebles [00282]
45 | 676 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Auditoría [00283]
46 | 693 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Servicios bancarios y similares [00284]
47 | 710 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Publicidad, propaganda y relaciones públicas [00285]
48 | 727 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Otros servicios [00286]
49 | 744 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Amortización de mobiliario y enseres [00287]
50 | 761 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Deterioros, excepto por invers. inmob. [00288]
51 | 778 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Deterioros [00289]
52 | 795 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Retenciones no recuperadas por invers. de cartera exterior [00290]
53 | 812 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Impuesto sobre beneficios [00291]
54 | 829 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Gasto por compartimento [00292]
55 | 846 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (I) - Otros [00293]
56 | 863 | 200 | An | RESERVADO PARA LA AEAT
57 | 1063 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20047000>"
Total: |  | 1074

# DP200048

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "48000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Ingresos  [00294]
7 | 30 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones de descuento a favor de la Institución [00295]
8 | 47 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas [00296]
9 | 64 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - De intermediarios financieros [00297]
10 | 81 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - Por inversiones en otras IIC [00298]
11 | 98 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - Otras [00299]
12 | 115 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Ingreso compartimento por IB [00300]
13 | 132 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Otros [00301]
14 | 149 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - Revalorización inmuebles uso propio y resultados por enajenación inmobilizado [00302]
15 | 166 | 17 | N | Inst. inversión colectiva - Estado variación patrimonial (II) - PATRIMONIO FINAL [00303]
16 | 183 | 200 | An | RESERVADO PARA LA AEAT
17 | 383 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20048000>"
Total: |  | 394

# DP200049

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "49000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Tesorería  [00101]
7 | 30 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Deudores comerciales y otras cuentas a cobrar  [00102]
8 | 47 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Socios dudosos  [00103]
9 | 64 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Deudores varios  [00104]
10 | 81 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Otros créditos con las Administraciones Públicas  [00105]
11 | 98 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Socios por desembolsos exigidos  [00106]
12 | 115 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Activos por impuesto corriente  [00107]
13 | 132 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Resto de cuentas a cobrar [00108]
14 | 149 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inversiones financieras  [00109]
15 | 166 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Instrumentos de patrimonio  [00110]
16 | 183 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Valores representativos de deuda  [00111]
17 | 200 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Depósitos a plazo en entidades de crédito  [00112]
18 | 217 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Activos financieros híbridos  [00113]
19 | 234 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Derivados de cobertura  [00114]
20 | 251 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Resto de derivados [00115]
21 | 268 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inversiones en empresas del grupo y asociadas  [00116]
22 | 285 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Activos no corrientes mantenidos para la venta  [00117]
23 | 302 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inmovilizado material  [00118]
24 | 319 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Terrenos y construcciones  [00119]
25 | 336 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Instalaciones técnicas y otro inmovilizado material  [00120]
26 | 353 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inversiones inmobiliarias  [00121]
27 | 370 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Inmovilizado intangible  [00122]
28 | 387 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Activos por impuesto diferido  [00123]
29 | 404 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Resto de activos  [00124]
30 | 421 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Periodificaciones  [00125]
31 | 438 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - Otros activos  [00126]
32 | 455 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Activo - TOTAL ACTIVO [00127]
33 | 472 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Acreedores comerciales y otras cuenta a pagar  [00129]
34 | 489 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Acreedores varios [00130]
35 | 506 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos por impuesto corriente [00131]
36 | 523 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Deudas [00132]
37 | 540 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Obligaciones [00133]
38 | 557 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Deudas con entidades de crédito [00134]
39 | 574 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Fianzas y depósitos recibidos  [00135]
40 | 591 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Sociedades de reafianzamiento [00136]
41 | 608 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Derivados de cobertura [00137]
42 | 625 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Resto de derivados [00138]
43 | 642 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Otras deudas [00139]
44 | 659 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos vinculados con activos no corrientes mantenidos para la venta  [00140]
45 | 676 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos por avales y garantías  [00141]
46 | 693 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Garantías financieras [00142]
47 | 710 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Resto de avales y garantías [00143]
48 | 727 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Provisiones [00144]
49 | 744 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Provisiones por avales y garantías [00145]
50 | 761 | 17 | N | Sociedades de garantía recíproca - Balance (I) - Pasivo - Otras provisiones [00146]
51 | 778 | 200 | An | RESERVADO PARA LA AEAT
52 | 978 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20049000>"
Total: |  | 989

# DP200050

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "50000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Fondo de provisiones técnicas. Cobertura conjunto operaciones [00147]
7 | 30 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Pasivos por impuesto diferido [00148]
8 | 47 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Resto de pasivos [00149]
9 | 64 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Capital reembolsable a la vista [00150]
10 | 81 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - TOTAL PASIVO [00128]
11 | 98 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Fondos propios [00151]
12 | 115 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital [00152]
13 | 132 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito [00153]
14 | 149 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito - Socios protectores [00154]
15 | 166 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito - Socios partícipes [00155]
16 | 183 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Menos: capital no exigido [00156]
17 | 200 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Menos: capital reembolsable a la vista [00157]
18 | 217 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reservas [00158]
19 | 234 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reservas revalorización (Ley 16/2012, de 27 diciembre) [00194]
20 | 251 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reserva de capitalización [01001]
21 | 268 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reserva de nivelación [01002]
22 | 285 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Otras reservas [00805]
23 | 302 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Resultados de ejercicios anteriores [00159]
24 | 319 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Resultado del ejercicio [00160]
25 | 336 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Ajustes por cambio de valor [00161]
26 | 353 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Activos financieros disponibles para la venta [00162]
27 | 370 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Otros [00163]
28 | 387 | 17 | N | Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Fondo de provisiones técnicas. Aportaciones de terceros [00164]
29 | 404 | 17 | N | Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - TOTAL PASIVO Y PATRIMONIO NETO [00165]
30 | 421 | 200 | An | RESERVADO PARA LA AEAT
31 | 621 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20050000>"
Total: |  | 632

# DP200051

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "51000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Importe neto cifra de negocios [00166]
7 | 30 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos por avales y garantías  [00167]
8 | 47 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos por prestación de servicios [00168]
9 | 64 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Otros ingresos de explotación [00169]
10 | 81 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Gastos de personal [00170]
11 | 98 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Sueldos, salarios y asimilados [00171]
12 | 115 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Cargas sociales [00172]
13 | 132 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Provisiones [00173]
14 | 149 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Otros gastos de explotación [00174]
15 | 166 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Dotaciones a provisiones por avales y garantías (neto) [00175]
16 | 183 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Correciones de valor por deterioro de socios dudosos (neto) [00176]
17 | 200 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Dotaciones al fondo de provisiones técnicas. Cobertura del conjunto de operaciones (neto) [00177]
18 | 217 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Fondo de provisiones técnicas. Aportaciones de terceros utilizadas [00178]
19 | 234 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Amortización del inmovilizado [00179]
20 | 251 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Deterioro y resultado por enajenaciones de inmovilizado [00180]
21 | 268 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Deterioro y resultado activos no corrientes en venta (neto) [00181]
22 | 285 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - RESULTADO DE EXPLOTACION [00182]
23 | 302 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos financieros [00183]
24 | 319 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - De participaciones en instrumentos de patrimonio [00184]
25 | 336 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - De valores negociables y otros instrumentos financieros [00185]
26 | 353 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Gastos financieros [00186]
27 | 370 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Variación de valor razonable en instrumentos financieros[00187]
28 | 387 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Diferencias de cambio [00188]
29 | 404 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Correcciones de valor por deterioro de instrumentos financieros[00189]
30 | 421 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado por enajenación de instrumentos financieros[00190]
31 | 438 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - RESULTADO FINANCIERO [00191]
32 | 455 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado antes de impuestos [00192]
33 | 472 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Impuestos sobre beneficios [00193]
34 | 489 | 17 | N | Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - RESULTADO DEL EJERCICIO [00500]
35 | 506 | 200 | An | RESERVADO PARA LA AEAT
36 | 706 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20051000>"
Total: |  | 717

# DP200052

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "52000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Resultado de la cuenta de pérdidas y ganancias [00500]
7 | 30 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Por ajustes por cambios de valor [00195]
8 | 47 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Activos financieros disponibles venta [00196]
9 | 64 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Otros [00197]
10 | 81 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Fondo provisiones técnicas. Aportaciones terceros [00198]
11 | 98 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Efecto impositivo [00199]
12 | 115 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio neto - Total ingresos gastos imputados directamente en el patrimonio neto  [00200]
13 | 132 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Por ajustes por cambio de valor  [00201]
14 | 149 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Activos financieros disponibles para venta  [00202]
15 | 166 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Otros [00203]
16 | 183 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Fondo provisiones técnicas. Aportaciones terceros [00204]
17 | 200 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Efecto impositivo [00205]
18 | 217 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - Total transferencias cuenta pérdidas y ganacias  [00206]
19 | 234 | 17 | N | Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias - TOTAL INGRESOS Y GASTOS RECONOCIDOS [00207]
20 | 251 | 200 | An | RESERVADO PARA LA AEAT
21 | 451 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20052000>"
Total: |  | 462

# DP200053

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "53000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital - Suscrito [00208]
7 | 30 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital - Menos: no exigido [00209]
8 | 47 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Saldo, final ejercicio anterior - Capital - Menos: reembolsable [00210]
9 | 64 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital - Reservas [00211]
10 | 81 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital - Resultados ejercicios anteriores [00212]
11 | 98 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Capital - Suscrito [00217]
12 | 115 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Capital - Menos: no exigido [00218]
13 | 132 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -  Ajustes por cambio de criterio - Capital - Menos: reembolsable [00219]
14 | 149 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Reservas [00220]
15 | 166 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Resultados ejercicios anteriores [00221]
16 | 183 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital -  Suscrito [00226]
17 | 200 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital -  Menos: no exigido [00227]
18 | 217 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital -  Menos: reembolsable [00228]
19 | 234 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Reservas [00229]
20 | 251 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Resultados ejercicios anteriores [00230]
21 | 268 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Capital - Suscrito [00235]
22 | 285 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Capital - Menos: no exigido [00236]
23 | 302 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Capital - Menos: reembolsable [00237]
24 | 319 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Reservas [00238]
25 | 336 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Resultados ejercicios anteriores [00239]
26 | 353 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Capital - Suscrito [00244]
27 | 370 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Capital - Menos: no exigido [00245]
28 | 387 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Capital - Menos: reembolsable [00246]
29 | 404 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Reservas [00247]
30 | 421 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Resultados ejercicios anteriores [00248]
31 | 438 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital - Suscrito [00253]
32 | 455 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital - Menos: no exigido [00254]
33 | 472 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital - Menos: reembolsable [00255]
34 | 489 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Reservas [00256]
35 | 506 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Resultados ejercicios anteriores [00257]
36 | 523 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Capital - Suscrito [00262]
37 | 540 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Capital - Menos: no exigido [00263]
38 | 557 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Capital - Menos: reembolsable [00264]
39 | 574 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Operaciones con socios -  Aumentos de capital - Reservas [00265]
40 | 591 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Resultados ejercicios anteriores [00266]
41 | 608 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Capital - Suscrito [00271]
42 | 625 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Capital - Menos: no exigido [00272]
43 | 642 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Capital - Menos: reembolsable [00273]
44 | 659 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Reservas [00274]
45 | 676 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Resultados ejercicios anteriores [00275]
46 | 693 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Capital - Suscrito [00280]
47 | 710 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Capital - Menos: no exigido [00281]
48 | 727 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Capital - Menos: reembolsable [00282]
49 | 744 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Reservas [00283]
50 | 761 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Resultados ejercicios anteriores [00284]
51 | 778 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Capital - Suscrito [00289]
52 | 795 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Capital - Menos: no exigido [00290]
53 | 812 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Capital - Menos: reembolsable [00291]
54 | 829 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Reservas [00292]
55 | 846 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Resultados ejercicios anteriores [00293]
56 | 863 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Capital - Suscrito [00298]
57 | 880 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Capital - Menos: no exigido [00299]
58 | 897 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Capital - Menos: reembolsable [00300]
59 | 914 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Reservas [00301]
60 | 931 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Resultados ejercicios anteriores [00302]
61 | 948 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital - Suscrito [00307]
62 | 965 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital - Menos: no exigido [00308]
63 | 982 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital - Menos: reembolsable [00309]
64 | 999 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Reservas [00310]
65 | 1016 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Resultados ejercicios anteriores [00311]
66 | 1033 | 200 | An | RESERVADO PARA LA AEAT
67 | 1233 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20053000>"
Total: |  | 1244

# DP200054

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "54000"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior - Resultado ejercicio [00213]
7 | 30 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior -  Ajustes cambio valor [00214]
8 | 47 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior - Fondos provisiones técnicas. Aportaciones de terceros [00215]
9 | 64 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior -  Total [00216]
10 | 81 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Resultado ejercicio [00222]
11 | 98 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Ajustes cambio valor [00223]
12 | 115 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -  Ajustes por cambio de criterio - Fondos provisiones técnicas. Aportaciones de terceros [00224]
13 | 132 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Total [00225]
14 | 149 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Resultado ejercicio [00231]
15 | 166 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Ajustes cambio valor [00232]
16 | 183 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -  Ajustes por errores - Fondos provisiones técnicas. Aportaciones de terceros [00233]
17 | 200 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Total [00234]
18 | 217 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Resultado ejercicio [00240]
19 | 234 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Ajustes cambio valor [00241]
20 | 251 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Fondos provisiones técnicas. Aportaciones de terceros [00242]
21 | 268 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Total [00243]
22 | 285 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Resultado ejercicio [00249]
23 | 302 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Ajustes cambio valor [00250]
24 | 319 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos - Fondos provisiones técnicas. Aportaciones de terceros [00251]
25 | 336 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Total ingresos/gastos reconocidos - Total [00252]
26 | 353 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Resultado ejercicio [00258]
27 | 370 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Ajustes cambio valor [00259]
28 | 387 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Fondos provisiones técnicas. Aportaciones de terceros [00260]
29 | 404 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Total [00261]
30 | 421 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Resultado ejercicio [00267]
31 | 438 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Ajustes cambio valor [00268]
32 | 455 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Fondos provisiones técnicas. Aportaciones de terceros [00269]
33 | 472 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de capital - Total [00270]
34 | 489 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Resultado ejercicio [00276]
35 | 506 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Ajustes cambio valor [00277]
36 | 523 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Fondos provisiones técnicas. Aportaciones de terceros [00278]
37 | 540 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones de capital - Total [00279]
38 | 557 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Resultado ejercicio [00285]
39 | 574 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Ajustes cambio valor [00286]
40 | 591 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Fondos provisiones técnicas. Aportaciones de terceros [00287]
41 | 608 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución de dividendos - Total [00288]
42 | 625 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Resultado ejercicio [00294]
43 | 642 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Ajustes cambio valor [00295]
44 | 659 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Fondos provisiones técnicas. Aportaciones de terceros [00296]
45 | 676 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras operaciones con socios - Total [00297]
46 | 693 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Resultado ejercicio [00303]
47 | 710 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Ajustes cambio valor [00304]
48 | 727 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Fondos provisiones técnicas. Aportaciones de terceros [00305]
49 | 744 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Total [00306]
50 | 761 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Resultado ejercicio [00312]
51 | 778 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Ajustes cambio valor [00313]
52 | 795 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Fondos provisiones técnicas. Aportaciones de terceros [00314]
53 | 812 | 17 | N | Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Total [00315]
54 | 829 | 200 | An | RESERVADO PARA LA AEAT
55 | 1029 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T20054000>"
Total: |  | 1040

# DP200DID

 | Agencia Tributaria
Modelo 200 |  | Diseño de registro
vers. 1.04 |  | Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español) 2018
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | OBLIGATORIO | Constante "<T"
2 | 3 | 3 | Num | Modelo. | OBLIGATORIO | Constante "200"
3 | 6 | 5 | An | Página. | OBLIGATORIO | Constante "DID00"
4 | 11 | 1 | An | Fin de identificador de modelo. | OBLIGATORIO | Constante ">"
5 | 12 | 1 | An | Indicador de página complementaria |  | En blanco
6 | 13 | 1 | An | Cuenta corriente tributaria |  | "0" o "1"
7 | 14 | 4 | Num | Identificación - Ejercicio
8 | 18 | 1 | Num | Tipo de ejercicio
9 | 19 | 2 | An | Período Impositivo |  | "0A"
10 | 21 | 2 | Num | Período Impositivo inicio - Día
11 | 23 | 2 | Num | Período Impositivo inicio - Mes
12 | 25 | 2 | Num | Período Impositivo inicio - Año
13 | 27 | 2 | Num | Período Impositivo fin - Día
14 | 29 | 2 | Num | Período Impositivo fin - Mes
15 | 31 | 2 | Num | Período Impositivo fin - Año
16 | 33 | 9 | An | Identificación - NIF
17 | 42 | 80 | An | Identificación - Apellidos y nombre o Razón Social
18 | 122 | 17 | N | Liquidación - Base imponible [00552]
19 | 139 | 17 | N | Liquidación - Cuota íntegra [00562]
20 | 156 | 17 | N | Liquidación - Líquido a ingresar o a devolver Estado [00621]
21 | 173 | 17 | Num | RESERVADO AEAT
22 | 190 | 17 | Num | RESERVADO AEAT
23 | 207 | 17 | Num | RESERVADO AEAT
24 | 224 | 17 | Num | RESERVADO AEAT
25 | 241 | 1 | An | Devolución - Renuncia o por Transferencia |  | "blanco", "R","D","X"
26 | 242 | 17 | Num | Devolución - Importe a devolver
27 | 259 | 1 | Num | Devolución - Marca SEPA |  | "0", "1", "2", "3" Nota 1
28 | 260 | 34 | An | Devolución - Número de cuenta IBAN
29 | 294 | 11 | An | Devolución - Código SWIFT-BIC
30 | 305 | 1 | An | Modalidad de ingreso. Uno de los siguientes valores |  | "blanco", "I" Ingreso o "U" Domiciliación
31 | 306 | 1 | An | RESERVADO AEAT
32 | 307 | 1 | An | RESERVADO AEAT
33 | 308 | 17 | Num | Ingreso - Importe a ingresar
34 | 325 | 34 | An | Número de cuenta IBAN
35 | 359 | 17 | N | Abono/Compensación -Abono por conversión de activos impuesto diferido - A
36 | 376 | 17 | N | Abono/Compensación -Compensación por conversión de activos impuesto diferido - C
37 | 393 | 1 | An | Cuota Cero |  | "0" o "1"
38 | 394 | 70 | An | Devolución - Banco/Bank name
39 | 464 | 35 | An | Devolución - Dirección del Banco/ Bank adress
40 | 499 | 30 | An | Devolución - Ciudad/City
41 | 529 | 40 | An | RESERVADO PARA LA AEAT
42 | 569 | 2 | An | Devolución - Código País/Country code
43 | 571 | 23 | An | RESERVADO PARA LA AEAT
44 | 594 | 12 | An | Identificador de fin de registro | OBLIGATORIO | Constante "</T200DID00>"
Total: |  | 605
Nota 1: Devolución marca SEPA
Valor | Descripción
0 | Vacía
1 | Cuenta España
2 | Unión Europea SEPA
3 | Resto Países