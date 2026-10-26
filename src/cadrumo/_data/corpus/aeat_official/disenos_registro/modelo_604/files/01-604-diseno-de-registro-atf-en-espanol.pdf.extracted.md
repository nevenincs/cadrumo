# Pag. 1

ANEXO II - DISEÑOS LÓGICOS A LOS QUE DEBEN AJUSTARSE LOS ARCHIVOS
QUE SE GENEREN PARA LA PRESENTACIÓN TELEMÁTICA DEL ANEXO
INFORMATIVO DEL MODELO 604
A.- TIPO DE REGISTRO 1: REGISTRO DE DECLARANTE.
Se consignarán los datos identificativos del sujeto pasivo junto con el resumen
global de la información recogida en el registro de tipo 2.
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO
Constante número '1'.
2-4 Alfabético MODELO DE ANEXO
“ATF”.
5-8 Numérico EJERCICIO
Las cuatro cifras del ejercicio fiscal al que corresponde el
anexo.
9-17 Alfanumérico NIF/C.I.I. DEL SUJETO PASIVO
Se consignará el NIF del sujeto pasivo.
Este campo deberá estar ajustado a la derecha, siendo la
última posición el carácter de control y rellenando con
ceros las posiciones de la izquierda, de acuerdo con las
reglas previstas en el Reglamento General de las
actuaciones y los procedimientos de gestión e inspección
tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos, aprobado por
el Real Decreto 1065/2007 de 27 de Julio (BOE del 5 de
septiembre).
Si no se dispone de NIF deberá consignarse el código de
identificación individual asignado.
18-57 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL
SUJETO PASIVO
Si es una persona física se consignará el primer apellido,
un espacio, el segundo apellido, un espacio y el nombre
completo, necesariamente en este orden.
Para personas jurídicas y entidades en régimen de
atribución de rentas, se consignará la razón social
completa, sin anagrama.
En ningún caso podrá figurar en este campo un nombre
comercial.
1

# Pag. 2

58-107 Blancos BLANCOS
Se consignará a blancos.
108-120 Alfanumérico NÚMERO IDENTIFICATIVO DEL ANEXO
Se consignará el número identificativo correspondiente al
anexo. Será un número secuencial cuyos tres primeros
dígitos se corresponderán con el código ATF.
121-122 Alfabético ANEXO COMPLEMENTARIO O SUSTITUTIVO
En el caso excepcional de segunda o posterior
presentación de anexos, deberá cumplimentarse
obligatoriamente uno de los siguientes campos:
121 ANEXO COMPLEMENTARIO: Se consignará una “C”
si la presentación de este anexo tiene por objeto incluir
registros que, debiendo haber figurado en otro anexo del
mismo ejercicio y periodo presentado anteriormente,
hubieran sido completamente omitidos en el mismo.
122 ANEXO SUSTITUTIVO: Se consignará una “S” si la
presentación tiene como objeto anular y sustituir
completamente a otro anexo anterior, del mismo ejercicio y
periodo. Un anexo sustitutivo sólo puede anular a un único
anexo anterior.
123-135 Alfanumérico NUMERO IDENTIFICATIVO DEL ANEXO ANTERIOR
En el caso de que se haya consignado una “C” en el
campo “Anexo complementario” o en el caso de que se
haya consignado “S” en el campo “Anexo sustitutivo”, se
consignará el número identificativo correspondiente al
anexo al que sustituye o complementa.
Campo de contenido alfanumérico de 13 posiciones.
En cualquier otro caso deberá rellenarse a CEROS.
136-137 Numérico PERIODO
Se hará constar el periodo al que corresponda el anexo.
Se consignará el que corresponda según la siguiente
relación de claves:
“01” - Enero
“02” - Febrero
“03” - Marzo
“04” - Abril
“05” - Mayo
“06” - Junio
“07” - Julio
2

# Pag. 3

