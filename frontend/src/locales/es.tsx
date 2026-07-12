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
    kicker: '¿Cuáles son los pasos para preparar un modelo?',
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
      'Guías, tutoriales y referencia para quienes presentan sus propios impuestos y para los profesionales que les ayudan.',
    open: 'Abrir la documentación',
    listLabel: 'Secciones de la documentación',
    links: [
      {
        title: 'Guía rápida',
        description: 'Instala, configura y prepara tu primer modelo.',
      },
      {
        title: 'Tutorial: un Modelo 130 de principio a fin',
        description: 'Sigue una declaración desde los registros hasta la exportación.',
      },
      {
        title: 'Guías prácticas',
        description: 'Recetas orientadas a tareas para situaciones habituales.',
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
  footer: {
    brandName: 'cadrumo',
    brandSummary:
      'Un asistente fiscal español, impulsado por un motor determinista y un arnés de agentes.',
    columns: [
      { heading: 'Producto', labels: ['Instalar el plugin', 'Funciones', 'Cómo funciona'] },
      { heading: 'Documentación', labels: ['Guía rápida', 'Tutorial', 'Arquitectura'] },
      { heading: 'Comunidad', labels: ['GitHub', 'PyPI: aeat-cli', 'cadrumo.neve.md'] },
    ],
    disclaimerPill: 'cadrumo',
    disclaimerText:
      'es un proyecto independiente de código abierto (Apache-2.0). No está afiliado a la AEAT y nunca presenta declaraciones; tú presentas a través de los canales oficiales de la AEAT y sigues siendo responsable de cada declaración.',
    copyright: '© 2026 los autores de cadrumo.',
  },
}
