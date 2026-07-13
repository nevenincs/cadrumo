import { useEffect, useState } from 'react'

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
import { availableLocales, useLocale } from './i18n'
import type { LocaleCode } from './i18n'

const docsBaseUrl = 'https://cadrumo.neve.md/docs'
const docsUrl = `${docsBaseUrl}/index.html`
const repositoryUrl = 'https://github.com/nevenincs/cadrumo'
const downloadUrl = 'https://pypi.org/project/cadrumo/'
const siteUrl = 'https://cadrumo.neve.md'

// Structural (non-localizable) data, zipped by index with the locale copy.
const stepMeta = [
  { href: `${docsBaseUrl}/how-to/import-bank-statements.html`, icon: stepInput },
  { href: `${docsBaseUrl}/how-to/classify-transactions.html`, icon: stepClassify },
  { href: `${docsBaseUrl}/explanation/from-records-to-figures.html`, icon: stepCalculate },
  { href: `${docsBaseUrl}/how-to/review-with-google-sheets.html`, icon: stepExport },
  { href: `${docsBaseUrl}/how-to/file-at-aeat.html#step-2-export-the-filing-file`, icon: stepSubmit },
  { href: `${docsBaseUrl}/how-to/reconcile.html`, icon: stepReconcile },
]

const docLinkHrefs = [
  `${docsBaseUrl}/how-to/quickstart.html`,
  `${docsBaseUrl}/how-to/index.html#run-through-a-filing-year`,
  `${docsBaseUrl}/how-to/index.html`,
  `${docsBaseUrl}/explanation/index.html`,
  `${docsBaseUrl}/architecture/index.html`,
]

const footerColumnHrefs: readonly (readonly [string, string, string])[] = [
  [downloadUrl, '#steps', '#harness'],
  [
    `${docsBaseUrl}/how-to/quickstart.html`,
    `${docsBaseUrl}/how-to/index.html`,
    `${docsBaseUrl}/architecture/index.html`,
  ],
  [repositoryUrl, downloadUrl, siteUrl],
]

const legalSectionKeys = [
  'identity',
  'nonAffiliation',
  'noAdvice',
  'privacy',
  'cookies',
  'licences',
  'liability',
] as const

const noticeAckStorageKey = 'cadrumo_notice_ack'

function useHashRoute(): string {
  const [hash, setHash] = useState(() => window.location.hash)
  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  return hash
}

function useScrollReveal(route: string) {
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
  }, [route])
}

