// Team password (backend app/auth.py). Off locally; on in production when APP_PASSWORD is set.

import { request, SIGNED_OUT_EVENT } from './api'

export { SIGNED_OUT_EVENT }

export interface AuthStatus {
  required: boolean
  authenticated: boolean
}

export const authApi = {
  status: () => request<AuthStatus>('/auth/status'),
  login: (password: string) =>
    request<{ ok: boolean }>('/auth/login', { method: 'POST', body: JSON.stringify({ password }) }),
  logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
}