“08” - Agosto
“09” - Septiembre
“10” - Octubre
“11” - Noviembre
“12” - Diciembre
138-154 Numérico NÚMERO TOTAL DE OPERACIONES DECLARADAS
Se consignará el número total de registros Tipo 2.
155-171 Numérico NÚMERO TOTAL DE OPERACIONES SUJETAS NO
EXENTAS INCLUIDAS EN EL ANEXO
Se consignará el número de registros Tipo 2 en los que el
Campo “Tipo de operación: operación no exenta o exenta”
sea “S” (posición 190 registro tipo 2) y el campo
“Rectificación” no tenga contenido.
(posición 325 registro tipo 2)
172-189 Numérico BASE IMPONIBLE TOTAL DE LAS OPERACIONES
SUJETAS NO EXENTAS INCLUIDAS EN EL ANEXO
Campo numérico de 18 posiciones.
Se consignará, sin signo y sin coma decimal, la suma del
campo Base imponible (posiciones 242-259 registro tipo 2)
de todos los registros Tipo 2 en los que el campo “Tipo de
operación: operación no exenta o exenta” sea “S” (posición
190 registro Tipo 2) y el campo “Rectificación” no tenga
contenido (posición 325 registro tipo 2)
Este campo se subdivide en dos:
- 172-187 Parte entera de la base imponible total de las
operaciones sujetas no exentas incluidas en el anexo.
- 188-189 Parte decimal de la base imponible total de las
operaciones sujetas no exentas incluidas en el anexo.
190-207 Numérico CUOTA TOTAL DE LAS OPERACIONES SUJETAS NO
EXENTAS INCLUIDAS EN EL ANEXO
Campo numérico de 18 posiciones.
Se consignará, sin signo y sin coma decimal, la suma del
campo “Cuota tributaria derivada de la operación”
(posiciones 291-308 registro tipo 2) de todos los registros
de Tipo 2 en los que el campo “Tipo de operación:
operación no exenta o exenta” sea “S” (posición 190
registro Tipo 2) y el campo “Rectificación” no tenga
contenido (posición 325 registro tipo 2)
Este campo se subdivide en dos:
3

# Pag. 4

190-205 Parte entera de la cuota total de las operaciones
sujetas no exentas incluidas en el anexo.
206-207 Parte decimal de la cuota total de las operaciones
sujetas no exentas incluidas en el anexo.
208-224 Numérico NÚMERO TOTAL DE OPERACIONES EXENTAS
INCLUIDAS EN EL ANEXO
Se consignará el número de registros Tipo 2 en los que el
Campo “Tipo de operación: operación no exenta o exenta”
sea “E” (posición 190 registro tipo 2) y el campo
“Rectificación” no tenga contenido (posición 325 registro
tipo 2)
225-242 Numérico IMPORTE TOTAL DE LAS OPERACIONES EXENTAS
INCLUIDAS EN EL ANEXO
Campo numérico de 18 posiciones.
Se consignará, sin signo y sin coma decimal, la suma del
campo “Importe de la adquisición de las operaciones
sujetas y exentas” (posiciones 273-290 registro tipo 2) de
todos los registros Tipo 2 en los que el campo “Tipo de
operación: operación no exenta o exenta” sea “E” (posición
190 registro Tipo 2) y el campo “Rectificación” no tenga
contenido (posición 325 registro tipo 2)
Este campo se subdivide en dos:
225-240 Parte entera del importe total de las operaciones
exentas incluidas en el anexo.
241-242 Parte decimal del importe total de las operaciones
exentas incluidas en anexo.
243-259 Numérico NÚMERO TOTAL DE RECTIFICACIONES.
Se consignará el número de registros Tipo 2 en los que
el Campo “Rectificación” sea ”X” (posición 325 registro
tipo 2)
260-278 Alfanumérico TOTAL B.I/IMPORTE DE LAS RECTIFICACIONES.
Campo alfanumérico de 19 posiciones.
Se consignará, la suma de las cantidades (sin coma
decimal) reflejadas en el campo “Resultado de la
rectificación BI/importe) (posiciones 387-405
correspondientes al registro de tipo 2) de todos los
4

# Pag. 5

