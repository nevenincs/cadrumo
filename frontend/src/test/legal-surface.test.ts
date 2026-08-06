import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const root = join(__dirname, '..', '..')

function read(relative: string): string {
  return readFileSync(join(root, relative), 'utf-8')
}

// The privacy posture published on the legal page and in PRIVACY.md states
// that visiting the site triggers no third-party requests. These checks make
// that claim regression-proof at the source level.
describe('legal surface', () => {
  // <link rel="canonical">/hreflang alternates are metadata, not fetched
  // resources; only stylesheet/icon/preload links and script src load bytes.
  const fetchedLinkPattern = /<link[^>]*rel="(?:stylesheet|icon|preload|modulepreload)"[^>]*/g
  const hrefPattern = /href="([^"]+)"/
  const scriptSrcPattern = /<script[^>]*src="([^"]+)"/g
  const cssUrlPattern = /url\(\s*['"]?([^'")]+)['"]?\s*\)/g

  it.each(['index.html', 'public/404.html'])(
    '%s loads every linked resource first-party',
    (page) => {
      const html = read(page)
      const urls = [
        ...[...html.matchAll(fetchedLinkPattern)]
          .map((match) => hrefPattern.exec(match[0])?.[1])
          .filter((url): url is string => url !== undefined),
        ...[...html.matchAll(scriptSrcPattern)].map((match) => match[1]),
      ]
      expect(urls.length).toBeGreaterThan(0)
      for (const url of urls) {
        expect(url, `${page} loads a third-party resource: ${url}`).toMatch(/^\//)
      }
    },
  )

  it.each(['src/styles.css', 'public/fonts/fonts.css'])(
    '%s references only local or data: URLs',
    (sheet) => {
      const css = read(sheet)
      for (const [, url] of css.matchAll(cssUrlPattern)) {
        expect(
          url.startsWith('/') || url.startsWith('data:'),
          `${sheet} references a remote URL: ${url}`,
        ).toBe(true)
      }
      expect(css).not.toMatch(/fonts\.googleapis\.com|fonts\.gstatic\.com/)
    },
  )

  it('embeds the non-affiliation disclaimer and publisher identity in the shipped page', () => {
    const html = read('index.html')
    expect(html).toContain('Not affiliated with, endorsed, or approved by the Agencia Estatal')
    expect(html).toContain('Neve Nincs')
    expect(html).toContain('NO relation to the Agencia Estatal')
  })
})
