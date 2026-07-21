import type { Copy } from './types'

export const es: Copy = {
  languageLabel: 'Idioma',
  skipToContent: 'Saltar al contenido',
  nav: {
    home: 'Inicio de Cadrumo',
    main: 'Navegación principal',
    documentation: 'Documentación',
    github: 'GitHub',
    download: 'Descargar',
  },
  bannerAlt: 'Un escritorio cuidadosamente ordenado con carpetas, notas y una calculadora',
  hero: {
    heading: (
      <>
        Motor de cálculo fiscal, <em>asistido</em> por agentes.
      </>
    ),
    lead1: (
      <>
        Cadrumo es una herramienta española de cálculo fiscal compatible* con la{' '}
        <strong className="accent">AEAT</strong>. Es un conjunto de herramientas para ti y para
        agentes como Claude o Codex, y te ayuda a preparar y gestionar de forma colaborativa
        tus obligaciones fiscales, tu libro contable y tu calendario fiscal.
      </>
    ),
    lead2:
      'Está diseñada para usarse como plugin de Claude Cowork, de modo que actúe como arnés para gestionar tus obligaciones fiscales de forma colaborativa.',
    footnote: (
      <>
        * «Compatible con la AEAT» describe únicamente que Cadrumo calcula conforme a los
        modelos y reglas publicados por la Agencia Estatal de Administración Tributaria.
        Cadrumo es un proyecto independiente sin relación alguna con la AEAT; consulta el{' '}
        <a href="#/legal">aviso legal</a>.
      </>
    ),
  },
  harness: {
    kicker: 'Un momento... ¿qué es un arnés de agentes?',
    heading: '¿MCP? ¿CLI? ¿Claude? Herramientas para personas y LLMs',
    p1: (
      <>
        Un arnés de agentes es simplemente un conjunto de herramientas: reglas, habilidades y
        utilidades que un asistente de IA puede usar. Cadrumo es un paquete con ayudas basadas
        en reglas para ti y tu chatbot LLM. Cadrumo incluye una{' '}
        <strong className="accent">CLI</strong>, la interfaz de comandos directa del motor de
        cálculo fiscal. También incluimos un <strong className="accent">MCP</strong> que
        permite a los asistentes usar las herramientas del paquete.
      </>
    ),
    p2: (
      <>
        <strong>Claude</strong> es un asistente que puede trabajar así. Puede ayudarte a
        navegar por tus registros, pedir a Cadrumo que ejecute una comprobación y explicar el
        resultado en lenguaje claro. El motor de reglas de Cadrumo produce los resultados.
        Claude no sustituye al motor, no presenta nada ante la AEAT ni decide qué debes
        declarar.
      </>
    ),
  },
  download: {
    kicker: 'Descarga y documentación',
    heading: 'Descargar',
    download: 'Descargar',
    readDocs: 'Leer la documentación',
    disclaimerTitle: 'AVISO',
    disclaimerBody:
      'Cadrumo es software independiente, no afiliado a la AEAT. No constituye asesoramiento fiscal. Cadrumo no permite presentar declaraciones directamente ante la AEAT. Es tu responsabilidad verificar manualmente todos los cálculos. Estamos en beta: las funciones pueden cambiar y la cobertura de impuestos y modelos no es completa. No asumimos responsabilidad por cálculos erróneos ni errores de presentación.',
  },
  pillars: {
    sectionLabel: 'Qué hace diferente a Cadrumo',
    kicker: '¿Qué hace diferente a Cadrumo?',
    items: [
      {
        label: '01 / ALMACENAMIENTO SEGURO',
        title: 'Almacenamiento local',
        description:
          'Las transacciones, facturas y justificantes permanecen cifrados en tu máquina. Cadrumo ofrece herramientas para preparar registros de gastos y facturas para los cálculos fiscales: siempre están a salvo.',
      },
      {
        label: '02 / MCP + CLI',
        title: 'Determinista',
        description:
          'Cadrumo calcula las cifras con la CLI incluida, un motor de cálculo determinista. Un agente puede ayudar a organizar o explicar el trabajo, pero los cálculos siempre los procesa el motor, nunca los agentes.',
      },
      {
        label: '03 / EXPORTA LOS CÁLCULOS PARA REVISARLOS',
        title: 'Revisable',
        description:
          'Tú inspeccionas los registros, cálculos, comprobaciones y justificantes. Tú decides si es correcto. Pide a tu agente que revise y verifique los cálculos, pero siempre tendrás los medios para comprobar y ajustar los detalles.',
      },
    ],
  },
  steps: {
    kicker: '¿Cuáles son los pasos para preparar un modelo?',
    heading: 'Los pasos del cálculo.',
    items: [
      {
        number: '01',
        title: 'Entrada',
        description:
          'Pide a tu agente que te ayude a leer e interpretar tus extractos bancarios, o añádelos manualmente con la CLI.',
      },
      {
        number: '02',
        title: 'Clasificar, filtrar, dividir',
        description:
          'Clasifica cada apunte del libro para los cálculos de IRPF e IVA, tipos incluidos, también los casos de uso mixto que requieren prorrateo.',
      },
      {
        number: '03',
        title: 'Calcular y verificar',
        description:
          'Calcula cada modelo con base en el BOE y las reglas de la AEAT detrás de cada casilla.',
      },
      {
        number: '04',
        title: 'Exportar los cálculos para revisión',
        description:
          'Compatibilidad con Google Drive y exportación XLS. Úsalas para verificar los cálculos antes de aprobar los valores de un modelo.',
      },
      {
        number: '05',
        title: 'Preparar la presentación',
        description:
          'Exporta un fichero en el formato oficial, listo para que lo subas a través de la AEAT.',
      },
      {
        number: '06',
        title: 'Conciliar con la AEAT',
        description:
          'Concilia tus registros con el justificante una vez presentada la declaración.',
      },
    ],
  },
  docsCta: {
    kicker: 'Documentación',
    heading: 'Aprende más.',
    summary:
      'Guías, recorridos completos y referencia para quienes presentan sus propios impuestos y para los profesionales que les ayudan.',
    open: 'Abrir la documentación',
    listLabel: 'Secciones de la documentación',
    links: [
      {
        title: 'Guía rápida',
        description: 'Instala, configura y prepara tu primer modelo.',
      },
      {
        title: 'Recorre un año de presentaciones',
        description: 'Sigue el año del IRPF y el del IVA, modelo a modelo.',
      },
      {
        title: 'Primeros pasos',
        description: 'Te dirige a la guía adecuada para cada tarea de presentación.',
      },
      {
        title: 'Cómo funciona',
        description: 'El arnés, el motor y la separación entre ambos.',
      },
      {
        title: 'Visión de la arquitectura',
        description: 'Cómo encajan las piezas y dónde viven tus datos.',
      },
    ],
  },
  legal: {
    linkLabel: 'Aviso legal, privacidad y cookies',
    title: 'Aviso legal, privacidad y cookies',
    updated: 'Última actualización: 12 de julio de 2026',
    backToHome: 'Volver a la página de inicio',
    identity: {
      heading: 'Titular del sitio',
      body: [
        <>
          Este sitio web, <strong>cadrumo.neve.md</strong>, y el dominio{' '}
          <strong>neve.md</strong> son publicados por <strong>Gergely Wootsch</strong>, la
          persona física detrás de neve.md y del proyecto Cadrumo, una iniciativa de código
          abierto sin ánimo comercial. Esta identificación se facilita en atención al
          artículo 10 de la Ley 34/2002 (LSSI-CE) en la medida en que resulte aplicable a un
          proyecto no comercial; se facilitarán datos identificativos adicionales a petición
          a través del canal de contacto indicado más abajo.
        </>,
        <>
          Contacto: <a href="mailto:hello@neve.md">hello@neve.md</a>, o a través del
          repositorio canónico del proyecto,{' '}
          <a href="https://github.com/nevenincs/cadrumo">github.com/nevenincs/cadrumo</a> (allí se
          indican los canales de incidencias y de seguridad).
        </>,
      ],
    },
    nonAffiliation: {
      heading: 'Sin relación con la AEAT',
      body: [
        <>
          Cadrumo es un <strong>proyecto independiente de código abierto</strong>. No es un
          producto de la Agencia Estatal de Administración Tributaria (AEAT) ni está afiliado
          a ella, ni respaldado, patrocinado o aprobado por ella ni por ninguna otra
          administración pública. No es software oficial y no sustituye a las herramientas
          propias de la AEAT.
        </>,
        <>
          Las referencias en este sitio y en el software a «AEAT», a números de modelo (como
          100, 130 o 303) y a casillas son puramente descriptivas: nombran los formularios y
          reglas públicas oficiales con los que calcula el software. Todos los nombres y
          signos oficiales pertenecen a sus titulares. Los impuestos se presentan únicamente a
          través de los canales oficiales de la AEAT; Cadrumo nunca presenta nada en tu
          nombre. El asterisco tras «compatible con la AEAT» en la portada remite a este
          aviso.
        </>,
      ],
    },
    noAdvice: {
      heading: 'No es asesoramiento fiscal',
      body: [
        <>
          Cadrumo calcula y comprueba cifras a partir de reglas publicadas; no evalúa tu
          situación personal y no constituye asesoramiento fiscal, legal ni financiero. En
          caso de duda, consulta a un profesional cualificado. Sigues siendo responsable de
          cada declaración que presentes.
        </>,
      ],
    },
    privacy: {
      heading: 'Privacidad: no recogemos nada',
      body: [
        <>
          Este sitio web <strong>no recoge ningún dato personal</strong>. No hay cuentas, ni
          formularios, ni analítica, ni publicidad, ni píxeles de seguimiento, ni
          fingerprinting, y no se comparte ni se solicita nada a terceros. Todos los recursos
          de esta página, incluidas sus fuentes tipográficas, se sirven desde este mismo
          dominio.
        </>,
        <>
          El sitio es un conjunto de ficheros estáticos servidos desde infraestructura de
          Amazon Web Services (S3 y CloudFront). Nuestra configuración no activa ningún
          registro de accesos: los datos de conexión, como tu dirección IP, los procesa esa
          infraestructura de forma transitoria solo en la medida técnicamente necesaria para
          entregar la página, y nosotros ni activamos, ni recibimos, ni almacenamos registros
          de acceso.
        </>,
        <>
          El software Cadrumo sigue la misma política: tus registros financieros permanecen
          cifrados en tu propia máquina y el software no nos envía telemetría alguna. Consulta
          la{' '}
          <a href="https://github.com/nevenincs/cadrumo/blob/main/PRIVACY.md">
            política de privacidad
          </a>{' '}
          del proyecto.
        </>,
        <>
          Como no disponemos de ningún dato personal tuyo, las solicitudes de derechos de los
          artículos 15 a 22 del RGPD no tienen objeto sobre el que operar. Si crees lo
          contrario, contáctanos a través del repositorio y responderemos.
        </>,
      ],
    },
    cookies: {
      heading: 'Cookies',
      body: [
        <>
          El sitio establece una única cookie funcional de origen, <code>cadrumo_lang</code>,
          y solo si eliges explícitamente un idioma. Guarda esa elección durante un máximo de
          un año, no es un rastreador y solo la lee este sitio. Cerrar la barra de aviso
          guarda un indicador similar (<code>cadrumo_notice_ack</code>) en el localStorage de
          tu navegador.
        </>,
        <>
          Conforme al artículo 22.2 de la LSSI-CE y a la Guía sobre el uso de cookies de la
          AEPD, las cookies de preferencias establecidas a petición expresa del usuario están
          exentas de consentimiento previo; aun así, las declaramos aquí. Puedes eliminarlas
          en cualquier momento desde la configuración de tu navegador y el sitio funciona
          plenamente sin ellas.
        </>,
      ],
    },
    licences: {
      heading: 'Licencias y qué distribuye este sitio',
      body: [
        <>
          Cadrumo es código abierto bajo la <strong>Apache License 2.0</strong>. El código de
          este sitio y del software vive en{' '}
          <a href="https://github.com/nevenincs/cadrumo">github.com/nevenincs/cadrumo</a>.
        </>,
        <>
          La página que estás leyendo distribuye React y ReactDOM (licencia MIT) y las
          tipografías Hanken Grotesk, Instrument Serif y JetBrains Mono (SIL Open Font License
          1.1), todas autoalojadas. La atribución completa está en los avisos de terceros del
          repositorio.
        </>,
      ],
    },
    liability: {
      heading: 'Garantías y responsabilidad',
      body: [
        <>
          El software y este sitio se proporcionan «tal cual», sin garantías ni condiciones de
          ningún tipo, según las secciones 7 y 8 de la Apache License 2.0. Cadrumo está en
          beta: las funciones pueden cambiar y la cobertura fiscal no es completa. Verifica
          cada cálculo antes de presentar. En la medida en que lo permita la ley aplicable,
          los autores no asumen responsabilidad por errores de cálculo, errores de
          presentación ni por ningún daño derivado del uso del software o de este sitio.
        </>,
      ],
    },
  },
  cookieBanner: {
    ariaLabel: 'Aviso de privacidad',
    message: (
      <>
        Este sitio no instala rastreadores ni recoge datos. Una cookie funcional guarda tu
        idioma, y solo si eliges uno.
      </>
    ),
    details: 'Aviso legal y privacidad',
    dismiss: 'Entendido',
  },
  footer: {
    brandName: 'cadrumo',
    brandSummary:
      'Un asistente fiscal español, impulsado por un motor determinista y un arnés de agentes.',
    columns: [
      { heading: 'Producto', labels: ['Instalar el plugin', 'Funciones', 'Cómo funciona'] },
      { heading: 'Documentación', labels: ['Guía rápida', 'Primeros pasos', 'Arquitectura'] },
      { heading: 'Comunidad', labels: ['GitHub', 'PyPI: cadrumo', 'cadrumo.neve.md'] },
    ],
    disclaimerPill: 'cadrumo',
    disclaimerText:
      'es un proyecto independiente de código abierto (Apache-2.0). No está afiliado a la AEAT y nunca presenta declaraciones; tú presentas a través de los canales oficiales de la AEAT y sigues siendo responsable de cada declaración.',
    legalLink: 'Aviso legal, privacidad y cookies',
    copyright: '© 2026 Gergely Wootsch y los contribuidores de cadrumo.',
  },
}
