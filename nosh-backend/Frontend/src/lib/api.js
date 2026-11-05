export const API = (import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000`).replace(/\/$/, '');
export function authHeaders() {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function request(path, options = {}) {
  const { timeout = 30000, ...init } = options;
  const controller = new AbortController();
  const cancel = () => controller.abort();
  init.signal?.addEventListener('abort', cancel, { once: true });
  if (init.signal?.aborted) controller.abort();
  const timer = setTimeout(cancel, timeout);
  try {
    const response = await fetch(`${API}${path}`, { ...init, signal: controller.signal });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = Array.isArray(data?.detail) ? data.detail.map(item => item.msg).join('. ') : data?.detail;
      const error = new Error(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
      error.status = response.status;
      throw error;
    }
    if (data === null) throw new Error('The server returned an incomplete response. Please try again.');
    return data;
  } catch (error) {
    if (init.signal?.aborted) throw error;
    if (error.name === 'AbortError') throw new Error('This is taking longer than expected. Please try again.', { cause: error });
    if (error instanceof TypeError) throw new Error('Unable to reach NOSH. Check that the backend is running and try again.', { cause: error });
    throw error;
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener('abort', cancel);
  }
}

export function memoryRequest(path = '', options = {}) {
  return request(`/memory${path}`, {
    ...options, headers: { 'Content-Type': 'application/json', ...authHeaders(), ...options.headers },
  });
}
