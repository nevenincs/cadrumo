import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('App', () => {
  it('keeps the Cadrumo proposition and its primary documentation path available', () => {
    render(<App />)

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
    render(<App />)

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
    render(<App />)

    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#top')
  })

  it('keeps the independence disclaimer visible', () => {
    render(<App />)

    expect(screen.getByText('DISCLAIMER')).toBeVisible()
    expect(
      screen.getByText(/not affiliated with the AEAT/i),
    ).toBeVisible()
  })
})
