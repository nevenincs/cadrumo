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
    footnote: (
      <>
        * «Compatible amb l&rsquo;AEAT» descriu únicament que Cadrumo calcula d&rsquo;acord amb
        els models i regles publicats per l&rsquo;Agencia Estatal de Administración Tributaria.
        Cadrumo és un projecte independent sense cap relació amb l&rsquo;AEAT; consulta
        l&rsquo;<a href="#/legal">avís legal</a>.
      </>
    ),
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
    kicker: 'Què fa diferent Cadrumo?',
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
      'Guies, recorreguts complets i referència per a qui presenta els seus propis impostos i per als professionals que els ajuden.',
    open: 'Obre la documentació',
    listLabel: 'Seccions de la documentació',
    links: [
      {
        title: 'Guia ràpida',
        description: 'Instal·la, configura i prepara el teu primer model.',
      },
      {
        title: 'Recorre un any de presentacions',
        description: "Segueix l'any de l'IRPF i el de l'IVA, model a model.",
      },
      {
        title: 'Primers passos',
        description: 'Et dirigeix a la guia adequada per a cada tasca de presentació.',
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
  legal: {
    linkLabel: 'Avís legal, privadesa i galetes',
    title: 'Avís legal, privadesa i galetes',
    updated: 'Darrera actualització: 12 de juliol de 2026',
    backToHome: 'Torna a la pàgina d’inici',
    identity: {
      heading: 'Titular del lloc',
      body: [
        <>
          Aquest lloc web, <strong>cadrumo.neve.md</strong>, i el domini{' '}
          <strong>neve.md</strong> són publicats per <strong>Gergely Wootsch</strong>, la
          persona física darrere de neve.md i del projecte Cadrumo, una iniciativa de codi
          obert sense ànim comercial. Aquesta identificació es facilita en atenció a
          l&rsquo;article 10 de la Llei 34/2002 (LSSI-CE) en la mesura que sigui aplicable a
          un projecte no comercial; es facilitaran dades identificatives addicionals a
          petició a través del canal de contacte indicat més avall.
        </>,
        <>
          Contacte: <a href="mailto:hello@neve.md">hello@neve.md</a>, o a través del
          repositori canònic del projecte,{' '}
          <a href="https://github.com/nevenincs/cadrumo">github.com/nevenincs/cadrumo</a> (allà
          s&rsquo;indiquen els canals d&rsquo;incidències i de seguretat).
        </>,
      ],
    },
    nonAffiliation: {
      heading: 'Sense relació amb l’AEAT',
      body: [
        <>
          Cadrumo és un <strong>projecte independent de codi obert</strong>. No és un producte
          de l&rsquo;Agencia Estatal de Administración Tributaria (AEAT) ni hi està afiliat,
          ni està avalat, patrocinat o aprovat per ella ni per cap altra administració
          pública. No és programari oficial i no substitueix les eines pròpies de
          l&rsquo;AEAT.
        </>,
        <>
          Les referències en aquest lloc i en el programari a «AEAT», a números de model (com
          100, 130 o 303) i a caselles són purament descriptives: anomenen els formularis i
          regles públiques oficials amb què calcula el programari. Tots els noms i signes
          oficials pertanyen als seus titulars. Els impostos es presenten únicament a través
          dels canals oficials de l&rsquo;AEAT; Cadrumo mai presenta res en nom teu.
          L&rsquo;asterisc després de «compatible amb l&rsquo;AEAT» a la portada remet a
          aquest avís.
        </>,
      ],
    },
    noAdvice: {
      heading: 'No és assessorament fiscal',
      body: [
        <>
          Cadrumo calcula i comprova xifres a partir de regles publicades; no avalua la teva
          situació personal i no constitueix assessorament fiscal, legal ni financer. En cas
          de dubte, consulta un professional qualificat. Continues sent responsable de cada
          declaració que presentis.
        </>,
      ],
    },
    privacy: {
      heading: 'Privadesa: no recollim res',
      body: [
        <>
          Aquest lloc web <strong>no recull cap dada personal</strong>. No hi ha comptes, ni
          formularis, ni analítica, ni publicitat, ni píxels de seguiment, ni fingerprinting,
          i no es comparteix ni es demana res a tercers. Tots els recursos d&rsquo;aquesta
          pàgina, incloses les seves tipografies, se serveixen des d&rsquo;aquest mateix
          domini.
        </>,
        <>
          El lloc és un conjunt de fitxers estàtics servits des d&rsquo;infraestructura
          d&rsquo;Amazon Web Services (S3 i CloudFront). La nostra configuració no activa cap
          registre d&rsquo;accessos: les dades de connexió, com la teva adreça IP, les
          processa aquesta infraestructura de manera transitòria només en la mesura
          tècnicament necessària per servir la pàgina, i nosaltres ni activem, ni rebem, ni
          emmagatzemem registres d&rsquo;accés.
        </>,
        <>
          El programari Cadrumo segueix la mateixa política: els teus registres financers
          romanen xifrats a la teva pròpia màquina i el programari no ens envia cap
          telemetria. Consulta la{' '}
          <a href="https://github.com/nevenincs/cadrumo/blob/main/PRIVACY.md">
            política de privadesa
          </a>{' '}
          del projecte.
        </>,
        <>
          Com que no disposem de cap dada personal teva, les sol·licituds de drets dels
          articles 15 a 22 del RGPD no tenen objecte sobre el qual operar. Si creus el
          contrari, contacta&rsquo;ns a través del repositori i respondrem.
        </>,
      ],
    },
    cookies: {
      heading: 'Galetes',
      body: [
        <>
          El lloc estableix una única galeta funcional de primera part,{' '}
          <code>cadrumo_lang</code>, i només si tries explícitament un idioma. Desa aquesta
          tria durant un màxim d&rsquo;un any, no és cap rastrejador i només la llegeix aquest
          lloc. Tancar la barra d&rsquo;avís desa un indicador similar (
          <code>cadrumo_notice_ack</code>) al localStorage del teu navegador.
        </>,
        <>
          D&rsquo;acord amb l&rsquo;article 22.2 de la LSSI-CE i la guia sobre l&rsquo;ús de
          galetes de l&rsquo;AEPD, les galetes de preferències establertes a petició expressa
          de l&rsquo;usuari estan exemptes de consentiment previ; tot i això, les declarem
          aquí. Pots eliminar-les en qualsevol moment des de la configuració del teu navegador
          i el lloc funciona plenament sense elles.
        </>,
      ],
    },
    licences: {
      heading: 'Llicències i què distribueix aquest lloc',
      body: [
        <>
          Cadrumo és codi obert sota la <strong>Apache License 2.0</strong>. El codi
          d&rsquo;aquest lloc i del programari viu a{' '}
          <a href="https://github.com/nevenincs/cadrumo">github.com/nevenincs/cadrumo</a>.
        </>,
        <>
          La pàgina que estàs llegint distribueix React i ReactDOM (llicència MIT) i les
          tipografies Hanken Grotesk, Instrument Serif i JetBrains Mono (SIL Open Font License
          1.1), totes autoallotjades. L&rsquo;atribució completa és als avisos de tercers del
          repositori.
        </>,
      ],
    },
    liability: {
      heading: 'Garanties i responsabilitat',
      body: [
        <>
          El programari i aquest lloc es proporcionen «tal com són», sense garanties ni
          condicions de cap mena, segons les seccions 7 i 8 de la Apache License 2.0. Cadrumo
          és en beta: les funcions poden canviar i la cobertura fiscal no és completa.
          Verifica cada càlcul abans de presentar. En la mesura que ho permeti la llei
          aplicable, els autors no assumeixen responsabilitat per errors de càlcul, errors de
          presentació ni per cap dany derivat de l&rsquo;ús del programari o d&rsquo;aquest
          lloc.
        </>,
      ],
    },
  },
  cookieBanner: {
    ariaLabel: 'Avís de privadesa',
    message: (
      <>
        Aquest lloc no instal·la rastrejadors ni recull dades. Una galeta funcional desa el
        teu idioma, i només si en tries un.
      </>
    ),
    details: 'Avís legal i privadesa',
    dismiss: 'Entesos',
  },
  footer: {
    brandName: 'cadrumo',
    brandSummary:
      "Un assistent fiscal espanyol, impulsat per un motor determinista i un arnès d'agents.",
    columns: [
      { heading: 'Producte', labels: ['Instal·lar el plugin', 'Funcions', 'Com funciona'] },
      { heading: 'Documentació', labels: ['Guia ràpida', 'Primers passos', 'Arquitectura'] },
      { heading: 'Comunitat', labels: ['GitHub', 'PyPI: cadrumo', 'cadrumo.neve.md'] },
    ],
    disclaimerPill: 'cadrumo',
    disclaimerText:
      "és un projecte independent de codi obert (Apache-2.0). No està afiliat a l'AEAT i mai presenta declaracions; tu presentes a través dels canals oficials de l'AEAT i continues sent responsable de cada declaració.",
    legalLink: 'Avís legal, privadesa i galetes',
    copyright: '© 2026 Gergely Wootsch i els contribuïdors de cadrumo.',
  },
}
