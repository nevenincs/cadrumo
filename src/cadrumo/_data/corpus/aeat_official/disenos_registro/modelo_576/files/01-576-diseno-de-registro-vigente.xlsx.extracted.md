# Pág 1

 | Agencia Tributaria
Modelo 576 |  | Diseño de registro. Castellano
vers. 1.10 |  | Impuesto especial sobre determinados medios de transporte
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 8 | An | RESERVADO para AEAT. (Etiqueta de Inicio de Datos del Modelo 576) | obligatorio | <T57601>
2 | 9 | 3 | An | Identificador de modelo | obligatorio | "576"
3 | 12 | 1 | A | Tipo declaración | obligatorio | "I" (Ingreso) ó "N" (Negativa)
4 | 13 | 9 | An | RESERVADO para AEAT.
5 | 22 | 4 | Num | Ejercicio de Devengo. | obligatorio | En 2.008, se aceptarán ejercicios de devengo hasta 2.005 inclusive.
6 | 26 | 4 | An | RESERVADO para AEAT.
7 | 30 | 2 | An | Periodo. | obligatorio | "0A"
8 | 32 | 1 | A | Tipo de transporte (V:Vehículos, E:Embarcaciones ó A:Aeronaves) | obligatorio | "V", "E" ó "A"
9 | 33 | 9 | An | Obligado tributario. NIF. | obligatorio
10 | 42 | 40 | An | Obligado tributario. Apellidos y nombre o Razón social. | obligatorio
11 | 82 | 279 | An | RESERVADO para AEAT.
12 | 361 | 1 | An | Ej. Devengo < 2.008: C.M.T. Medio de transporte nuevo                                 Ej. Devengo >= 2.008: Medio de transporte Nuevo / Usado. | obligatorio | Ej.Dev.<2008: "1" o blanco       Ej.Dev.>=2008: "1": Nuevo; "2": Usado.
13 | 362 | 1 | An | Ej.Devengo < 2.008: C.M.T. Adquirido en España o adquirido en un Estado distinto de España.                                                                          Ej.Devengo >= 2.008: Lugar de adquisición del Vehículo. | obligatorio | Ej.Dev.<2008: "1", "2" o blanco           Ej.Dev.>=2008:                        1: Adquirido en España.        2: Adq. en un Estado de la UE distinto de España.                                      3: Adquirido en un Estado no miembro de la UE.
14 | 363 | 1 | An | RESERVADO para AEAT.
15 | 364 | 8 | Num | Ej.Devengo < 2008: Medio de transp.usado. Fecha de primera matriculación.               Ej.Devengo >= 2.008: Medio de transporte nuevo o usado.Fecha de primera matriculación, puesta en servicio o  primera utilización. | obligatorio si usado | formato : DDMMAAAA
16 | 372 | 40 | An | C.M.T. Vehículos. Marca | obligatorio
17 | 412 | 80 | An | C.M.T. Vehículos. Modelo-Tipo | obligatorio
18 | 492 | 22 | An | C.M.T. Vehículos. Nº identificación (bastidor) | obligatorio | Alineado a la izquierda.
19 | 514 | 40 | An | Ejercicio Devengo < 2.008: C.M.T. Vehículos. Clasificación                     Ejercicio Devengo >=2.008: Este campo se desglosa en los 8 campos siguientes.
19.1 | 514 | 4 | An | C.M.T. Vehículos. Clasificación por criterio de construcción y de utilización (RD 2822/1998). | obligatorio | 4 dígitos (2 + 2).
19.2 | 518 | 2 | An | C.M.T. Vehículos. Clasificación según Directiva 70/156/CEE | obligatorio apartir del 01/06/08 | M1, M2,M3, ....
19.3 | 520 | 8 | An | RESERVADO para AEAT.
19.4 | 528 | 5 | Num | C.M.T. Vehículos. Emisiones CO2. | obligatorio | (En gramos / Km.).
19.5 | 533 | 2 | An | C.M.T. Vehículos. Epígrafe. | obligatorio | Epígrafe según Ley Calidad del Aire y protección de la Atmósfera. Valores: 01,02,03,04,05.                                             Se añaden para 2009 los valores: 06,07,08,09.
19.6 | 535 | 6 | Num | Kilómetros/Nº Horas de uso. | obligatorio si usado | Número de Kilimetros del vehículo, o numero de horas de utilizacion si Embarcaciones o Aeronaves.
19.7 | 541 | 12 | An | C.M.T. Vehículos. Nº de serie de Tarjeta ITV | obligatorio | Número de Serie que aparece en la tarjeta ITV
19.8 | 553 | 1 | An | C.M.T. Vehículos. Tipo tarjeta ITV | obligatorio | Valores posibles:
Modelo 576: "A" ,"B", "C" o "D". ;
Modelo 006: "A","B","C" y "O"
de Otras.
20 | 554 | 1 | An | C.M.T. Vehículos. Motor de gasolina, diesel, otros | obligatorio | "1", "2" o "3"
21 | 555 | 5 | Num | C.M.T. Vehículos. Cilindrada (c.c.) | obligatorio
22 | 560 | 40 | An | C.M.T. Embarcaciones. Fabricante o Importador | obligatorio
23 | 600 | 80 | An | C.M.T. Embarcaciones. Modelo | obligatorio
24 | 680 | 22 | An | C.M.T. Embarcaciones. Identificación (Nº construcción) | obligatorio
25 | 702 | 5 | Num | C.M.T. Embarcaciones. Eslora máxima (en metros) |  | 3 enteros + 2 decimales
26 | 707 | 40 | An | C.M.T. Aeronaves. Fabricante. | obligatorio
27 | 747 | 80 | An | C.M.T. Aeronaves. Modelo. | obligatorio
28 | 827 | 22 | An | C.M.T. Aeronaves. Nº serie. | obligatorio
29 | 849 | 4 | Num | C.M.T. Aeronaves. Año fabricación. |  | AAAA
30 | 853 | 10 | Num | C.M.T. Aeronaves. Peso máximo despegue (en Kg.)
31 | 863 | 9 | An | C.M.T. Vehículos. Código ITV.
32 | 872 | 223 | An | RESERVADO para AEAT.
33 | 1095 | 13 | Num | Liquidación. Base imponible. | obligatorio | 11 enteros y 2 decimales
34 | 1108 | 13 | Num | Liquidación. Base imponible reducida. |  | 11 enteros y 2 decimales
35 | 1121 | 5 | Num | Liquidación. Tipo %. | obligatorio | 3 enteros y 2 decimales
36 | 1126 | 13 | Num | Liquidación. Cuota. | obligatorio | 11 enteros y 2 decimales
37 | 1139 | 13 | Num | Liquidación. Deducción lineal |  | 11 enteros y 2 decimales
38 | 1152 | 13 | Num | Liquidación. Cuota a ingresar. | obligatorio | 11 enteros y 2 decimales
39 | 1165 | 13 | Num | Liquidación. A deducir |  | 11 enteros y 2 decimales
40 | 1178 | 13 | Num | Liquidación. Resultado de la liquidación | obligatorio | 11 enteros y 2 decimales
41 | 1191 | 13 | Num | Declación complementaria. Número de justificante de la declaración anterior
42 | 1204 | 30 | An | RESERVADO para AEAT.
43 | 1234 | 30 | An | RESERVADO para los gestores. (Numero de expediente o referencia.)
44 | 1264 | 76 | An | RESERVADO para AEAT.
45 | 1340 | 1 | An | Modelo 576: Causa del Hecho Imponible. | obligatorio | Valores:                               1 : Primera matric. definitiva en España.                                                                             2 : Circulación o utilización en España sin solicitar su matriculación definitiva.                                                                                       3 :  Modificación de circunstancias o requisitos.                                                                                                                4 : Traslado desde Canarias a la Península o Islas Baleares.                                                                                                         5 :  Renuncia a beneficios fiscales reconocidos por la Administración tributaria.
46 | 1341 | 8 | An | RESERVADO para futura modific.
47 | 1349 | 9 | An | NIF de la persona que ha introducido el vehiculo en España | obligatorio (si tipo de tarjeta ITV "A")
48 | 1358 | 40 | An | Apellidos y Nombre o Razon Social del Introductor del vehículo en España. | obligatorio (si tipo de tarjeta ITV "A")
49 | 1398 | 84 | An | RESERVADO para AEAT.
50 | 1482 | 2 | An | C.M.T. Vehículos. Observaciones | obligatorio | Para Vehículos, valores: 00 - Resto de vehículos, 01 - Vehículo tipo quad, 02 - Vehículo tipo todo terreno,                                      03 - Vehículo destinado a vivienda,                             04 - Motocicletas con potencia CEE >o igual a  74 KW (100 CV) y relacion Potencia/Masa < 0.66,                                      05 - Motocicletas  con potencia CEE < 74 KW (100 CV).
06 - Motocicletas con potencia CEE >o igual a  74 KW (100 CV) y relacion Potencia/Masa >= 0.66
07 - Vehículos de tres ruedas con clasificación europea L5e
51 | 1484 | 2 | An | C.M.T. Embarcaciones. Observaciones | obligatorio | Para Embarcaciones, valores:   00 - Resto de vehículos, 01 - moto náutica
52 | 1486 | 23 | An | RESERVADO para AEAT.
53 | 1509 | 9 | An | RESERVADO para AEAT. (Fin Etiqueta de Inicio de Datos del Modelo 576) | obligatorio | </T57601>
TOTAL |  | 1517 | Posiciones
NOTA: Los campos obligatorios en C.M.T., lo son exclusivamente para ese tipo de medio de transporte
C.M.T.: Características del Medio de Transporte.