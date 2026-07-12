import { useEffect } from 'react'

import bannerImage from './assets/cadrumo/banner.png'
import harnessIllustration from './assets/cadrumo/harness-illustration.png'
import iconArrowCta from './assets/cadrumo/icon-arrow-cta.svg'
import iconArrowLink from './assets/cadrumo/icon-arrow-link.svg'
import iconDocs from './assets/cadrumo/icon-docs.svg'
import logo from './assets/cadrumo/logo.svg'
import stepCalculate from './assets/cadrumo/step-calculate.svg'
import stepClassify from './assets/cadrumo/step-classify.svg'
import stepExport from './assets/cadrumo/step-export.svg'
import stepInput from './assets/cadrumo/step-input.svg'
import stepReconcile from './assets/cadrumo/step-reconcile.svg'
import stepSubmit from './assets/cadrumo/step-submit.svg'

const docsBaseUrl = 'https://cadrumo.neve.md/docs'
const docsUrl = `${docsBaseUrl}/index.html`
const repositoryUrl = 'https://github.com/nevenincs/aeat'
const downloadUrl = 'https://pypi.org/project/aeat-cli/'
const siteUrl = 'https://cadrumo.neve.md'

const pillars = [
  {
    description:
      'Transactions, invoices, and evidence stay in encrypted storage on your local machine. Cadrumo provides tools to help you prepare expense records and invoices for tax calculations - these are always safe.',
    label: '01 / SECURE STORAGE',
    title: 'Local storage',
  },
  {
    description:
      'Cadrumo calculates figures using the bundled CLI, a deterministic calculation engine. An agent may help organize or explain the work but calculations are always processed by the engine, never by the agents themselves.',
    label: '02 / MCP + CLI',
    title: 'Deterministic',
  },
  {
    description:
      'You inspect the records, calculations, checks, and supporting evidences. You decide whether it is right. Instruct your agent to review, check and verify calculations but you’ll always have the means to verify and adjust details.',
    label: '03 / EXPORT CALCULATIONS FOR REVIEW',
    title: 'Reviewable',
  },
]

const calculationSteps = [
  {
    description:
      'Ask your agent to help you read and parse your financial statements or manually add them using the CLI.',
    href: `${docsBaseUrl}/how-to/import-bank-statements.html`,
    icon: stepInput,
    number: '01',
    title: 'Input',
  },
  {
    description:
      'Classifies each ledger entry for IRPF and IVA calculations, rates, including mixed-use cases that need apportioning.',
    href: `${docsBaseUrl}/how-to/classify-transactions.html`,
    icon: stepClassify,
    number: '02',
    title: 'Classify, filter, split',
  },
  {
    description:
      'Computes each modelo grounded in the BOE and the AEAT rules behind every casilla.',
    href: `${docsBaseUrl}/explanation/from-records-to-figures.html`,
    icon: stepCalculate,
    number: '03',
    title: 'Calculate and Verify',
  },
  {
    description:
      'We support Google Drive and XLS exports. Use these to verify calculations before approving a modelo’s values.',
    href: `${docsBaseUrl}/how-to/review-with-google-sheets.html`,
    icon: stepExport,
    number: '04',
    title: 'Export calculations for review',
  },
  {
    description:
      'Exports a file in the official format, ready for you to upload through AEAT.',
    href: `${docsBaseUrl}/how-to/file-at-aeat.html#step-2-export-the-filing-file`,
    icon: stepSubmit,
    number: '05',
    title: 'Prepare submission',
  },
  {
    description:
      'Reconciles your records against the justificante once a filing has been submitted.',
    href: `${docsBaseUrl}/how-to/reconcile.html`,
    icon: stepReconcile,
    number: '06',
    title: 'Reconcile against AEAT',
  },
]

const documentationLinks = [
  {
    description: 'Install, configure, and prepare your first modelo.',
    href: `${docsBaseUrl}/how-to/quickstart.html`,
    title: 'Quickstart',
  },
  {
    description: 'Follow one filing from records to export.',
    href: `${docsBaseUrl}/tutorials/index.html`,
    title: 'Tutorial: a Modelo 130 end to end',
  },
  {
    description: 'Task-focused recipes for common filing situations.',
    href: `${docsBaseUrl}/how-to/index.html`,
    title: 'How-to guides',
  },
  {
    description: 'The harness, the engine, and the split between them.',
    href: `${docsBaseUrl}/explanation/index.html`,
    title: 'How it works',
  },
  {
    description: 'How the pieces fit and where your data lives.',
    href: `${docsBaseUrl}/architecture/index.html`,
    title: 'Architecture overview',
  },
]

