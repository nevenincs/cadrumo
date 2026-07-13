import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { JSDOM } from 'jsdom'
import { describe, expect, it } from 'vitest'

const errorPageHtml = readFileSync(resolve(process.cwd(), 'public/404.html'), 'utf-8')
const indexHtml = readFileSync(resolve(process.cwd(), 'index.html'), 'utf-8')

function renderErrorPage(lang?: string): JSDOM {
  const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
    runScripts: 'dangerously',
    url: 'https://cadrumo.neve.md/missing',
  })
  if (lang) dom.window.document.cookie = `cadrumo_lang=${lang}`
  dom.window.document.open()
  dom.window.document.write(errorPageHtml)
  dom.window.document.close()
  return dom
}

describe('404 page localization', () => {
  it('stays English without a language cookie', () => {
    const dom = renderErrorPage()
    expect(dom.window.document.querySelector('h2')?.textContent).toContain(
      'doesn’t exist',
    )
  })

  it('localizes to Spanish from the cadrumo_lang cookie', () => {
    const dom = renderErrorPage('es')
    expect(dom.window.document.querySelector('h2')?.textContent).toBe('Esta casilla no existe.')
    expect(dom.window.document.title).toBe('Casilla no encontrada - Cadrumo')
    expect(dom.window.document.documentElement.lang).toBe('es')
    expect(dom.window.document.querySelector('.button-primary')?.textContent).toBe(
      'Volver a Cadrumo',
    )
  })

  it('localizes to Catalan from the cadrumo_lang cookie', () => {
    const dom = renderErrorPage('ca')
    expect(dom.window.document.querySelector('h2')?.textContent).toBe(
      'Aquesta casella no existeix.',
    )
    expect(dom.window.document.documentElement.lang).toBe('ca')
  })
})

describe('landing head metadata', () => {
  const dom = new JSDOM(indexHtml)
  const head = dom.window.document.head

  it('carries parseable JSON-LD naming the software and its provenance', () => {
    const raw = head.querySelector('script[type="application/ld+json"]')?.textContent
    expect(raw).toBeTruthy()
    const graph = JSON.parse(raw as string)['@graph'] as Array<Record<string, unknown>>
    const software = graph.find((node) => node['@type'] === 'SoftwareApplication')
    expect(software?.downloadUrl).toBe('https://pypi.org/project/cadrumo/')
    expect(software?.softwareHelp).toBe('https://cadrumo.neve.md/docs/')
    expect(software?.license).toBe('https://www.apache.org/licenses/LICENSE-2.0')
  })

  it('declares the canonical URL and language alternates', () => {
    expect(head.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(
      'https://cadrumo.neve.md/',
    )
    const hreflangs = [...head.querySelectorAll('link[rel="alternate"]')].map((link) =>
      link.getAttribute('hreflang'),
    )
    expect(hreflangs).toEqual(expect.arrayContaining(['en', 'x-default']))
  })
})
