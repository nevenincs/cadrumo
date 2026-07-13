import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { ca } from './locales/ca'
import { en } from './locales/en'
import { es } from './locales/es'
import type { Copy } from './locales/types'

export type LocaleCode = 'en' | 'es' | 'ca'

export const availableLocales: readonly { code: LocaleCode; label: string; name: string }[] = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'es', label: 'ES', name: 'Español' },
  { code: 'ca', label: 'CA', name: 'Català' },
]

const dictionaries: Record<LocaleCode, Copy> = { ca, en, es }

const LOCALE_COOKIE = 'cadrumo_lang'
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365

function isLocaleCode(value: string): value is LocaleCode {
  return value === 'en' || value === 'es' || value === 'ca'
}

function localeFromCookie(): LocaleCode | null {
  const match = document.cookie.match(/(?:^|;\s*)cadrumo_lang=([a-z]{2})/)
  return match && isLocaleCode(match[1]) ? match[1] : null
}

function detectLocale(): LocaleCode {
  const fromCookie = localeFromCookie()
  if (fromCookie) return fromCookie
  for (const candidate of navigator.languages ?? [navigator.language]) {
    const base = (candidate ?? '').slice(0, 2).toLowerCase()
    if (isLocaleCode(base)) return base
  }
  return 'en'
}

interface LocaleContextValue {
  locale: LocaleCode
  copy: Copy
  setLocale: (locale: LocaleCode) => void
}

const LocaleContext = createContext<LocaleContextValue>({
  copy: en,
  locale: 'en',
  setLocale: () => {},
})

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleCode>(detectLocale)

  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = useCallback((next: LocaleCode) => {
    setLocaleState(next)
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}; samesite=lax`
  }, [])

  return (
    <LocaleContext.Provider value={{ copy: dictionaries[locale], locale, setLocale }}>
      {children}
    </LocaleContext.Provider>
  )
}

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext)
}
