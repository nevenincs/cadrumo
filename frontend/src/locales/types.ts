import type { ReactNode } from 'react'

export interface PillarCopy {
  label: string
  title: string
  description: string
}

export interface StepCopy {
  number: string
  title: string
  description: ReactNode
}

export interface DocLinkCopy {
  title: string
  description: string
}

export interface FooterColumnCopy {
  heading: string
  labels: readonly [string, string, string]
}

export interface LegalSectionCopy {
  heading: string
  body: readonly ReactNode[]
}

export interface LegalCopy {
  linkLabel: string
  title: string
  updated: string
  backToHome: string
  identity: LegalSectionCopy
  nonAffiliation: LegalSectionCopy
  noAdvice: LegalSectionCopy
  privacy: LegalSectionCopy
  cookies: LegalSectionCopy
  licences: LegalSectionCopy
  liability: LegalSectionCopy
}

export interface CookieBannerCopy {
  ariaLabel: string
  message: ReactNode
  details: string
  dismiss: string
}

export interface Copy {
  languageLabel: string
  skipToContent: string
  nav: {
    home: string
    main: string
    documentation: string
    github: string
    download: string
  }
  bannerAlt: string
  hero: {
    heading: ReactNode
    lead1: ReactNode
    lead2: string
    footnote: ReactNode
  }
  harness: {
    kicker: string
    heading: string
    p1: ReactNode
    p2: ReactNode
  }
  download: {
    kicker: string
    heading: string
    download: string
    readDocs: string
    disclaimerTitle: string
    disclaimerBody: string
  }
  pillars: {
    sectionLabel: string
    kicker: ReactNode
    items: readonly [PillarCopy, PillarCopy, PillarCopy]
  }
  steps: {
    kicker: ReactNode
    heading: string
    items: readonly StepCopy[]
  }
  docsCta: {
    kicker: string
    heading: string
    summary: string
    open: string
    listLabel: string
    links: readonly DocLinkCopy[]
  }
  legal: LegalCopy
  cookieBanner: CookieBannerCopy
  footer: {
    brandName: string
    brandSummary: string
    columns: readonly FooterColumnCopy[]
    disclaimerPill: string
    disclaimerText: string
    legalLink: string
    copyright: string
  }
}
