// Light / dark / system theme. The `.dark` class on <html> switches the tokens in styles/tokens.css.
// index.html applies the saved theme before first paint to avoid a flash.

import { useEffect, useState } from 'react'
import { readPref, writePref } from './storage'

export type ThemePref = 'system' | 'light' | 'dark'

const media = () => window.matchMedia('(prefers-color-scheme: dark)')

function apply(pref: ThemePref) {
  const dark = pref === 'dark' || (pref === 'system' && media().matches)
  document.documentElement.classList.toggle('dark', dark)
}

export function useTheme() {
  const [pref, setPref] = useState<ThemePref>(() => readPref<ThemePref>('theme', 'system'))

  useEffect(() => {
    apply(pref)
    writePref('theme', pref)
    if (pref !== 'system') return
    const m = media()
    const onChange = () => apply('system')
    m.addEventListener('change', onChange)
    return () => m.removeEventListener('change', onChange)
  }, [pref])

  const cycle = () => setPref((p) => (p === 'system' ? 'light' : p === 'light' ? 'dark' : 'system'))
  return { pref, cycle }
}
