---
tags:
  - '#audit'
  - '#operator-testimonial'
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# Operator persona

Me llamo Juan García. Soy fontanero autónomo en Madrid, llevo 15 años con mi propio negocio. Alguien me dijo que esta herramienta me ayuda a gestionar mis modelos de hacienda sin tener que ir a la gestoría cada tres meses. No soy informático. Sé abrir el terminal porque mi sobrino me enseñó, pero no sé lo que significa "bucket" ni "Argon2id" ni "namespace".

# What I tried to do

- Ejecutar `aeat` sin nada para ver qué hace
- Ejecutar `aeat --help` para entender cómo empezar
- Ejecutar `aeat config --help` para encontrar cómo crear un perfil
- Leer la ayuda de `aeat config profile create` para entender qué opciones necesito
- Crear mi primer perfil como fontanero autónomo en Madrid con mi NIF
- Ver el perfil recién creado para confirmar que se guardó bien
- Intentar ver el estado general de mi cuenta
- Intentar borrar el perfil para empezar de nuevo
- Intentar encontrar mis facturas o declaraciones guardadas

# What worked

- `aeat config --help` tiene una sección "first run" con `aeat config profile create NAME` como primer paso. Eso tiene sentido: busco "crear perfil" y lo veo ahí.
- `aeat config auth providers` me dijo en dos segundos qué métodos de autenticación existen, y los nombres (Cl@ve Móvil, Certificado digital) son los mismos que uso en la sede electrónica de hacienda. Eso lo entendí perfectamente.
- La ayuda de `aeat config profile create` está en español. Eso lo agradezco mucho.
- El menú de `aeat --help` está dividido en secciones ("setup", "daily ledger", "modelo lifecycle"). Tiene sentido conceptualmente, aunque las etiquetas en inglés me desconciertan.

# What hurt

## Pain 1 — El primer comando devuelve un error técnico que no dice nada útil (Severidad: 5/5)

Antes de hacer nada, ejecuté `aeat` a secas. Esto es lo que recibí:

```
Exit code 5
Failed. aeat_database_url is empty; set AEAT_DATABASE_URL.
```

No tengo ni idea de lo que es una "database URL". Nadie me dijo que tenía que configurar eso antes de empezar. La herramienta no me dijo dónde encontrar esa información ni qué valor poner. Esto es lo primero que ve alguien que instala el programa. Si esto me hubiera pasado en la vida real, habría desinstalado el programa en ese momento.

## Pain 2 — "config bucket" en la descripción del comando (Severidad: 3/5)

Cuando leí la ayuda de `aeat config profile create`, la descripción dice:

```
Initialize a new active profile and config bucket.
```

¿Qué es un "config bucket"? Pensé que iba a crear un perfil, no un cubo. Esta frase está en inglés cuando todo lo demás está en español. Me hace sentir que estoy haciendo algo técnico que no entiendo.

## Pain 3 — El flag `--address-postco` no funciona aunque lo copié del menú truncado (Severidad: 4/5)

La tabla de ayuda mostraba `--address-postco…` con puntos suspensivos porque el nombre era demasiado largo para la pantalla. Escribí `--address-postco` y recibí:

```
No such option: --address-postco Did you mean --address-postcode?
```

El problema es que el menú me mostró el nombre cortado. No sabía que había más letras. Tuve que adivinar. Y encima, la sugerencia "Did you mean..." está en inglés cuando el resto del mensaje ya estaba en español.

## Pain 4 — `--tax-residence-region` no existe aunque parece lógico (Severidad: 3/5)

Intenté poner `--tax-residence-region madrid` porque eso es lo que significa en español. El comando me dijo que no existe y me sugirió `--tax-residence-ccaa`. ¿Qué es CCAA para alguien que no trabaja en administración pública? Yo digo "comunidad autónoma", no "CCAA". Y Madrid no es un código técnico, es una ciudad. Funcionó al final, pero me costó un intento extra.

## Pain 5 — La herramienta me pide `--quiet` para funcionar sin asistente, pero luego falla con un error incomprensible (Severidad: 5/5)

Después de dos errores de flags, finalmente puse el comando correcto con `--quiet` como me sugirió el mensaje de error anterior. El resultado fue una pantalla llena de texto técnico que empieza así:

```
Exit code 6
NoActiveBucketSessionError: no active bucket session; run `aeat config profile switch NAME`
...
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
```

Yo intentaba CREAR un perfil, no usar uno que ya existe. ¿Por qué me dice que cambie a un perfil si todavía no tengo ninguno? Y lo de "NoActiveBucketSessionError" y "Traceback" y "_encrypted_columns.py" — eso no es para mí. Yo soy fontanero. No puedo resolver esto.

Al final el mensaje dice `Run aeat config repair` pero cuando lo ejecuté, vi cientos de líneas de errores técnicos sobre archivos que no se encuentran. No hay ningún resumen claro de "esto está roto, haz esto para arreglarlo".

## Pain 6 — Ningún comando funciona, incluidos los de solo lectura (Severidad: 5/5)