registros Tipo 2 en los que el campo “Rectificación” sea “X”
(posición 325 registro Tipo 2).
Este campo se subdivide en:
260: SIGNO:
Campo alfabético que se cumplimentará cuando el resultado de
la operación a que se acaba de hacer referencia sea menor que 0
(cero); en este caso se consignará una “N”. En cualquier otro caso
el contenido del campo será blanco.
261-278 IMPORTE Campo numérico de 18
posiciones
Se consignará el importe resultante de la operación a que
se ha hecho referencia más arriba
Este campo se subdivide en dos:
- 261-276 Parte entera de la base imponible total de las
rectificaciones.
- 277-278 Parte decimal de la base imponible total de las
rectificaciones.
279-296 Alfanumérico CUOTA RESULTANTE DE LAS RECTIFICACIONES.
Campo alfanumérico de 18 posiciones.
Se consignará la suma de las cantidades (sin coma
decimal) reflejadas en los campos IMPORTE DE LA
RECTIFICACION (CUOTA) (posiciones 368 a 386
correspondientes al registro de tipo 2) de todos los
registros Tipo 2 en los que el campo “Rectificación” sea “X”
(posición 325 registro Tipo 2).
Este campo se subdivide en:
279 SIGNO:
Campo alfabético que se cumplimentará cuando el resultado de la
suma a que se acaba de hacer referencia sea menor que 0 (cero); en
este caso se consignará una “N”. En cualquier otro caso el contenido
del campo será un espacio.
280-296 IMPORTE Campo numérico de 17 posiciones.
5

# Pag. 6

Este campo se subdivide en dos:
280-294 Parte entera de la cuota resultante de las
rectificaciones.
295-296 Parte decimal de la cuota resultante de las
rectificaciones .
297 Alfabético OPCIÓN POR LA FECHA TEÓRICA DE LIQUIDACIÓN
Se cumplimentará con “X” en la primera autoliquidación
que se presente en cada año natural si se opta por la
fecha teórica de liquidación.
En los demás casos, este campo figurará en blanco.
298 Alfabético REVOCACIÓN DE LA OPCIÓN POR LA FECHA
TEÓRICA DE LIQUIDACIÓN.
Se cumplimentará con “X” en la primera autoliquidación
que se presente en cada año natural si se revoca la
opción por la fecha teórica de liquidación.
299-500 Blancos BLANCOS
6

# Pag. 7

TIPO DE REGISTRO 2: REGISTRO DE OPERACIONES.
En el registro de tipo 2 se debe informar de manera individualizada cada operación de
acuerdo a los siguientes criterios de registro:
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO
Numérico de una posición
Constante "2" (Dos)
2-4 Alfabético MODELO DE ANEXO
Alfabético de tres posiciones.
“ATF”
5-8 Numérico EJERCICIO
Las cuatro cifras del ejercicio fiscal al que corresponde el
anexo.
9-17 Alfanumérico NIF/C.I.I DEL SUJETO PASIVO
Se consignará el NIF del sujeto pasivo.
Consignar el mismo NIF contenido en estas mismas
posiciones (9-17) del registro de tipo 1.
Si no se dispone de NIF deberá consignarse el código de
identificación individual asignado.
18-75 Blancos BLANCOS
76-77 Numérico PERIODO
Se hará constar el periodo al que corresponda el anexo.
Se consignará el que corresponda según la siguiente
relación de claves:
“01” - Enero
“02” - Febrero
“03” - Marzo
“04” - Abril
“05” - Mayo
“06” - Junio
“07” - Julio
“08” - Agosto
“09” - Septiembre
7

# Pag. 8

