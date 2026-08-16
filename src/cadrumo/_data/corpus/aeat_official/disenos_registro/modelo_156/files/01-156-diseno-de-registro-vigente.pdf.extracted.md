# Pag. 1

ANEXO II
DISEÑOS FÍSICOS Y LÓGICOS A LOS QUE DEBE AJUSTARSE EL SOPORTE DIRECTAMENTE LEGIBLE
POR ORDENADOR Y LA TRANSMISIÓN TELEMÁTICA POR TELEPROCESO DEL MODELO 156
Ejercicio 2021

# Pag. 2

Los soportes directamente legibles por ordenador para la presentación de la declaración informativa anual,
modelo 156, habrán de cumplir las siguientes características:
A) CARACTERÍSTICAS DE LOS SOPORTES MAGNÉTICOS
Cartucho Magnético
Tipo: IBM-3480 o compatible
Pistas: 18 ó 36
Longitud: standard o extendida (3490E)
Compresión: Opcional (standard IDRC)
Código: EBCDIC, en mayúsculas.
Etiquetas: Sin etiquetas.
Marcas: En principio y fin de cinta.
Registros de: 250 posiciones.
Factor de bloqueo: 10
Disquetes
De 3 1/2" doble cara. Doble densidad (720 KB) Sistema operativo MS-DOS y compatibles.
De 3 1/2" doble cara. Alta densidad (1.44 MB) Sistema operativo MS-DOS y compatibles.
Código ASCII en mayúsculas sin caracteres de control o tabulación.
Registros de 250 posiciones.
Los disquetes de 3 1/2" deberán llevar un sólo fichero, cuyo nombre será AFIxxxx , siendo xxxx las cuatro
cifras del ejercicio fiscal al que corresponde la declaración, conteniendo este único fichero los diferentes tipos de
registros y en el orden que se menciona en el apartado B).
Si el fichero ocupa más de un disquete, deberá particionarse en tantos ficheros como sea necesario. Cada uno de
los ficheros parciales tendrá la denominación AFIxxxx.NNN (NNN=001,002, ), siendo xxxx las cuatro cifras del
ejercicio fiscal al que corresponde la declaración y NNN el número consecutivo del fichero comenzando por el 001.
Los archivos parciales contendrán siempre registros completos, es decir, nunca podrá particionarse el fichero
dejando registros incompletos en los ficheros parciales.
Si las características del equipo de que dispone el declarante no le permite ajustarse a las especificaciones
técnicas exigidas, y está obligado a presentar la declaración informativa anual, modelo 156, deberá dirigirse por
escrito a la Subdirección General de Aplicaciones del Departamento de Informática Tributaria de la Agencia Estatal
de Administración Tributaria (A.E.A.T.), calle Santa María Magdalena, 16, 28016 Madrid, exponiendo sus propias
características técnicas y el número de registros que presentaría, con objeto de encontrar, si lo hay, un sistema
compatible con las características técnicas de la A.E.A.T.
Ejercicio 2021

# Pag. 3

B) DISEÑOS LÓGICOS
DESCRIPCIÓN DE LOS REGISTROS
Para cada declarante se incluirán dos tipos diferentes de registro, que se distinguen por la primera posición, con
arreglo a los siguientes criterios:
Tipo 1: Registro del declarante: Datos identificativos y resumen de la declaración. Diseño de tipo de registro 1
de los recogidos más adelante en estos mismos apartados y Anexo de la presente Orden.
Tipo 2: Registro del afiliado o mutualista. Diseño de tipo de registro 2 de los recogidos más adelante en estos
mismos apartados y Anexo de la presente Orden.
El orden de presentación será el del tipo de registro, existiendo un único registro del tipo 1 y tantos registros del
tipo 2 como afiliados o mutualistas tenga la declaración.
Todos los campos alfanuméricos y alfabéticos se presentarán alineados a la izquierda y rellenos de blancos por
la derecha, en mayúsculas sin caracteres especiales, y sin vocales acentuadas.
Para los caracteres específicos del idioma se utilizará la codificación ISO-8859-1. De esta forma la letra “Ñ”
tendrá el valor ASCII 209 (Hex. D1) y la “Ç”(cedilla mayúscula) el valor ASCII 199 (Hex. C7).
Todos los campos numéricos se presentarán alineados a la derecha y rellenos a ceros por la izquierda sin signos
y sin empaquetar.
Todos los campos tendrán contenido, a no ser que se especifique lo contrario en la descripción del campo. Si no
lo tuvieran, los campos numéricos se rellenarán a ceros y tanto los alfanuméricos como los alfabéticos a blancos.
Ejercicio 2021

# Pag. 4

MODELO 156
A.- TIPO DE REGISTRO 1: REGISTRO DE DECLARANTE.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO.
Constante número '1'.
2-4 Numérico MODELO DECLARACIÓN.
Constante '156'.
5-8 Numérico EJERCICIO.
Las cuatro cifras del ejercicio fiscal al que corresponde la declaración.
9-17 Alfanumérico N.I.F. DEL DECLARANTE.
Se consignará el N.I.F. del declarante.
Este campo deberá estar ajustado a la derecha, siendo la última posición
el carácter de control y rellenando con ceros las posiciones de la
izquierda, de acuerdo con las reglas previstas en el Real Decreto
338/1990 de 9 de Marzo, por el que se regula la composición y forma de
utilización del NIF, (B.O.E. del 14 de marzo).
18-57 Alfanumérico RAZÓN SOCIAL DEL DECLARANTE
Se consignará la razón social completa, sin anagrama.
En ningún caso podrá figurar en este campo un nombre comercial.
58 Alfabético TIPO DE SOPORTE.
Se cumplimentará una de las siguientes claves:
'C': Si la información se presenta en cartucho magnético.
'D': Si la información se presenta en disquete.
'T': Transmisión telemática.
59-107 Alfanumérico PERSONA CON QUIEN RELACIONARSE
Datos de la persona con quien relacionarse. Este campo se subdivide en
dos:
59-67 TELÉFONO: Campo numérico de 9 posiciones.
68-107 APELLIDOS Y NOMBRE: Se consignará el primer
apellido, un espacio, el segundo apellido, un espacio y el
nombre completo, necesariamente en este orden.
108- 120 Numérico NÚMERO DE JUSTIFICANTE DE LA
DECLARACIÓN.
Se consignará el número de justificante correspondiente a la declaración.
Campo de contenido numérico de 13 posiciones.
Ejercicio 2021

# Pag. 5

121- 122 Alfabético DECLARACIÓN COMPLEMENTARIA
O SUSTITUTIVA.
En el caso excepcional de segunda o posterior presentación de
declaraciones, deberá cumplimentarse obligatoriamente uno de los
siguientes campos:
121 DECLARACIÓN COMPLEMENTARIA.: Se consignará
una “C” si la presentación de esta declaración tiene por objeto
incluir afiliados o mutualistas que, debiendo haber figurado en
otra declaración del mismo ejercicio presentada
anteriormente, hubieran sido completamente omitidos en la
misma.
122 DECLARACIÓN SUSTITUTIVA: Se consignará una “S”
si la presentación tiene como objeto anular y sustituir
completamente a otra declaración anterior, del mismo
ejercicio. Una declaración sustitutiva sólo puede anular a una
única declaración anterior.
123- 135 Numérico NÚMERO IDENTIFICATIVO DE LA
DECLARACIÓN ANTERIOR.
En caso de que se haya consignado una “C” en el campo “Declaración
complementaria”, o en el caso de que se haya consignado una “S” en el
campo “Declaración sustitutiva”, se consignará el número identificativo
correspondiente a la declaración a la que sustituye o complementa.
Campo de contenido numérico de 13 posiciones.
En cualquier otro caso deberá rellenarse a CEROS.
136-144 Numérico NÚMERO TOTAL DE REGISTROS DE AFILIADOS O
MUTUALISTAS .
Se consignará el número total de afiliados o mutualistas declarados en el
soporte por este declarante(Número de registros de tipo 2).
145-250 ------------ BLANCOS
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos por la
derecha, en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que se especifique lo
contrario en la descripción del campo.
Ejercicio 2021

# Pag. 6

B.- TIPO DE REGISTRO 2: REGISTRO DE AFILIADO O MUTUALISTA
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO.
Constante '2'
2-4 Numérico MODELO DECLARACIÓN.
Constante '156'.
5-8 Numérico EJERCICIO.
Consignar lo contenido en estas mismas posiciones del registro de tipo 1.
9-17 Alfanumérico N.I.F. DEL DECLARANTE.
Consignar lo contenido en estas mismas posiciones del registro de tipo 1.
18-26 Alfanumérico N.I.F. DEL AFILIADO O MUTUALISTA.
Se consignará en este campo el número de identificación fiscal del
afiliado o mutualista, de acuerdo con las reglas previstas en el Real
Decreto 338/1990 de 9 de Marzo, por el que se regula la composición y
forma de utilización del NIF (B.O.E. del 14 de marzo).
Este campo deberá estar ajustado a la derecha, siendo la última posición
el carácter de control y rellenando con ceros las posiciones a la izquierda.
27-35 ---------- BLANCO
36 – 75 Afabético APELLIDOS Y NOMBRE DEL AFILIADO O MUTUALISTA.
Por ser personas físicas se consignará el primer apellido, un espacio, el
segundo apellido, un espacio y el nombre completo, necesariamente en
este mismo orden.
76– 87 Alfanumérico NÚMERO DE AFILIACIÓN.
Se consignarán únicamente los dígitos sin caracteres especiales que
identifiquen al afiliado o mutualista al sistema de protección.
88– 96 Alfanumérico ENERO
Este campo se subdivide en dos:
88 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
Ejercicio 2021

# Pag. 7

89-96 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
89-94 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
95-96 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
97-105 Alfanumérico FEBRERO
Este campo se subdivide en dos:
97 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
98-105 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
98-103 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
104-105 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
106-114 Alfanumérico MARZO
Este campo se subdivide en dos:
106 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
107-114 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Ejercicio 2021

# Pag. 8

Este campo se subdivide en dos:
107-112 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
113-114 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
115-123 Alfanumérico ABRIL
Este campo se subdivide en dos:
115 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
116-123 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
116-121 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
122-123 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
124-132 Alfanumérico MAYO
Este campo se subdivide en dos:
124 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
125-132 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
125-130 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
131-132 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
Ejercicio 2021

# Pag. 9

133-141 Alfanumérico JUNIO
Este campo se subdivide en dos:
133 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
134-141 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
134-139 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
140-141 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
142-150 Alfanumérico JULIO
Este campo se subdivide en dos:
142 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
143-150 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
143-148 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
149-150 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
151-159 Alfanumérico AGOSTO
Este campo se subdivide en dos:
151 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Ejercicio 2021

# Pag. 10

Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
152-159 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
152-157 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
158-159 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
160-168 Alfanumérico SEPTIEMBRE
Este campo se subdivide en dos:
160 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
161-168 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
161-166 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
167-168 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
169-177 Alfanumérico OCTUBRE
Este campo se subdivide en dos:
169 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
170-177 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Ejercicio 2021

# Pag. 11

Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
170-175 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
176-177 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
178-186 Alfanumérico NOVIEMBRE
Este campo se subdivide en dos:
178 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
179-186 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
179-184 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
185-186 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
187-195 Alfanumérico DICIEMBRE
Este campo se subdivide en dos:
187 SITUACIÓN MENSUAL DE LAS COTIZACIONES
Campo alfabético de 1 posición.
Se consignará una S o una N, según se haya cotizado o no, al
menos un día en el mes correspondiente.
188-195 IMPORTE CUOTA DE COTIZACIÓN DEVENGADA:
Campo numérico de 8 posiciones.
Se consignará, sin coma decimal, el importe de la cuota de
cotización devengada por el afiliado o mutualista, por el
empleador y/o pagador, durante el mes correspondiente.
Este campo se subdivide en dos:
188-193 Parte entera del importe. Si no tiene contenido se
consignará a ceros.
Ejercicio 2021

# Pag. 12

194-195 Parte decimal del importe. Si no tiene contenido se
consignará a ceros.
196-250 ------------ BLANCOS
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos por la
derecha, en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que se especifique lo
contrario en la descripción del campo.
Ejercicio 2021