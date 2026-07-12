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
        Cadrumo is a <strong className="accent">AEAT</strong> compatible* Spanish tax
        calculation tool. It is a toolset for you and agents, like Claude or Codex and it helps
        you collaboratively file and manage tax obligation, your business ledger and tax
        calendar.
      </>
    ),
    lead2:
      'It was designed to be used as a Claude Cowork plugin so it can act as harness to manage your tax obligations in a collaborative capacity.',
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
      'Cadrumo is independent software, not affiliated with the AEAT. It does not constitute as tax advice. Cadrumo does not support filing directly to AEAT. It is your responsibility to verify all calculations manually. We’re in beta. Features might change. Tax and modelo support is not complete. We cannot assume liability for wrong calculation, filing errors.',
  },
  pillars: {
    sectionLabel: 'What makes Cadrumo different',
    kicker: (
      <>
        What are the steps for preparing a <span lang="es">modelo</span>?
      </>
    ),
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
      'Guides, tutorials, and reference for people filing their own taxes and the professionals who help them.',
    open: 'Open documentation',
    listLabel: 'Documentation sections',
    links: [
      {
        title: 'Quickstart',
        description: 'Install, configure, and prepare your first modelo.',
      },
      {
        title: 'Tutorial: a Modelo 130 end to end',
        description: 'Follow one filing from records to export.',
      },
      {
        title: 'How-to guides',
        description: 'Task-focused recipes for common filing situations.',
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
  footer: {
    brandName: 'cadrumo',
    brandSummary:
      'A Spanish tax-filing assistant, driven by a deterministic engine and an agent harness.',
    columns: [
      { heading: 'Product', labels: ['Install plugin', 'Capabilities', 'How it works'] },
      { heading: 'Docs', labels: ['Quickstart', 'Tutorial', 'Architecture'] },
      { heading: 'Community', labels: ['GitHub', 'PyPI: aeat-cli', 'cadrumo.neve.md'] },
    ],
    disclaimerPill: 'cadrumo',
    disclaimerText:
      "is an independent open-source project (Apache-2.0). It is not affiliated with AEAT and never submits filings; you file through AEAT's official channels and remain responsible for every declaration.",
    copyright: '© 2026 the cadrumo authors.',
  },
}
