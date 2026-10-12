# Pag. 1

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de rentas.
Declaración anual.
1
Ejercicio 2023

# Pag. 2

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Diseños lógicos
Descripción de los registros
Para cada declarante se incluirán dos tipos diferentes de registro, que se distinguen por
la primera posición, con arreglo a los siguientes criterios:
Tipo 1: Registro del declarante. Datos identificativos y resumen de la declaración.
Diseño de tipo de registro 1 de los descritos más adelante y recogidos en el Anexo
de la Orden.
Tipo 2: Registro de declarado. Diseño de tipo de registro 2 de los descritos más
adelante y recogidos en el Anexo de la Orden.
El orden de presentación será el del tipo de registro, existiendo un único registro del tipo
1 y tantos registros del tipo 2 como claves y subclaves declaradas por la entidad y
declaradas por cada socio, heredero, comunero o partícipe.
Todos los campos alfanuméricos y alfabéticos se presentarán alineados a la izquierda y
rellenos de blancos por la derecha, en mayúsculas sin caracteres especiales, y sin vocales
acentuadas.
Para los caracteres específicos del idioma se utilizará la codificación ISO-8859-1. De esta
forma la letra "Ñ" tendrá el valor ASCII 209 (Hex.D1) y la "Ç" (cedilla mayúscula) el valor
ASCII 199 (Hex.C7).
Todos los campos numéricos se presentarán alineados a la derecha y rellenos a ceros
por la izquierda sin signos y sin empaquetar.
Todos los campos tendrán contenido, a no ser que se especifique lo contrario en la
descripción del campo. Si no lo tuvieran, los campos numéricos se rellenarán a ceros y
tanto los alfanuméricos como los alfabéticos a blancos.
2
Ejercicio 2023

# Pag. 3

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Registro de tipo 1: Registro de declarante
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSIC. NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO
Constante número "1"
2-4 Numérico MODELO DECLARACIÓN
Constante "184"
5-8 Numérico EJERCICIO
Las cuatro cifras del ejercicio fiscal al que corresponde la
declaración
9-17 Alfanumérico NIF DEL DECLARANTE
Se consignará el NIF de la entidad en régimen de
atribución de rentas.
Este campo deberá estar ajustado a la derecha, siendo la
última posición el carácter de control y rellenando con
ceros las posiciones de la izquierda, de acuerdo con las
reglas previstas en el Real Decreto 1065/2007, de 27 de
julio, por el que se aprueba el Reglamento General de las
actuaciones y los procedimientos de gestión e inspección
tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos.
18-57 Alfanumérico DENOMINACIÓN O RAZÓN SOCIAL DEL DECLARANTE
Para entidades en régimen de atribución de rentas, se
consignará la razón social completa, sin anagrama.
En ningún caso podrá figurar en este campo un nombre
comercial.
58 Alfabético TIPO DE SOPORTE
Se cumplimentará una de las siguientes claves:
"C": Si la información se presenta en soporte
directamente legible por ordenador.1
"T": Transmisión telemática
59-107 Alfanumérico PERSONA CON QUIÉN RELACIONARSE
Datos de la persona con quién relacionarse, este campo
se subdivide en dos:
1 Derogado tácitamente por la Orden HFP/231/2018, de 6 de marzo.
3
Ejercicio 2023

# Pag. 4

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
59-67 TELÉFONO: Campo numérico de nueve
posiciones
68-107 APELLIDOS Y NOMBRE: Se consignará el
primer apellido, un espacio, el segundo apellido, un
espacio y el nombre completo necesariamente en este
orden.
108-120 Numérico NÚMERO IDENTIFICATIVO DE LA DECLARACIÓN
Se consignará el número identificativo correspondiente a
la declaración. Campo de contenido numérico de 13
posiciones.
El número identificativo que habrá de figurar será un
número secuencial cuyos tres primeros dígitos se
corresponderán con el código 184.
121-122 Alfabético DECLARACIÓN COMPLEMENTARIA O SUSTITUTIVA
En el caso de segunda o posterior presentación de
declaraciones, deberá cumplimentarse obligatoriamente
uno de los siguientes campos:
121 DECLARACIÓN COMPLEMENTARIA: Se
consignará una "C" si la presentación de esta declaración
tiene por objeto incluir nuevos registros de tipo 2 que,
debiendo haber figurado en otra declaración del mismo
ejercicio presentada anteriormente, hubieran sido
completamente omitidas en la misma.
La modificación del contenido de datos declarados en otra
declaración del mismo ejercicio presentada anteriormente,
se realizará desde el servicio de consulta y modificación
de declaraciones informativas en la Sede Electrónica de
la Agencia Tributaria https://sede.agenciatributaria.gob.es
122 DECLARACIÓN SUSTITUTIVA: Se consignará
una "S" si la presentación tiene por objeto anular y sustituir
completamente a otra declaración anterior, del mismo
ejercicio. Una declaración sustitutiva sólo puede anular a
una única declaración anterior.
123-135 Numérico NÚMERO IDENTIFICATIVO DE LA DECLARACIÓN ANTERIOR
En el caso de que se haya consignado una "C" en el
campo "Declaración complementaria" o en caso de que se
haya consignado "S" en el campo "Declaración
sustitutiva", se consignará el número identificativo
correspondiente a la declaración a la que complementa o
sustituye.
En cualquier otro caso deberá rellenarse a CEROS
4
Ejercicio 2023

# Pag. 5

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
136-144 Numérico NÚMERO TOTAL DE REGISTROS DE SOCIOS, HEREDEROS,
COMUNEROS O PARTÍCIPES.
Se consignará el número total de registros de socios, herederos,
comuneros o partícipes declarados en el el registro de detalle de
tipo 2 (Registro de Socios, Herederos, Comuneros o Partícipes,
Tipo de Hoja, posición 76, igual a 'S').
145-146 Numérico ENTIDADES EN RÉGIMEN DE ATRIBUCIÓN DE RENTAS
CONSTITUIDAS EN ESPAÑA.
Numérico de 2 posiciones.
Este campo se subdivide en dos:
145 Numérico TIPO DE ENTIDAD: campo numérico.
Se hará constar el dígito numérico indicativo del tipo de
entidad, de acuerdo con la siguiente relación:
1- Sociedad civil.
2- Comunidad de bienes.
3- Herencia yacente.
4- Comunidad de propietarios.
5- Otros
146 Numérico ACTIVIDAD PRINCIPAL: Se hará constar
el dígito numérico que corresponda a la actividad principal
realizada por la entidad, de acuerdo con la siguiente
relación:
1- Actividad empresarial.
2- Actividad profesional.
3- Tenencia y administración de bienes inmuebles.
4- Tenencia y administración de valores o activos
financieros.
5- Otras.
147-155 Alfanumérico ENTIDADES EN RÉGIMEN DE ATRIBUCIÓN DE
RENTAS CONSTITUIDAS EN EL EXTRANJERO.
Este campo se subdivide en cuatro:
147 Numérico TIPO DE ENTIDAD:
Se hará constar el dígito numérico que corresponda a la
actividad principal realizada por la entidad, de acuerdo con
la siguiente relación:
1- Corporación, asociación o ente con personalidad
jurídica propia.
2- Corporación o ente independiente, pero sin
personalidad jurídica propia.
3- Conjunto unitario de bienes pertenecientes a dos o más
personas en común sin personalidad jurídica propia.
5
Ejercicio 2023

# Pag. 6

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
4- Otras
148 Alfabético OBJETO
Se hará constar la actividad o finalidad a la que
principalmente se dedica la entidad declarante, de
acuerdo con la siguiente relación:
A - Realización de una actividad de naturaleza
empresarial (actividad productiva, extractiva, industrial,
comercial, de distribución de bienes o productos, etc.).
B - Realización de una actividad de naturaleza profesional
(asesoramiento, consultoría, mediación, actividad
artística, etc.).
149-150 Alfabético CLAVE PAÍS:
Si la entidad en régimen de atribución de rentas está
constituida en el extranjero deberán consignarse como
clave país los dos caracteres alfabéticos correspondientes
al país o territorio en el que esté constituida, de acuerdo
con la relación de códigos de países que figura en la lista
desplegable.
151-155 PORCENTAJE DE RENTA ATRIBUIBLE A
MIEMBROS RESIDENTES: campo numérico. Consignará
el porcentaje correspondiente a la parte de renta que
resulte atribuible a los miembros residentes de la entidad.
Este campo se subdivide en otros dos:
151- 153 ENTERO: Numérico. Parte entera. Se
consignará la parte entera del porcentaje (si no tiene,
consignar CEROS).
154-155 DECIMAL: Numérico. Parte decimal. Se
consignará la parte decimal del porcentaje (si no tiene,
consignar CEROS).
156 Alfabético TRIBUTACIÓN EN RÉGIMEN DEL IMPUESTO SOBRE
SOCIEDADES.
Se consignará "X" si todos los miembros de la entidad en
régimen de atribución de rentas son contribuyentes del
Impuesto sobre Sociedades o contribuyentes por el
Impuesto sobre la Renta de no Residentes con
establecimiento permanente.
157-171 Numérico IMPORTE NETO DE LA CIFRA DE NEGOCIOS.
Campo numérico de 13 posiciones. Se hará constar sin
signo y sin coma decimal, el importe neto de la cifra de
negocios de la entidad en régimen de atribución de rentas.
Los importes deben consignarse en EUROS.
6
Ejercicio 2023

