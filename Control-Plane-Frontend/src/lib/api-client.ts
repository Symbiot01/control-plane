const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

let _token: string | null = null;

export function setAuthToken(token: string | null) {
  _token = token;
}

export async function apiClient<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(_token ? { Authorization: `Bearer ${_token}` } : {}),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string>) },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const errorMsg = Array.isArray(body.detail)
      ? body.detail.map((d: any) => `${d.loc?.join('.') || 'Error'}: ${d.msg}`).join(', ')
      : body.detail || body.message || res.statusText;
    throw new Error(errorMsg);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}