const footerColumns = [
  {
    heading: 'Product',
    links: [
      ['Install plugin', downloadUrl],
      ['Capabilities', '#steps'],
      ['How it works', '#harness'],
    ],
  },
  {
    heading: 'Docs',
    links: [
      ['Quickstart', `${docsBaseUrl}/how-to/quickstart.html`],
      ['Tutorial', `${docsBaseUrl}/tutorials/index.html`],
      ['Architecture', `${docsBaseUrl}/architecture/index.html`],
    ],
  },
  {
    heading: 'Community',
    links: [
      ['GitHub', repositoryUrl],
      ['PyPI: aeat-cli', downloadUrl],
      ['cadrumo.neve.md', siteUrl],
    ],
  },
]

function useScrollReveal() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const elements = Array.from(document.querySelectorAll('[data-reveal]'))
    for (const element of elements) element.classList.add('reveal-init')
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-revealed')
            observer.unobserve(entry.target)
          }
        }
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.1 },
    )
    for (const element of elements) observer.observe(element)
    return () => observer.disconnect()
  }, [])
}

function useScrollEffects() {
  useEffect(() => {
    const bar = document.querySelector<HTMLElement>('.scroll-progress')
    const header = document.querySelector<HTMLElement>('.site-header')
    const bannerImage = document.querySelector<HTMLElement>('.banner img')
    const allowMotion = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let frame = 0
    const update = () => {
      const root = document.documentElement
      const max = root.scrollHeight - root.clientHeight
      const top = root.scrollTop
      if (bar) bar.style.transform = `scaleX(${max > 0 ? top / max : 0})`
      header?.classList.toggle('is-scrolled', top > 8)
      if (allowMotion && bannerImage) {
        bannerImage.style.transform = `translateY(${Math.min(top * 0.12, 28)}px) scale(1.18)`
      }
      frame = 0
    }
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])
}