# Pag. 7

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Este campo se subdivide en dos:
157-169 Parte entera del importe, si no tiene contenido se
consignará a ceros.
170-171 Parte decimal del importe, si no tiene contenido
se consignará a ceros.
172-180 Alfanumérico N.I.F. DEL REPRESENTANTE.
Se consignará el N.I.F. del representante de la entidad en
régimen de atribución de rentas.
Este campo deberá estar ajustado a la derecha, siendo la
última posición el carácter de control y rellenando con
ceros las posiciones de la izquierda, de acuerdo con las
reglas previstas en el Real Decreto 1065/2007, de 27 de
julio, por el que se aprueba el Reglamento General de las
actuaciones y los procedimientos de gestión e inspección
tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos.
181-220 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL
REPRESENTANTE.
Si es una persona física se consignará el primer apellido,
un espacio, el segundo apellido, un espacio y el nombre
completo necesariamente en este orden.
Para personas jurídicas y entidades en régimen de
atribución de Rentas, se consignará la razón social
completa, sin anagrama.
En ningún caso podrá figurar en este campo un nombre
comercial.
221-487 ------------ BLANCOS
488-500 Alfanumérico SELLO ELECTRONICO
Campo reservado para el sello electrónico en
presentaciones individuales, que será cumplimentado
exclusivamente por los programas de la A.E.A.T. En
cualquier otro caso, y en presentaciones colectivas se
rellenará a blancos.
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de
blancos por la derecha, en mayúsculas, sin caracteres especiales y sin vocales
acentuadas, excepto que se especifique lo contrario en la descripción del campo.
7
Ejercicio 2023

# Pag. 8

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Registro de tipo 2. Registro de rentas de la
entidad
Se consignará un registro por cada clave o subclave de rendimientos, deducciones o
retenciones atribuibles para los que se haya consignado un importe y país.
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO
Constante '2'
2-4 Numérico MODELO DECLARACIÓN.
Constante '184'.
5-8 Numérico EJERCICIO.
Consignar lo contenido en estas mismas posiciones del
registro de tipo 1.
9-17 Alfanumérico N.I.F. DEL DECLARANTE.
Consignar lo contenido en estas mismas posiciones del
registro de tipo 1.
18-26 Alfanumérico N.I.F. ENTIDAD.
Consignar lo contenido en el campo "N.I.F. del Declarante",
posiciones 9-17 del registro de tipo 1
27-35 ---------- BLANCO
36-75 Alfanumérico DENOMINACIÓN O RAZÓN SOCIAL DEL DECLARANTE.
Consignar lo contenido en el campo "Denominación o razón
social del declarante", posiciones 18-57 del registro de tipo
1.
76 Alfabético TIPO DE HOJA
Constante "E".
77 Alfabético CLAVE
8
Ejercicio 2023

# Pag. 9

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Se consignará la clave alfabética que corresponda al
registro que se esté declarando, según la relación de claves
siguientes:
A. Rendimientos del capital mobiliario.
B. Identificación de la persona o entidad cesionaria de
los capitales propios. En el supuesto de que la
entidad en régimen de atribución de rentas obtenga
rentas de capital mobiliario derivadas de la cesión a
terceros de capitales propios y alguno de los
miembros de la entidad sea sujeto pasivo del
Impuesto sobre Sociedades o contribuyente por el
Impuesto sobre la Renta de no Residentes con
establecimiento permanente.
C. Rendimientos del capital inmobiliario.
D. Rendimientos de actividades económicas.
E. Rentas contabilizadas derivadas de la participación
en Instituciones de Inversión Colectiva.
Cumplimentarán este clave las entidades en
régimen de atribución de rentas que posean
acciones o participaciones en Instituciones de
Inversión Colectiva, y que cuenten entre sus
miembros con sujetos pasivos del Impuesto sobre
Sociedades o contribuyentes por el Impuesto sobre
la Renta de no Residentes con establecimiento
permanente. Estas rentas se consignarán
exclusivamente con esta clave en la declaración.
F. Ganancias y pérdidas patrimoniales no derivadas
de transmisiones de elementos patrimoniales. Con
esta clave se declarará el importe total de las
ganancias y pérdidas patrimoniales tanto
generadas en España como en el extranjero,
producidas en el ejercicio y no derivadas de
transmisiones de elementos patrimoniales. Se
consignarán las ganancias y pérdidas patrimoniales
que efectivamente se imputen en el ejercicio.
G. Ganancias y pérdidas patrimoniales derivadas de
transmisiones de elementos patrimoniales. Con
esta clave se declarará el importe total de las
ganancias y pérdidas patrimoniales, tanto
generadas en España como en el extranjero,
producidas en el ejercicio con ocasión de la
transmisión de elementos patrimoniales, incluidas,
en su caso, las derivadas de elementos
patrimoniales afectos a actividades económicas, Se
consignarán las ganancias y pérdidas patrimoniales
que efectivamente se imputen en el ejercicio.
H. Entidades que determinan la renta atribuible según
el Impuesto sobre Sociedades. Cuando todos los
miembros de la entidad en régimen de atribución de
rentas sean sujetos pasivos del Impuesto sobre
9
Ejercicio 2023

# Pag. 10

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Sociedades o contribuyentes por el Impuesto sobre
la Renta de no Residentes con establecimiento
permanente, la renta atribuible a los socios,
herederos, comuneros o partícipes se determinará
de acuerdo con las normas del Impuesto sobre
Sociedades.
I. Deducciones Ley Impuesto Renta Personas
Físicas. Se hará constar el importe que constituya
base de deducción por alguno de los conceptos
previstos en la Ley del IRPF.
J. Deducciones Ley Impuesto Sociedades. Deberán
cumplimentar esta clave las entidades en régimen
de atribución de rentas que tengan socios,
comuneros, herederos o partícipes que sean
contribuyentes del Impuesto sobre Sociedades o
del Impuesto sobre la Renta de no Residentes con
establecimiento permanente, incluyendo la base de
la deducción aplicable en virtud de lo dispuesto en
la Ley del Impuesto sobre Sociedades.
K. Retenciones e ingresos a cuenta soportados por la
entidad. Se consignarán los importes de las
retenciones e ingresos a cuenta del Impuesto sobre
la Renta de las Personas Físicas, del Impuesto
sobre Sociedades o del Impuesto sobre la Renta de
no Residentes que le hubieran sido practicadas a la
entidad en régimen de atribución de rentas, durante
el periodo objeto de declaración.
L. Exceso de rentas negativas obtenidas en países sin
convenio con España. Cuando el país en el que se
obtengan las rentas no tenga suscrito convenio con
España para evitar la doble imposición con cláusula
de intercambio de información, no se computarán
las rentas negativas que excedan de las positivas
siempre que procedan de la misma fuente y el
mismo país.
78-79 Alfanumérico SUBCLAVE.
Se consignará la subclave numérica o alfabética que
corresponda al registro que se esté declarando, según la
relación de claves siguientes:
Subclaves a utilizar en los registros correspondientes a la
clave A (Rendimientos del capital mobiliario):
01. Rendimientos obtenidos en España.
02. Rendimientos obtenidos en el extranjero
03. Reducciones aplicables
Subclaves a utilizar en los registros correspondientes a la
clave C (Rendimientos del capital inmobiliario):
01. Rendimientos obtenidos en España.
02. Rendimientos obtenidos en el extranjero
10
Ejercicio 2023

# Pag. 11

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
03. Reducciones aplicables
Subclaves a utilizar en los registros correspondientes a la
clave D (Rendimientos de actividades económicas):
01. Rendimientos obtenidos en España.
02. Rendimientos obtenidos en el extranjero
03. Importe del rendimiento con derecho a reducción.
Subclaves a utilizar en los registros correspondientes a la
clave F (Ganancias y pérdidas patrimoniales no derivadas
de transmisiones de elementos patrimoniales):
01. Ganancias generadas en España.
02. Pérdidas generadas en España.
03. Ganancias generadas en el extranjero.
04. Pérdidas generadas en el extranjero.
Subclaves a utilizar en los registros correspondientes a la
clave G (Ganancias y pérdidas patrimoniales derivadas de
la transmisión de elementos patrimoniales):
01. Ganancias sin reducción generadas en España.
02. Pérdidas sin reducción generadas en España.
03. Ganancias sin reducción generadas en el extranjero.
04. Pérdidas sin reducción generadas en el extranjero.
05. Ganancias con reducción, relativas a elementos no
afectos a actividades económicas generadas en España.
06 Ganancias con reducción, relativas a elementos no
afectos a actividades económicas generadas en el
extranjero.
07. Ganancias con reducción, relativas a elementos
afectos a actividades económicas generadas en España.
08. Ganancias con reducción, relativas a elementos
afectos a actividades económicas generadas en el
extranjero.
Subclaves a utilizar en los registros correspondientes a la
clave I (Deducciones Ley IRPF):
01. Por protección Patrimonio Español y Mundial
02. Por donativos, donaciones y aportaciones a
determinadas entidades
03. Por rentas obtenidas en Ceuta y Melilla
04. Deducciones en actividades económicas
05. Por doble imposición internacional (importe efectivo
satisfecho en el extranjero).
06. Por inversión en empresas de nueva o reciente creación.
Subclaves a utilizar en los registros correspondientes a la
clave J (Deducciones Ley Impuesto Sociedades):
01. Por doble imposición internacional (importe efectivo
satisfecho en el extranjero).
02. Deducciones con límite de cuota.
11
Ejercicio 2023

# Pag. 12

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
03. Deducción por donativos a entidades sin fines lucrativos.
04. Otras deducciones
Subclaves a utilizar en los registros correspondientes a la
clave K (Retenciones e ingresos a cuenta soportados por la
entidad):
01. Por rendimientos del capital mobiliario. Suma de
retenciones e ingresos a cuenta.
02. Por arrendamiento de inmuebles urbanos
(constituyan o no actividad económica) Suma de
retenciones e ingresos a cuenta.
03. Por rendimientos de actividades económicas
(excepto arrendamientos de inmuebles urbanos) Suma de
retenciones e ingresos a cuenta.
04. Por ganancias patrimoniales Suma de retenciones e
ingresos a cuenta.
05. Por otros conceptos. Suma de retenciones e ingresos a
cuenta.
Subclaves a utilizar en los registros correspondientes a la
clave L (Exceso de rentas negativas obtenidas en países
sin convenio con España):
A Rendimientos del capital mobiliario.
C Rendimientos del capital inmobiliario.
D Rendimientos de actividades económicas.
E Rentas contabilizadas derivadas de la participación
en Instituciones de Inversión Colectiva.
F Ganancias y pérdidas patrimoniales no derivadas de
transmisiones de elementos patrimoniales.
G Ganancias y pérdidas patrimoniales derivadas de
transmisiones de elementos patrimoniales
80 – 81 Alfabético CLAVE PAÍS
En este campo se consignarán los dos dígitos
correspondientes al país o territorio en el que hayan sido
obtenidos los rendimientos o las ganancias o pérdidas de
patrimonio, cuando:
- En el campo "Clave", posición 77 del registro de tipo
2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02". En este caso se indicará
en este campo el país o territorio en el que hayan sido
obtenidos los rendimientos del capital mobiliario.
- En el campo "Clave", posición 77 del registro de tipo
2 del registro entidad, se consigne "B". En este caso se
indicará en este campo el país o territorio en el que hayan
sido obtenidos los rendimientos del capital mobiliario.
- En el campo "Clave", posición 77 del registro de tipo
2 del registro entidad, se consigne "C" y en el campo
12
Ejercicio 2023

