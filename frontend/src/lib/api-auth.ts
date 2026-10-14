// Team password (backend app/auth.py). Off locally; on in production when APP_PASSWORD is set.

import { request, SIGNED_OUT_EVENT } from './api'

export { SIGNED_OUT_EVENT }

export interface AuthStatus {
  required: boolean
  authenticated: boolean
  /** Who is signed in (null when signed out or when sign-in is off). */
  email: string | null
}

export const authApi = {
  status: () => request<AuthStatus>('/auth/status'),
  login: (email: string, password: string) =>
    request<{ ok: boolean; email: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
}