“10” - Octubre
“11” - Noviembre
“12” - Diciembre
78-113 Alfanumérico REFERENCIA DE LA TRANSACCIÓN O
IDENTIFICADOR ÚNICO
Deberá consignarse la referencia de la transacción o
identificador único que permita al sujeto pasivo identificar
la operación informada y el periodo de liquidación.
114 Alfabético TRANSACCIÓN POR CUENTA PROPIA O AJENA
Se consignarán una de las siguientes claves:
P: Si la transacción es ejecutada por el sujeto pasivo por
cuenta propia.
A: Si la transacción es ejecutada por el sujeto pasivo por
cuenta de terceros.
115 Alfabético TIPO DE SUPUESTO DE PRESENTACIÓN A TRAVES
DE DEPOSITARIO CENTRAL DE VALORES SITUADO
EN TERRITORIO ESPAÑOL
En el caso de que la presentación se realice a través de
un depositario central de valores situado en territorio
español deberá identificarse el supuesto por el cual se
hace de este modo la presentación.
A estos efectos se consignará alguna de las siguientes
claves:
A. Supuesto previsto en el artículo 3.a) del Real Decreto
366/2021, de 25 de mayo
B. Supuesto previsto en el artículo 3.b) del Real Decreto
366/2021, de 25 de mayo
C. Supuesto previsto en el artículo 4.1.a) del Real
Decreto 366/2021, de 25 de mayo
D. Supuesto previsto en el artículo 4.1.b) del Real
Decreto 366/2021, de 25 de mayo
E. Supuesto previsto en el artículo 4.1.c) del Real
Decreto 366/2021, de 25 de mayo
F. Supuesto previsto en el artículo 2.2 del Real Decreto
366/2021, de 25 de mayo
116 Alfabético SUPUESTO DE PRESENTACIÓN POR EL SUJETO
PASIVO
Este campo se cumplimentará cuando la presentación e
ingreso se realice por el sujeto pasivo.
Cuando la presentación e ingreso se realice por el sujeto
pasivo se consignará la clave “X”. En los demás casos,
este campo figurará en blanco.
8

# Pag. 9

117-132 Numérico NÚMERO DE TÍTULOS ADQUIRIDOS
Se consignará el número de títulos adquiridos en la
operación declarada.
133-144 Alfanumérico CÓDIGO ISIN DE LOS TÍTULOS ADQUIRIDOS
Se consignará el código ISIN de identificación de los
títulos adquiridos.
145-153 Alfanumérico NIF EMISOR
Se consignará el NIF del emisor de los valores.
154-173 Alfanumérico CÓDIGO LEI EMISOR
Se consignará el código LEI del emisor de los valores.
174-181 Numérico FECHA DE LIQUIDACION / REGISTRO
Se consignará la fecha teórica de liquidación en caso de
que se hubiese ejercido la opción por dicha fecha, o la
fecha de anotación registral si no se hubiese ejercido la
opción.
174-177 Numérico Año
178-179 Numérico Mes
180-181 Numérico Día
182-189 Numérico FECHA DE EJECUCIÓN
Fecha de ejecución. Solo se consignará en el caso de
que la regla de determinación de la base imponible sea la
prevista en el artículo 5.3. de la Ley del Impuesto.
182-185 Numérico Año
186-187 Numérico Mes
188-189 Numérico Día
190 Alfabético TIPO DE OPERACIÓN: OPERACIÓN NO EXENTA O
EXENTA
Se informará con una de las dos claves siguientes el tipo
de operación:
S: Operación sujeta y no exenta.
E: Operación sujeta y exenta.
191 Alfabético MODALIDADES DE DETERMINACIÓN DE LA BASE
IMPONIBLE EN LAS OPERACIONES SUJETAS Y NO
EXENTAS
En el caso de las operaciones sujetas y no exentas se
consignará la clave que corresponda según la modalidad
de determinación de la base imponible prevista en el
9

# Pag. 10

