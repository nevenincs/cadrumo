# dr308

 | Agencia Tributaria
Modelo 308 |  | Diseño de registro
vers. 2.0 |  | IVA. Solicitud de Devolución. Rég. especial recargo de equivalencia, art. 30bis RIVA y sujetos pasivos ocasionales.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido | Uso
1 | 1 | 3 | Num | Modelo |  | Constante '308'
2 | 4 | 1 | An | Moneda |  | Constante 'E' Euros
3 | 5 | 1 | A | Tipo declaración |  | Constante 'D' Solic. Devolución
4 | 6 | 9 | An | Identificación - N.I.F. |  | NIF válido P.F. Ó P.J.
5 | 15 | 4 | An | Primer Apellidos (comienzo del 1er apellido personas físicas)
6 | 19 | 4 | Num | Ejercicio
7 | 23 | 2 | An | Período |  | 1T, 2T, 3T, 4T
8 | 25 | 9 | An | Medios transporte nuevos (MTN) - Adquirente - NIF
9 | 34 | 40 | An | MTN - Adquirente - Apellidos y nombre ó Razón social
10 | 74 | 14 | An | MTN - Adquirente - País
11 | 88 | 40 | An | MTN - Vehículos - Marca
12 | 128 | 40 | An | MTN - Vehículos - Tipo
13 | 168 | 40 | An | MTN - Vehículos - Modelo (denominación comercial)
14 | 208 | 40 | An | MTN - Vehículos - Nº Id. Bastidor
15 | 248 | 40 | An | MTN - Vehículos - Clasificación
16 | 288 | 40 | An | MTN - Embarcaciones - Fabricante
17 | 328 | 40 | An | MTN - Embarcaciones - Tipo
18 | 368 | 40 | An | MTN - Embarcaciones - Identificación
19 | 408 | 6 | Num | MTN - Embarcaciones - Eslora máxima |  | 4 enteros y 2 decimales
20 | 414 | 40 | An | MTN - Aeronaves - Fabricante
21 | 454 | 40 | An | MTN - Aeronaves - Marca
22 | 494 | 40 | An | MTN - Aeronaves - Nº serie
23 | 534 | 4 | Num | MTN - Aeronaves - Año fabricación
24 | 538 | 12 | Num | MTN - Aeronaves - Peso máximo despegue
25 | 550 | 13 | Num | MTN - Liquidación - Precio Adquisición [01] |  | 11 enteros y 2 decimales
26 | 563 | 5 | Num | MTN - Liquidación - Tipo (%) [02] |  | 3 enteros y 2 decimales
27 | 568 | 13 | Num | MTN - Liquidación - IVA soportado [03] |  | 11 enteros y 2 decimales
28 | 581 | 13 | Num | MTN - Liquidación - Precio de venta [04] |  | 11 enteros y 2 decimales
29 | 594 | 5 | Num | MTN - Liquidación - Tipo (%) [05] |  | 3 enteros y 2 decimales
30 | 599 | 13 | Num | MTN - Liquidación - Máximo a devolver [06] |  | 11 enteros y 2 decimales
31 | 612 | 13 | Num | MTN - Liquidación - IVA a devolver [07] |  | 11 enteros y 2 decimales
32 | 625 | 13 | Num | Rég. Espec. recargo equival. (REQ) - Liquidación - Base Imponible [08] |  | 11 enteros y 2 decimales
33 | 638 | 5 | Num | REQ - Liquidación - Tipo (%) [09] |  | 3 enteros y 2 decimales
34 | 643 | 13 | Num | REQ - Liquidación - Cuota [10] |  | 11 enteros y 2 decimales
35 | 656 | 13 | Num | REQ - Liquidación - Base Imponible [11] |  | 11 enteros y 2 decimales
36 | 669 | 5 | Num | REQ - Liquidación - Tipo (%) [12] |  | 3 enteros y 2 decimales
37 | 674 | 13 | Num | REQ - Liquidación - Cuota [13] |  | 11 enteros y 2 decimales
38 | 687 | 13 | Num | REQ - Liquidación - Base Imponible [14] |  | 11 enteros y 2 decimales
39 | 700 | 5 | Num | REQ - Liquidación - Tipo (%) [15] |  | 3 enteros y 2 decimales
40 | 705 | 13 | Num | REQ - Liquidación - Cuota [16] |  | 11 enteros y 2 decimales
41 | 718 | 13 | Num | REQ - Liquidación - IVA a devolver por entregas intracomunitarias [17] |  | 11 enteros y dos decimales
42 | 731 | 13 | Num | MTN - Liquidación - IVA a devolver actividad de transporte[18] |  | 11 enteros y dos decimales
43 | 744 | 20 | Num | Devolución - Código Cuenta Cliente
44 | 764 | 100 | An | Persona de contacto
45 | 864 | 20 | An | Teléfono
46 | 884 | 350 | An | Observaciones
TOTAL |  | 1233 | POSICIONES