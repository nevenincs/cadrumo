import { render, screen } from '@testing-library/react'
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

  it('switches to Spanish through the language picker and persists the choice', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(screen.getByRole('button', { name: 'Español' }))

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
})
