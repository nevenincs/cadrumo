import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { App } from './App'
import { LocaleProvider } from './i18n'

function renderApp() {
  return render(
    <LocaleProvider>
      <App />
    </LocaleProvider>,
  )
}

afterEach(() => {
  document.cookie = 'cadrumo_lang=; max-age=0; path=/'
  window.localStorage.clear()
  window.location.hash = ''
})

describe('App', () => {
  it('keeps the Cadrumo proposition and its primary documentation path available', () => {
    renderApp()

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /tax calculation engine, assisted by agents\./i,
      }),
    ).toBeVisible()
    expect(screen.getByRole('link', { name: /open documentation/i })).toHaveAttribute(
      'href',
      'https://cadrumo.neve.md/docs/index.html',
    )
  })

  it('links every calculation step to its deployed docs page', () => {
    renderApp()

    for (const name of [
      'Input',
      'Classify, filter, split',
      'Calculate and Verify',
      'Export calculations for review',
      'Prepare submission',
      'Reconcile against AEAT',
    ]) {
      expect(screen.getByRole('link', { name })).toHaveAttribute(
        'href',
        expect.stringContaining('https://cadrumo.neve.md/docs/'),
      )
    }
  })

  it('offers keyboard users a skip-to-content link', () => {
    renderApp()

    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#top')
  })

  it('keeps the independence disclaimer visible', () => {
    renderApp()

    expect(screen.getByText('DISCLAIMER')).toBeVisible()
    expect(screen.getByText(/not affiliated with the AEAT/i)).toBeVisible()
  })

  it('elevates the header, tracks scroll progress, and moves the banner parallax', async () => {
    renderApp()

    Object.defineProperty(document.documentElement, 'scrollHeight', {
      configurable: true,
      value: 2000,
    })
    Object.defineProperty(document.documentElement, 'clientHeight', {
      configurable: true,
      value: 800,
    })
    Object.defineProperty(document.documentElement, 'scrollTop', {
      configurable: true,
      value: 600,
    })
    window.dispatchEvent(new Event('scroll'))

    await waitFor(() => {
      expect(document.querySelector('.site-header')).toHaveClass('is-scrolled')
    })
    expect(document.querySelector<HTMLElement>('.scroll-progress')?.style.transform).toBe(
      'scaleX(0.5)',
    )
    expect(document.querySelector<HTMLElement>('.banner img')?.style.transform).toBe(
      'translateY(28px) scale(1.18)',
    )
  })

  it('switches to Spanish through the language picker and persists the choice', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.selectOptions(screen.getByRole('combobox', { name: 'Language' }), 'es')

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /motor de cálculo fiscal, asistido por agentes\./i,
      }),
    ).toBeVisible()
    expect(screen.getByText('AVISO')).toBeVisible()
    expect(document.cookie).toContain('cadrumo_lang=es')
    expect(document.documentElement.lang).toBe('es')
  })

  it('restores the cookie-selected language on load', () => {
    document.cookie = 'cadrumo_lang=ca; path=/'
    renderApp()

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /motor de càlcul fiscal, assistit per agents\./i,
      }),
    ).toBeVisible()
  })

  it('shows the privacy notice banner once and remembers dismissal', async () => {
    const user = userEvent.setup()
    renderApp()

    const banner = screen.getByRole('region', { name: 'Privacy notice' })
    expect(banner).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Understood' }))
    expect(screen.queryByRole('region', { name: 'Privacy notice' })).not.toBeInTheDocument()
    expect(window.localStorage.getItem('cadrumo_notice_ack')).toBe('1')
  })

  it('renders the localized legal page on the #/legal route', () => {
    window.location.hash = '#/legal'
    renderApp()

    expect(
      screen.getByRole('heading', { level: 1, name: /legal notice, privacy & cookies/i }),
    ).toBeVisible()
    expect(screen.getByText(/published by/i)).toBeVisible()
    expect(screen.getAllByText(/Neve Nincs/).length).toBeGreaterThan(0)
    expect(screen.getByText(/collects no personal data/i)).toBeVisible()
    expect(screen.getByRole('heading', { name: /no relation to the aeat/i })).toBeVisible()
  })

  it('qualifies the AEAT-compatible claim with a footnote linking to the legal notice', () => {
    renderApp()

    expect(screen.getByText(/independent project with no relation to the AEAT/i)).toBeVisible()
    expect(screen.getByRole('link', { name: 'legal notice' })).toHaveAttribute('href', '#/legal')
  })
})