# Pag. 13

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02". En este caso se indicará
en este campo el país o territorio en el que hayan sido
obtenidos los rendimientos del capital inmobiliario.
- En el campo "Clave", posición 77 del registro de tipo
2 del registro entidad, se consigne "D" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02". En este caso se indicará
en este campo el país o territorio en el que hayan sido
obtenidos los rendimientos de las actividades económicas.
- En el campo "Clave", posición 77 del registro de tipo
2 del registro entidad, se consigne "F" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" ó "04". En este caso se
indicará en este campo el país o territorio en el que hayan
sido obtenidas las ganancias / pérdidas patrimoniales.
- En el campo "Clave", posición 77 del registro de tipo
2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03", "04", "06" ó "08". En este
caso se indicará en este campo el país o territorio en el que
hayan sido obtenidas las ganancias / pérdidas
patrimoniales.
- En el campo "Clave", posición 77 del registro de tipo
2 del registro entidad, se consigne "L" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "A", "C", "D", "E", "F" o "G" .
En este caso se indicará en este campo el país o territorio
en el que hayan sido obtenidas las rentas.
En el caso que para una misma clave y subclave, en su
caso, se hubiese obtenido un mismo tipo de rendimiento en
más de un país, se consignarán en tantos registros como
países en los que se haya obtenido.
En los demás casos este campo no tendrá contenido.
82 Numérico RÉGIMEN DETERMINACIÓN RENDIMIENTOS.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" se indicará en
este campo el régimen de determinación de los
rendimientos de actividades económicas de la entidad en
régimen de atribución de rentas, consignando para ello la
clave numérica que en cada caso corresponda, de las tres
siguientes:
1 Estimación directa modalidad normal
2 Estimación directa modalidad simplificada
3 Estimación objetiva (sólo si todos los miembros de la
entidad son personas físicas)
83 Numérico TIPO DE ACTIVIDAD.
13
Ejercicio 2023

# Pag. 14

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" se indicará en
este campo el tipo o naturaleza de la actividad cuyos datos
vayan a consignarse en este registro, consignando para ello
la clave que en cada caso corresponda de las cinco
siguientes:
1. Actividades empresariales de carácter mercantil
2. Actividades agrícolas y ganaderas
3. Otras actividades empresariales de carácter no mercantil
4. Actividades profesionales de carácter artístico o deportivo
5. Restantes actividades profesionales
En los demás casos este campo no tendrá contenido.
84-87 Numérico GRUPO O EPÍGRAFE IAE
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" se indicará en
este campo el grupo o el epígrafe en el que se encuentra
clasificada la actividad realizada a efectos del Impuesto
sobre Actividades Económicas (IAE).
En los demás casos este campo no tendrá contenido.
88-96 Alfanumérico NIF DE PERSONA O ENTIDAD CESIONARIA / NIF DE
LA INSTITUCIÓN DE INVERSIÓN COLECTIVA.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "B" se indicará en
este campo el número de identificación fiscal (NIF) de la
entidad cesionaria de los capitales propios.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "E" se indicará en
este campo el número de identificación fiscal (NIF) de la
institución de inversión colectiva.
En los demás casos este campo no tendrá contenido.
97-116 Alfanumérico DENOMINACIÓN O RAZÓN SOCIAL DEL CESIONARIO /
DENOMINACIÓN DE LA INSTITUCIÓN DE INVERSIÓN COLECTIVA.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "B" se indicará en
este campo la denominación completa, sin anagramas, de
la entidad cesionaria de los capitales propios.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "E" se indicará en
este campo la denominación, o razón social, de la
Institución de Inversión Colectiva de que se trate.
En los demás casos este campo no tendrá contenido.
117-124 Numérico FECHA ADQUISICIÓN.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "E" se indicará en
14
Ejercicio 2023

# Pag. 15

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
este campo la fecha de adquisición o suscripción de la
acción o participación. Este campo se subdivide en 3:
117-120 Numérico Año
121-122 Numérico Mes
123-124 Numérico Día
En los demás casos este campo no tendrá contenido.
125-137 Numérico VALOR LIQUIDATIVO / AJUSTES: AUMENTOS.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "E" se indicará en
este campo, sin signo y sin coma decimal, el valor
liquidativo de la acción o participación al día del cierre del
ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "H" se indicará en
este campo, sin signo y sin coma decimal, los importes que,
de acuerdo con lo dispuesto en la Ley del Impuesto sobre
Sociedades aprobado por Ley 27/2014, de 27 de
noviembre, y el resto de normas fiscales aplicables, deban
añadirse al resultado contable a efectos de determinar la
renta fiscal generada por la entidad en el ejercicio.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
125-135 Parte entera del importe, si no tiene contenido se
consignará a ceros.
136-137 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
138-150 Numérico VALOR ADQUISICIÓN, SUSCRIPCIÓN O CONTABLE /
AJUSTES: DISMINUCIONES.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "E" se indicará en
este campo, sin signo y sin coma decimal, el valor contable
de la acción o participación a la fecha de cierre del ejercicio
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "H" se indicará en
este campo, sin signo y sin coma decimal, los importes que,
de acuerdo con lo dispuesto en la Ley 27/2014, de 27 de
noviembre del Impuesto sobre Sociedades, y el resto de
normas fiscales aplicables, deban restarse del resultado
contable a efectos de determinar la renta fiscal generada
por la entidad en el ejercicio.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
138-148 Parte entera del importe, si no tiene contenido se
consignará a ceros.
149-150 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
15
Ejercicio 2023

# Pag. 16

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
En los demás casos este campo no tendrá contenido.
151-164 Alfanumérico INGRESOS ÍNTEGROS / IMP. RENDIMIENTOS DEVENGADOS
/ RESULTADO CONTABLE.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo el importe de los ingresos íntegros del capital
mobiliario obtenidos en España. Este importe incluirá los
rendimientos derivados de la cesión a terceros de capitales
propios que se hubieran devengado a favor de la entidad
en régimen de atribución de rentas en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo el importe de los ingresos íntegros del capital
mobiliario obtenidos en el extranjero. Este importe incluirá
los rendimientos derivados de la cesión a terceros de
capitales propios que se hubieran devengado a favor de la
entidad en régimen de atribución de rentas en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "B" se indicará en
este campo el importe de los rendimientos del capital
mobiliario derivados de la cesión a terceros de capitales
propios que se hubieran devengado a favor de la entidad
en régimen de atribución de rentas atribuibles a los
miembros de la entidad contribuyentes del Impuesto sobre
Sociedades o del Impuesto sobre la Renta de no
Residentes con establecimiento permanente.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "C" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo el importe de los ingresos íntegros del capital
inmobiliario obtenidos en España. Este importe incluirá los
rendimientos del capital inmobiliario que se hubieran
devengado a favor de la entidad en régimen de atribución
de rentas en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "C" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo el importe de los ingresos íntegros del capital
inmobiliario obtenidos en el extranjero. Este importe incluirá
los rendimientos del capital inmobiliario que se hubieran
devengado a favor de la entidad en régimen de atribución
de rentas en el ejercicio.
16
Ejercicio 2023

# Pag. 17

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo el importe de los ingresos íntegros obtenidos en
España por la entidad en régimen de atribución de rentas
referido a la actividad económica que corresponda. Si el
régimen de atribución de rentas es "Estimación Objetiva" no
se cumplimentará este campo.,.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo el importe de los ingresos íntegros obtenidos en el
extranjero por la entidad en régimen de atribución de rentas
referido a la actividad económica que corresponda.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "H" se indicará en
este campo el resultado contable del ejercicio que figure en
las cuentas anuales de la entidad, elaboradas de acuerdo
con las normas mercantiles y contables que sean de
aplicación.
151 SIGNO: Se cumplimentará este campo cuando el
importe de los ingresos íntegros, importe de los
rendimientos devengados o el resultado contable sea
negativo. En este caso se consignará una "N", en cualquier
otro caso el contenido de este campo será un espacio.
152–164 IMPORTE: Campo numérico de 13
posiciones. Se hará constar sin signo y sin coma decimal,
el importe de los ingresos íntegros, importe de los
rendimientos devengados o del resultado contable.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
152-162 Parte entera del importe, si no tiene contenido se
consignará a ceros.
163-164 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
165-176 Numérico GASTOS / EXCESO RENTAS NEGATIVAS
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo, sin signo y sin coma decimal, el importe de los
gastos fiscalmente deducibles de los rendimientos del
capital mobiliario obtenidos en España.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
17
Ejercicio 2023

# Pag. 18

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
registro entidad, se consigne "02" se indicará en este
campo, sin signo y sin coma decimal, el importe de los
gastos fiscalmente deducibles de los rendimientos del
capital mobiliario, obtenidos en el extranjero.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "C" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo, sin signo y sin coma decimal, consignará el importe
de los gastos fiscalmente deducibles de los rendimientos
íntegros del capital inmobiliario obtenidos en España.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "C" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo, sin signo y sin coma decimal, el importe de los
gastos fiscalmente deducibles de los rendimientos del
capital inmobiliario obtenidos en el extranjero.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01". Si el régimen de
atribución de rentas es "Estimación Objetiva" no se
cumplimentará este campo. En otro caso, se indicará en
este campo, sin signo y sin coma decimal, el importe de los
gastos fiscalmente deducibles de los rendimientos de
actividades económicas obtenidos en España.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo, sin signo y sin coma decimal, el importe de los
gastos fiscalmente deducibles de los rendimientos de
actividades económicas obtenidos en el extranjero.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "L" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "A", "C", "D", "E", "F" o "G" , se
indicará en este campo, sin signo y sin coma decimal, el
importe de las rentas negativas que excedan de las
positivas obtenidas en el mismo país y procedentes de la
misma fuente.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
165-174 Parte entera del importe, si no tiene contenido se
consignará a ceros.
175-176 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
18
Ejercicio 2023

# Pag. 19

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
177-190 Alfanumérico RENTA ATRIBUIBLE / RENDIMIENTO NETO
ATRIBUIBLERENDIMIENTO NETO ATRIBUIBLE PREVIO.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo el importe de la renta atribuible en concepto de
rendimientos de capital mobiliario obtenidos en España.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo el importe de la renta atribuible en concepto de
rendimientos del capital mobiliario obtenidos en un mismo
país.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "C" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo el importe de la renta atribuible en concepto de
rendimientos del capital inmobiliario obtenidos en España.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "C" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este el
importe de la renta atribuible en concepto de rendimientos
del capital inmobiliario obtenidos en un mismo país.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad se consigne "01", y en el campo •Régimen
de determinación de rendimientos", posición 82 del mismo
registro no se consigne la posición "2", se indicará en este
campo la diferencia entre los ingresos íntegros y los gastos
fiscalmente deducibles obtenidos en España. No obstante,
lo anterior, si el régimen de atribución de rentas es
"Estimación Objetiva" se indicará en este campo el importe
del rendimiento neto de la actividad en el período.
Cuando en el campo 'Clave', posición 77 del registro de tipo
2, registro de entidad, se consigne 'D' y en el campo
'Subclave', posiciones 78 a 79 del mismo registro se
consigne '01', y en el campo •Régimen de determinación de
rendimientos", posición 82 del mismo registro se consigne
la posición "2", se indicará en este campo la diferencia entre
los ingresos íntegros y los gastos fiscalmente deducibles
obtenidos en España (rendimiento neto atribuible previo).
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
19
Ejercicio 2023

# Pag. 20

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
campo la diferencia entre los ingresos íntegros y los gastos
fiscalmente deducibles obtenidos en un mismo país.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "E" se indicará en
este campo el importe de las rentas contabilizadas, o que
deban contabilizarse, derivadas de las acciones o
participaciones de las instituciones de inversión colectiva
atribuibles a los miembros de la entidad contribuyentes del
Impuesto sobre Sociedades y del Impuesto sobre la Renta
de no Residentes.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "H" se indicará en
este campo el importe de la renta obtenida por la entidad
que resulte atribuible a los miembros de la misma en el
ejercicio.
177 SIGNO: Se cumplimentará este campo cuando el
importe de la renta atribuible o del rendimiento neto
atribuible sea negativo. En este caso se consignará una "N",
en cualquier otro caso el contenido de este campo será un
espacio.
178–190 IMPORTE: Campo numérico de 13
posiciones. Se hará constar sin signo y sin coma decimal,
el importe de la renta atribuible o del rendimiento neto
atribuible.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
178-188 Parte entera del importe, si no tiene contenido se
consignará a ceros.
189-190 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
191-195 Numérico PORCENTAJE DE REDUCCIÓN.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo el porcentaje de reducción previsto en el artículo
26.2 de la Ley del IRPF aplicable sobre los rendimientos
netos del capital mobiliario cuando tengan un período de
generación superior a dos años, así como cuando hayan
sido obtenidos de forma notoriamente irregular en el tiempo.
Las reducciones sólo serán aplicables a los miembros de la
entidad en régimen de atribución de rentas que sean
contribuyentes del Impuesto sobre la Renta de las
Personas Físicas.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "C" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
20
Ejercicio 2023

# Pag. 21

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
campo el porcentaje de reducción que corresponda
conforme a lo previsto en el artículo 23 de la Ley del IRPF.
Las reducciones anteriores sólo serán aplicables a los
miembros de la entidad en régimen de atribución de rentas
que sean contribuyentes del Impuesto sobre la Renta de las
Personas Físicas
Este campo se subdivide en dos:
191-193 ENTERO: Numérico. Parte entera. Se
consignará la parte entera del porcentaje (si no tiene,
consignar CEROS).
194-195 DECIMAL: Numérico. Parte decimal. Se
consignará la parte decimal del porcentaje (si no tiene,
consignar CEROS).
En los demás casos este campo no tendrá contenido.
196-207 Alfanumérico RENTA ATRIBUIBLE CON DERECHO A REDUCCIÓN.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "A" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo, sin signo y sin coma decimal, el importe de la parte
de renta atribuible a la que resulte aplicable un mismo
porcentaje de reducción. Las reducciones sólo serán
aplicables a los miembros de la entidad en régimen de
atribución de rentas que sean contribuyentes del Impuesto
sobre la Renta de las Personas Físicas
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "C" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo, sin signo y sin coma decimal, el importe de la parte
de renta atribuible con derecho a reducción a la que resulte
aplicable un mismo porcentaje de reducción. Las
reducciones anteriores sólo serán aplicables a los
miembros de la entidad en régimen de atribución de rentas
que sean contribuyentes del Impuesto sobre la Renta de las
Personas Físicas
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "D" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo, sin signo y sin coma decimal, el importe de la parte
del rendimiento neto con derecho a reducción. En los
supuestos de rendimientos cuyo periodo de generación sea
superior a dos años o que hayan sido obtenidos de forma
notoriamente irregular en el tiempo será de aplicación la
reducción prevista en el art. 32 de la Ley del I.R.P.F
Los importes deben consignarse en EUROS.
21
Ejercicio 2023

# Pag. 22

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
196. SIGNO : campo alfabético que se cumplimentará
cuando el valor de la renta atribuible con derecho a
reducción sea menor que 0 (cero); en este caso se
consignará una "N". En cualquier otro caso el contenido del
campo será un espacio.
197-207 IMPORTE: Campo numérico de 13 posiciones. Se
hará constar sin signo y sin coma decimal, el importe de la
parte de renta atribuible.
Este campo se subdivide en dos:
197-205 Parte entera del importe, si no tiene contenido se
consignará a ceros.
206-207 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
208-220 Numérico GANANCIAS / PÉRDIDAS.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "F" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
ganancias patrimoniales obtenidas en España imputables
en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "F" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
pérdidas patrimoniales obtenidas en España imputables en
el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "F" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
ganancias patrimoniales obtenidas en el extranjero
imputables en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "F" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "04" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
pérdidas patrimoniales obtenidas en el extranjero
imputables en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
22
Ejercicio 2023

# Pag. 23

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
ganancias patrimoniales sin derecho a reducción obtenidas
en España imputables en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
pérdidas patrimoniales sin derecho a reducción obtenidas
en España imputables en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
ganancias patrimoniales sin derecho a reducción obtenidas
en el extranjero imputables en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "04" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
pérdidas patrimoniales sin derecho a reducción obtenidas
en el extranjero imputables en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "05" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
ganancias patrimoniales de elementos no afectos con
derecho a reducción obtenidas en España que proceda
integrar en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "06" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
ganancias patrimoniales de elementos no afectos con
derecho a reducción obtenidas en el extranjero que proceda
integrar en el ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "07" se indicará en este
campo, sin signo y sin coma decimal, la parte de la
ganancia patrimonial de elementos afectos con derecho a
reducción que proceda integrar en el ejercicio, en función
de la reducción (licencia municipal autotaxis en estimación
objetiva) que corresponda aplicar en cada caso según el
tiempo transcurrido desde la adquisición del activo fijo
inmaterial hasta su transmisión, conforme a lo previsto en
23
Ejercicio 2023

# Pag. 24

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
las normas del Impuesto sobre la Renta de las Personas
Físicas.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "G" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "08" se indicará en este
campo, sin signo y sin coma decimal, la parte de la
ganancia patrimonial de elementos afectos que proceda en
el ejercicio, en función de la reducción (licencia municipal
autotaxis en estimación objetiva) que corresponda aplicar
en cada caso según el tiempo transcurrido desde la
adquisición del activo fijo inmaterial hasta su transmisión,
conforme a lo previsto en las normas del Impuesto sobre la
Renta de las Personas Físicas.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
208-218 Parte entera del importe, si no tiene contenido se
consignará a ceros.
219-220 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
221-232 Numérico BASE DE LA DEDUCCIÓN / IMPORTE.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "I" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo, sin signo y sin coma decimal, la base de la
deducción, la cual estará formada por el importe de las
inversiones o gastos que se realicen para la protección y
difusión del Patrimonio Histórico Español y de las ciudades,
conjuntos y bienes declarados Patrimonio Mundial.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "I" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo, sin signo y sin coma decimal, la base de la
deducción, la cual estará formada por el importe
correspondiente al valor del donativo efectuado, calculado
de acuerdo con lo previsto en el artículo 68.3 de la Ley del
Impuesto sobre la Renta de las Personas Físicas.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "I" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo, sin signo y sin coma decimal, la base de la
deducción, la cual estará formada por el importe de las
rentas computadas que hayan sido obtenidas en Ceuta y
Melilla y que den derecho a deducción, de acuerdo con lo
24
Ejercicio 2023

# Pag. 25

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
previsto en el artículo 68.4 de la Ley del Impuesto sobre la
Renta de las Personas Físicas.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "I" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "04" se indicará en este
campo, sin signo y sin coma decimal, la base de la
deducción, la cual estará formada por el importe de las
inversiones o gastos efectuados en el ejercicio y que den
derecho a alguna de las deducciones previstas en el
artículo 68.2 de la Ley del IRPF.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "I" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "05" se indicará en este
campo, sin signo y sin coma decimal, siempre y cuando
entre las rentas de la entidad figuren rendimientos o
ganancias patrimoniales obtenidos y gravados en el
extranjero, se consignará el importe satisfecho por razón de
gravamen sobre dichas rentas, en los términos previstos en
el artículo 80 de la Ley del Impuesto sobre la Renta de las
Personas Físicas.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "J" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo, sin signo y sin coma decimal:
Cuando la entidad hubiera obtenido rentas gravadas en el
extranjero, consignará en este campo el importe satisfecho
por razón del gravamen sobre dichas rentas, en los
términos previstos en la normativa del Impuesto sobre
Sociedades.
Cuando entre las rentas de la entidad se computen
dividendos o participaciones en beneficios pagados por una
sociedad no residente, se hará constar en este campo el
importe del impuesto efectivamente pagado por la entidad
respecto de los beneficios con cargo a los cuales se abona
el dividendo, en la cuantía correspondiente a tales
dividendos.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "J" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo, sin signo y sin coma decimal, el importe total de las
cantidades invertidas o gastadas en la realización de
cualquiera de las actividades que generan derecho a
deducción en la cuota, de acuerdo con lo dispuesto en el
capítulo IV del título VI de la Ley del Impuesto sobre
Sociedades.
25
Ejercicio 2023

# Pag. 26

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "J" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
cantidades donadas a entidades sin fines lucrativos a las
que resulte de aplicación el régimen de incentivos fiscales
al mecenazgo previsto en el título III de la Ley 49/2002, de
23 de diciembre, de régimen fiscal de las entidades sin fines
lucrativos y de los incentivos fiscales al mecenazgo. En el
caso de donativos, donaciones o aportaciones en especie,
se hará constar el valor de lo donado o aportado,
determinado de acuerdo con las normas de valoración
previstas en dicha Ley.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "J" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "04" se indicará en este
campo, sin signo y sin coma decimal, el importe de las
inversiones o gastos que, al margen de los contemplados
en las claves anteriores, den derecho a deducción en la
cuota, de acuerdo con la normativa del Impuesto sobre
Sociedades o cualquier otra Ley aplicable.
.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
221-230 Parte entera del importe, si no tiene contenido se
consignará a ceros.
231-232 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
233-244 Numérico RETENCIONES E INGRESOS A CUENTA.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "K" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "01" se indicará en este
campo, sin signo y sin coma decimal, el importe total de las
retenciones e ingresos a cuenta que correspondan a los
rendimientos de capital mobiliario del ejercicio.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "K" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "02" se indicará en este
campo, sin signo y sin coma decimal, el importe total de las
retenciones e ingresos a cuenta que correspondan a los
rendimientos del ejercicio derivados del arrendamiento de
bienes inmuebles urbanos, con independencia de que
deban calificarse como procedentes del capital inmobiliario
o como derivados de actividades económicas.
26
Ejercicio 2023

# Pag. 27

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "K" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "03" se indicará en este
campo, sin signo y sin coma decimal, el importe total de las
retenciones e ingresos a cuenta que correspondan a los
rendimientos del ejercicio procedentes de actividades
económicas, con excepción de las retenciones e ingresos a
cuenta derivados del arrendamiento de bienes inmuebles
urbanos, cuyo importe se hará constar, en su caso, en la
casilla anterior.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "K" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "04" se indicará en este
campo, sin signo y sin coma decimal, el importe total de las
retenciones e ingresos a cuenta que correspondan a las
ganancias patrimoniales del ejercicio procedentes de la
transmisión o reembolso de acciones o participaciones en
Instituciones de Inversión Colectiva, así como a los premios
obtenidos por la participación en concursos, juegos, rifas o
combinaciones aleatorias.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2 del registro entidad, se consigne "K" y en el campo
"Subclave", posición 78 a 79 del registro de tipo 2 del
registro entidad, se consigne "05" se indicará en este
campo, sin signo y sin coma decimal, el importe total de las
retenciones e ingresos a cuenta correspondientes a
cualquier otro concepto distinto de los códigos anteriores.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
233-242 Parte entera del importe, si no tiene contenido se
consignará a ceros.
243-244 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
245 Numérico SITUACIÓN DEL INMUEBLE
Cuando en el campo "CLAVE", que ocupa la
posición 77 del registro de tipo 2, registro de entidad,
se consigne una "C", se consignará de entre las
siguientes claves la que corresponda al bien
inmueble del que provenga el rendimiento:
1. Inmueble con referencia catastral situado en
cualquier punto del territorio español, excepto País
Vasco y Navarra.
27
Ejercicio 2023

# Pag. 28

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
2. Inmueble situado en la Comunidad Autónoma del
País Vasco.
3. Inmueble situado en la Comunidad Foral de
Navarra.
4. Inmueble en cualquiera de las situaciones
anteriores, pero sin referencia catastral.
5. Inmueble situado en el extranjero.
246-265 Alfanumérico REFERENCIA CATASTRAL
Cuando en el campo "CLAVE", que ocupa la
posición 77 del registro de tipo 2, registro de entidad,
se consigne una "C", se consignará en este campo
la referencia catastral del inmueble del que
provengan los rendimientos del capital inmobiliario.
266-395 Numérico DETALLE DE GASTOS RENDIMIENTOS DE
ACTIVIDADES ECONÓMICAS
Cuando en el campo «CLAVE», que ocupa la
posición 77 del registro de tipo 2, registro de entidad,
se consigne «D» y en el campo «SUBCLAVE», que
ocupa las posiciones 78 y 79 del mismo registro, se
consigne «01» o «02», y el régimen de
determinación del rendimiento no sea el de
estimación objetiva, se consignará, en función de su
naturaleza, el importe de los gastos fiscalmente
deducibles de los rendimientos de actividades
económicas obtenidos en España o en el extranjero,
en los siguientes apartados:
266-277. GASTOS DE PERSONAL
Se consignará en este apartado el importe de los
sueldos y salarios, seguridad social a cargo de la
empresa y otros gastos de personal.
Este campo se subdivide en dos:
266-275 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
gastos de personal.
276-277 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
gastos de personal.
278-289. CONSUMOS DE EXPLOTACIÓN
28
Ejercicio 2023

# Pag. 29

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Se consignará en este apartado el importe
satisfecho en concepto de consumos de
explotación.
Este campo se subdivide en dos:
278-287 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
consumos de explotación.
288-289 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
consumos de explotación.
290-301. TRIBUTOS FISCALMENTE
DEDUCIBLES
Se consignará el importe de aquellos tributos que
sean fiscalmente deducibles.
Este campo se subdivide en dos:
290-299 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
tributos fiscalmente deducibles.
300-301 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
tributos fiscalmente deducibles.
302-313. ARRENDAMIENTOS Y CÁNONES
Se consignará el importe deducible de los gastos
originados en concepto de alquileres, cánones,
asistencia técnica, etc., por la cesión al
contribuyente de bienes o derechos que se hallen
afectos a la actividad, cuando no se adquiera la
titularidad de los mismos.
Este campo se subdivide en dos:
302-311 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
arrendamientos y cánones deducibles.
312-313 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
arrendamientos y cánones deducibles.
314-325. REPARACIONES Y CONSERVACIÓN
Se consignará el importe deducible de los gastos de
conservación y reparación del activo material afecto.
29
Ejercicio 2023

# Pag. 30

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Este campo se subdivide en dos:
314-323 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
gastos de reparación y conservación deducibles.
324-325 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
gastos de reparación y conservación deducibles.
326-337. SERVICIOS PROFESIONALES
INDEPENDIENTES
Se consignará el importe deducible de los gastos
satisfechos a los profesionales por los servicios
prestados a la actividad económica, tales como
honorarios de economistas, abogados, auditores,
notarios, etc., así como las comisiones de agentes
mediadores independientes.
Este campo se subdivide en dos:
326-335 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
gastos por servicios profesionales deducibles.
336-337 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
gastos por servicios profesionales deducibles.
338-349. SUMINISTROS
Se consignará el importe deducible de los gastos
correspondientes a electricidad y cualquier otro
abastecimiento (agua, gas, telefonía, internet, etc.)
que no tuviere la cualidad de almacenable.
Este campo se subdivide en dos:
338-347 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
gastos por suministros deducibles.
348-349 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
gastos por suministros deducibles.
350-361. GASTOS FINANCIEROS
Se consignará el importe deducible de los gastos
derivados de la utilización de recursos financieros
30
Ejercicio 2023

# Pag. 31

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
ajenos, para la financiación de las actividades de la
entidad o de sus elementos de activo.
Este campo se subdivide en dos:
350-359 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
gastos financieros deducibles.
360-361 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
gastos financieros deducibles.
362-373. AMORTIZACIONES
Se consignará el importe deducible de las
amortizaciones, de acuerdo con lo dispuesto en el
artículo 12 de la Ley 27/2014, de 27 de noviembre,
del Impuesto sobre Sociedades (LIS) y en los
artículos 3 a 7 de su Reglamento, aprobado por Real
Decreto 634/2015, de 10 de julio.
Este campo se subdivide en dos:
362-371 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
gastos derivados de la amortización.
372-373 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
gastos derivados de la amortización.
374-385. PROVISIONES
Cuando en el campo «CLAVE», que ocupa la
posición 77 del registro de tipo 2, registro de entidad,
se consigne «D» y en el campo «SUBCLAVE», que
ocupa las posiciones 78 y 79 del mismo registro, se
consigne «01» o «02», y el campo «RÉGIMEN DE
DETERMINACIÓN DE RENDIMIENTOS», que
ocupa la posición 82 del mismo registro, se consigne
«1», se consignará el importe deducible de las
provisiones fiscalmente deducibles de acuerdo con
lo dispuesto en el artículo 14 de la Ley 27/2014, de
27 de noviembre, del Impuesto sobre Sociedades.
Cuando en el campo «Clave», posición 77 del
registro de tipo 2, registro de entidad, se consigne
«D», en el campo «Subclave», posiciones 78 a 79
del mimo registro, se consigne «01» o «02», y en el
31
Ejercicio 2023

# Pag. 32

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
campo “Régimen de determinación de
rendimientos”, posición 82 del mismo registro se
consigne “2”, no se incluirá en este campo el importe
de las provisiones deducibles y los gastos de difícil
justificación a que se refiere el artículo 30.2ª del
Reglamento del Impuesto sobre la Renta de las
Personas Físicas, aprobado por Real Decreto
439/2007, de 30 de marzo.
Este campo se subdivide en dos:
374-383 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los
gastos por provisiones fiscalmente deducibles.
384-385 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los
gastos por provisiones fiscalmente deducibles.
386-395. OTROS GASTOS FISCALMENTE
DEDUCIBLES
Se consignará el importe del resto de gastos
fiscalmente deducibles por conceptos no incluidos
en otras posiciones de este campo (DETALLE DE
GASTOS).
Este campo se subdivide en dos:
386-393 Numérico. ENTERO:
Parte entera. Se consignará la parte entera del resto
de gastos fiscalmente deducibles.
394-395 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal del
resto de gastos fiscalmente deducibles.
396 Numérico CRITERIO DE COBROS Y PAGOS
Se consignará "X" si la entidad ha aplicado a las rentas
derivadas de las actividades económicas desarrolladas
en el ejercicio el criterio de imputación temporal previsto
en el artículo 11.4 de la Ley del Impuesto sobre
Sociedades o, en su caso, el criterio de cobros y pagos
previsto en el artículo 7.2 del Reglamento del IRPF.
En los demás casos, este campo se dejará en blanco.
32
Ejercicio 2023

# Pag. 33

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
397-497 Numérico DETALLE DE GASTOS / RENDIMIENTOS DEL CAPITAL
INMOBILIARIO
Cuando en el campo «CLAVE», que ocupa la posición 77 del
registro de tipo 2, registro de entidad, se consigne «C» y en el
campo «SUBCLAVE», que ocupa las posiciones 78 y 79 del mismo
registro, se consigne «01» o «02», se consignará, en función de
su naturaleza, el importe de los gastos fiscalmente deducibles de
los rendimientos de capital inmobiliario obtenidos en España o en
el extranjero, en los siguientes apartados:
397-407. INTERESES Y DEMÁS GASTOS DE FINANCIACIÓN
Se consignará en este apartado el importe de los intereses y
demás gastos de financiación del ejercicio de los capitales ajenos
invertidos en la adquisición o mejora del bien, derecho o facultad
de uso o disfrute, así como, en su caso, de los bienes cedidos con
el mismo
Este campo se subdivide en dos:
397-405 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los intereses y
demás gastos de financiación del ejercicio.
406-407 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los intereses y
demás gastos de financiación del ejercicio.
408-418. CONSERVACIÓN Y REPARACIÓN.
Se consignará en este apartado el importe de los gastos de
conservación y reparación del ejercicio de los bienes productores
de los rendimientos.
Este campo se subdivide en dos:
408-416 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de los gastos de
conservación y reparación del ejercicio.
417-418 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de los gastos de
conservación y reparación del ejercicio.
419-429. INTERESES/GASTOS DE REPARACIÓN Y
CONSERVACIÓN PENDIENTES.
Se consignará en este apartado el importe de los intereses, demás
gastos de financiación, gastos de conservación y reparación
pendientes de aplicación de los últimos cuatro ejercicios y
procedentes de los bienes productores de los rendimientos.
Este campo se subdivide en dos:
419-427 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de estos gastos
pendientes de aplicación de los últimos cuatro ejercicios.
33
Ejercicio 2023

# Pag. 34

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
428-429 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de estos gastos
pendientes de aplicación de los últimos cuatro ejercicios.
430-439. TRIBUTOS Y RECARGOS.
Se consignará en este apartado el importe de los tributos y
recargos no estatales, así como las tasas y recargos estatales
deducibles de los rendimientos (por ejemplo, el Impuesto sobre
Bienes Inmuebles, las tasas por gestión de residuos urbanos).
Este campo se subdivide en dos:
430-437 Numérico. ENTERO:
Parte entera. Se consignará la parte entera de la cuantía de los
tributos y recargos deducibles.
438-439 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal de la cuantía de los
tributos y recargos deducibles.
440-450.SALDOS DE DUDOSO COBRO.
Se consignará en este apartado el importe de los saldos de dudoso
cobro deducible de los rendimientos.
Este campo se subdivide en dos:
440-448 Numérico. ENTERO:
Parte entera. Se consignará la parte entera del importe de los
saldos de dudoso cobro.
449-450 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal del importe de los
saldos de dudoso cobro.
451-460. CANTIDADES DEVENGADAS POR TERCEROS
Se consignará en este apartado el importe deducible
correspondiente a cantidades devengadas por terceros en
contraprestación directa o indirecta o como consecuencia de
servicios personales, tales como los de administración, vigilancia,
portería, cuidado de jardines, etc.
Este campo se subdivide en dos:
451-458 Numérico. ENTERO:
Parte entera. Se consignará la parte entera del importe de las
cantidades devengadas por terceros.
459-460 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal del importe de las
cantidades devengadas por terceros.
461-470. PRIMAS DE SEGUROS
Se consignará en este apartado el importe deducible de las primas
de contratos de seguro, bien sea de responsabilidad civil, incendio,
robo, rotura de cristales u otros de naturaleza análoga sobre los
bienes o derechos productores de los rendimientos.
34
Ejercicio 2023

# Pag. 35

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Este campo se subdivide en dos:
461-468 Numérico. ENTERO:
Parte entera. Se consignará la parte entera del importe de las
primas de seguros.
469-470 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal del importe de las
primas de seguros.
471-480. AMORTIZACIÓN DEL INMUEBLE
Se consignará en este apartado el importe deducible
correspondiente a las cantidades destinadas a la amortización del
inmueble, siempre que respondan a su depreciación efectiva.
Este campo se subdivide en dos:
471-478 Numérico. ENTERO:
Parte entera. Se consignará la parte entera del importe de la
amortización.
479-480 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal del importe de la
amortización.
481-488. AMORTIZACIÓN DE BIENES MUEBLES
Se consignará en este apartado el importe deducible
correspondiente a las cantidades destinadas a la amortización de
los demás bienes cedidos con el inmueble, siempre que
respondan a su depreciación efectiva.
Este campo se subdivide en dos:
481-486 Numérico. ENTERO:
Parte entera. Se consignará la parte entera del importe de la
amortización.
487-488 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal del importe de la
amortización.
489-497. OTROS GASTOS DEDUCIBLES
Se consignará en este apartado el importe del resto de gastos
deducibles necesarios para la obtención de los correspondientes
rendimientos, no contemplados específicamente en otros campos.
Este campo se subdivide en dos:
489-495 Numérico. ENTERO:
Parte entera. Se consignará la parte entera del importe del resto
de gastos deducibles necesarios para la obtención de los
correspondientes rendimientos.
496-497 Numérico. DECIMAL:
Parte decimal. Se consignará la parte decimal del importe resto de
gastos deducibles necesarios para la obtención de los
correspondientes rendimientos.
35
Ejercicio 2023

# Pag. 36

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
498-500 Numérico NÚMERO DE DÍAS DE ARRENDAMIENTO O CESIÓN DE USO
Y DISFRUTE
Cuando en el campo «CLAVE», que ocupa la posición 77 del
registro de tipo 2, registro de entidad, se consigne «C» y en el
campo «SUBCLAVE», que ocupa las posiciones 78 y 79 del mismo
registro, se consigne «01» o «02», se consignará el número de
días del ejercicio en los que el inmueble de los que proceden los
rendimientos de capital inmobiliario ha estado arrendado o cedido
su uso y disfrute.
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a
blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la
izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de
blancos por la derecha, en mayúsculas, sin caracteres especiales y sin vocales
acentuadas, excepto que se especifique lo contrario en la descripción del campo.
Registro de tipo 2. Registro de socio, heredero,
comunero o partícipe
Se consignará un registro por cada clave o subclave de rendimientos, deducciones o
retenciones atribuibles para los que se haya consignado un importe y país.
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO.
Constante '2'
2-4 Numérico MODELO DECLARACIÓN.
Constante '184'.
5-8 Numérico EJERCICIO.
Consignar lo contenido en estas mismas posiciones del
registro de tipo 1.
9-17 Alfanumérico NIF DEL DECLARANTE.
Consignar lo contenido en estas mismas posiciones del
registro de tipo 1.
18-26 Alfanumérico NIF DEL MIEMBRO.
Se consignará el número de identificación fiscal
correspondiente al socio, heredero, comunero o partícipe
miembro de la entidad en régimen de atribución de rentas
36
Ejercicio 2023

# Pag. 37

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Si es una persona física se consignará el NIF del declarado
de acuerdo con las reglas previstas en el Real Decreto
1065/2007, de 27 de julio, por el que se aprueba el
Reglamento General de las actuaciones y los
procedimientos de gestión e inspección tributaria y de
desarrollo de las normas comunes de los procedimientos de
aplicación de los tributos.
Si el declarado es una persona jurídica o una entidad en
régimen de atribución de rentas (Comunidad de bienes,
Sociedad civil, herencia yacente, etc.), se consignará el
número de identificación fiscal correspondiente a la misma.
Para la identificación de los menores de 14 años en sus
relaciones de naturaleza o con trascendencia tributaria
habrán de figurar tanto los datos de la persona menor de 14
años, incluido su número de identificación fiscal, como los
de su representante legal.
Este campo deberá estar ajustado a la derecha, siendo la
última posición el carácter de control y rellenando con ceros
las posiciones a la izquierda.
27-35 Alfanumérico NIF DEL REPRESENTANTE FISCAL.
En el supuesto de miembros de la entidad menores de 14
años se cumplimentará la casilla "NIF representante fiscal",
en la que se hará constar el NIF de la persona que ostente
en cada caso la representación legal del menor (padre,
madre o tutor).
En el caso de que el miembro de la entidad en régimen de
atribución de rentas no sea residente en territorio español,
se deberá consignar, en su caso, el número de
identificación fiscal de quien ostente la representación fiscal
del mismo de acuerdo con lo establecido en el artículo 10
de la Ley del Impuesto sobre la Renta de no Residentes y
Normas Tributarias.
En cualquier otro caso el contenido de este campo se
rellenará a espacios.
Este campo deberá estar ajustado a la derecha, siendo la
última posición el carácter de control y rellenando con ceros
las posiciones a la izquierda.
36-75 Alfanumérico APELLIDOS Y NOMBRE, RAZÓN SOCIAL O
DENOMINACIÓN DEL MIEMBRO.
a). Para personas físicas se consignará el primer
apellido, un espacio, el segundo apellido, un espacio y el
nombre completo, necesariamente en este mismo orden. Si
el declarado es menor de 14 años, se consignarán en este
campo los apellidos y nombre del menor de 14 años.
b). Tratándose de personas jurídicas y entidades en
régimen de atribución de rentas, se consignará la razón
37
Ejercicio 2023

# Pag. 38

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
social o denominación completa de la entidad, sin
anagramas.
76 Alfabético TIPO DE HOJA.
Constante "S".
77-78 Numérico CÓDIGO PROVINCIA.
Con carácter general, se consignarán los dos dígitos
numéricos que correspondan a la provincia o, en su caso,
ciudad autónoma, del domicilio del declarado, según la
siguiente relación:
ALBACETE 02 JAÉN 23
ALICANTE 03 LEÓN 24
ALMERIA 04 LLEIDA 25
ARABA/ÁLAVA 01 LUGO 27
ASTURIAS 33 MADRID 28
ÁVILA 05 MÁLAGA 29
BADAJOZ 06 MELILLA 52
BARCELONA 08 MURCIA 30
BIZKAIA 48 NAVARRA 31
BURGOS 09 OURENSE 32
CÁCERES 10 PALENCIA 34
CÁDIZ 11 PALMAS, LAS 35
CANTABRIA 39 PONTEVEDRA 36
CASTELLÓN 12 RIOJA, LA 26
CEUTA 51 SALAMANCA 37
CIUDAD REAL 13 S.C.TENERIFE 38
CÓRDOBA 14 SEGOVIA 40
CORUÑA, A 15 SEVILLA 41
CUENCA 16 SORIA 42
GIPUZKOA 20 TARRAGONA 43
GIRONA 17 TERUEL 44
GRANADA 18 TOLEDO 45
GUADALAJARA 19 VALENCIA 46
HUELVA 21 VALLADOLID 47
HUESCA 22 ZAMORA 49
ILLES BALEARES 07 ZARAGOZA 50
En el caso de no residentes que no operen en territorio
español mediante establecimiento permanente, se
consignará 99.
79 - 80 Alfabético CLAVE PAÍS.
En el caso de no residentes sin establecimiento
permanente, se consignará XX, siendo XX el Código del
país de residencia del declarado, de acuerdo con los
códigos alfabéticos de países y territorios que figuran en la
38
Ejercicio 2023

# Pag. 39

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Orden EHA/3496/2011, de 15 de diciembre, en su anexo II
(BOE 26/12/2011)
En el caso de residentes o de no residentes que operen en
territorio español mediante establecimiento permanente, se
consignará BLANCOS en las posiciones 79 a 80.
81 Numérico CLAVE TIPO DE PARTÍCIPE.
Se consignará la clave que proceda de las tres siguientes:
1.- Residente.
2.- No residente sin establecimiento permanente.
3.- No residente con establecimiento permanente.
82 Alfabético MIEMBRO A 31 DICIEMBRE.
Si el miembro de la entidad en régimen de atribución de
rentas sigue siendo miembro de la entidad a 31 de
diciembre marcará una "X" en este campo.
83-85 Numérico NÚMERO DÍAS MIEMBRO.
Se consignará el número de días del año en que ha sido
miembro de la entidad en la casilla correspondiente.
86-92 Numérico PORCENTAJE DE PARTICIPACIÓN.
Se consignará el porcentaje de participación que
corresponda al socio, heredero, comunero o partícipe en la
entidad. Dicho porcentaje, cuando no sea un número
entero, se expresará con cuatro decimales.
Este campo se subdivide en otros dos:
86-88 ENTERO: Numérico. Parte entera. Se consignará la
parte entera del porcentaje (si no tiene, consignar CEROS).
89-92 DECIMAL: Numérico. Parte decimal. Se consignará
la parte decimal del porcentaje (si no tiene, consignar
CEROS).
93 Alfabético CLAVE.
Se consignará la clave alfabética que corresponda al
registro que se esté declarando, según la relación de claves
siguientes:
A Rendimientos del capital mobiliario.
C Rendimientos del capital inmobiliario.
D Rendimientos de actividades económicas.
E Rentas contabilizadas de participaciones de
Instituciones de Inversión Colectiva.
F Ganancias y pérdidas no derivadas de la transmisión
de elementos patrimoniales.
G Ganancias y pérdidas patrimoniales derivadas de la
transmisión de elementos patrimoniales
I Deducciones Ley del IRPF
J Deducciones Ley del Impuesto sobre Sociedades.
39
Ejercicio 2023

# Pag. 40

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
K Retenciones e ingresos a cuenta.
94-95 Numérico SUBCLAVE.
Se consignará la subclave numérica que corresponda al
registro que se esté declarando, según la relación de claves
siguientes:
Subclaves a utilizar en los registros correspondientes
a la clave A (Rendimientos de capital mobiliario):
01 Rendimientos del capital mobiliario previstos en los
apartados 1, 2 y 3 del artículo 25 de la LIRPF.
02 Rendimientos del capital mobiliario previstos en el
apartado 4 del artículo 25 de la LIRPF.
Subclaves a utilizar en los registros correspondientes
a la clave F (Ganancias y pérdidas patrimoniales no
derivadas de transmisiones de elementos
patrimoniales):
01. Ganancias.
02. Pérdidas.
Subclaves a utilizar en los registros correspondientes
a la clave G (Ganancias y pérdidas patrimoniales
derivadas de transmisiones de elementos
patrimoniales):
01. Ganancias.
02. Pérdidas.
Subclaves a utilizar en los registros correspondientes
a la clave I (Deducciones Ley IRPF):
01. Por protección Patrimonio Español y
Mundial.
02. Por donativos, donaciones y
aportaciones a determinadas entidades (Ley IRPF)
03. Por rentas obtenidas en Ceuta y Melilla.
04. Deducciones en actividades
económicas.
05. Deducción por doble imposición
internacional.
06. Por inversión en empresas de nueva o
reciente creación
Subclaves a utilizar en los registros correspondientes
a la clave J (Deducciones Ley Impuesto Sociedades):
01. Deducciones por doble imposición internacional.
02. Deducciones con límite sobre cuota.
03. Deducción por donativos a entidades sin fines
lucrativos
04. Otras deducciones. (Ley Impuesto Sociedades).
40
Ejercicio 2023

# Pag. 41

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Subclaves a utilizar en los registros correspondientes
a la clave K (Retenciones e ingresos a cuenta):
01 Por rendimientos del capital mobiliario
02 Por arrendamiento de inmuebles urbanos
03 Por rendimientos de actividades económicas
04 Por ganancias patrimoniales
05 Por otros conceptos
96-108 Alfanumérico IMPORTE (RENDIMIENTO / RETENCIÓN /
DEDUCCIÓN).
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "A" se indicará en este campo el importe de la
renta atribuible (ingresos menos, en su caso, gastos
deducibles o en el caso del régimen de "Estimación
Objetiva" el importe del rendimiento neto) al miembro de la
entidad en régimen de atribución de rentas en concepto de
rendimientos del capital mobiliario.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "C" se indicará en este campo el importe de la
renta atribuible (ingresos menos, en su caso, gastos
deducibles o en el caso del régimen de "Estimación
Objetiva" el importe del rendimiento neto) al miembro de la
entidad en régimen de atribución de rentas en concepto de
rendimientos del capital inmobiliario.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "D" se indicará en este campo el importe de la
renta atribuible (ingresos menos, en su caso, gastos
deducibles o en el caso del régimen de "Estimación
Objetiva" el importe del rendimiento neto) al miembro de la
entidad en régimen de atribución de rentas en concepto de
rendimientos de actividades económicas. No obstante lo
anterior, cuando en el campo «Clave», posición 77 del
registro de tipo 2, registro de entidad, se consigne «D», en
el campo «Subclave», posiciones 78 a 79 del mimo registro,
se consigne «01» o «02», y en el campo "Régimen de
determinación de rendimientos", posición 82 del mismo
registro se consigne "2", se indicará en este campo el
importe del rendimiento atribuible (rendimiento neto
atribuible previo) minorado en el importe de las provisiones
deducibles y los gastos de difícil justificación consignados
en el campo "Provisiones deducibles y gastos de difícil
justificación", posiciones 160 a 171 del registro de tipo 2,
registro de socio, heredero, comunero y partícipe.
41
Ejercicio 2023

# Pag. 42

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "E" se indicará en este campo el importe de la
renta atribuible al miembro de la entidad en concepto de
renta contabilizada derivada de la participación en
Instituciones de Inversión Colectiva, teniendo en cuenta que
dicha renta sólo es atribuible a los miembros de la entidad
contribuyentes del Impuesto sobre Sociedades o por el
Impuesto sobre la Renta de no Residentes con
establecimiento permanente.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "F" y en el campo "Subclave", posición 94 a 95 del
registro de tipo 2 del registro socio, heredero, comunero y
partícipe, se consigne "01" se indicará en este campo el
importe de las ganancias netas atribuibles al miembro de la
entidad en régimen de atribución de rentas, no derivadas de
transmisiones de elementos patrimoniales.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "F" y en el campo "Subclave", posición 94 a 95 del
registro de tipo 2 del registro socio, heredero, comunero y
partícipe, se consigne "02" se indicará en este campo el
importe de las pérdidas netas atribuibles al miembro de la
entidad en régimen de atribución de rentas, no derivadas de
transmisiones de elementos patrimoniales.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "G" y en el campo "Subclave", posición 94 a 95
del registro de tipo 2 del registro socio, heredero, comunero
y partícipe, se consigne "01" se indicará en este campo el
importe de las ganancias netas atribuibles al miembro de la
entidad en régimen de atribución de rentas derivadas de
transmisiones de elementos patrimoniales.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "G" y en el campo "Subclave", posición 94 a 95
del registro de tipo 2 del registro socio, heredero, comunero
y partícipe, se consigne "02" se indicará en este campo el
importe de las pérdidas netas atribuibles al miembro de la
entidad en régimen de atribución de rentas derivadas de
transmisiones de elementos patrimoniales.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "I" y en el campo "Subclave", posición 94 a 95 del
42
Ejercicio 2023

# Pag. 43

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
registro de tipo 2 del registro socio, heredero, comunero y
partícipe, se consigne "01", "02", "03", "04", 05" o "06", se
indicará en este campo las bases o los importes de
deducción que resulten atribuibles al socio, heredero,
comunero o partícipe.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "J" y en el campo "Subclave", posición 94 a 95 del
registro de tipo 2 del registro socio, heredero, comunero y
partícipe, se consigne "01", "02", "03", o "04”, se indicará en
este campo las bases o los importes de deducción que
resulten atribuibles al socio, heredero, comunero o
partícipe.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "K" y en el campo "Subclave", posición 94 a 95 del
registro de tipo 2 del registro socio, heredero, comunero y
partícipe, se consigne "01", "02", "03", "04”, ó "05", se
indicará en este campo los importes de las retenciones o
ingresos a cuenta que resulten atribuibles al socio,
heredero, comunero o partícipe.
96 SIGNO: Se cumplimentará este campo cuando el
importe del rendimiento sea negativo. En este caso
se consignará una "N", en cualquier otro caso el
contenido de este campo será un espacio.
97-108 IMPORTE: Campo numérico de 13 posiciones. Se
hará constar sin signo y sin coma decimal, el
importe de los rendimientos, de las bases o los
importes de deducción y de las retenciones e
ingresos a cuenta.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
97-106 Parte entera del importe, si no tiene
contenido se consignará a ceros.
107-108 Parte decimal del importe, si no tiene
contenido se consignará a ceros.
En los demás casos este campo no tendrá contenido.
109-119 Numérico REDUCCIÓN.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "A" y en el campo 'Subclave', posiciones 94 a 95
del mismo registro se consigne '02', se indicará en este
campo, de haberse incluido entre los rendimientos del
capital mobiliario algún rendimiento al que resulte aplicable
43
Ejercicio 2023

# Pag. 44

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
la reducción prevista en el artículo 24.2 de la Ley IRPF, y
sólo para los miembros que sean contribuyentes por el
Impuesto, el importe de la reducción que corresponda.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "C" se indicará en este campo, de haberse
incluido entre los rendimientos del capital inmobiliario algún
rendimiento al que resulte aplicable cualquiera de las
reducciones previstas en los artículos 23.2 y 23.3 de la Ley
IRPF, y sólo para los miembros que sean contribuyentes
por el Impuesto, el importe de la reducción o reducciones
que corresponda.
Cuando en el campo "Clave", posición 93 del registro de
tipo 2 del registro socio, heredero, comunero y partícipe, se
consigne "D" se indicará en este campo, de haberse
incluido entre los rendimientos de actividades económicas
atribuidos al miembro de la entidad algún rendimiento al que
resulte aplicable la reducción prevista en el artículo 32 de la
Ley IRPF, y sólo para los miembros que sean
contribuyentes por el Impuesto, el importe de la reducción
que corresponda.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
109-117 Parte entera del importe, si no tiene contenido se
consignará a ceros.
118-119 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos este campo no tendrá contenido.
120-159 Alfanumérico DOMICILIO FISCAL DEL MIEMBRO DE LA ENTIDAD.
Se consignará el domicilio fiscal correspondiente al
miembro de la entidad.
160-171 Numérico PROVISIONES DEDUCIBLES Y GASTOS DE DIFÍCIL
JUSTIFICACIÓN.
Cuando en el campo "Clave", posición 77 del registro de
tipo 2, registro de entidad, se consigne "D" y en la posición
82 ("RÉGIMEN DE DETERMINACIÓN DE
RENDIMIENTOS") del registro de tipo 2, registro de
entidad, se consigne la clave "2", se cumplimentará el
importe correspondiente al socio o partícipe de las
44
Ejercicio 2023

# Pag. 45

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
provisiones deducibles y los gastos de difícil justificación a
que se refiere el artículo 30. 2ª del Reglamento del IRPF.
A estos efectos, se consignará en este campo el resultado
de aplicar el porcentaje del 5 por 100 al importe del
rendimiento neto de la entidad, excluido este concepto de
gasto, y se multiplicará dicho resultado por el porcentaje de
participación en la entidad, con un límite máximo de 2.000
euros para cada uno de los socios o partícipes.
172 Numérico NATURALEZA DEL INMUEBLE.
Cuando en el campo «CLAVE», que ocupa la posición 93
del registro de tipo 2, registro de socio, heredero, comunero
o partícipe, se consigne una «C», se cumplimentará de
entre las siguientes claves la que corresponda al bien
inmueble del que provenga el rendimiento:
1. Inmueble urbano
2. Inmueble rústico.
173 Numérico SITUACIÓN DEL INMUEBLE.
Cuando en el campo «CLAVE», que ocupa la posición 93
del registro de tipo 2, registro de socio, heredero, comunero
o partícipe, se consigne una «C», se cumplimentará de
entre las siguientes claves la que corresponda al bien
inmueble del que provenga el rendimiento:
1. Inmueble con referencia catastral situado en cualquier
punto del territorio español, excepto País Vasco y Navarra.
2. Inmueble situado en la Comunidad Autónoma del País
Vasco.
3. Inmueble situado en la Comunidad Foral de Navarra.
4. Inmueble en cualquiera de las situaciones anteriores,
pero sin referencia catastral.
5. Inmueble situado en el extranjero.
174-193 Alfanumérico REFERENCIA CATASTRAL.
Cuando en el campo «CLAVE», que ocupa la posición 93
del registro de tipo 2, registro de socio, heredero, comunero
o partícipe, se consigne una «C», y en el campo
«SITUACIÓN DEL INMUEBLE», que ocupa la posición 173
del registro de tipo 2, registro de socio, heredero, comunero
o partícipe, se consigne "1", "2" o "3", se cumplimentará en
este campo la referencia catastral del inmueble del que
provengan los rendimientos del capital inmobiliario.
194 Alfabético CLAVE DE DECLARADO.
45
Ejercicio 2023

# Pag. 46

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
Cuando en el campo "Situación del inmueble", posición 173
del registro de tipo 2, registro de socio, heredero, comunero
o partícipe tenga contenido, se consignará la clave que
corresponda respecto de la titularidad del inmueble
correspondiente al socio, heredero, comunero o partícipe:
N Nudo propietario.
T Titular.
U Usufructuario.
O Otro derecho real.
195-199 Numérico PORCENTAJE DE TITULARIDAD DEL INMUEBLE.
Cuando en el campo «CLAVE», que ocupa la posición 93
del registro de tipo 2, registro de socio, heredero, comunero
o partícipe, se consigne una «C»,, se consignará el
porcentaje de titularidad o de derechos reales de uso en el
inmueble del socio, heredero, comunero o partícipe
Se subdivide en dos campos:
195-197: Figurará la parte entera del porcentaje (si no tiene,
configurar a ceros).
198-199: Figurará la parte decimal del porcentaje (si no
tiene, configurar a ceros).
200-202 Numérico NÚMERO DE DÍAS DE ARRENDAMIENTO O CESIÓN
DE USO Y DISFRUTE DEL INMUEBLE
Cuando en el campo “CLAVE” que ocupa la posición 93,
del registro de tipo 2, registro de socio, heredero,
comunero y partícipe, se consigne la letra “C”, se
consignará el número de días del ejercicio en los que el
inmueble del que proceden los rendimientos de capital
inmobiliario, ha estado arrendado o cedido su uso y
disfrute.
203-215 Numérico RENDIMIENTO NETO PREVIO DE ACTIVIDADES
ECONÓMICAS EN ESTIMACIÓN OBJETIVA
(EXCEPTO AGRÍCOLAS, GANADERAS Y
FORESTALES)
Cuando en el campo "Clave", posición 77, del registro de
tipo 2 del registro de rentas de la entidad, se consigne "D" y
en el campo “Régimen de determinación de rendimientos",
posición 82, del mismo tipo de registro se consigne "3", se
46
Ejercicio 2023

# Pag. 47

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
indicará en este campo el importe del rendimiento neto
previo de las actividades económicas (excepto agrícolas,
ganaderas y forestales) atribuible a cada miembro de la
entidad en régimen de atribución de rentas.
Campo numérico de 13 posiciones. Se hará constar sin
coma decimal, el importe en EUROS del rendimiento neto
previo.
A estos efectos, el rendimiento neto previo se determinará
de acuerdo con las instrucciones de la Orden ministerial en
cuya virtud se fijen los signos, índices o módulos aplicables
en el ejercicio al que se refiere la declaración informativa.
Este campo se subdivide en dos:
203-213 Parte entera del importe, si no tiene contenido se
consignará a ceros.
214-215 Parte decimal del importe, si no tiene contenido se
consignará a ceros.
En los demás casos, este campo no tendrá contenido.
216-229 Numérico RENDIMIENTO NETO MINORADO DE ACTIVIDADES
AGRÍCOLAS, GANADERAS Y FORESTALES EN
ESTIMACIÓN OBJETIVA
Cuando en el campo "Clave", posición 77, del registro de
tipo 2 del registro de rentas de la entidad, se consigne "D" y
en el campo “Régimen de determinación de rendimientos",
posición 82, del mismo tipo de registro se consigne "3", se
indicará en este campo el importe del rendimiento neto
minorado de las actividades agrícolas, ganaderas y
forestales atribuible a cada miembro de la entidad en
régimen de atribución de rentas.
A estos efectos, el rendimiento neto minorado se
determinará de acuerdo con las instrucciones de la Orden
ministerial en cuya virtud se fijen los signos, índices o
módulos aplicables en el ejercicio al que se refiere la
declaración informativa.
Este campo se subdivide en dos:
216 SIGNO: Se cumplimentará este subcampo cuando el
importe del rendimiento neto minorado sea negativo. En
este caso se consignará una "N", en cualquier otro caso el
contenido de este campo será un espacio.
47
Ejercicio 2023

# Pag. 48

Modelo 184.
Declaración Informativa. Entidades en régimen de atribución de
rentas. Declaración anual.
217-229 IMPORTE: Subcampo numérico de 13 posiciones.
Se hará constar sin signo y sin coma decimal, el importe en
EUROS del rendimiento neto minorado.
Este subcampo se subdivide en dos:
217-227 Parte entera del importe, si no tiene
contenido se consignará a ceros.
228-229 Parte decimal del importe, si no tiene
contenido se consignará a ceros.
En los demás casos, este campo no tendrá contenido.
230-500 ---- BLANCOS
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a
blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la
izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de
blancos por la derecha, en mayúsculas, sin caracteres especiales y sin vocales
acentuadas, excepto que se especifique lo contrario en la descripción del campo.
48
Ejercicio 2023