artículo 5 de la Ley 5/2020, de 15 de octubre, del
Impuesto sobre las Transacciones Financiera:
A: Se consignará esta clave cuando la base imponible
esté constituida por el importe de la contraprestación sin
incluir los costes de transacción derivados de los precios
de las infraestructuras de mercado, ni las comisiones de
intermediación, ni ningún otro gasto asociado a la
operación. (Artículo 5.1 de la Ley del Impuesto sobre las
Transacciones Financieras).
B: Se consignará esta clave cuando la base imponible
esté constituida por el valor correspondiente al cierre del
mercado regulado más relevante por liquidez del valor en
cuestión el último día de negociación anterior al de la
operación. (Artículo 5.1 de la Ley del Impuesto sobre las
Transacciones Financieras).
C: Cuando la adquisición de valores proceda de bonos u
obligaciones convertibles o canjeables o de otros valores
negociables que den lugar a la adquisición, la base
imponible será el valor establecido en el documento de
emisión de estos. (Artículo 5.2.a) de la Ley del Impuesto
sobre las Transacciones Financieras).
D: Cuando la adquisición proceda de la ejecución o
liquidación de opciones o de otros instrumentos
financieros derivados que otorguen un derecho a adquirir
o transmitir los valores sometidos al impuesto, la base
imponible será el precio del ejercicio fijado en el contrato.
(Artículo 5.2.b) de la Ley del Impuesto sobre las
Transacciones Financieras).
E: Cuando la adquisición proceda de un instrumento
derivado que constituya una transacción a plazo, la base
imponible será el precio pactado, salvo que dicho
derivado se negocie en un mercado regulado, en cuyo
caso la base imponible será el precio de entrega al que
deba realizarse dicha adquisición al vencimiento. (Artículo
5.2.c) de la Ley del Impuesto sobre las Transacciones
Financieras).
F: Cuando la adquisición proceda de la liquidación de un
contrato financiero definido en el cuarto párrafo del
artículo 2.1. de la Orden EHA/3537/2005, de 10 de
noviembre, por la que se desarrolla el artículo 27.4 de la
Ley 24/1988, de 28 de julio, del Mercado de Valores; la
base imponible será el valor correspondiente al cierre del
mercado regulado más relevante por liquidez del valor en
cuestión el último día de negociación anterior al de la
10

# Pag. 11

operación. (artículo 5.2.d) de la Ley del Impuesto sobre
las Transacciones Financieras).
G: En el caso de las operaciones intradía previstas en el
artículo 5.3 de la Ley del Impuesto sobre las
Transacciones Financieras, la base imponible establecida
en este mismo artículo para estos supuestos.
192-207 Numérico NÚMERO DE TITULOS TRANSMITIDOS
Este campo sólo podrá cumplimentarse cuando el campo
“MODALIDADES DE DETERMINACIÓN DE LA BASE
IMPONIBLE EN LAS OPERACIONES SUJETAS Y NO
EXENTAS” (posición 191 registro Tipo 2) tome el valor
“G”.
En este campo se consignará el número de títulos
transmitidos en las operaciones intradía declaradas.
208-223 Numérico TÍTULOS NETOS ADQUIRIDOS
Este campo sólo podrá cumplimentarse cuando el campo
“MODALIDADES DE DETERMINACIÓN DE LA BASE
IMPONIBLE EN LAS OPERACIONES SUJETAS Y NO
EXENTAS” (posición 191 registro Tipo 2) tome el valor
“G”.
Se consignará la diferencia entre “NUMERO DE
TÍTULOS ADQUIRIDOS” (posiciones 117-132) y
“NÚMERO DE TÍTULOS TRANSMITIDOS” (posiciones
192-207).
224-241 Numérico IMPORTE TOTAL DE LAS ADQUISICIONES
Este campo sólo podrá cumplimentarse cuando el campo
“MODALIDADES DE DETERMINACIÓN DE LA BASE
IMPONIBLE EN LAS OPERACIONES SUJETAS Y NO
EXENTAS” (posición 191 registro Tipo 2) tome el valor
“G”.
Se consignará el importe de las adquisiciones de los
títulos adquiridos consignados en las posiciones (117-
132).
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
224-239 Parte entera del importe total de las
adquisiciones, si no tiene contenido se consignará a
ceros.
240-241 Parte decimal del importe total de las
adquisiciones, si no tiene contenido se consignará a
ceros
11

# Pag. 12

