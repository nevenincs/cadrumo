import type { Copy } from './types'

export const ca: Copy = {
  languageLabel: 'Idioma',
  skipToContent: 'Salta al contingut',
  nav: {
    home: 'Inici de Cadrumo',
    main: 'Navegació principal',
    documentation: 'Documentació',
    github: 'GitHub',
    download: 'Descarrega',
  },
  bannerAlt: 'Un escriptori curosament ordenat amb carpetes, notes i una calculadora',
  hero: {
    heading: (
      <>
        Motor de càlcul fiscal, <em>assistit</em> per agents.
      </>
    ),
    lead1: (
      <>
        Cadrumo és una eina espanyola de càlcul fiscal compatible* amb l&rsquo;
        <strong className="accent">AEAT</strong>. És un conjunt d&rsquo;eines per a tu i per a
        agents com Claude o Codex, i t&rsquo;ajuda a preparar i gestionar de manera
        col·laborativa les teves obligacions fiscals, el teu llibre comptable i el teu
        calendari fiscal.
      </>
    ),
    lead2:
      'Està dissenyada per usar-se com a plugin de Claude Cowork, de manera que actuï com a arnès per gestionar les teves obligacions fiscals de manera col·laborativa.',
  },
  harness: {
    kicker: "Un moment... què és un arnès d'agents?",
    heading: 'MCP? CLI? Claude? Eines per a persones i LLMs',
    p1: (
      <>
        Un arnès d&rsquo;agents és simplement un conjunt d&rsquo;eines: regles, habilitats i
        utilitats que un assistent d&rsquo;IA pot fer servir. Cadrumo és un paquet amb ajudes
        basades en regles per a tu i el teu chatbot LLM. Cadrumo inclou una{' '}
        <strong className="accent">CLI</strong>, la interfície d&rsquo;ordres directa del motor
        de càlcul fiscal. També incloem un <strong className="accent">MCP</strong> que permet
        als assistents fer servir les eines del paquet.
      </>
    ),
    p2: (
      <>
        <strong>Claude</strong> és un assistent que pot treballar així. Et pot ajudar a navegar
        pels teus registres, demanar a Cadrumo que executi una comprovació i explicar el
        resultat en llenguatge clar. El motor de regles de Cadrumo produeix els resultats.
        Claude no substitueix el motor, no presenta res davant l&rsquo;AEAT ni decideix què has
        de declarar.
      </>
    ),
  },
  download: {
    kicker: 'Descàrrega i documentació',
    heading: 'Descarrega',
    download: 'Descarrega',
    readDocs: 'Llegeix la documentació',
    disclaimerTitle: 'AVÍS',
    disclaimerBody:
      "Cadrumo és programari independent, no afiliat a l'AEAT. No constitueix assessorament fiscal. Cadrumo no permet presentar declaracions directament davant l'AEAT. És responsabilitat teva verificar manualment tots els càlculs. Som en beta: les funcions poden canviar i la cobertura d'impostos i models no és completa. No assumim responsabilitat per càlculs erronis ni errors de presentació.",
  },
  pillars: {
    sectionLabel: 'Què fa diferent Cadrumo',
    kicker: (
      <>
        Quins són els passos per preparar un <span lang="es">modelo</span>?
      </>
    ),
    items: [
      {
        label: '01 / EMMAGATZEMATGE SEGUR',
        title: 'Emmagatzematge local',
        description:
          'Les transaccions, factures i justificants romanen xifrats a la teva màquina. Cadrumo ofereix eines per preparar registres de despeses i factures per als càlculs fiscals: sempre estan segurs.',
      },
      {
        label: '02 / MCP + CLI',
        title: 'Determinista',
        description:
          'Cadrumo calcula les xifres amb la CLI inclosa, un motor de càlcul determinista. Un agent pot ajudar a organitzar o explicar la feina, però els càlculs sempre els processa el motor, mai els agents.',
      },
      {
        label: '03 / EXPORTA ELS CÀLCULS PER REVISAR-LOS',
        title: 'Revisable',
        description:
          'Tu inspecciones els registres, càlculs, comprovacions i justificants. Tu decideixes si és correcte. Demana al teu agent que revisi i verifiqui els càlculs, però sempre tindràs els mitjans per comprovar i ajustar els detalls.',
      },
    ],
  },
  steps: {
    kicker: (
      <>
        Quins són els passos per preparar un <span lang="es">modelo</span>?
      </>
    ),
    heading: 'Els passos del càlcul.',
    items: [
      {
        number: '01',
        title: 'Entrada',
        description:
          "Demana al teu agent que t'ajudi a llegir i interpretar els teus extractes bancaris, o afegeix-los manualment amb la CLI.",
      },
      {
        number: '02',
        title: 'Classificar, filtrar, dividir',
        description:
          "Classifica cada apunt del llibre per als càlculs d'IRPF i IVA, tipus inclosos, també els casos d'ús mixt que requereixen prorrateig.",
      },
      {
        number: '03',
        title: 'Calcular i verificar',
        description: (
          <>
            Calcula cada <span lang="es">modelo</span> amb base al BOE i les regles de
            l&rsquo;AEAT darrere de cada <span lang="es">casilla</span>.
          </>
        ),
      },
      {
        number: '04',
        title: 'Exportar els càlculs per a revisió',
        description:
          "Compatibilitat amb Google Drive i exportació XLS. Fes-les servir per verificar els càlculs abans d'aprovar els valors d'un model.",
      },
      {
        number: '05',
        title: 'Preparar la presentació',
        description:
          "Exporta un fitxer en el format oficial, a punt perquè el pugis a través de l'AEAT.",
      },
      {
        number: '06',
        title: "Conciliar amb l'AEAT",
        description: (
          <>
            Concilia els teus registres amb el <span lang="es">justificante</span> un cop
            presentada la declaració.
          </>
        ),
      },
    ],
  },
  docsCta: {
    kicker: 'Documentació',
    heading: 'Aprèn-ne més.',
    summary:
      'Guies, tutorials i referència per a qui presenta els seus propis impostos i per als professionals que els ajuden.',
    open: 'Obre la documentació',
    listLabel: 'Seccions de la documentació',
    links: [
      {
        title: 'Guia ràpida',
        description: 'Instal·la, configura i prepara el teu primer model.',
      },
      {
        title: 'Tutorial: un Modelo 130 de principi a fi',
        description: "Segueix una declaració des dels registres fins a l'exportació.",
      },
      {
        title: 'Guies pràctiques',
        description: 'Receptes orientades a tasques per a situacions habituals.',
      },
      {
        title: 'Com funciona',
        description: "L'arnès, el motor i la separació entre tots dos.",
      },
      {
        title: "Visió de l'arquitectura",
        description: 'Com encaixen les peces i on viuen les teves dades.',
      },
    ],
  },
  footer: {
    brandName: 'cadrumo',
    brandSummary:
      "Un assistent fiscal espanyol, impulsat per un motor determinista i un arnès d'agents.",
    columns: [
      { heading: 'Producte', labels: ['Instal·lar el plugin', 'Funcions', 'Com funciona'] },
      { heading: 'Documentació', labels: ['Guia ràpida', 'Tutorial', 'Arquitectura'] },
      { heading: 'Comunitat', labels: ['GitHub', 'PyPI: aeat-cli', 'cadrumo.neve.md'] },
    ],
    disclaimerPill: 'cadrumo',
    disclaimerText:
      "és un projecte independent de codi obert (Apache-2.0). No està afiliat a l'AEAT i mai presenta declaracions; tu presentes a través dels canals oficials de l'AEAT i continues sent responsable de cada declaració.",
    copyright: '© 2026 els autors de cadrumo.',
  },
}