export function App() {
  useScrollReveal()
  useScrollEffects()

  return (
    <div className="site-shell">
      <a className="skip-link" href="#top">
        Skip to content
      </a>
      <header className="site-header">
        <span className="scroll-progress" aria-hidden="true" />
        <div className="page-container header-content">
          <a className="brand" href="#top" aria-label="Cadrumo home">
            <img className="brand-logo" src={logo} alt="" />
            <span className="brand-wordmark">CADRUMO</span>
          </a>
          <nav className="header-links" aria-label="Main navigation">
            <a className="button button-ghost" href={docsUrl}>
              Documentation
            </a>
            <a className="button button-ghost" href={repositoryUrl}>
              GitHub
            </a>
            <a className="button button-primary" href={downloadUrl}>
              Download
            </a>
          </nav>
        </div>
      </header>

      <main id="top">
        <div className="banner">
          <img src={bannerImage} alt="A carefully arranged desk of folders, notes, and a calculator" />
        </div>

        <section className="hero page-container" aria-labelledby="hero-heading">
          <h1 id="hero-heading">
            Tax calculation engine, <em>assisted</em> by agents.
          </h1>
          <p className="hero-lead">
            Cadrumo is a <strong className="accent">AEAT</strong> compatible* Spanish tax
            calculation tool. It is a toolset for you and agents, like Claude or Codex and it
            helps you collaboratively file and manage tax obligation, your business ledger and
            tax calendar.
          </p>
          <p className="hero-lead">
            It was designed to be used as a Claude Cowork plugin so it can act as harness to
            manage your tax obligations in a collaborative capacity.
          </p>
        </section>

        <section id="harness" className="harness" aria-labelledby="harness-heading">
          <p className="kicker">But wait...what is an agent harness?</p>
          <div className="harness-row" data-reveal>
            <div className="harness-figure" aria-hidden="true">
              <img src={harnessIllustration} alt="" />
            </div>
            <div className="harness-copy">
              <h2 id="harness-heading">MCP? CLI? Claude? A toolset for humans and LLMs</h2>
              <p>
                An agent harness is just a set of tools: rules, skills, and machine tools an AI
                assistant can use. Cadrumo is a bundle that contains rules based helpers for you
                and your LLM chatbot. Cadrumo ships a <strong className="accent">CLI</strong>{' '}
                direct command interface, the core engine used for tax calculations. We also
                ship a <strong className="accent">MCP</strong> that lets assistants use the
                bundled tools.
              </p>
              <p>
                <strong>Claude</strong> is one assistant that can work in this way. It can help
                you navigate records, ask Cadrumo to run a check, and explain the result in
                plain language. Cadrumo’s rule engine produces them. Claude does not replace the
                engine, submit anything to the AEAT, or decide what you should file.
              </p>
            </div>
          </div>
        </section>

        <section id="download" className="download page-container" aria-labelledby="download-heading">
          <p className="kicker">Download &amp; Documentation</p>
          <div className="download-card" data-reveal>
            <h2 id="download-heading">Download</h2>
            <div className="download-actions">
              <a className="button button-primary" href={downloadUrl}>
                Download
              </a>
              <a className="button button-secondary" href={docsUrl}>
                Read the documentation
              </a>
            </div>
            <aside className="trust-note">
              <p className="trust-note-title">DISCLAIMER</p>
              <p>
                Cadrumo is independent software, not affiliated with the AEAT. It does not
                constitute as tax advice. Cadrumo does not support filing directly to AEAT. It
                is your responsibility to verify all calculations manually. We’re in beta.
                Features might change. Tax and modelo support is not complete. We cannot assume
                liability for wrong calculation, filing errors.
              </p>
            </aside>
          </div>
        </section>

        <section className="pillars" aria-label="What makes Cadrumo different">
          <p className="kicker">What are the steps for preparing a modelo?</p>
          <div className="pillars-row">
            {pillars.map((pillar, index) => (
              <article
                className="pillar"
                key={pillar.title}
                data-reveal
                style={{ transitionDelay: `${index * 90}ms` }}
              >
                <p className="pillar-label">{pillar.label}</p>
                <h3>{pillar.title}</h3>
                <p className="pillar-description">{pillar.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="steps" className="steps" aria-labelledby="steps-heading">
          <div className="page-container steps-content">
            <p className="kicker">What are the steps for preparing a modelo?</p>
            <h2 id="steps-heading">The calculation steps.</h2>
            <div className="steps-grid">
              {calculationSteps.map((step, index) => (
                <article
                  className="step-card"
                  key={step.number}
                  data-reveal
                  style={{ transitionDelay: `${(index % 3) * 90}ms` }}
                >
                  <img className="step-icon" src={step.icon} alt="" />
                  <h3 className="step-title">
                    {step.number}{' '}
                    <a href={step.href} target="_blank" rel="noreferrer">
                      {step.title}
                    </a>
                  </h3>
                  <p className="step-description">{step.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="docs-cta" aria-labelledby="docs-heading">
          <div className="docs-cta-intro" data-reveal>
            <p className="kicker kicker-with-icon">
              <img src={iconDocs} alt="" />
              Documentation
            </p>
            <h2 id="docs-heading">Learn more.</h2>
            <p className="docs-cta-summary">
              Guides, tutorials, and reference for people filing their own taxes and the
              professionals who help them.
            </p>
            <a className="button button-primary" href={docsUrl}>
              Open documentation
              <img src={iconArrowCta} alt="" />
            </a>
          </div>
          <nav className="docs-cta-list" aria-label="Documentation sections">
            {documentationLinks.map((link, index) => (
              <a
                className="docs-link"
                href={link.href}
                key={link.title}
                data-reveal
                style={{ transitionDelay: `${index * 70}ms` }}
              >
                <span className="docs-link-text">
                  <span className="docs-link-title">{link.title}</span>
                  <span className="docs-link-description">{link.description}</span>
                </span>
                <img src={iconArrowLink} alt="" />
              </a>
            ))}
          </nav>
        </section>
      </main>

      <footer className="site-footer">
        <div className="page-container footer-content">
          <div className="footer-columns">
            <div className="footer-brand">
              <p className="footer-brand-name">cadrumo</p>
              <p className="footer-brand-summary">
                A Spanish tax-filing assistant, driven by a deterministic engine and an agent
                harness.
              </p>
            </div>
            {footerColumns.map((column) => (
              <div className="footer-column" key={column.heading}>
                <p className="footer-heading">{column.heading}</p>
                <ul>
                  {column.links.map(([label, href]) => (
                    <li key={label}>
                      <a href={href}>{label}</a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="footer-legal">
            <p className="footer-disclaimer">
              <span className="aeat-pill">cadrumo</span> is an independent open-source project
              (Apache-2.0). It is not affiliated with AEAT and never submits filings; you file
              through AEAT's official channels and remain responsible for every declaration.
            </p>
            <p className="footer-copyright">© 2026 the cadrumo authors.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