242-259 Numérico BASE IMPONIBLE DE LA OPERACIÓN SUJETA Y NO
EXENTA DECLARADA
Se consignará el importe de la base imponible de la
operación sujeta y no exenta declarada conforme a la
modalidad que proceda de acuerdo con lo previsto en el
artículo 5 de la Ley del Impuesto sobre Transacciones
Financieras.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
242-257 Parte entera del importe de la base imponible, si
no tiene contenido se consignará a ceros.
258-259 Parte decimal del importe de la base imponible,
si no tiene contenido se consignará a ceros
260-272 Alfanumérico SUPUESTOS DE EXENCIÓN APLICABLE
En el caso de las operaciones sujetas y exentas se
consignará el supuesto o supuestos de exención
aplicables a la operación de acuerdo con lo previsto en el
artículo 3 de la Ley 5/2020, de 15 de octubre, del
Impuesto sobre Transacciones Financieras, de acuerdo
con las siguientes posiciones y claves:
260 Alfabético A: exención artículo 3.1.a) de la Ley
5/2020, de 15 de octubre, del
Impuesto sobre Transacciones
Financieras.
261 Alfabético B: exención 3.1.b) de la Ley 5/2020,
de 15 de octubre, del Impuesto sobre
Transacciones Financieras.
262 Alfabético C: exención 3.1.c) de la Ley 5/2020,
de 15 de octubre, del Impuesto sobre
Transacciones Financieras.
263 Alfabético D: exención 3.1.d) de la Ley 5/2020,
de 15 de octubre, del Impuesto sobre
Transacciones Financieras.
264 Alfabético E: exención 3.1.e) de la Ley 5/2020,
de 15 de octubre, del Impuesto sobre
Transacciones Financieras.
265 Alfabético F: exención 3.1.f) de la Ley 5/2020, de
15 de octubre, del Impuesto sobre
Transacciones Financieras.
266 Alfabético G: exención 3.1.g) de la Ley 5/2020,
de 15 de octubre, del Impuesto sobre
Transacciones Financieras.
12

# Pag. 13

267 Alfabético H: exención 3.1.h) de la Ley 5/2020,
de 15 de octubre, del Impuesto sobre
Transacciones Financieras.
268 Alfabético I: exención 3.1.i) de la Ley 5/2020, de
15 de octubre, del Impuesto sobre
Transacciones Financieras.
269 Alfabético J: exención 3.1.j) de la Ley 5/2020 de
15 de octubre, del Impuesto sobre
Transacciones Financieras.
270 Alfabético K: exención 3.1.k) de la Ley 5/2020 de
15 de octubre, del Impuesto sobre
Transacciones Financieras.
271 Alfabético L: exención 3.1.l) de la Ley 5/2020, de
15 de octubre, del Impuesto sobre
Transacciones Financieras.
272 Alfabético M: Otros supuestos de exención.
Cuando se utilice esta clave será
obligatorio indicar la exención aplicada
en el campo “Descripción” (posiciones
406-449 registro tipo 2).
273-290 Numérico IMPORTE DE ADQUISICIÓN DE LAS OPERACIONES
SUJETAS Y EXENTAS
Se consignará el importe de la base imponible de la
operación sujeta y exenta informada.
Solo se cumplimentará si el campo “Tipo de operación:
operación no exenta o exenta” (posición 190 registro Tipo
2) sea “E”.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
273-288 Parte entera del importe de adquisición de las
operaciones sujetas y exentas, si no tiene contenido se
consignará a ceros.
289-290 Parte decimal del importe de adquisición de las
operaciones sujetas y exentas, si no tiene contenido se
consignará a ceros
291-308 Numérico CUOTA TRIBUTARIA DERIVADA DE LA OPERACIÓN
DECLARADA
Se consignará el importe de la cuota impositiva de la
operación sujeta y no exenta declarada.
Solo se cumplimentará si el campo “Tipo de operación:
operación no exenta o exenta” (posición 190 registro Tipo
2) sea “S”.
13

# Pag. 14

Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
291-306 Parte entera del importe de la cuota tributaria, si
no tiene contenido se consignará a ceros.
307-308 Parte decimal del importe de la cuota tributaria,
si no tiene contenido se consignará a ceros
309-316 Numérico FECHA DE COMUNICACIÓN DE LA INFORMACIÓN AL
DCV
Se consignará la fecha en que el sujeto pasivo ha
comunicado al depositario central de valores la
información establecida en el artículo 5.2 del Real
Decreto 366/2021, de 25 de mayo, por el que se
desarrolla el procedimiento de presentación e ingreso de
las autoliquidaciones del Impuesto sobre Transacciones
Financieras.
309-312 Numérico Año
313-314 Numérico Mes
315-316 Numérico Día
317-324 Numérico FECHA DE PAGO DEL SUJETO PASIVO
Se consignará la fecha de pago del sujeto pasivo a la
entidad participante en el depositario central de valores.
No se cumplimentará si el sujeto pasivo tiene la condición
de entidad participante en depositario central de valores
establecido en territorio español.
317-320 Numérico Año
321-322 Numérico Mes
323-324 Numérico Día
325 Alfabético RECTIFICACIÓN.
Este campo se cumplimentará cuando el registro
corresponda a una rectificación de acuerdo con el
artículo 9 del Real Decreto 366/2021, de 25 de mayo.
Cuando el registro corresponda a una rectificación se
consignará la clave “X”. En los demás casos, este campo
figurará en blanco.
326-329 Numérico EJERCICIO DE LA OPERACIÓN RECTIFICADA.
14

# Pag. 15

Las cuatro cifras del ejercicio fiscal en que se declaró la
operación que se rectifica.
330-331 Numérico PERÍODO DE LA OPERACIÓN QUE SE RECTIFICA.
Se hará constar el periodo en que se declaró la operación
que se rectica.
.
Se consignará el que corresponda según la siguiente
relación de claves:
“01” - Enero
“02” - Febrero
“03” - Marzo
“04” - Abril
“05” - Mayo
“06” - Junio
“07” - Julio
“08” - Agosto
“09” - Septiembre
“10” - Octubre
“11” - Noviembre
“12” - Diciembre
332-349 Numérico BI RECTIFICADA/IMPORTE RECTIFICADO.
Se consignará el importe de la base imponible o de la
operación exenta que resulte de la rectificación
de acuerdo con el artículo 9 del Real Decreto 366/2021,
de 25 de mayo.
Los importes deben consignarse en EUROS.
Este campo se subdivide en:
332-347 Parte entera del importe de la base imponible
rectificada, si no tiene contenido se consignará a ceros.
348-349 Parte decimal del importe de la base imponible
rectificada, si no tiene contenido se consignará a ceros.
15

# Pag. 16

350-367 Numérico CUOTA TRIBUTARIA RECTIFICADA.
Se consignará el importe de la cuota tributaria que resulte
de la rectificación de acuerdo con el artículo 9 del Real
Decreto XX/2020, de xx.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
350-365 Parte entera del importe de la cuota tributaria
rectificada, si no tiene contenido se consignará a ceros.
366-367 Parte decimal del importe de la cuota tributaria
rectificada, si no tiene contenido se consignará a ceros.
368-386 Alfanumérico IMPORTE DE LA RECTIFICACIÓN (CUOTA)
Este campo se subdivide en dos:
368 SIGNO: campo alfabético. Se consignará una
N cuando el importe de la rectificación sea menor que
cero. En cualquier otro caso, el contenido de este
campo será un blanco.
369-386 IMPORTE: Campo numérico de 18
Posiciones.
Se consignará la diferencia en entre el campo “Cuota
tributaria rectificada” (posiciones 350-367 registro tipo 2)
y el campo “Cuota tributaria derivada de la operación
declarada” (posiciones 291-308 registro tipo 2). Cuando
no tenga contenido figurará a ceros.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
369-384 Parte entera del importe de la rectificación, si no
tiene contenido se consignará a ceros.
385-386 Parte decimal del importe de la rectificación, si
no tiene contenido se consignará a ceros.
16

# Pag. 17

387-405 Alfanumérico RESULTADO DE LA RECTIFICACIÓN (BI/IMPORTE)
Este campo se subdivide en dos:
387 SIGNO: campo alfabético. Se consignará una
N cuando el importe de la rectificación sea menor que
cero. En cualquier otro caso, el contenido de este
campo será un blanco.
388-405 IMPORTE: Campo numérico de 18
Posiciones.
Se consignará la diferencia entre el campo
“BI rectificada/Importe rectificado” (posiciones 332-349
Registro tipo 2) y el campo “BI de la operación sujeta y no
exenta declarada” (posiciones 242-259 registro tipo 2)
Cuando no tenga contenido figurará a ceros.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
388-403 Parte entera del importe de la rectificación, si no
tiene contenido se consignará a ceros.
404-405 Parte decimal del importe de la rectificación, si
no tiene contenido se consignará a ceros.
406-449 Alfanumérico DESCRIPCIÓN
Campo de texto libre.
450-500 Blancos BLANCOS
17