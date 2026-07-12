# DR 13000

 | Agencia Tributaria
Modelo 130
versión 1.2 |  | Diseño de registro
 |  | IMPUESTO SOBRE LA RENTA DE LAS PERSONAS FÍSICAS. Actividades económicas en estimación directa.
 |  | Pago fraccionado |  | Autoliquidación
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "130"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) |  | 1T" … "4T"
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T1230+Ejercicio+periodo+0000> |  | "</T1300AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# DR 13001

 | Agencia Tributaria
Modelo 130 |  | Diseño de registro.
 |  | IMPUESTO SOBRELA RENTA DE LAS PERSONAS FÍSICAS 
Actividades económicas en estimación directa. PAGO FRACCIONADO - AUTOLIQUIDACIÓN
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "130"
3 | 6 | 2 | Num | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | A | Indicador de página complementaria | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An | Declarante (1). Sujeto pasivo. NIF
8 | 23 | 60 | An | Declarante (1). Sujeto pasivo. Apellidos
9 | 83 | 20 | An | Declarante (1). Sujeto pasivo. Nombre
10 | 103 | 4 | Num | Devengo (2). Ejercicio
11 | 107 | 2 | An | Devengo (2). Periodo | "1T" … "4T"
12 | 109 | 17 | Num | Liquidación (3). I. Actividades econ. Estim. Directa - [01] Ingresos computables correspondientes al conjunto … | [quince enteros + dos decimales]
13 | 126 | 17 | Num | Liquidación (3). I. Actividades econ. Estim. Directa - [02] Gastos fiscalmente deducibles (…) | [quince enteros + dos decimales]
14 | 143 | 17 | N | Liquidación (3). I. Actividades econ. Estim. Directa - [03 ]Rendimiento neto ([01] - [02]). | [quince enteros + dos decimales]
15 | 160 | 17 | Num | Liquidación (3). I. Actividades econ. Estim. Directa - [04] 20 por 100 del importe de la casilla [03]. | [quince enteros + dos decimales]
16 | 177 | 17 | Num | Liquidación (3). I. Actividades econ. Estim. Directa - [05] A deducir : De los trim. anteriores, suma de los importes (…) | [quince enteros + dos decimales]
17 | 194 | 17 | Num | Liquidación (3). I. Actividades econ. Estim. Directa - [06] A deducir: Retenciones e ingresos a cta. soportados (…) | [quince enteros + dos decimales]
18 | 211 | 17 | N | Liquidación (3). I. Actividades econ. Estim. Directa - [07] Pago fraccionado previo del trimestre ([04]-[05]-[06]) | [quince enteros + dos decimales]
19 | 228 | 17 | Num | Liquidación (3). II. Actividades agrícolas, ganaderas, etc. - [08] Volumen de ingresos del trimestre (…) | [quince enteros + dos decimales]
20 | 245 | 17 | Num | Liquidación (3). II. Actividades agrícolas, ganaderas, etc. - [09] 2 por 100 del importe de la casilla [08] | [quince enteros + dos decimales]
21 | 262 | 17 | Num | Liquidación (3). II. Actividades agrícolas, ganaderas, etc. - [10] A deducir: Retenciones e Ingresos a cuenta (…) | [quince enteros + dos decimales]
22 | 279 | 17 | N | Liquidación (3). II. Actividades agrícolas, ganaderas, etc. - [11] Pago fraccionado previo del trimestre (…) ([09]-[10]) | [quince enteros + dos decimales]
23 | 296 | 17 | Num | Liquidación (3). III. Total Liquidación - [12] Suma de pagos fraccionados del trimestre ([07]+[11]) | [quince enteros + dos decimales]
24 | 313 | 17 | Num | Liquidación (3). III. Total Liquidación - [13] A deducir: Minorac. por aplic. de la deducc. art. 110,3 del Reglam. del Impto. | [quince enteros + dos decimales]
25 | 330 | 17 | N | Liquidación (3). III. Total Liquidación - [14] Diferencia ([12]-[13]) | [quince enteros + dos decimales]
26 | 347 | 17 | Num | Liquidación (3). III. Total Liquidación - [15] A deducir: Resultados negativos ejercicios anteriores | [quince enteros + dos decimales]
27 | 364 | 17 | Num | Liquidación (3). III. Total Liquidación - [16] A deducir: cantidades al pago adquis. o rehab. vivienda habitual (…) | [quince enteros + dos decimales]
28 | 381 | 17 | N | Liquidación (3). III. Total Liquidación - [17] Total ([14]-[15]-[16]) | [quince enteros + dos decimales]
29 | 398 | 17 | Num | Liquidación (3). III. Total Liquidación - [18] A deducir (exclus. complementaria) Resultado anteriores liquidaciones (…) | [quince enteros + dos decimales]
30 | 415 | 17 | N | Liquidación (3). III. Total Liquidación - [19] Resultado de la autoliquidación ([17]-[18]) | [quince enteros + dos decimales]
31 | 432 | 1 | An | Declaración complementaria. | blanco o "X"
32 | 433 | 13 | An | Número de justificante de la declaración anterior
33 | 446 | 34 | An | Domiciliación IBAN
34 | 480 | 96 | An | Reservado AEAT | En blanco
35 | 576 | 13 | An | Reservado para la Administración. Sello electronico | En blanco
36 | 589 | 12 | An | Indicador de fin de registro. | Constante "</T13001000>"
 | TOTAL | 600 | POSICIONES
Nota 1: El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (ingreso a anotar en CCT), N (negativa) y B (resultado al deducir)
Nota 2:
1. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 130.txt
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES