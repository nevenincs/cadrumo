# Pag. 1

Presentación por fichero Modelo 369
Este documento es una ayuda complementaria al diseño de registro del modelo 369, que
contiene el esquema que debe seguir el fichero de texto para la presentación electrónica del
modelo. Se incluye una explicación de la estructura del fichero y la descripción de los datos
que debe incluir en el fichero.
Estructura general diseño de registro modelo 369
- Pestaña T3690 Estruc. Gral: estructura general del fichero a presentar.
- La estructura general contiene la información de los campos a incluir en el fichero, con
las posiciones relativas, absolutas, longitud, tipo y descripción de cada campo. El
campo ‘Contenido de la presentación’, es de longitud variable, y contendrá la
información detallada de la declaración a presentar, dependiendo del régimen de que
se trate. El contenido de la información de declaración se detalla en las pestañas
T36900 a T369012 del Excel con el diseño de registro.
- Cada página de información de la declaración tiene una etiqueta de apertura y cierre, y
un contenido entre las anteriores etiquetas, todo especificado en las pestañas del
fichero Excel de diseño de registro para la presentación por fichero.
- Cada página puede contener los datos básicos del régimen a presentar y la lista a la
que referencia la página. Dicha lista tiene hasta 28 elementos, donde los que no
tengan información vendrán en blanco. Si una de las listas de la página excede los 28
elementos rellenos, se puede añadir la misma página indicando que es
complementaria y rellenando elementos en la lista con el formato anteriormente
mencionado.
- La presentación por fichero se generará en un fichero de texto plano siguiendo el
esquema del Excel del fichero, según el régimen que se quiera presentar. Cada fichero
sólo puede contener la declaración de un único declarante y para un único régimen.
- En función del régimen de la declaración a presentar se incluirán sólo las páginas
correspondientes, según se explica en columna 'Contenido' del Excel con el DR.

# Pag. 2

Contenido del fichero de texto
Régimen de la Unión
El fichero incluirá los datos especificados en la pestaña ‘T3690 Estructura gral’.
El campo de longitud variable ‘Contenido de la presentación’ contendrá la información
detallada de la declaración a presentar para régimen Union.
Dicho detalle de la declaración se detalla en las pestañas T36900, T36904 a T36909:
o T36900 Info Adicional
 Contenido vacío especificado en la página
 Esta página es obligatoria
o T36904 Un
 Datos básicos del régimen
 Prestaciones de servicios desde el EMID España y desde establecimientos
permanentes situados fuera de la UE
 Esta página es obligatoria
o T36905 Un
 Entregas de bienes expedidos o transportados desde EMID España
 Esta página es opcional
o T36906 Un
 Prestaciones de servicios desde establecimientos permanentes en otros EM
distintos de España
 Esta página es opcional
o T36907 Un
 Entregas de bienes expedidos o transportados desde otros EM distintos de España
 Esta página es opcional
o T36908 Un
 Correcciones de autoliquidaciones de periodos anteriores (máximo 3 años)
 Esta página es opcional
o T36909 Un
 Contenido vacío especificado en la página
 Esta página es obligatoria

# Pag. 3

Régimen exterior
El fichero incluirá los datos especificados en la pestaña ‘T3690 Estructura gral’.
El campo de longitud variable ‘Contenido de la presentación’ contendrá la información
detallada de la declaración a presentar para régimen Exterior.
Dicho detalle de la declaración se detalla en las pestañas T36900, T36901 a T36903:
o T36900 Info Adicional
 Contenido vacío especificado en la página
 Esta página es obligatoria
o T36901 Ext
 Datos básicos del régimen
 Prestaciones de servicios
 Esta página es obligatoria
o T36902 Ext
 Correcciones de autoliquidaciones de periodos anteriores (máximo 3 años)
 Esta página es opcional
o T36903 Ext
 Contenido vacío especificado en la página
 Esta página es obligatoria
Régimen de importación
El fichero incluirá los datos especificados en la pestaña ‘T3690 Estructura gral’.
El campo de longitud variable ‘Contenido de la presentación’ contendrá la información
detallada de la declaración a presentar para régimen Importación.
Dicho detalle de la declaración se detalla en las pestañas T36900, T36910 a T36912:
o T36900 Info Adicional
 Contenido vacío especificado en la página
 Esta página es obligatoria
o T36910 Imp
 Datos básicos del régimen
 Importaciones de bienes de menos de 150 €
 Esta página es obligatoria

# Pag. 4

o T36911 Imp
 Correcciones de autoliquidaciones de periodos anteriores (máximo 3 años)
 Esta página es opcinal
o T36912 Imp
 Contenido vacío especificado en la página
 Esta página es obligatoria
Conceptos campos:
Campo Valores
Periodo cabecera [1T, 2T, 3T, 4T] Trimestrales
[01, 02, 03…, 12] Mensuales
Régimen [MOSS, VOES, IMPO]
MOSS -> Régimen Union
VOES -> Régimen exterior
IMPO -> Régimen importación
Categoría [D]
D -> Declaración
Tipo de pago [O, S, I, N, T]
O -> Reconocimiento de deuda con los
Estados Miembros de Consumo con
imposibilidad de pago
S -> Ingreso parcial y Reconocimiento de
deuda con los Estados Miembros de
Consumo con imposibilidad de pago
I -> A ingresar
N -> Negativa
T -> Ingreso por transferencia desde el
extranjero
Complementaria [“ “, C]
“ “ (espacio en blanco) -> única página
C -> página extra si hay más de 28 elementos
Tipo de periodo [T, M]
T -> Trimestral
M -> Mensual
Periodo Dependiendo tipo periodo:
T -> 1 .. 4
M -> 1 .. 12
Declaración sin actividad [0, 1]
0 -> false
1 -> true
Tipos de IVA [R, S]
R -> reducido
S -> estándar