function useScrollEffects(route: string) {
  useEffect(() => {
    const bar = document.querySelector<HTMLElement>('.scroll-progress')
    const header = document.querySelector<HTMLElement>('.site-header')
    const bannerElement = document.querySelector<HTMLElement>('.banner img')
    const allowMotion = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let frame = 0
    const update = () => {
      const root = document.documentElement
      const max = root.scrollHeight - root.clientHeight
      const top = root.scrollTop
      if (bar) bar.style.transform = `scaleX(${max > 0 ? top / max : 0})`
      header?.classList.toggle('is-scrolled', top > 8)
      if (allowMotion && bannerElement) {
        bannerElement.style.transform = `translateY(${Math.min(top * 0.12, 28)}px) scale(1.18)`
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
  }, [route])
}

function NoticeBanner() {
  const { copy } = useLocale()
  const [visible, setVisible] = useState(() => {
    try {
      return window.localStorage.getItem(noticeAckStorageKey) !== '1'
    } catch {
      return true
    }
  })
  if (!visible) return null
  const dismiss = () => {
    try {
      window.localStorage.setItem(noticeAckStorageKey, '1')
    } catch {
      // Storage unavailable: the banner simply reappears next visit.
    }
    setVisible(false)
  }
  return (
    <aside className="notice-banner" role="region" aria-label={copy.cookieBanner.ariaLabel}>
      <p className="notice-banner-text">
        {copy.cookieBanner.message} <a href="#/legal">{copy.cookieBanner.details}</a>
      </p>
      <button className="button button-primary notice-banner-dismiss" type="button" onClick={dismiss}>
        {copy.cookieBanner.dismiss}
      </button>
    </aside>
  )
}

function LegalPage() {
  const { copy } = useLocale()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [])
  return (
    <article className="legal-page page-container" aria-labelledby="legal-heading">
      <p className="kicker">{copy.legal.updated}</p>
      <h1 id="legal-heading">{copy.legal.title}</h1>
      {legalSectionKeys.map((key) => {
        const section = copy.legal[key]
        return (
          <section className="legal-section" id={`legal-${key}`} key={key}>
            <h2>{section.heading}</h2>
            {section.body.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </section>
        )
      })}
      <a className="button button-secondary legal-back" href="#top">
        {copy.legal.backToHome}
      </a>
    </article>
  )
}

function LanguagePicker() {
  const { copy, locale, setLocale } = useLocale()
  return (
    <select
      className="lang-select"
      aria-label={copy.languageLabel}
      value={locale}
      onChange={(event) => setLocale(event.target.value as LocaleCode)}
    >
      {availableLocales.map((option) => (
        <option key={option.code} value={option.code} lang={option.code} aria-label={option.name}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

export function App() {
  const { copy } = useLocale()
  const route = useHashRoute()
  const isLegalRoute = route.startsWith('#/legal')
  useScrollReveal(route)
  useScrollEffects(route)

  return (
    <div className="site-shell">
      <a className="skip-link" href="#top">
        {copy.skipToContent}
      </a>
      <header className="site-header">
        <span className="scroll-progress" aria-hidden="true" />
        <div className="page-container header-content">
          <a className="brand" href="#top" aria-label={copy.nav.home}>
            <img className="brand-logo" src={logo} alt="" aria-hidden="true" />
            <span className="brand-wordmark">CADRUMO</span>
          </a>
          <nav className="header-links" aria-label={copy.nav.main}>
            <a className="button button-ghost" href={docsUrl}>
              {copy.nav.documentation}
            </a>
            <a className="button button-ghost" href={repositoryUrl}>
              {copy.nav.github}
            </a>
            <a className="button button-primary" href={downloadUrl}>
              {copy.nav.download}
            </a>
            <LanguagePicker />
          </nav>
        </div>
      </header>

      <main id="top">
        {isLegalRoute ? (
          <LegalPage />
        ) : (
          <>
        <div className="banner">
          <img src={bannerImage} alt={copy.bannerAlt} />
        </div>

        <section className="hero page-container" aria-labelledby="hero-heading">
          <h1 id="hero-heading">{copy.hero.heading}</h1>
          <p className="hero-lead">{copy.hero.lead1}</p>
          <p className="hero-lead">{copy.hero.lead2}</p>
          <p className="hero-footnote">{copy.hero.footnote}</p>
        </section>

        <section id="harness" className="harness" aria-labelledby="harness-heading">
          <p className="kicker">{copy.harness.kicker}</p>
          <div className="harness-row" data-reveal>
            <div className="harness-figure" aria-hidden="true">
              <img src={harnessIllustration} alt="" />
            </div>
            <div className="harness-copy">
              <h2 id="harness-heading">{copy.harness.heading}</h2>
              <p>{copy.harness.p1}</p>
              <p>{copy.harness.p2}</p>
            </div>
          </div>
        </section>

        <section id="download" className="download page-container" aria-labelledby="download-heading">
          <p className="kicker">{copy.download.kicker}</p>
          <div className="download-card" data-reveal>
            <h2 id="download-heading">{copy.download.heading}</h2>
            <div className="download-actions">
              <a className="button button-primary" href={downloadUrl}>
                {copy.download.download}
              </a>
              <a className="button button-secondary" href={docsUrl}>
                {copy.download.readDocs}
              </a>
            </div>
            <aside className="trust-note">
              <p className="trust-note-title">{copy.download.disclaimerTitle}</p>
              <p>{copy.download.disclaimerBody}</p>
            </aside>
          </div>
        </section>

        <section className="pillars" aria-label={copy.pillars.sectionLabel}>
          <p className="kicker">{copy.pillars.kicker}</p>
          <div className="pillars-row">
            {copy.pillars.items.map((pillar, index) => (
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
            <p className="kicker">{copy.steps.kicker}</p>
            <h2 id="steps-heading">{copy.steps.heading}</h2>
            <div className="steps-grid">
              {copy.steps.items.map((step, index) => (
                <article
                  className="step-card"
                  key={step.number}
                  data-reveal
                  style={{ transitionDelay: `${(index % 3) * 90}ms` }}
                >
                  <img className="step-icon" src={stepMeta[index].icon} alt="" aria-hidden="true" />
                  <h3 className="step-title">
                    {step.number}{' '}
                    <a href={stepMeta[index].href} target="_blank" rel="noreferrer">
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
              <img src={iconDocs} alt="" aria-hidden="true" />
              {copy.docsCta.kicker}
            </p>
            <h2 id="docs-heading">{copy.docsCta.heading}</h2>
            <p className="docs-cta-summary">{copy.docsCta.summary}</p>
            <a className="button button-primary" href={docsUrl}>
              {copy.docsCta.open}
              <img src={iconArrowCta} alt="" aria-hidden="true" />
            </a>
          </div>
          <nav className="docs-cta-list" aria-label={copy.docsCta.listLabel}>
            {copy.docsCta.links.map((link, index) => (
              <a
                className="docs-link"
                href={docLinkHrefs[index]}
                key={link.title}
                data-reveal
                style={{ transitionDelay: `${index * 70}ms` }}
              >
                <span className="docs-link-text">
                  <span className="docs-link-title">{link.title}</span>
                  <span className="docs-link-description">{link.description}</span>
                </span>
                <img src={iconArrowLink} alt="" aria-hidden="true" />
              </a>
            ))}
          </nav>
        </section>
          </>
        )}
      </main>

      <footer className="site-footer">
        <div className="page-container footer-content">
          <div className="footer-columns">
            <div className="footer-brand">
              <p className="footer-brand-name">{copy.footer.brandName}</p>
              <p className="footer-brand-summary">{copy.footer.brandSummary}</p>
            </div>
            {copy.footer.columns.map((column, columnIndex) => (
              <nav className="footer-column" key={column.heading} aria-label={column.heading}>
                <p className="footer-heading">{column.heading}</p>
                <ul>
                  {column.labels.map((label, labelIndex) => (
                    <li key={label}>
                      <a href={footerColumnHrefs[columnIndex][labelIndex]}>{label}</a>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
          <div className="footer-legal">
            <p className="footer-disclaimer">
              <span className="aeat-pill">{copy.footer.disclaimerPill}</span>{' '}
              {copy.footer.disclaimerText}
            </p>
            <p className="footer-legal-links">
              <a href="#/legal">{copy.footer.legalLink}</a>
            </p>
            <p className="footer-copyright">{copy.footer.copyright}</p>
          </div>
        </div>
      </footer>
      <NoticeBanner />
    </div>
  )
}
