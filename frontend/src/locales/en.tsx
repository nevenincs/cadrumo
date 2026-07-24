import type { Copy } from './types'

export const en: Copy = {
  languageLabel: 'Language',
  skipToContent: 'Skip to content',
  nav: {
    home: 'Cadrumo home',
    main: 'Main navigation',
    documentation: 'Documentation',
    github: 'GitHub',
    download: 'Download',
  },
  bannerAlt: 'A carefully arranged desk of folders, notes, and a calculator',
  hero: {
    heading: (
      <>
        Tax calculation engine, <em>assisted</em> by agents.
      </>
    ),
    lead1: (
      <>
        Cadrumo is an <strong className="accent">AEAT</strong>-compatible* Spanish tax
        calculation tool. It is a toolset for you and agents, like Claude or Codex and it helps
        you collaboratively file and manage tax obligation, your business ledger and tax
        calendar.
      </>
    ),
    lead2:
      'It was designed to be used as a Claude Cowork plugin so it can act as harness to manage your tax obligations in a collaborative capacity.',
    footnote: (
      <>
        * “AEAT compatible” describes only that Cadrumo computes against the published forms and
        rules of the Agencia Estatal de Administración Tributaria. Cadrumo is an independent
        project with no relation to the AEAT; see the <a href="#/legal">legal notice</a>.
      </>
    ),
  },
  harness: {
    kicker: 'But wait...what is an agent harness?',
    heading: 'MCP? CLI? Claude? A toolset for humans and LLMs',
    p1: (
      <>
        An agent harness is just a set of tools: rules, skills, and machine tools an AI
        assistant can use. Cadrumo is a bundle that contains rules based helpers for you and
        your LLM chatbot. Cadrumo ships a <strong className="accent">CLI</strong> direct
        command interface, the core engine used for tax calculations. We also ship a{' '}
        <strong className="accent">MCP</strong> that lets assistants use the bundled tools.
      </>
    ),
    p2: (
      <>
        <strong>Claude</strong> is one assistant that can work in this way. It can help you
        navigate records, ask Cadrumo to run a check, and explain the result in plain language.
        Cadrumo’s rule engine produces them. Claude does not replace the engine, submit
        anything to the AEAT, or decide what you should file.
      </>
    ),
  },
  download: {
    kicker: 'Download & Documentation',
    heading: 'Download',
    download: 'Download',
    readDocs: 'Read the documentation',
    disclaimerTitle: 'DISCLAIMER',
    disclaimerBody:
      'Cadrumo is independent software, not affiliated with the AEAT. It is not tax advice. Cadrumo does not support filing directly to AEAT. It is your responsibility to verify all calculations manually. We’re in beta. Features might change. Tax and modelo support is not complete. We cannot assume liability for wrong calculations or filing errors.',
  },
  pillars: {
    sectionLabel: 'What makes Cadrumo different',
    kicker: 'What makes Cadrumo different?',
    items: [
      {
        label: '01 / SECURE STORAGE',
        title: 'Local storage',
        description:
          'Transactions, invoices, and evidence stay in encrypted storage on your local machine. Cadrumo provides tools to help you prepare expense records and invoices for tax calculations - these are always safe.',
      },
      {
        label: '02 / MCP + CLI',
        title: 'Deterministic',
        description:
          'Cadrumo calculates figures using the bundled CLI, a deterministic calculation engine. An agent may help organize or explain the work but calculations are always processed by the engine, never by the agents themselves.',
      },
      {
        label: '03 / EXPORT CALCULATIONS FOR REVIEW',
        title: 'Reviewable',
        description:
          'You inspect the records, calculations, checks, and supporting evidences. You decide whether it is right. Instruct your agent to review, check and verify calculations but you’ll always have the means to verify and adjust details.',
      },
    ],
  },
  steps: {
    kicker: (
      <>
        What are the steps for preparing a <span lang="es">modelo</span>?
      </>
    ),
    heading: 'The calculation steps.',
    items: [
      {
        number: '01',
        title: 'Input',
        description:
          'Ask your agent to help you read and parse your financial statements or manually add them using the CLI.',
      },
      {
        number: '02',
        title: 'Classify, filter, split',
        description:
          'Classifies each ledger entry for IRPF and IVA calculations, rates, including mixed-use cases that need apportioning.',
      },
      {
        number: '03',
        title: 'Calculate and Verify',
        description: (
          <>
            Computes each <span lang="es">modelo</span> grounded in the BOE and the AEAT rules
            behind every <span lang="es">casilla</span>.
          </>
        ),
      },
      {
        number: '04',
        title: 'Export calculations for review',
        description:
          'We support Google Drive and XLS exports. Use these to verify calculations before approving a modelo’s values.',
      },
      {
        number: '05',
        title: 'Prepare submission',
        description:
          'Exports a file in the official format, ready for you to upload through AEAT.',
      },
      {
        number: '06',
        title: 'Reconcile against AEAT',
        description: (
          <>
            Reconciles your records against the <span lang="es">justificante</span> once a
            filing has been submitted.
          </>
        ),
      },
    ],
  },
  docsCta: {
    kicker: 'Documentation',
    heading: 'Learn more.',
    summary:
      'Guides, run-throughs, and reference for people filing their own taxes and the professionals who help them.',
    open: 'Open documentation',
    listLabel: 'Documentation sections',
    links: [
      {
        title: 'Quickstart',
        description: 'Install, configure, and prepare your first modelo.',
      },
      {
        title: 'Run through a filing year',
        description: 'Follow the income-tax and IVA years, modelo by modelo.',
      },
      {
        title: 'Getting started',
        description: 'Routes you to the right guide for each filing task.',
      },
      {
        title: 'How it works',
        description: 'The harness, the engine, and the split between them.',
      },
      {
        title: 'Architecture overview',
        description: 'How the pieces fit and where your data lives.',
      },
    ],
  },
  legal: {
    linkLabel: 'Legal notice, privacy & cookies',
    title: 'Legal notice, privacy & cookies',
    updated: 'Last updated: 12 July 2026',
    backToHome: 'Back to the home page',
    identity: {
      heading: 'Site operator',
      body: [
        <>
          This website, <strong>cadrumo.neve.md</strong>, and the <strong>neve.md</strong>{' '}
          domain are published by <strong>Neve Nincs</strong>, the individual behind
          neve.md and the Cadrumo project, a non-commercial open-source effort. This
          identification is provided in view of Article 10 of Spain’s Ley 34/2002 (LSSI-CE)
          to the extent it applies to a non-commercial project; further identification
          details are available on request through the contact channel below.
        </>,
        <>
          Contact: <a href="mailto:hello@neve.md">hello@neve.md</a>, or through the project’s
          canonical repository,{' '}
          <a href="https://github.com/nevenincs/cadrumo">github.com/nevenincs/cadrumo</a> (issues and
          security contacts are listed there).
        </>,
      ],
    },
    nonAffiliation: {
      heading: 'No relation to the AEAT',
      body: [
        <>
          Cadrumo is an <strong>independent open-source project</strong>. It is not a product
          of, and is not affiliated with, endorsed by, sponsored by, or approved by the Agencia
          Estatal de Administración Tributaria (AEAT) or any other public administration. It is
          not official software and does not replace the AEAT’s own tools.
        </>,
        <>
          References on this site and in the software to “AEAT”, to modelo numbers (such as
          100, 130 or 303) and to casillas are purely descriptive: they name the official
          public forms and rules the software computes against. All official names and marks
          remain the property of their respective holders. Taxes are filed only through the
          AEAT’s own official channels; Cadrumo never files anything on your behalf. The
          asterisk after “AEAT compatible” on the home page refers to this notice.
        </>,
      ],
    },
    noAdvice: {
      heading: 'Not tax advice',
      body: [
        <>
          Cadrumo computes and checks figures from published rules; it does not assess your
          personal situation and does not constitute tax, legal, or financial advice. When in
          doubt, consult a qualified professional. You remain responsible for every
          declaration you file.
        </>,
      ],
    },
    privacy: {
      heading: 'Privacy: we collect nothing',
      body: [
        <>
          This website <strong>collects no personal data</strong>. There are no accounts, no
          forms, no analytics, no advertising, no tracking pixels and no fingerprinting, and
          nothing is shared with or requested from any third party. Every asset on this page,
          including its fonts, is served first-party from this domain.
        </>,
        <>
          The site is a set of static files delivered from Amazon Web Services infrastructure
          (S3 and CloudFront). Our configuration enables no access logging: connection data
          such as your IP address is processed transiently by that infrastructure only as
          technically necessary to deliver the page, and we neither enable, receive, nor store
          access logs.
        </>,
        <>
          The Cadrumo software follows the same policy: your financial records stay in
          encrypted storage on your own machine, and the software sends no telemetry to us.
          See the project’s{' '}
          <a href="https://github.com/nevenincs/cadrumo/blob/main/PRIVACY.md">privacy policy</a>.
        </>,
        <>
          Because we hold no personal data about you, data-subject requests under Articles
          15–22 of the GDPR have nothing to operate on. If you believe otherwise, contact us
          through the repository and we will respond.
        </>,
      ],
    },
    cookies: {
      heading: 'Cookies',
      body: [
        <>
          The site sets a single first-party functional cookie, <code>cadrumo_lang</code>, and
          only if you explicitly pick a language. It stores that choice for up to one year, is
          not a tracker, and is read by nothing but this site. Dismissing the notice bar
          stores a similar flag (<code>cadrumo_notice_ack</code>) in your browser’s
          localStorage.
        </>,
        <>
          Under Article 22.2 of the LSSI-CE and the AEPD’s cookie guidance, preference cookies
          set at your explicit request are exempt from prior consent; we disclose them here
          all the same. You can delete them at any time from your browser settings, and the
          site works fully without them.
        </>,
      ],
    },
    licences: {
      heading: 'Licences and what this site ships',
      body: [
        <>
          Cadrumo is open source under the <strong>Apache License 2.0</strong>. The source of
          this website and of the software lives at{' '}
          <a href="https://github.com/nevenincs/cadrumo">github.com/nevenincs/cadrumo</a>.
        </>,
        <>
          The page you are reading ships React and ReactDOM (MIT licence) and the typefaces
          Hanken Grotesk, Instrument Serif and JetBrains Mono (SIL Open Font License 1.1), all
          self-hosted. Full attribution lives in the repository’s third-party notices.
        </>,
      ],
    },
    liability: {
      heading: 'Warranty and liability',
      body: [
        <>
          The software and this website are provided “as is”, without warranties or conditions
          of any kind, as set out in sections 7 and 8 of the Apache License 2.0. Cadrumo is in
          beta: features can change and tax coverage is not complete. Verify every calculation
          before filing. To the extent permitted by applicable law, the authors accept no
          liability for calculation errors, filing errors, or any damages arising from the use
          of the software or this site.
        </>,
      ],
    },
  },
  cookieBanner: {
    ariaLabel: 'Privacy notice',
    message: (
      <>
        This site sets no trackers and collects no data. One functional cookie stores your
        language, and only if you pick one.
      </>
    ),
    details: 'Legal & privacy',
    dismiss: 'Understood',
  },
  footer: {
    brandName: 'cadrumo',
    brandSummary:
      'A Spanish tax-filing assistant, driven by a deterministic engine and an agent harness.',
    columns: [
      { heading: 'Product', labels: ['Install plugin', 'Capabilities', 'How it works'] },
      { heading: 'Docs', labels: ['Quickstart', 'Getting started', 'Architecture'] },
      { heading: 'Community', labels: ['GitHub', 'PyPI: cadrumo', 'cadrumo.neve.md'] },
    ],
    disclaimerPill: 'cadrumo',
    disclaimerText:
      "is an independent open-source project (Apache-2.0). It is not affiliated with AEAT and never submits filings; you file through AEAT's official channels and remain responsible for every declaration.",
    legalLink: 'Legal notice, privacy & cookies',
    copyright: '© 2026 Neve Nincs and the cadrumo contributors.',
  },
}
