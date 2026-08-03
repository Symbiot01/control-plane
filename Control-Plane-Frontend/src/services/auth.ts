import type { AuthExchangeResponse } from '@/types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function exchangeToken(idToken: string, displayName?: string | null): Promise<AuthExchangeResponse> {
  const payload: any = { id_token: idToken };
  const res = await fetch(`${API_BASE}/auth/exchange`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'Token exchange failed' }));
    throw new Error(body.detail || 'Token exchange failed');
  }
  return res.json();
}