Después del error de creación, intenté `aeat config profile list` para ver si al menos se había guardado algo. Mismo error. Intenté `aeat config profile show`. Mismo error. Intenté `aeat config profile status`. Mismo error. Intenté `aeat config profile switch fontanero_madrid`. Mismo error. Intenté `aeat app overview status`. Mismo error.

La herramienta está completamente bloqueada. No puedo ver nada, no puedo hacer nada, no puedo siquiera confirmar si se creó algo. El único mensaje que recibo es siempre el mismo. Ejecuto repair y recibo 500 líneas de errores internos. Círculo sin salida.

## Pain 7 — `aeat config --help` listaba `profile view` pero ese comando no existe (Severidad: 3/5)

El menú de `aeat config --help` listaba `aeat config profile view [NAME]` bajo "profile inspection". Cuando ejecuté ese comando, la respuesta fue:

```
No such command 'view'.
```

El comando real se llama `show`. Si el menú dice `view` y el comando es `show`, ¿cuál es el correcto?

## Pain 8 — `aeat --help` muestra texto de plantilla sin rellenar (Severidad: 2/5)

La primera pantalla de `aeat --help` muestra:

```
Heading

Paragraph two roots
Paragraph type
```

Parece que esos son marcadores de plantilla sin rellenar. No me dicen nada sobre para qué sirve la herramienta ni cómo empezar.

# Verbatim commands I ran and what came back

```
$ aeat
Exit code 5
Failed. aeat_database_url is empty; set AEAT_DATABASE_URL.

$ aeat --help
Heading
Paragraph two roots
Paragraph type
Section setup
  aeat config profile create NAME  Setup create profile
  ...

$ aeat config profile create --help
 Initialize a new active profile and config bucket.
 ...
 --address-postco…   TEXT  Código postal del domicilio fiscal
 --tax-residence-…   [andalucia|aragon|...]  Comunidad autónoma de residencia fiscal
 ...

$ aeat config profile create fontanero_madrid --tax-id "12345678Z" --name "Juan" \
    --surnames "García López" --activity "Fontanero autónomo" \
    --address-postco "28001" --output-language es --tax-residence-region madrid
Exit code 2
No such option: --address-postco Did you mean --address-postcode?

$ aeat config profile create fontanero_madrid ... --address-postcode "28001" \
    --tax-residence-region madrid
Exit code 2
No such option: --tax-residence-region Did you mean --tax-residence-ccaa?

$ aeat config profile create fontanero_madrid ... --address-postcode "28001" \
    --tax-residence-ccaa madrid
Exit code 2
Refused. No pude abrir el asistente guiado en esta ejecución.
...
-> Run `aeat config profile create NAME --quiet --tax-id NIF --activity ACTIVITY`

$ aeat config profile create fontanero_madrid --quiet --tax-id "12345678Z" \
    --activity "Fontanero autónomo"
Exit code 6
NoActiveBucketSessionError: no active bucket session; run `aeat config profile switch NAME`
...sqlalchemy.exc.StatementError...
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`

$ aeat config profile list
[mismo NoActiveBucketSessionError + traza de Python]

$ aeat config profile show
[mismo NoActiveBucketSessionError + traza de Python]

$ aeat config profile switch fontanero_madrid
[mismo NoActiveBucketSessionError + traza de Python]

$ aeat config repair
[500+ líneas de advertencias internas sobre archivos no encontrados]
...
Next label  Inspect registry toml
warn  runtime.dependency_sync  Venv stale
Next label  uv sync

$ aeat config profile view
No such command 'view'.

$ aeat config profile delete fontanero_madrid --yes
[mismo NoActiveBucketSessionError + traza de Python]

$ aeat app overview status
[mismo NoActiveBucketSessionError + traza de Python]
```

# If I were honest with the developer

Llevas todo el primer arranque roto. Un usuario nuevo no puede hacer absolutamente nada: el primer comando devuelve un error de base de datos que no explica qué hacer, el intento de crear perfil falla con una traza de Python de 50 líneas, y a partir de ahí cada comando devuelve el mismo error en bucle sin salida posible.

El mensaje "NoActiveBucketSessionError" es un nombre de clase de Python, no un mensaje de usuario. Necesitas traducir todos los errores internos a frases en español que digan exactamente qué hacer en un solo paso, sin jerga técnica.

Configurar AEAT_DATABASE_URL es un requisito oculto que ningún usuario final puede adivinar. Si la herramienta necesita una base de datos, debe crearla sola la primera vez con un valor predeterminado, o bien preguntar dónde guardarla durante la primera ejecución, como hace cualquier app de escritorio normal.

El menú de ayuda tiene texto de plantilla sin rellenar ("Heading", "Paragraph two roots") y lista un comando (`profile view`) que no existe. Esto hace que la herramienta parezca incompleta, no profesional.

La única cosa que funcionó sin error fue `aeat config auth providers`. Si toda la CLI funcionara así de limpio y en español, esta herramienta sería muy útil para alguien como yo.
